import json
import httpx
from markdownify import markdownify as md


async def read_web_content(url: str, max_chars: int = 20000, timeout: float = 10.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text or ""
            if len(html) > 200000:
                html = html[:200000]
            markdown = md(html)
            if max_chars > 0:
                markdown = markdown[:max_chars]
            payload = {
                "url": url,
                "content": markdown,
                "content_length": len(markdown),
                "content_type": response.headers.get("content-type"),
            }
            return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return f"Error leyendo contenido web: {str(e)}"


tools = [read_web_content]
