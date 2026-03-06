import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Add backend to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.skills.google_drive import _download_to_path_sync, _EXPORT_MIME_TYPES

class TestGoogleDriveExport(unittest.TestCase):

    @patch('app.skills.google_drive.get_drive_service')
    @patch('app.skills.google_drive.MediaIoBaseDownload')
    def test_download_google_sheet_exports_as_xlsx(self, mock_downloader, mock_get_service):
        """
        Test that downloading a Google Sheet triggers export_media with correct MIME type.
        """
        # Setup mocks
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock file metadata response
        file_id = "test_sheet_id"
        mock_service.files().get().execute.return_value = {
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "name": "Test Sheet"
        }
        
        # Mock export_media return value (the request object)
        mock_request = MagicMock()
        mock_service.files().export_media.return_value = mock_request
        
        # Mock downloader behavior
        mock_downloader_instance = mock_downloader.return_value
        # Simulate immediate completion
        mock_downloader_instance.next_chunk.return_value = (None, True)
        
        # Execute function under test
        target_path = "/tmp/test_sheet.xlsx"
        with patch('builtins.open', mock_open()) as mocked_file:
            _download_to_path_sync(file_id, target_path)
            
        # Assertions
        
        # 1. Verify files().get() was called to check mimeType
        mock_service.files().get.assert_called_with(fileId=file_id, fields="mimeType,name")
        
        # 2. Verify export_media was called instead of get_media
        expected_export_mime = _EXPORT_MIME_TYPES["application/vnd.google-apps.spreadsheet"]
        mock_service.files().export_media.assert_called_with(
            fileId=file_id, 
            mimeType=expected_export_mime
        )
        mock_service.files().get_media.assert_not_called()
        
        # 3. Verify downloader was initialized with the export request
        mock_downloader.assert_called_with(mocked_file(), mock_request)

    @patch('app.skills.google_drive.get_drive_service')
    @patch('app.skills.google_drive.MediaIoBaseDownload')
    def test_download_regular_file_uses_get_media(self, mock_downloader, mock_get_service):
        """
        Test that downloading a regular file (e.g. PDF) uses get_media.
        """
        # Setup mocks
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock file metadata response for a PDF
        file_id = "test_pdf_id"
        mock_service.files().get().execute.return_value = {
            "mimeType": "application/pdf",
            "name": "Test PDF"
        }
        
        # Mock get_media return value
        mock_request = MagicMock()
        mock_service.files().get_media.return_value = mock_request
        
        # Mock downloader behavior
        mock_downloader_instance = mock_downloader.return_value
        mock_downloader_instance.next_chunk.return_value = (None, True)
        
        # Execute function under test
        target_path = "/tmp/test.pdf"
        with patch('builtins.open', mock_open()) as mocked_file:
            _download_to_path_sync(file_id, target_path)
            
        # Assertions
        
        # 1. Verify get_media was called
        mock_service.files().get_media.assert_called_with(fileId=file_id)
        
        # 2. Verify export_media was NOT called
        mock_service.files().export_media.assert_not_called()

if __name__ == '__main__':
    unittest.main()
