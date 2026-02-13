import os
import logging
from typing import List, Optional
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import socket

try:
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

try:
    from google.oauth2.credentials import Credentials as UserCredentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

from app.core.config_manager import get_settings

logger = logging.getLogger(__name__)

# Base directory for the app (two levels up from this file: app/core -> app)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Credential paths
CREDS_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_service.json')
OAUTH_CLIENT_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_oauth_client.json')
OAUTH_TOKEN_PATH = os.path.join(BASE_DIR, 'core', 'credentials', 'google_oauth_token.json')

# Define all necessary scopes for the application
ALL_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar'
]

def check_google_dependencies():
    """Checks if google-api-python-client is installed."""
    if not GOOGLE_API_AVAILABLE:
        raise ImportError("The 'google-api-python-client' library is required but not installed.")

def ensure_oauth_dependencies():
    """Checks if google-auth-oauthlib is installed."""
    if not OAUTH_AVAILABLE:
        raise ImportError("The 'google-auth-oauthlib' library is required but not installed.")

def get_workspace_config():
    """Retrieves Google Workspace configuration from settings."""
    try:
        settings = get_settings()
        return settings.google_workspace_config or {}
    except Exception:
        return {}

def _save_oauth_token(creds: UserCredentials) -> None:
    """Saves OAuth credentials to token file."""
    os.makedirs(os.path.dirname(OAUTH_TOKEN_PATH), exist_ok=True)
    with open(OAUTH_TOKEN_PATH, "w", encoding="utf-8") as handle:
        handle.write(creds.to_json())

# Global variable to hold the server instance so we can stop it if needed
_oauth_server = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if "code=" in self.path:
                # Extract code simply
                query_part = self.path.split("?", 1)[-1]
                code = None
                for param in query_part.split("&"):
                    if param.startswith("code="):
                        code = param.split("=", 1)[1]
                        break
                
                if code:
                    # Save credentials
                    try:
                        save_credentials_from_code(code)
                        self.send_response(200)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                            <html>
                            <head><title>Autenticacion Exitosa</title></head>
                            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                                <h1 style="color: green;">Autenticacion Exitosa</h1>
                                <p>NaviBot ha recibido tus credenciales.</p>
                                <p>Puedes cerrar esta ventana y volver al chat.</p>
                                <script>setTimeout(function(){ window.close(); }, 3000);</script>
                            </body>
                            </html>
                        """)
                    except Exception as e:
                        logger.error(f"Error saving credentials in callback: {e}")
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(f"Error saving credentials: {str(e)}".encode())
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"No code found in request")
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logger.error(f"Error in OAuth handler: {e}")
            # Try to send error response if possible
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass

def start_oauth_listener(port: int = 8080):
    """Starts a background HTTP server to listen for the OAuth callback."""
    global _oauth_server
    
    # Stop existing server if any
    if _oauth_server:
        try:
            _oauth_server.shutdown()
            _oauth_server.server_close()
        except:
            pass
            
    try:
        # Check if port is in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            logger.warning(f"Port {port} is already in use. OAuth listener might fail or conflict.")
            # We continue anyway, hoping the existing process is us or dead
            
        server = HTTPServer(('localhost', port), OAuthCallbackHandler)
        _oauth_server = server
        
        # Run in a thread
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        # Schedule shutdown after 5 minutes to release port
        def shutdown_server():
            try:
                server.shutdown()
                server.server_close()
            except:
                pass
        
        timer = threading.Timer(300.0, shutdown_server)
        timer.daemon = True
        timer.start()
        
        logger.info(f"OAuth listener started on port {port}")
        return True
    except Exception as e:
        logger.error(f"Failed to start OAuth listener: {e}")
        return False

def get_authorization_url(scopes: List[str] = ALL_SCOPES) -> str:
    """
    Generates the authorization URL for the OAuth2 flow.
    
    Args:
        scopes: List of scopes to request. Defaults to ALL_SCOPES.
        
    Returns:
        The authorization URL.
    """
    ensure_oauth_dependencies()
    
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )
        
    workspace_config = get_workspace_config()
    redirect_uri = workspace_config.get("oauth_redirect_uri")
    
    # Use 'urn:ietf:wg:oauth:2.0:oob' for manual copy-paste flow if no redirect_uri is set
    # or if we want to force the manual flow to display the code.
    # However, 'urn:ietf:wg:oauth:2.0:oob' is deprecated for some client types but still works for Installed Apps.
    # Using 'http://localhost' requires a running listener.
    # We will use the flow's default behavior which usually defaults to localhost or OOB depending on client config.
    
    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_PATH, scopes=scopes)
    
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    else:
        # Default to http://localhost:8080/ because OOB is deprecated and blocked for new clients
        flow.redirect_uri = 'http://localhost:8080/'
        
    # Start the background listener if we are using the default localhost redirect
    if flow.redirect_uri.startswith('http://localhost:8080'):
        start_oauth_listener(8080)
        
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return url

def save_credentials_from_code(code: str, scopes: List[str] = ALL_SCOPES) -> None:
    """
    Exchanges the authorization code for credentials and saves them.
    
    Args:
        code: The authorization code provided by the user.
        scopes: List of scopes used in the request.
    """
    ensure_oauth_dependencies()
    
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError("OAuth client secrets file not found.")
        
    workspace_config = get_workspace_config()
    redirect_uri = workspace_config.get("oauth_redirect_uri")
    
    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_PATH, scopes=scopes)
    
    if redirect_uri:
        flow.redirect_uri = redirect_uri
    else:
        flow.redirect_uri = 'http://localhost:8080/'
        
    flow.fetch_token(code=code)
    _save_oauth_token(flow.credentials)

def get_google_credentials(scopes: Optional[List[str]] = None) -> Optional[UserCredentials]:
    """
    Retrieves OAuth2 user credentials from storage, refreshing if necessary.
    
    Args:
        scopes: Optional list of scopes to validate/request.
        
    Returns:
        UserCredentials object if valid, None otherwise.
    """
    ensure_oauth_dependencies()
    
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales OAuth en: {OAUTH_CLIENT_PATH}. "
            "Por favor, coloca tu 'google_oauth_client.json' en esa ubicación."
        )

    creds: Optional[UserCredentials] = None
    if os.path.exists(OAUTH_TOKEN_PATH):
        try:
            creds = UserCredentials.from_authorized_user_file(OAUTH_TOKEN_PATH, scopes)
        except Exception as e:
            logger.warning(f"Error loading credentials from file: {e}")
            creds = None
            
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_oauth_token(creds)
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            # If refresh fails, we might want to return None so user can re-auth
            return None

    if creds and creds.valid:
        return creds
        
    return None
