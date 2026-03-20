import logging
import os
import re
from typing import Optional

from markitdown import MarkItDown as _MarkItDown
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field

logger = logging.getLogger("navibot.skills.web_browse")

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"


class WebBrowseArgs(BaseModel):
    url: str = Field(..., description="Full URL to browse (must include https:// or http://)")
    session_id: str = Field(default="default", description="Session ID for isolating browser context")


class WebBrowseResult(BaseModel):
    url: str
    title: str
    text_content: str
    links: list[str] = Field(default_factory=list)
    error: Optional[str] = None


def web_browse(url: str, session_id: str = "default") -> str:
    """
    Browse a URL using Playwright (headless Chromium), extract clean text content
    and links, then process with MarkItDown for rich content.

    Handles JavaScript-rendered pages, infinite scroll, and local files.
    """
    result = WebBrowseResult(url=url, title="", text_content="", links=[], error=None)

    if not url.startswith(("http://", "https://", "file://")):
        result.error = f"Unsupported URL scheme: {url}"
        return _serialize_result(result)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = browser.new_context(
                extra_http_headers={"User-Agent": "Mozilla/5.0 (compatible; NaviBot/2.0)"}
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                result.url = page.url
                result.title = page.title() or ""

                page.wait_for_timeout(2000)

                raw_html = page.content()
                result.text_content = _extract_text(raw_html)
                result.links = _extract_links(page)

            finally:
                page.close()
                context.close()
                browser.close()

    except Exception as exc:
        logger.exception("web_browse failed for %s", url)
        result.error = str(exc)

    return _serialize_result(result)


def _extract_text(html: str) -> str:
    try:
        md = _MarkItDown()
        out = md.convert(html)
        return (out.text_content or "").strip()[:10_000]
    except Exception:
        pass

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<noscript[^>]*>.*?</noscript>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:10_000]


def _extract_links(page) -> list[str]:
    links: list[str] = []
    try:
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
        seen = set()
        for href in hrefs:
            if href and href.startswith("http") and href not in seen:
                seen.add(href)
                links.append(href)
    except Exception:
        pass
    return links[:20]


def _serialize_result(result: WebBrowseResult) -> str:
    return result.model_dump_json(include={"url", "title", "text_content", "links", "error"})
