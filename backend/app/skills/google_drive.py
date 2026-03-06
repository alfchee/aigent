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
    Lists files and folders within a specific Google Drive directory.
    
    Args:
        folder_id: The folder ID in Drive (default: 'root').
        
    Returns:
        A formatted string with the list of files/folders found.
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
    Searches for a file or folder by name in the entire shared Drive.
    
    Args:
        name: The name (or part of the name) to search for.
        
    Returns:
        List of results found with their IDs.
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
    Downloads a file from Drive to the local workspace of the current session to be processed.
    
    Args:
        file_id: The ID of the file in Google Drive.
        file_name: The name to save locally (e.g. 'data.xlsx').
        
    Returns:
        Success message with the relative path of the file.
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


async def create_drive_folder(name: str, parent_folder_id: str = 'root') -> str:
    """
    Creates a new folder in Google Drive.
    
    Args:
        name: The name of the folder to create.
        parent_folder_id: The ID of the parent folder (default: 'root').
        
    Returns:
        Success message with the folder ID and link.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create_drive_folder_sync, name, parent_folder_id)
        return result
    except Exception as e:
        logger.exception(f"Error creating folder {name}")
        return f"Error creating folder: {str(e)}"


def _create_drive_folder_sync(name: str, parent_folder_id: str) -> str:
    service = get_drive_service()
    folder_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_folder_id and parent_folder_id != 'root':
        folder_metadata['parents'] = [parent_folder_id]
    
    folder = service.files().create(body=folder_metadata, fields='id, name, webViewLink').execute()
    return f"✅ Folder created: {folder['name']} (ID: {folder['id']})\n🔗 Link: {folder.get('webViewLink', 'No link available')}"


async def create_drive_file(file_type: str, name: str, parent_folder_id: str = 'root') -> str:
    """
    Creates a new Google Docs, Sheets, or Slides file in Drive.
    
    Args:
        file_type: The type of file - 'document', 'spreadsheet', or 'presentation'.
        name: The name of the file to create.
        parent_folder_id: The ID of the parent folder (default: 'root').
        
    Returns:
        Success message with the file ID and link.
    """
    mime_types = {
        'document': 'application/vnd.google-apps.document',
        'spreadsheet': 'application/vnd.google-apps.spreadsheet',
        'presentation': 'application/vnd.google-apps.presentation'
    }
    
    if file_type not in mime_types:
        return f"Error: Invalid file_type '{file_type}'. Use 'document', 'spreadsheet', or 'presentation'."
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create_drive_file_sync, mime_types[file_type], name, parent_folder_id)
        return result
    except Exception as e:
        logger.exception(f"Error creating {file_type} {name}")
        return f"Error creating {file_type}: {str(e)}"


def _create_drive_file_sync(mime_type: str, name: str, parent_folder_id: str) -> str:
    service = get_drive_service()
    file_metadata = {
        'name': name,
        'mimeType': mime_type
    }
    if parent_folder_id and parent_folder_id != 'root':
        file_metadata['parents'] = [parent_folder_id]
    
    file = service.files().create(body=file_metadata, fields='id, name, webViewLink, mimeType').execute()
    
    file_type_name = {
        'application/vnd.google-apps.document': 'Google Doc',
        'application/vnd.google-apps.spreadsheet': 'Google Sheet',
        'application/vnd.google-apps.presentation': 'Google Slides'
    }.get(file.get('mimeType'), 'File')
    
    return f"✅ {file_type_name} created: {file['name']} (ID: {file['id']})\n🔗 Link: {file.get('webViewLink', 'No link available')}"


async def delete_drive_file(file_id: str) -> str:
    """
    Deletes a file or folder from Google Drive.
    
    Args:
        file_id: The ID of the file to delete.
        
    Returns:
        Success or error message.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_drive_file_sync, file_id)
        return result
    except Exception as e:
        logger.exception(f"Error deleting file {file_id}")
        return f"Error deleting file: {str(e)}"


def _delete_drive_file_sync(file_id: str) -> str:
    service = get_drive_service()
    try:
        file_meta = service.files().get(fileId=file_id, fields='name').execute()
        file_name = file_meta.get('name', file_id)
    except:
        file_name = file_id
    
    service.files().delete(fileId=file_id).execute()
    return f"🗑️ File deleted: {file_name} (ID: {file_id})"


async def copy_drive_file(file_id: str, new_name: str = None) -> str:
    """
    Copies a file in Google Drive.
    
    Args:
        file_id: The ID of the file to copy.
        new_name: The name for the copy (optional, defaults to 'Copy of [original name]').
        
    Returns:
        Success message with the copied file ID and link.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _copy_drive_file_sync, file_id, new_name)
        return result
    except Exception as e:
        logger.exception(f"Error copying file {file_id}")
        return f"Error copying file: {str(e)}"


def _copy_drive_file_sync(file_id: str, new_name: str) -> str:
    service = get_drive_service()
    
    # Get original file name if not provided
    if not new_name:
        original = service.files().get(fileId=file_id, fields='name').execute()
        new_name = f"Copy of {original.get('name', 'file')}"
    
    copy_metadata = {'name': new_name}
    copied_file = service.files().copy(fileId=file_id, body=copy_metadata, fields='id, name, webViewLink').execute()
    
    return f"✅ File copied: {copied_file['name']} (ID: {copied_file['id']})\n🔗 Link: {copied_file.get('webViewLink', 'No link available')}"


async def get_drive_file_info(file_id: str) -> str:
    """
    Gets detailed metadata information about a file in Google Drive.
    
    Args:
        file_id: The ID of the file.
        
    Returns:
        Detailed file information including size, created date, modified date, owners, permissions, etc.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _get_drive_file_info_sync, file_id)
        return result
    except Exception as e:
        logger.exception(f"Error getting info for file {file_id}")
        return f"Error getting file info: {str(e)}"


def _get_drive_file_info_sync(file_id: str) -> str:
    service = get_drive_service()
    
    file_meta = service.files().get(
        fileId=file_id,
        fields='id, name, mimeType, size, createdTime, modifiedTime, owners, parents, webViewLink, webContentLink, permissions'
    ).execute()
    
    from datetime import datetime
    
    def format_date(iso_date):
        if not iso_date:
            return "N/A"
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            return iso_date
    
    def format_size(size_bytes):
        if not size_bytes:
            return "N/A"
        try:
            size = int(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size} {unit}"
                size /= 1024
            return f"{size} TB"
        except:
            return str(size_bytes)
    
    owners = file_meta.get('owners', [])
    owner_names = [o.get('displayName', o.get('emailAddress', 'Unknown')) for o in owners]
    
    parents = file_meta.get('parents', [])
    
    mime_type = file_meta.get('mimeType', 'Unknown')
    is_folder = mime_type == 'application/vnd.google-apps.folder'
    
    output = [f"📄 File Information for: {file_meta.get('name', 'Unknown')}"]
    output.append(f"━━━━━━━━━━━━━━━━━━━━━━━━")
    output.append(f"�ds: {file_meta.get('id')}")
    output.append(f"📁 Type: {'Folder' if is_folder else mime_type}")
    output.append(f"💾 Size: {format_size(file_meta.get('size'))}")
    output.append(f"📅 Created: {format_date(file_meta.get('createdTime'))}")
    output.append(f"✏️ Modified: {format_date(file_meta.get('modifiedTime'))}")
    output.append(f"👤 Owner(s): {', '.join(owner_names) if owner_names else 'Unknown'}")
    output.append(f"📂 Parent(s): {', '.join(parents) if parents else 'Root'}")
    
    if file_meta.get('webViewLink'):
        output.append(f"🔗 View: {file_meta.get('webViewLink')}")
    if file_meta.get('webContentLink'):
        output.append(f"⬇️ Download: {file_meta.get('webContentLink')}")
    
    return "\n".join(output)


async def share_drive_file(file_id: str, email: str, role: str = 'reader') -> str:
    """
    Shares a file in Google Drive with a specific email address.
    
    Args:
        file_id: The ID of the file to share.
        email: The email address to share with.
        role: The permission role - 'reader', 'writer', or 'commenter' (default: 'reader').
        
    Returns:
        Success or error message.
    """
    valid_roles = ['reader', 'writer', 'commenter', 'owner']
    if role not in valid_roles:
        return f"Error: Invalid role '{role}'. Use: {', '.join(valid_roles)}"
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _share_drive_file_sync, file_id, email, role)
        return result
    except Exception as e:
        logger.exception(f"Error sharing file {file_id}")
        return f"Error sharing file: {str(e)}"


def _share_drive_file_sync(file_id: str, email: str, role: str) -> str:
    service = get_drive_service()
    
    permission = {
        'type': 'user',
        'role': role,
        'emailAddress': email
    }
    
    service.permissions().create(
        fileId=file_id,
        body=permission,
        sendNotificationEmail=True
    ).execute()
    
    role_emoji = {'reader': '👁️', 'writer': '✏️', 'commenter': '💬', 'owner': '👑'}
    return f"✅ File shared with {email}\n🔖 Role: {role_emoji.get(role, '')} {role}\n📎 File ID: {file_id}"


# Export tools
tools = [
    list_drive_files,
    search_drive,
    move_drive_file,
    download_file_from_drive,
    create_drive_folder,
    create_drive_file,
    delete_drive_file,
    copy_drive_file,
    get_drive_file_info,
    share_drive_file
]
