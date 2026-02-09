import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.skills.reader import read_web_content


class TestReadWebContent(unittest.IsolatedAsyncioTestCase):
    @patch("app.skills.reader.httpx.AsyncClient")
    async def test_read_web_content_parses_table(self, mock_client):
        html = "<table><tr><th>Juego</th><th>Año</th></tr><tr><td>Zelda</td><td>1986</td></tr></table>"
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.text = html
        response.headers = {"content-type": "text/html"}
        client = MagicMock()
        client.get = AsyncMock(return_value=response)
        mock_client.return_value.__aenter__.return_value = client
        mock_client.return_value.__aexit__.return_value = None

        output = await read_web_content("https://example.com", max_chars=20000)
        data = json.loads(output)
        self.assertIn("| Juego | Año |", data["content"])
        self.assertEqual(data["url"], "https://example.com")
