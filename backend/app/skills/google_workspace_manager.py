import os
import json
import logging
from typing import List, Union, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_service.json')
OAUTH_CLIENT_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_oauth_client.json')
OAUTH_TOKEN_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_oauth_token.json')

from app.core.config_manager import get_settings

try:
    import gspread
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from google.auth.exceptions import TransportError, RefreshError
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from google.oauth2.credentials import Credentials as UserCredentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

def _check_dependencies():
    if not GSPREAD_AVAILABLE:
        raise ImportError("The 'gspread' and 'google-auth' libraries are required but not installed.")

def _get_workspace_config() -> Dict[str, Any]:
    try:
        settings = get_settings()
        return settings.google_workspace_config or {}
    except Exception:
        return {}

def _ensure_oauth_dependencies():
    if not OAUTH_AVAILABLE:
        raise ImportError("The 'google-auth-oauthlib' library is required but not installed.")

def _save_oauth_token(creds: UserCredentials) -> None:
    with open(OAUTH_TOKEN_PATH, "w", encoding="utf-8") as handle:
        handle.write(creds.to_json())

def _get_oauth_credentials(scopes: List[str]) -> Optional[UserCredentials]:
    _ensure_oauth_dependencies()
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )
    creds: Optional[UserCredentials] = None
    if os.path.exists(OAUTH_TOKEN_PATH):
        creds = UserCredentials.from_authorized_user_file(OAUTH_TOKEN_PATH, scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_oauth_token(creds)
    if creds and creds.valid:
        return creds
    return None

def _build_oauth_authorization_url(scopes: List[str]) -> str:
    _ensure_oauth_dependencies()
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )
    workspace_config = _get_workspace_config()
    redirect_uri = workspace_config.get("oauth_redirect_uri")
    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_PATH, scopes=scopes)
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return url

def _exchange_oauth_code(auth_code: str, scopes: List[str]) -> None:
    _ensure_oauth_dependencies()
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )
    workspace_config = _get_workspace_config()
    redirect_uri = workspace_config.get("oauth_redirect_uri")
    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_PATH, scopes=scopes)
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    flow.fetch_token(code=auth_code)
    _save_oauth_token(flow.credentials)

def _run_local_oauth_flow(scopes: List[str]) -> UserCredentials:
    _ensure_oauth_dependencies()
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )
    workspace_config = _get_workspace_config()
    redirect_uri = workspace_config.get("oauth_redirect_uri")
    host = workspace_config.get("oauth_local_host", "localhost")
    port_value = workspace_config.get("oauth_local_port", 8080)
    try:
        port = int(port_value)
    except (TypeError, ValueError):
        port = 8080
    prompt_message = workspace_config.get("oauth_authorization_prompt_message") or "Por favor, visita esta URL para autorizar a NaviBot: {url}"
    success_message = workspace_config.get("oauth_success_message") or "¡Éxito! Puedes cerrar esta ventana."
    open_browser = workspace_config.get("oauth_open_browser", True)
    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_PATH, scopes=scopes)
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    creds = flow.run_local_server(
        host=host,
        port=port,
        authorization_prompt_message=prompt_message,
        success_message=success_message,
        open_browser=open_browser
    )
    _save_oauth_token(creds)
    return creds

def get_sheets_client():
    _check_dependencies()
    workspace_config = _get_workspace_config()
    auth_mode = workspace_config.get("auth_mode", "service_account")

    if auth_mode == "oauth":
        creds = _get_oauth_credentials(SCOPES)
        if not creds:
            raise RuntimeError(
                "OAuth no configurado. Ejecuta get_google_oauth_authorization_url y luego set_google_oauth_token, o usa authorize_google_oauth_local_server."
            )
        return gspread.authorize(creds)

    if not os.path.exists(CREDS_PATH):
        error_msg = (
            f"No se encontró el archivo de credenciales en: {CREDS_PATH}. "
            "Por favor, coloca tu 'google_service.json' en esa ubicación."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        delegated_user_email = workspace_config.get("delegated_user_email")
        if delegated_user_email:
            creds = ServiceAccountCredentials.from_service_account_file(
                CREDS_PATH,
                scopes=SCOPES,
                subject=delegated_user_email
            )
        else:
            creds = ServiceAccountCredentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        return gspread.authorize(creds)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Invalid credentials file format: {e}")
        raise RuntimeError(f"El archivo de credenciales es inválido: {str(e)}")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise RuntimeError(f"Error al autenticar con Google Workspace: {str(e)}")

# Retry configuration: exponential backoff, max 3 attempts, retry on specific API errors
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((Exception,)) # We can refine this if we import specific exceptions
}

if GSPREAD_AVAILABLE:
    # Refine retry exceptions if modules are available
    from gspread.exceptions import APIError, GSpreadException
    RETRY_CONFIG["retry"] = retry_if_exception_type((APIError, GSpreadException, TransportError, RefreshError))

@retry(**RETRY_CONFIG)
def _create_spreadsheet_with_retry(client, title: str):
    return client.create(title)

@retry(**RETRY_CONFIG)
def _update_sheet_with_retry(worksheet, range_name, values):
    return worksheet.update(range_name, values)

@retry(**RETRY_CONFIG)
def _open_sheet_with_retry(client, key):
    return client.open_by_key(key)

def _get_drive_service(creds):
    if not GOOGLE_API_AVAILABLE:
        raise ImportError("The 'google-api-python-client' library is required but not installed.")
    return build("drive", "v3", credentials=creds)

def _resolve_folder_id(folder_id: Optional[str], folder_name: Optional[str], creds) -> Optional[str]:
    if folder_id:
        return folder_id
    if not folder_name:
        return None
    service = _get_drive_service(creds)
    safe_name = folder_name.replace("'", "\\'")
    query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{safe_name}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    files = results.get("files", [])
    if not files:
        return None
    return files[0].get("id")

def _move_file_to_folder(file_id: str, folder_id: str, creds) -> None:
    service = _get_drive_service(creds)
    file_meta = service.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file_meta.get("parents", []))
    service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=previous_parents,
        fields="id, parents"
    ).execute()

def _transfer_ownership(file_id: str, owner_email: str, creds) -> None:
    service = _get_drive_service(creds)
    permission = {
        "type": "user",
        "role": "owner",
        "emailAddress": owner_email,
    }
    service.permissions().create(
        fileId=file_id,
        body=permission,
        transferOwnership=True,
        sendNotificationEmail=False
    ).execute()

async def create_google_spreadsheet(title: str, folder_id: Optional[str] = None) -> dict:
    """
    Crea una nueva hoja de cálculo en Google Sheets y devuelve su URL e ID.
    
    Args:
        title: El título del nuevo documento.
        
    Returns:
        Un diccionario con 'url' e 'id' del documento creado.
    """
    try:
        workspace_config = _get_workspace_config()
        owner_email = workspace_config.get("owner_email")
        delegated_user_email = workspace_config.get("delegated_user_email")
        default_folder_id = workspace_config.get("default_drive_folder_id")
        default_folder_name = workspace_config.get("default_drive_folder_name")

        client = get_sheets_client()
        spreadsheet = _create_spreadsheet_with_retry(client, title)
        
        # Share logic
        try:
            spreadsheet.share(None, perm_type='anyone', role='writer')
        except Exception as e:
            logger.warning(f"Failed to share spreadsheet publicly: {e}")

        ownership_note = None
        location_note = None

        try:
            creds = client.auth
            resolved_folder_id = _resolve_folder_id(folder_id or default_folder_id, default_folder_name, creds)
            if resolved_folder_id:
                _move_file_to_folder(spreadsheet.id, resolved_folder_id, creds)
                location_note = "Movido a la carpeta destino."
            elif folder_id or default_folder_id or default_folder_name:
                location_note = "No se encontró la carpeta destino."
        except Exception as e:
            logger.error(f"Move to folder failed: {e}")
            location_note = "No se pudo mover a la carpeta destino."

        if owner_email:
            try:
                creds = client.auth
                _transfer_ownership(spreadsheet.id, owner_email, creds)
                ownership_note = f"Propiedad transferida a {owner_email}."
            except HttpError as e:
                logger.error(f"Ownership transfer failed: {e}")
                ownership_note = f"No se pudo transferir la propiedad a {owner_email}."
            except Exception as e:
                logger.error(f"Ownership transfer error: {e}")
                ownership_note = f"No se pudo transferir la propiedad a {owner_email}."
        elif delegated_user_email:
            ownership_note = f"Creado bajo la cuenta delegada {delegated_user_email}."

        notes = " ".join([n for n in [ownership_note, location_note] if n])
        return {
            "url": spreadsheet.url,
            "id": spreadsheet.id,
            "message": (
                f"Hoja creada. [Ver Google Sheet]({spreadsheet.url}). Nota: Se ha compartido como 'cualquiera con el enlace' para que puedas verla."
                if not notes
                else f"Hoja creada. [Ver Google Sheet]({spreadsheet.url}). {notes}"
            )
        }
    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        error_str = str(e).lower()
        if "quota" in error_str or "storage" in error_str:
            return {"error": "Fallo al crear hoja de cálculo: cuota de Drive excedida para la cuenta propietaria."}
        logger.exception("Error creating spreadsheet")
        return {"error": f"Fallo al crear hoja de cálculo: {str(e)}"}

async def update_sheet_data(spreadsheet_id: str, range_name: str, values: List[List[Union[str, int, float]]]) -> str:
    """
    Inserta o actualiza datos en una hoja de cálculo existente.
    
    Args:
        spreadsheet_id: El ID del documento (se puede obtener de la URL).
        range_name: El rango (ej. 'Hoja 1!A1') o nombre de la hoja (ej. 'Sheet1').
        values: Lista de listas con los datos a insertar [[f1c1, f1c2], [f2c1...]].
        
    Returns:
        Un mensaje de confirmación o error.
    """
    try:
        client = get_sheets_client()
        sh = _open_sheet_with_retry(client, spreadsheet_id)
        
        if '!' in range_name:
            sheet_name, cell_range = range_name.split('!', 1)
            try:
                worksheet = sh.worksheet(sheet_name)
                target_range = cell_range or "A1"
                _update_sheet_with_retry(worksheet, target_range, values)
            except gspread.WorksheetNotFound:
                 return f"Error: No se encontró la hoja '{sheet_name}'."
        else:
            # Assume it's a sheet name or default range
            try:
                worksheet = sh.worksheet(range_name)
                _update_sheet_with_retry(worksheet, 'A1', values)
            except gspread.WorksheetNotFound:
                # Fallback to first sheet
                worksheet = sh.get_worksheet(0)
                _update_sheet_with_retry(worksheet, range_name, values)

        return f"Datos actualizados exitosamente en '{range_name}'."
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        logger.exception("Error updating sheet data")
        return f"Error al actualizar datos: {str(e)}"

async def get_google_oauth_authorization_url() -> str:
    try:
        url = _build_oauth_authorization_url(SCOPES)
        return f"Autoriza aquí: [Abrir URL OAuth]({url})\n\nURL: {url}"
    except Exception as e:
        return f"Error al generar URL OAuth: {str(e)}"

async def set_google_oauth_token(auth_code: str) -> str:
    try:
        _exchange_oauth_code(auth_code, SCOPES)
        return "Token OAuth guardado correctamente."
    except Exception as e:
        return f"Error al guardar token OAuth: {str(e)}"

async def authorize_google_oauth_local_server() -> str:
    try:
        _run_local_oauth_flow(SCOPES)
        return "OAuth completado correctamente con servidor local."
    except Exception as e:
        return f"Error al completar OAuth local: {str(e)}"

tools = [
    create_google_spreadsheet,
    update_sheet_data,
    get_google_oauth_authorization_url,
    set_google_oauth_token,
    authorize_google_oauth_local_server
]
