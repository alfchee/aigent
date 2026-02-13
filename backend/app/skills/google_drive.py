import os
import io
import logging
import asyncio
from typing import List, Optional

# Imports from shared auth module
from app.core.google_auth import (
    get_google_credentials,
    check_google_dependencies,
    ensure_oauth_dependencies,
    get_workspace_config,
    CREDS_PATH,
    OAUTH_CLIENT_PATH,
    OAUTH_TOKEN_PATH,
    ALL_SCOPES
)

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
except ImportError:
    class HttpError(Exception):
        pass
    pass

from app.core.runtime_context import get_session_id
from app.core.filesystem import SessionWorkspace

logger = logging.getLogger(__name__)

SCOPES = ALL_SCOPES

_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.google-apps.drawing": "image/png",
}

def get_drive_service():
    check_google_dependencies()
    workspace_config = get_workspace_config()
    auth_mode = workspace_config.get("auth_mode", "service_account")

    if auth_mode == "oauth":
        creds = get_google_credentials(SCOPES)
        if not creds:
            raise RuntimeError(
                "OAuth no configurado. Ejecuta get_google_oauth_authorization_url y luego set_google_oauth_token, o usa authorize_google_oauth_local_server."
            )
        return build('drive', 'v3', credentials=creds)

    if not os.path.exists(CREDS_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales en: {CREDS_PATH}. "
            "Por favor, coloca tu 'google_service.json' en esa ubicación."
        )

    try:
        creds = ServiceAccountCredentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Failed to create Drive service: {e}")
        raise RuntimeError(f"Error al conectar con Google Drive: {str(e)}")

async def list_drive_files(folder_id: str = 'root') -> str:
    """
    Lista archivos y carpetas dentro de un directorio específico de Google Drive.
    
    Args:
        folder_id: El ID de la carpeta en Drive (default: 'root').
        
    Returns:
        Un string formateado con la lista de archivos/carpetas encontrados.
    """
    try:
        # Run synchronous API call in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _list_drive_files_sync, folder_id)
        return result
    except Exception as e:
        logger.exception(f"Error listing files in folder {folder_id}")
        return f"Error al listar archivos: {str(e)}"

def _list_drive_files_sync(folder_id: str) -> str:
    service = get_drive_service()
    # Ensure folder_id is safe against injection if that were possible, 
    # though the API handles it. Just strictly use single quotes around ID.
    query = f"'{folder_id}' in parents and trashed = false"
    
    results = service.files().list(
        q=query, 
        fields="nextPageToken, files(id, name, mimeType)",
        pageSize=20
    ).execute()
    
    files = results.get('files', [])
    if not files:
        return f"No se encontraron archivos en la carpeta con ID: {folder_id}"
    
    output = [f"Contenido de la carpeta ({folder_id}):"]
    for f in files:
        is_folder = f['mimeType'] == 'application/vnd.google-apps.folder'
        type_str = "[CARPETA]" if is_folder else "[ARCHIVO]"
        output.append(f"- {f['name']} (ID: {f['id']}) {type_str}")
    
    return "\n".join(output)

async def search_drive(name: str) -> str:
    """
    Busca un archivo o carpeta por nombre en todo el Drive compartido.
    
    Args:
        name: El nombre (o parte del nombre) a buscar.
        
    Returns:
        Lista de resultados encontrados con sus IDs.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _search_drive_sync, name)
        return result
    except Exception as e:
        logger.exception(f"Error searching for {name}")
        return f"Error al buscar en Drive: {str(e)}"

def _search_drive_sync(name: str) -> str:
    service = get_drive_service()
    # Sanitize name to avoid query syntax errors? 
    # The client handles basic escaping but let's be careful with quotes.
    safe_name = name.replace("'", "\\'")
    query = f"name contains '{safe_name}' and trashed = false"
    
    results = service.files().list(
        q=query, 
        fields="files(id, name, mimeType)",
        pageSize=20
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        return "No se encontró nada con ese nombre."
    
    output = [f"Resultados de búsqueda para '{name}':"]
    for f in files:
        is_folder = f['mimeType'] == 'application/vnd.google-apps.folder'
        type_str = "[CARPETA]" if is_folder else "[ARCHIVO]"
        output.append(f"- {f['name']} (ID: {f['id']}) {type_str}")
        
    return "\n".join(output)

async def move_drive_file(file_id: str, folder_id: str) -> str:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _move_drive_file_sync, file_id, folder_id)
        return result
    except Exception as e:
        logger.exception(f"Error moving file {file_id} to folder {folder_id}")
        return f"Error al mover archivo: {str(e)}"

def _move_drive_file_sync(file_id: str, folder_id: str) -> str:
    service = get_drive_service()
    file_meta = service.files().get(fileId=file_id, fields="parents, name").execute()
    previous_parents = ",".join(file_meta.get("parents", [])) if file_meta.get("parents") else None
    update_kwargs = {"fileId": file_id, "addParents": folder_id, "fields": "id, parents"}
    if previous_parents:
        update_kwargs["removeParents"] = previous_parents
    service.files().update(**update_kwargs).execute()
    name = file_meta.get("name") or file_id
    return f"Archivo movido: {name} (ID: {file_id}) → carpeta {folder_id}."

async def download_file_from_drive(file_id: str, file_name: str) -> str:
    """
    Descarga un archivo de Drive al workspace local de la sesión actual para ser procesado.
    
    Args:
        file_id: El ID del archivo en Google Drive.
        file_name: El nombre con el que se guardará localmente (ej. 'datos.xlsx').
        
    Returns:
        Mensaje de éxito con la ruta relativa del archivo.
    """
    session_id = get_session_id()
    if not session_id:
        return "Error: No se pudo determinar la sesión actual."

    try:
        loop = asyncio.get_event_loop()
        workspace = SessionWorkspace(session_id)
        target_path = workspace.safe_path(file_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        await loop.run_in_executor(None, _download_to_path_sync, file_id, target_path)
        return f"Archivo descargado exitosamente: {file_name}. Ahora puedes usarlo con 'execute_python'."

    except HttpError as e:
        logger.exception(f"Error downloading file {file_id}")
        return f"Error al descargar archivo: {str(e)}"
    except Exception as e:
        logger.exception(f"Error downloading file {file_id}")
        return f"Error al descargar archivo: {str(e)}"

def _download_to_path_sync(file_id: str, target_path) -> None:
    service = get_drive_service()
    file_meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime_type = file_meta.get("mimeType")
    export_mime = _EXPORT_MIME_TYPES.get(mime_type)
    if export_mime:
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        request = service.files().get_media(fileId=file_id)

    with open(target_path, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

# Export tools
tools = [list_drive_files, search_drive, move_drive_file, download_file_from_drive]
