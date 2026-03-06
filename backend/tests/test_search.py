import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.skills.search import search_brave, search_duckduckgo_fallback


class TestSearchTools(unittest.IsolatedAsyncioTestCase):
    async def test_search_brave_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            output = await search_brave("hola")
        self.assertIn("BRAVE_API_KEY", output)

    @patch("app.skills.search.httpx.AsyncClient")
    async def test_search_brave_parses_results(self, mock_client):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "web": {"results": [{"title": "t", "url": "u", "description": "d"}]}
        }
        mock_client_instance = MagicMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None
        with patch.dict(os.environ, {"BRAVE_API_KEY": "token"}):
            output = await search_brave("hola", count=1)
        data = json.loads(output)
        self.assertEqual(data["results"][0]["url"], "u")

    @patch("app.skills.search.async_playwright")
    async def test_search_duckduckgo_fallback_parses_results(self, mock_playwright):
        page = MagicMock()
        page.goto = AsyncMock()
        page.eval_on_selector_all = AsyncMock(
            return_value=[{"title": "t", "url": "u", "description": "d"}]
        )
        browser = MagicMock()
        browser.new_page = AsyncMock(return_value=page)
        browser.close = AsyncMock()
        chromium = MagicMock()
        chromium.launch = AsyncMock(return_value=browser)
        playwright = MagicMock()
        playwright.chromium = chromium
        mock_playwright.return_value.__aenter__.return_value = playwright
        mock_playwright.return_value.__aexit__.return_value = None
        output = await search_duckduckgo_fallback("hola", max_results=1)
        data = json.loads(output)
        self.assertEqual(data["results"][0]["title"], "t")
