from typing import Optional, List
from datetime import datetime, timedelta, timezone
import logging
from langchain_core.tools import tool
from app.core.google_auth import get_google_credentials, ALL_SCOPES

logger = logging.getLogger(__name__)

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    class HttpError(Exception):
        pass
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

@tool
async def list_upcoming_events(max_results: int = 5):
    """
    Lists the upcoming events from your primary calendar.
    Useful for answering: 'What do I have to do today?'
    """
    try:
        service = get_calendar_service()
        if not service:
             return "No se pudo conectar al calendario. Verifica tus credenciales de Google."

        # Obtener hora actual en formato UTC ISO (requerido por Google)
        now = datetime.now(timezone.utc).isoformat()
        
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

@tool
async def create_calendar_event(summary: str, start_iso: str, end_iso: str, description: str = ""):
    """
    Creates an event in the calendar.
    IMPORTANT: The Agent must generate dates in ISO 8601 format
    (e.g: '2023-10-27T10:00:00')
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
        return f"Evento creado: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return f"❌ Error creando evento: {str(e)}"

@tool
async def update_calendar_event(
    event_id: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None
) -> str:
    """
    Updates an existing event in the calendar.
    
    Args:
        event_id: ID of the event to update.
        summary: New title (optional).
        description: New description (optional).
        start_iso: New start date in ISO 8601 (optional).
        end_iso: New end date in ISO 8601 (optional).
        location: New location (optional).
        attendees: List of attendee emails (optional, replaces previous list).
    """
    try:
        service = get_calendar_service()
        if not service:
            return "No se pudo conectar al calendario. Verifica tus credenciales de Google."

        # 1. Recuperar el evento existente para no perder datos no modificados
        try:
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return f"❌ Error: No se encontró ningún evento con el ID '{event_id}'."
            raise e

        # 2. Actualizar campos si se proporcionan
        if summary:
            event['summary'] = summary
        
        if description is not None: # Permitir limpiar descripción con string vacío
            event['description'] = description
            
        if location is not None:
            event['location'] = location

        if start_iso:
            event['start'] = {
                'dateTime': start_iso,
                'timeZone': event['start'].get('timeZone', 'America/Mexico_City')
            }
        
        if end_iso:
            event['end'] = {
                'dateTime': end_iso,
                'timeZone': event['end'].get('timeZone', 'America/Mexico_City')
            }

        if attendees is not None:
            # Convert list of emails to list of dicts required by API
            event['attendees'] = [{'email': email} for email in attendees]

        # 3. Ejecutar actualización
        updated_event = service.events().update(
            calendarId='primary', 
            eventId=event_id, 
            body=event
        ).execute()

        return f"✅ Evento actualizado con éxito: {updated_event.get('htmlLink')}"

    except HttpError as e:
        logger.error(f"Google API Error updating event: {e}")
        return f"❌ Error de Google Calendar al actualizar: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error updating event: {e}")
        return f"❌ Error inesperado al actualizar evento: {str(e)}"

@tool
async def delete_calendar_event(event_id: str) -> str:
    """
    Deletes an event from the calendar.
    
    Args:
        event_id: ID of the event to delete.
    """
    try:
        service = get_calendar_service()
        if not service:
            return "No se pudo conectar al calendario. Verifica tus credenciales de Google."

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"✅ Evento eliminado con éxito (ID: {event_id})."

    except HttpError as e:
        if e.resp.status == 404:
            return f"❌ Error: El evento con ID '{event_id}' no existe o ya fue eliminado."
        if e.resp.status == 410:
             return f"❌ Error: El evento con ID '{event_id}' ya ha sido eliminado permanentemente."
        logger.error(f"Google API Error deleting event: {e}")
        return f"❌ Error de Google Calendar al eliminar: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error deleting event: {e}")
        return f"❌ Error inesperado al eliminar evento: {str(e)}"

tools = [list_upcoming_events, create_calendar_event, update_calendar_event, delete_calendar_event]
