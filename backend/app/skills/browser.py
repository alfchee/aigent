from playwright.async_api import async_playwright
import asyncio

# Global state to hold browser instance
browser_context = {
    "playwright": None,
    "browser": None,
    "page": None
}

async def ensure_browser():
    """Ensures the browser is open."""
    if not browser_context["playwright"]:
        browser_context["playwright"] = await async_playwright().start()
    
    if not browser_context["browser"]:
        # Launch headless by default, or False for debugging if needed
        browser_context["browser"] = await browser_context["playwright"].chromium.launch(headless=True)
        
    if not browser_context["page"]:
        browser_context["page"] = await browser_context["browser"].new_page()

async def navigate(url: str):
    """Navigates the browser to the specified URL."""
    try:
        await ensure_browser()
        await browser_context["page"].goto(url)
        title = await browser_context["page"].title()
        return f"Navigated to {url}. Page title: {title}"
    except Exception as e:
        return f"Error navigating: {str(e)}"

async def get_page_content():
    """Returns the text content of the current page."""
    try:
        if not browser_context["page"]:
            return "No page open. Navigate first."
        # We can optimize this to return simplified HTML or just text
        content = await browser_context["page"].content()
        return content[:10000] # truncate for now
    except Exception as e:
        return f"Error getting content: {str(e)}"

async def screenshot(filename: str = "screenshot.png"):
    """Takes a screenshot of the current page."""
    try:
        if not browser_context["page"]:
            return "No page open."
        await browser_context["page"].screenshot(path=filename)
        return f"Screenshot saved to {filename}"
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

async def close_browser():
    """Closes the browser session."""
    if browser_context["browser"]:
        await browser_context["browser"].close()
        browser_context["browser"] = None
        browser_context["page"] = None
    if browser_context["playwright"]:
        await browser_context["playwright"].stop()
        browser_context["playwright"] = None
    return "Browser closed."

tools = [navigate, get_page_content, screenshot, close_browser]
