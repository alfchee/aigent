import logging
import os
from typing import Optional

from pydantic import BaseModel, Field
from duckduckgo_search import DDGS

logger = logging.getLogger("navibot.skills.smart_search")

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")


class SmartSearchArgs(BaseModel):
    query: str = Field(..., description="Search query string")
    num_results: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    search_type: str = Field(default="web", description="Type: web, news, or videos")


class SmartSearchResult(BaseModel):
    query: str
    results: list[dict]
    error: Optional[str] = None


def smart_search(query: str, num_results: int = 5, search_type: str = "web") -> str:
    """
    Smart search using Brave Search API (primary) with DuckDuckGo fallback.
    Returns web results with title, URL, and snippet.
    """
    result = SmartSearchResult(query=query, results=[], error=None)

    if not query or not query.strip():
        result.error = "Empty query"
        return _serialize_result(result)

    try:
        if BRAVE_API_KEY:
            result.results = _brave_search(query, num_results, search_type, BRAVE_API_KEY)
        else:
            logger.info("Brave API key not set, using DuckDuckGo fallback")
            result.results = _duckduckgo_search(query, num_results, search_type)
    except Exception as exc:
        logger.exception("smart_search failed for query: %s", query)
        result.error = str(exc)

    return _serialize_result(result)


def _brave_search(query: str, num_results: int, search_type: str, api_key: str) -> list[dict]:
    import requests

    endpoint = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "X-Subscription-Token": api_key,
        "Accept": "application/json",
    }
    params = {
        "q": query,
        "count": num_results,
        "freshness": "y" if search_type == "news" else "y" if search_type == "web" else "y",
    }
    resp = requests.get(endpoint, headers=headers, params=params, timeout=15)
    if resp.status_code != 200:
        logger.warning("Brave API error %s: %s", resp.status_code, resp.text[:200])
        return _duckduckgo_search(query, num_results, search_type)

    data = resp.json()
    web = data.get("web", {}) or {}
    results = []
    for item in (web.get("results") or [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "source": "brave",
        })
    return results


def _duckduckgo_search(query: str, num_results: int, search_type: str) -> list[dict]:
    results = []
    ddgs = DDGS()
    try:
        if search_type == "news":
            generator = ddgs.news(query, max_results=num_results)
        elif search_type == "videos":
            generator = ddgs.videos(query, max_results=num_results)
        else:
            generator = ddgs.text(query, max_results=num_results)

        for r in generator:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "description": r.get("body", ""),
                "source": "duckduckgo",
            })
    finally:
        try:
            ddgs.close()
        except Exception:
            pass

    return results


def _serialize_result(result: SmartSearchResult) -> str:
    return result.model_dump_json(include={"query", "results", "error"})
