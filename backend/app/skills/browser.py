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

import base64
import os
import time

# Define user_data directory relative to this file
# .../backend/app/skills/browser.py -> .../backend/user_data
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_data")

async def screenshot(filename: str = None, return_base64: bool = False):
    """Takes a screenshot of the current page."""
    try:
        if not browser_context["page"]:
            return "No page open."
        
        if return_base64:
            # Return base64 string directly
            image_bytes = await browser_context["page"].screenshot()
            base64_str = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:image/png;base64,{base64_str}"
        else:
            # Generate filename if not provided
            if not filename:
                timestamp = int(time.time())
                filename = f"screenshot_{timestamp}.png"
            
            # Ensure it ends with .png
            if not filename.endswith('.png'):
                filename += '.png'
                
            # Save to user_data
            filepath = os.path.join(USER_DATA_DIR, filename)
            await browser_context["page"].screenshot(path=filepath)
            
            # Return Artifact format for frontend
            # The frontend can access this via http://localhost:8231/files/{filename}
            # But the [FILE_ARTIFACT: path] tag usually expects a path or full URL.
            # Let's provide a relative path that the frontend can resolve or a full URL if we knew the host.
            # Ideally, we return a relative path "/files/{filename}"
            return f"Screenshot saved. [FILE_ARTIFACT: /files/{filename}]"
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

async def click_coords(x: int, y: int):
    """Clicks at the specified coordinates (x, y)."""
    try:
        if not browser_context["page"]:
            return "No page open."
        await browser_context["page"].mouse.click(x, y)
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error clicking at coordinates: {str(e)}"

async def navigate_document_hierarchy(section: str, target_link: str):
    """
    Navigates hierarchical documentation menus (e.g. 'Live API > Get Started').
    Uses text selectors for higher precision than pure vision.
    """
    try:
        if not browser_context["page"]:
            return "No page open. Navigate first."
        
        page = browser_context["page"]
        
        # 1. Locate Sidebar (adjust selectors as needed)
        sidebar = page.locator("nav, aside, .sidebar, [role='navigation']").first
        if not await sidebar.count():
             # Fallback to body if no sidebar found, but warn
             sidebar = page.locator("body")
        
        # 2. Find Parent Section to ensure context
        # We look for a text match that might be a header or accordion trigger
        section_loc = sidebar.get_by_text(section, exact=False).first
        
        # Expand if needed (heuristic)
        if await section_loc.count() > 0:
            if await section_loc.get_attribute("aria-expanded") == "false":
                await section_loc.click()
                await page.wait_for_timeout(500) # Wait for animation
        
        # 3. Find Target Link WITHIN the sidebar context
        # This avoids finding "Get Started" in the footer
        link_loc = sidebar.get_by_role("link", name=target_link).first
        
        if await link_loc.is_visible():
            # Scroll into view if needed
            await link_loc.scroll_into_view_if_needed()
            
            # Verify URL before and after
            start_url = page.url
            await link_loc.click()
            await page.wait_for_load_state("networkidle")
            end_url = page.url
            
            return f"Successfully navigated to: {section} > {target_link}. URL: {end_url}"
        else:
            return f"Error: Found section '{section}' (or tried to), but could not find visible link '{target_link}' in sidebar."

    except Exception as e:
        return f"Semantic navigation error: {str(e)}"

async def go_back():
    """Navigates back to the previous page."""
    try:
        if not browser_context["page"]:
            return "No page open."
        await browser_context["page"].go_back()
        return f"Navigated back. Current URL: {browser_context['page'].url}"
    except Exception as e:
        return f"Error going back: {str(e)}"

async def inject_set_of_marks():
    """Injects numeric markers on interactive elements and returns semantic map."""
    try:
        if not browser_context["page"]:
            return "No page open."
        
        js_code = """
        (function() {
            // Remove existing marks
            document.querySelectorAll('.navi-mark').forEach(el => el.remove());
            
            // Prioritize navigation elements
            const selectors = 'nav a, aside a, [role="navigation"] a, button, input, select, textarea, [role="button"]';
            const elements = document.querySelectorAll(selectors);
            
            let marksData = [];
            let count = 0;
            
            elements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                
                // Check visibility
                if (rect.width > 0 && rect.height > 0 && 
                    style.visibility !== 'hidden' &&
                    style.display !== 'none') {
                    
                    // Create Visual Mark
                    const mark = document.createElement('div');
                    mark.className = 'navi-mark';
                    mark.style.position = 'absolute';
                    mark.style.left = (rect.left + window.scrollX) + 'px';
                    mark.style.top = (rect.top + window.scrollY) + 'px';
                    mark.style.zIndex = '999999';
                    mark.style.backgroundColor = '#ef4444'; // Red-500
                    mark.style.color = 'white';
                    mark.style.padding = '1px 4px';
                    mark.style.fontSize = '11px';
                    mark.style.fontWeight = 'bold';
                    mark.style.borderRadius = '3px';
                    mark.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
                    mark.style.pointerEvents = 'none';
                    mark.innerText = index;
                    mark.setAttribute('data-navi-id', index);
                    
                    // Add ID to original element for hierarchy extractor
                    el.setAttribute('data-navi-id', index);
                    
                    document.body.appendChild(mark);
                    
                    // Collect Metadata for the Agent
                    let text = el.innerText || el.getAttribute('aria-label') || el.value || "";
                    text = text.substring(0, 50).replace(/\\s+/g, ' ').trim();
                    
                    // Try to find a parent header/context
                    let parentContext = "";
                    const parentSection = el.closest('section, nav, aside, div[class*="sidebar"]');
                    if (parentSection) {
                         // Naive attempt to find a header in the parent
                         const header = parentSection.querySelector('h1, h2, h3, h4, strong, .header');
                         if (header) parentContext = header.innerText.substring(0, 30).trim();
                    }

                    marksData.push({
                        id: index,
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        context: parentContext
                    });
                    
                    count++;
                }
            });
            
            return { count, marks: marksData.slice(0, 100) }; // Limit to avoid context overflow
        })()
        """
        result = await browser_context["page"].evaluate(js_code)
        
        # Format the map for the LLM
        map_str = "\\n".join([f"[{m['id']}] {m['tag'].upper()}: '{m['text']}' (Context: {m['context']})" for m in result['marks']])
        
        return f"Injected {result['count']} markers. \nSEMANTIC MAP (Use this to identify elements):\n{map_str}"
    except Exception as e:
        return f"Error injecting marks: {str(e)}"

async def get_sidebar_hierarchy():
    """
    Extracts the sidebar structure as a clean text tree for the LLM.
    Assumes elements already have 'data-navi-id' from inject_set_of_marks.
    """
    try:
        if not browser_context["page"]:
            return "No page open."
            
        tree_map = await browser_context["page"].evaluate("""() => {
            // 1. Identify sidebar container
            const sidebar = document.querySelector('nav, aside, [role="navigation"], .sidebar, #sidebar');
            if (!sidebar) return "No clear sidebar detected.";

            let output = "";
            
            // 2. Recursive traverse function
            function traverse(element, depth = 0) {
                const children = Array.from(element.children);
                
                for (const child of children) {
                    // Check visibility (simplified)
                    const style = window.getComputedStyle(child);
                    const isVisible = style.display !== 'none' && style.visibility !== 'hidden';
                    
                    // Get text (first line only)
                    let text = (child.innerText || "").split('\\n')[0].trim();
                    
                    // Get ID if present (from inject_set_of_marks)
                    const elementId = child.getAttribute('data-navi-id') || 
                                      child.querySelector('[data-navi-id]')?.getAttribute('data-navi-id');

                    if (isVisible && text && text.length > 2) {
                        const indent = "  ".repeat(depth);
                        const idTag = elementId ? `[ID: ${elementId}]` : "";
                        
                        // Heuristic: Only add if it looks like a link, button, header or list item
                        const validTags = ['A', 'BUTTON', 'SPAN', 'DIV', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'];
                        if (validTags.includes(child.tagName)) {
                             output += `${indent}- ${idTag} ${text}\\n`;
                        }
                    }

                    // Recursion for sub-menus
                    traverse(child, depth + 1);
                }
            }

            traverse(sidebar);
            return output;
        }""")
        
        return f"SIDEBAR HIERARCHY MAP:\n{tree_map}"
    except Exception as e:
        return f"Error extracting hierarchy: {str(e)}"

async def find_element_by_text_content(text_target: str):
    """
    Finds elements by their exact or partial text content, ignoring CSS selectors.
    Useful when visual hierarchy is confusing.
    """
    try:
        if not browser_context["page"]:
            return "No page open."
        
        page = browser_context["page"]
        
        # 1. Try Exact Match on Link/Button (High Precision)
        locator = page.get_by_role("link", name=text_target, exact=True)
        if await locator.count() > 0 and await locator.first.is_visible():
            await locator.first.click()
            await page.wait_for_load_state("networkidle")
            return f"Success: Clicked exact link '{text_target}'. URL: {page.url}"
            
        # 2. Try Fuzzy Match on Text (Medium Precision)
        locator = page.get_by_text(text_target)
        count = await locator.count()
        
        if count > 0:
            # Filter for clickable/visible elements
            for i in range(count):
                el = locator.nth(i)
                if await el.is_visible():
                    # Check if it's clickable or inside a clickable
                    await el.click()
                    await page.wait_for_load_state("networkidle")
                    return f"Success: Clicked text element '{text_target}'. URL: {page.url}"
        
        return f"Failure: No visible element found containing text '{text_target}'."
    except Exception as e:
        return f"Error finding element by text: {str(e)}"

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

tools = [navigate, get_page_content, screenshot, click_coords, navigate_document_hierarchy, go_back, inject_set_of_marks, get_sidebar_hierarchy, find_element_by_text_content, close_browser]
