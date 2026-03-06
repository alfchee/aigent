import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import asyncio
from pathlib import Path

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.skills import google_drive

class TestGoogleDrive(unittest.IsolatedAsyncioTestCase):
    
    @patch('app.skills.google_drive.get_drive_service')
    async def test_list_drive_files(self, mock_get_service):
        # Setup mocks
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_files = mock_service.files.return_value
        mock_list = mock_files.list.return_value
        mock_list.execute.return_value = {
            'files': [
                {'id': '123', 'name': 'TestFolder', 'mimeType': 'application/vnd.google-apps.folder'},
                {'id': '456', 'name': 'TestFile.txt', 'mimeType': 'text/plain'}
            ]
        }
        
        # Execute
        result = await google_drive.list_drive_files('root')
        
        # Verify
        self.assertIn("TestFolder", result)
        self.assertIn("[CARPETA]", result)
        self.assertIn("TestFile.txt", result)
        self.assertIn("[ARCHIVO]", result)

    @patch('app.skills.google_drive.get_drive_service')
    async def test_search_drive(self, mock_get_service):
        # Setup mocks
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        mock_files = mock_service.files.return_value
        mock_list = mock_files.list.return_value
        mock_list.execute.return_value = {
            'files': [
                {'id': '999', 'name': 'FoundFile.xlsx', 'mimeType': 'application/vnd.google-apps.spreadsheet'}
            ]
        }
        
        # Execute
        result = await google_drive.search_drive('FoundFile')
        
        # Verify
        self.assertIn("FoundFile.xlsx", result)
        self.assertIn("999", result)

    @patch('app.skills.google_drive.get_drive_service')
    async def test_move_drive_file(self, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        mock_files = mock_service.files.return_value
        mock_files.get.return_value.execute.return_value = {
            "parents": ["old_parent"],
            "name": "Archivo.txt"
        }

        result = await google_drive.move_drive_file("file_id", "new_folder")

        self.assertIn("Archivo movido", result)
        mock_files.update.assert_called_once_with(
            fileId="file_id",
            addParents="new_folder",
            removeParents="old_parent",
            fields="id, parents"
        )

    @patch('app.skills.google_drive.get_drive_service')
    @patch('app.skills.google_drive.get_session_id')
    @patch('app.skills.google_drive.SessionWorkspace')
    async def test_download_file(self, mock_workspace_cls, mock_get_session, mock_get_service):
        # Setup mocks
        mock_get_session.return_value = "test_session"
        mock_workspace = MagicMock()
        mock_workspace.safe_path.return_value = Path("/tmp/test.txt")
        mock_workspace_cls.return_value = mock_workspace
        
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        with patch('app.skills.google_drive._download_to_path_sync') as mock_download_sync:
            
            # Execute
            result = await google_drive.download_file_from_drive('file_id', 'test.txt')
            
            # Verify
            self.assertIn("descargado exitosamente", result)
            mock_download_sync.assert_called_once()

if __name__ == '__main__':
    unittest.main()
