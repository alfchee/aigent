import json
import os
import urllib.parse
import httpx
from playwright.async_api import async_playwright


def _get_brave_api_key() -> str | None:
    return os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")


async def search_brave(query: str, count: int = 5, offset: int = 0, lang: str = "es") -> str:
    api_key = _get_brave_api_key()
    if not api_key:
        return "Error: BRAVE_API_KEY no configurado."
    params = {
        "q": query,
        "count": count,
        "offset": offset,
        "search_lang": lang,
        "source": "web",
    }
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.search.brave.com/res/v1/web/search", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        results = []
        web = data.get("web", {})
        for item in web.get("results", [])[:count]:
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "description": item.get("description") or item.get("snippet"),
                }
            )
        payload = {"query": query, "source": "brave", "results": results}
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return f"Error en Brave Search: {str(e)}"


async def search_duckduckgo_fallback(query: str, max_results: int = 5) -> str:
    url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    browser = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            results = await page.eval_on_selector_all(
                "div.result",
                """(nodes, maxResults) => nodes.slice(0, maxResults).map(node => {
                    const link = node.querySelector('a.result__a');
                    const snippet = node.querySelector('.result__snippet') || node.querySelector('.result__extras__snippet');
                    return {
                        title: link ? link.innerText : '',
                        url: link ? link.href : '',
                        description: snippet ? snippet.innerText : ''
                    };
                })""",
                max_results,
            )
            payload = {"query": query, "source": "duckduckgo", "results": results}
            return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return f"Error en DuckDuckGo fallback: {str(e)}"
    finally:
        if browser:
            await browser.close()


tools = [search_brave, search_duckduckgo_fallback]
