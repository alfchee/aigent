import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.skills import google_workspace_manager

class TestGoogleWorkspaceManager(unittest.IsolatedAsyncioTestCase):
    
    @patch('app.skills.google_workspace_manager._get_workspace_config')
    @patch('app.skills.google_workspace_manager.get_sheets_client')
    @patch('app.skills.google_workspace_manager._create_spreadsheet_with_retry')
    async def test_create_google_spreadsheet_success(self, mock_create, mock_get_client, mock_get_config):
        # Setup mocks
        mock_get_config.return_value = {}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.url = "http://mock.url"
        mock_spreadsheet.id = "mock_id"
        mock_create.return_value = mock_spreadsheet
        
        # Execute
        result = await google_workspace_manager.create_google_spreadsheet("Test Sheet")
        
        # Verify
        self.assertEqual(result["url"], "http://mock.url")
        self.assertEqual(result["id"], "mock_id")
        mock_create.assert_called_once_with(mock_client, "Test Sheet")
        mock_spreadsheet.share.assert_called_once() # Should try to share

    @patch('app.skills.google_workspace_manager._get_workspace_config')
    @patch('app.skills.google_workspace_manager._transfer_ownership')
    @patch('app.skills.google_workspace_manager.get_sheets_client')
    @patch('app.skills.google_workspace_manager._create_spreadsheet_with_retry')
    async def test_create_google_spreadsheet_transfer_ownership(self, mock_create, mock_get_client, mock_transfer, mock_get_config):
        mock_get_config.return_value = {"owner_email": "owner@example.com"}
        mock_client = MagicMock()
        mock_client.auth = MagicMock()
        mock_get_client.return_value = mock_client

        mock_spreadsheet = MagicMock()
        mock_spreadsheet.url = "http://mock.url"
        mock_spreadsheet.id = "mock_id"
        mock_create.return_value = mock_spreadsheet

        result = await google_workspace_manager.create_google_spreadsheet("Test Sheet")

        self.assertEqual(result["id"], "mock_id")
        mock_transfer.assert_called_once_with("mock_id", "owner@example.com", mock_client.auth)

    @patch('app.skills.google_workspace_manager._get_workspace_config')
    @patch('app.skills.google_workspace_manager.get_sheets_client')
    async def test_create_google_spreadsheet_creds_missing(self, mock_get_client, mock_get_config):
        # Setup
        mock_get_config.return_value = {}
        mock_get_client.side_effect = FileNotFoundError("Creds missing")
        
        # Execute
        result = await google_workspace_manager.create_google_spreadsheet("Test Sheet")
        
        # Verify
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Creds missing")

    @patch('app.skills.google_workspace_manager.get_sheets_client')
    @patch('app.skills.google_workspace_manager._open_sheet_with_retry')
    @patch('app.skills.google_workspace_manager._update_sheet_with_retry')
    async def test_update_sheet_data_success(self, mock_update, mock_open, mock_get_client):
        # Setup
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_sh = MagicMock()
        mock_worksheet = MagicMock()
        mock_sh.worksheet.return_value = mock_worksheet
        mock_open.return_value = mock_sh
        
        # Execute
        result = await google_workspace_manager.update_sheet_data("sheet_id", "Sheet1!A1", [["data"]])
        
        # Verify
        self.assertIn("Datos actualizados exitosamente", result)
        mock_sh.worksheet.assert_called_with("Sheet1")
        mock_update.assert_called_once_with(mock_worksheet, "A1", [["data"]])

if __name__ == '__main__':
    unittest.main()
