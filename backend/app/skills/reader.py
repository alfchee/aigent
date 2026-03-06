import json
import httpx
from app.core.content_processor import process_html, get_content_stats


async def read_web_content(url: str, max_chars: int = 20000, timeout: float = 10.0) -> str:
    """
    Lee y convierte a Markdown el contenido de una página web.
    
    Usa MarkItDown para limpiar el HTML (elimina scripts, estilos, navegación, ads)
    y preservar solo el contenido semántico.
    
    Args:
        url: La URL de la página a leer.
        max_chars: Máximo de caracteres a retornar.
        timeout: Tiempo máximo de espera.
        
    Returns:
        JSON string con el contenido en Markdown.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text or ""
            
            if len(html) > 200000:
                html = html[:200000]
            
            # Get stats before processing
            stats = get_content_stats(html)
            
            # Use MarkItDown for cleaner conversion
            markdown = process_html(html)
            
            if max_chars > 0 and len(markdown) > max_chars:
                markdown = markdown[:max_chars]
            
            payload = {
                "url": url,
                "content": markdown,
                "content_length": len(markdown),
                "content_type": response.headers.get("content-type"),
                "processing_stats": stats,
            }
            return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return f"Error leyendo contenido web: {str(e)}"


tools = [read_web_content]
