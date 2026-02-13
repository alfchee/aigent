import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import asyncio

# Add backend to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.skills.calendar import update_calendar_event, delete_calendar_event, list_upcoming_events, create_calendar_event
# Import HttpError from googleapiclient.errors or the local fallback in calendar.py
try:
    from googleapiclient.errors import HttpError
except ImportError:
    # If not installed, we can't easily mock HttpError unless we mock the module before import, 
    # but app.skills.calendar defines a fallback class if import fails.
    # To test properly, we should assume the structure of HttpError if it exists.
    class HttpError(Exception):
        def __init__(self, resp, content):
            self.resp = resp
            self.content = content

class TestCalendarManagement(unittest.TestCase):

    def setUp(self):
        # Create a helper to run async tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('app.skills.calendar.get_calendar_service')
    def test_list_upcoming_events_success(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock events list response
        mock_events = {
            'items': [
                {
                    'summary': 'Test Event',
                    'start': {'dateTime': '2023-01-01T10:00:00Z'},
                    'htmlLink': 'http://calendar/event'
                }
            ]
        }
        mock_service.events().list().execute.return_value = mock_events
        
        result = self.loop.run_until_complete(
            list_upcoming_events()
        )
        
        self.assertIn("📅 **Próximos Eventos:**", result)
        self.assertIn("Test Event", result)
        mock_service.events().list.assert_called()

    @patch('app.skills.calendar.get_calendar_service')
    def test_create_calendar_event_success(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock insert response
        mock_event_response = {
            'htmlLink': 'http://calendar/new_event'
        }
        mock_service.events().insert().execute.return_value = mock_event_response
        
        result = self.loop.run_until_complete(
            create_calendar_event(
                summary='New Event',
                start_iso='2023-01-01T10:00:00',
                end_iso='2023-01-01T11:00:00'
            )
        )
        
        self.assertIn("✅ Evento creado con éxito", result)
        mock_service.events().insert.assert_called()

    @patch('app.skills.calendar.get_calendar_service')
    def test_update_calendar_event_success(self, mock_get_service):
        # Setup mock service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock existing event retrieval
        existing_event = {
            'id': 'test_id',
            'summary': 'Old Title',
            'start': {'dateTime': '2023-01-01T10:00:00', 'timeZone': 'UTC'},
            'end': {'dateTime': '2023-01-01T11:00:00', 'timeZone': 'UTC'}
        }
        mock_service.events().get().execute.return_value = existing_event
        
        # Mock update response
        updated_event_response = existing_event.copy()
        updated_event_response['summary'] = 'New Title'
        updated_event_response['htmlLink'] = 'http://calendar/event'
        mock_service.events().update().execute.return_value = updated_event_response

        # Run test
        result = self.loop.run_until_complete(
            update_calendar_event(event_id='test_id', summary='New Title')
        )

        # Assertions
        mock_service.events().get.assert_called_with(calendarId='primary', eventId='test_id')
        
        # Check that update was called with modified event
        expected_body = existing_event.copy()
        expected_body['summary'] = 'New Title'
        mock_service.events().update.assert_called_with(
            calendarId='primary', 
            eventId='test_id', 
            body=expected_body
        )
        
        self.assertIn("✅ Evento actualizado con éxito", result)

    @patch('app.skills.calendar.get_calendar_service')
    def test_update_calendar_event_not_found(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock HttpError 404 on get
        resp = MagicMock()
        resp.status = 404
        error = HttpError(resp, b'Not Found')
        mock_service.events().get().execute.side_effect = error

        result = self.loop.run_until_complete(
            update_calendar_event(event_id='non_existent')
        )

        self.assertIn("❌ Error: No se encontró ningún evento", result)

    @patch('app.skills.calendar.get_calendar_service')
    def test_delete_calendar_event_success(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_service.events().delete().execute.return_value = None

        result = self.loop.run_until_complete(
            delete_calendar_event(event_id='test_id')
        )

        mock_service.events().delete.assert_called_with(calendarId='primary', eventId='test_id')
        self.assertIn("✅ Evento eliminado con éxito", result)

    @patch('app.skills.calendar.get_calendar_service')
    def test_delete_calendar_event_not_found(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock HttpError 404
        resp = MagicMock()
        resp.status = 404
        error = HttpError(resp, b'Not Found')
        mock_service.events().delete().execute.side_effect = error

        result = self.loop.run_until_complete(
            delete_calendar_event(event_id='test_id')
        )

        self.assertIn("❌ Error: El evento con ID 'test_id' no existe", result)

if __name__ == '__main__':
    unittest.main()
