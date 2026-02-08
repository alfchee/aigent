from playwright.async_api import async_playwright
import asyncio
import json

from app.core.filesystem import SessionWorkspace
from app.core.runtime_context import get_session_id

_playwright = None
_sessions: dict[str, dict] = {}


def _ctx() -> dict:
    sid = get_session_id()
    if sid not in _sessions:
        _sessions[sid] = {"browser": None, "page": None}
    return _sessions[sid]

async def ensure_browser():
    """Ensures the browser is open."""
    global _playwright
    ctx = _ctx()
    if not _playwright:
        _playwright = await async_playwright().start()
    
    if not ctx["browser"]:
        # Launch headless by default, or False for debugging if needed
        ctx["browser"] = await _playwright.chromium.launch(headless=True)
        
    if not ctx["page"]:
        ctx["page"] = await ctx["browser"].new_page()

async def navigate(url: str):
    """Navigates the browser to the specified URL."""
    try:
        await ensure_browser()
        ctx = _ctx()
        await ctx["page"].goto(url)
        title = await ctx["page"].title()
        return f"Navigated to {url}. Page title: {title}"
    except Exception as e:
        return f"Error navigating: {str(e)}"

async def get_page_content():
    """Returns the text content of the current page."""
    try:
        ctx = _ctx()
        if not ctx["page"]:
            return "No page open. Navigate first."
        # We can optimize this to return simplified HTML or just text
        content = await ctx["page"].content()
        return content[:10000] # truncate for now
    except Exception as e:
        return f"Error getting content: {str(e)}"

async def screenshot(filename: str = "screenshot.png"):
    """Takes a screenshot of the current page."""
    try:
        ctx = _ctx()
        if not ctx["page"]:
            return "No page open."
        data = await ctx["page"].screenshot()
        ws = SessionWorkspace(get_session_id())
        meta = ws.write_bytes(filename, data)
        return json.dumps({"saved": meta}, ensure_ascii=False)
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

async def close_browser():
    """Closes the browser session."""
    global _playwright
    sid = get_session_id()
    ctx = _ctx()
    if ctx["browser"]:
        await ctx["browser"].close()
        ctx["browser"] = None
        ctx["page"] = None
    try:
        _sessions.pop(sid, None)
    except Exception:
        pass
    if _playwright and not any(v.get("browser") for v in _sessions.values()):
        await _playwright.stop()
        _playwright = None
    return "Browser closed."

tools = [navigate, get_page_content, screenshot, close_browser]
