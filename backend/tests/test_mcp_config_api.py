
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

class TestMcpConfigApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.mcp.bot_pool")
    @patch("app.api.mcp.upsert_server_config")
    @patch("app.api.mcp.get_active_config_runtime")
    @patch("app.api.mcp.get_registry_merged")
    @patch("app.api.mcp._resolve_definition")
    def test_save_server(self, mock_resolve, mock_registry, mock_config, mock_upsert, mock_bot_pool):
        # Configure mocks
        mock_bot_pool.reload_all_mcp = AsyncMock()
        mock_registry.return_value = {"test-server": {"name": "Test"}}
        mock_config.return_value = {}
        mock_resolve.return_value = {"name": "Test", "command": "echo", "args": []}
        
        payload = {
            "server_id": "test-server",
            "enabled": True,
            "params": {},
            "env_vars": {}
        }
        
        response = self.client.post("/api/mcp/servers", json=payload)
        self.assertEqual(response.status_code, 200)
        mock_upsert.assert_called_once()
        mock_bot_pool.reload_all_mcp.assert_awaited_once()

    @patch("app.api.mcp.bot_pool")
    @patch("app.api.mcp.delete_server_config")
    def test_delete_server(self, mock_delete, mock_bot_pool):
        # Configure mocks
        mock_bot_pool.reload_all_mcp = AsyncMock()
        mock_delete.return_value = True
        
        response = self.client.delete("/api/mcp/servers/test-server")
        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once_with("test-server")
        mock_bot_pool.reload_all_mcp.assert_awaited_once()
