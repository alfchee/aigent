from datetime import datetime, timedelta
import logging
from app.core.google_auth import get_google_credentials, ALL_SCOPES

logger = logging.getLogger(__name__)

try:
    from googleapiclient.discovery import build
except ImportError:
    pass

# Calendar Scope
SCOPES = ALL_SCOPES

def get_calendar_service():
    """Reutiliza las credenciales de OAuth2 del usuario."""
    creds = get_google_credentials(SCOPES)
    if not creds:
        # Si no hay credenciales, retornamos None para que las funciones manejen el error
        return None
    return build('calendar', 'v3', credentials=creds)

async def list_upcoming_events(max_results: int = 5):
    """
    Lista los próximos eventos de tu calendario principal.
    Útil para responder: '¿Qué tengo que hacer hoy?'
    """
    try:
        service = get_calendar_service()
        if not service:
             return "No se pudo conectar al calendario. Verifica tus credenciales de Google."

        # Obtener hora actual en formato UTC ISO (requerido por Google)
        now = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"📅 Consultando calendario desde: {now}")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            return "No se encontraron eventos próximos."

        output = ["📅 **Próximos Eventos:**"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Limpiamos un poco el formato de la fecha si viene muy complejo
            summary = event.get('summary', 'Sin título')
            link = event.get('htmlLink', '')
            output.append(f"- **{start}**: {summary} ([Ver]({link}))")

        return "\n".join(output)
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        return f"Error al consultar eventos: {str(e)}"

async def create_calendar_event(summary: str, start_iso: str, end_iso: str, description: str = ""):
    """
    Crea un evento en el calendario.
    IMPORTANTE: El Agente debe generar las fechas en formato ISO 8601
    (Ej: '2023-10-27T10:00:00')
    """
    try:
        service = get_calendar_service()
        if not service:
             return "No se pudo conectar al calendario. Verifica tus credenciales de Google."

        # Si el usuario no especifica timezone, Google Calendar usa la del calendario principal
        # o podemos forzar una. El ejemplo del usuario usaba 'America/Mexico_City'.
        # Lo ideal sería configurarlo, pero lo dejaré hardcoded como en el ejemplo por ahora
        # o lo haré configurable si puedo, pero seguiré el snippet.
        
        event_body = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_iso,
                'timeZone': 'America/Mexico_City', # Ajusta esto a tu zona horaria local
            },
            'end': {
                'dateTime': end_iso,
                'timeZone': 'America/Mexico_City',
            },
            # Opcional: Añadir recordatorios por defecto
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return f"✅ Evento creado con éxito: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return f"❌ Error creando evento: {str(e)}"

tools = [list_upcoming_events, create_calendar_event]
