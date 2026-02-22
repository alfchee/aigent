"""
Content Processor Module using MarkItDown

This module provides utilities for converting various document formats
(HTML, PDF, DOCX, PPTX, etc.) to clean Markdown using the MarkItDown library.

Benefits:
- Removes HTML clutter (scripts, styles, navigation, ads)
- Preserves semantic elements (headings, lists, tables, links)
- Reduces token usage when processing web content
- Improves LLM reasoning by providing clean content
"""

import logging
from typing import Optional, Union, TYPE_CHECKING
from io import BytesIO

if TYPE_CHECKING:
    from markitdown import MarkItDown

logger = logging.getLogger(__name__)

# MarkItDown instance (singleton for performance)
_markitdown_instance: Optional['MarkItDown'] = None


def get_markitdown() -> Optional['MarkItDown']:
    """
    Get or create MarkItDown singleton instance.
    
    Returns:
        MarkItDown instance or None if not available
    """
    global _markitdown_instance
    
    if _markitdown_instance is not None:
        return _markitdown_instance
    
    try:
        from markitdown import MarkItDown
        _markitdown_instance = MarkItDown()
        logger.info("MarkItDown initialized successfully")
        return _markitdown_instance
    except ImportError:
        logger.warning("MarkItDown not installed. Run: pip install markitdown")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize MarkItDown: {e}")
        return None


def process_html(html_content: str, max_length: Optional[int] = None) -> str:
    """
    Process HTML content to clean Markdown.
    
    This removes:
    - Scripts, styles, meta tags
    - Navigation elements
    - Ads and trackers
    - Empty containers
    
    Preserves:
    - Headings (h1-h6)
    - Lists (ordered/unordered)
    - Tables
    - Links with hrefs
    - Images with alt text
    - Code blocks
    - Blockquotes
    
    Args:
        html_content: Raw HTML string
        max_length: Optional max length for output (truncates if exceeded)
        
    Returns:
        Cleaned Markdown string
    """
    md = get_markitdown()
    if md is None:
        logger.warning("MarkItDown unavailable, returning raw content")
        return html_content
    
    try:
        # Convert HTML to Markdown
        result = md.convert(html_content)
        
        if hasattr(result, 'text_content'):
            markdown = result.text_content
        elif hasattr(result, 'content'):
            markdown = result.content
        elif isinstance(result, str):
            markdown = result
        else:
            markdown = str(result)
        
        # Truncate if needed
        if max_length and len(markdown) > max_length:
            markdown = markdown[:max_length] + "\n\n... [truncated]"
        
        return markdown.strip()
        
    except Exception as e:
        logger.error(f"Error processing HTML: {e}")
        # Fallback: return original content
        return html_content


def process_content(
    content: Union[str, bytes],
    content_type: Optional[str] = None,
    max_length: Optional[int] = None
) -> str:
    """
    Process content based on its type.
    
    Automatically detects content type if not provided.
    
    Args:
        content: Raw content (string or bytes)
        content_type: MIME type or 'html', 'pdf', 'docx', etc.
        max_length: Optional max length for output
        
    Returns:
        Processed Markdown string
    """
    md = get_markitdown()
    if md is None:
        # Return as-is if MarkItDown unavailable
        return content.decode('utf-8') if isinstance(content, bytes) else content
    
    # Auto-detect content type if not provided
    if content_type is None:
        if isinstance(content, bytes):
            # Try to detect from bytes
            if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
                content_type = 'text/html'
            elif content.startswith(b'%PDF'):
                content_type = 'application/pdf'
            else:
                content_type = 'text/html'  # Default
        elif isinstance(content, str):
            if content.strip().startswith('<') and ('<!DOCTYPE' in content or '<html' in content):
                content_type = 'text/html'
            else:
                content_type = 'text/plain'
    
    try:
        if content_type in ['text/html', 'application/xhtml+xml']:
            return process_html(content, max_length)
        
        # For other types (PDF, DOCX, PPTX, etc.)
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        result = md.convert(content_bytes)
        
        if hasattr(result, 'text_content'):
            markdown = result.text_content
        elif hasattr(result, 'content'):
            markdown = result.content
        elif isinstance(result, str):
            markdown = result
        else:
            markdown = str(result)
        
        if max_length and len(markdown) > max_length:
            markdown = markdown[:max_length] + "\n\n... [truncated]"
        
        return markdown.strip()
        
    except Exception as e:
        logger.error(f"Error processing {content_type} content: {e}")
        # Fallback: return original
        return content.decode('utf-8') if isinstance(content, bytes) else content


def is_html_content(content: str) -> bool:
    """
    Check if content appears to be HTML.
    
    Args:
        content: Content to check
        
    Returns:
        True if content appears to be HTML
    """
    if not content:
        return False
    
    # Check for HTML doctype or root element
    content_lower = content.strip().lower()
    return (
        content_lower.startswith('<!doctype') or
        content_lower.startswith('<html') or
        '<head>' in content_lower or
        '<body>' in content_lower or
        ('<div' in content_lower and '</div>' in content_lower)
    )


def get_content_stats(content: str) -> dict:
    """
    Get statistics about content before/after processing.
    
    Args:
        content: HTML content
        
    Returns:
        Dictionary with stats (original_length, markdown_length, reduction_percent)
    """
    original_length = len(content)
    markdown = process_html(content)
    markdown_length = len(markdown)
    
    reduction = 0
    if original_length > 0:
        reduction = ((original_length - markdown_length) / original_length) * 100
    
    return {
        "original_length": original_length,
        "markdown_length": markdown_length,
        "reduction_percent": round(reduction, 2),
        "estimated_tokens_saved": (original_length - markdown_length) // 4
    }


# Convenience function for quick processing
def clean_html(html: str, max_length: Optional[int] = None) -> str:
    """
    Quick function to clean HTML content.
    
    Args:
        html: Raw HTML string
        max_length: Optional max output length
        
    Returns:
        Cleaned Markdown
    """
    return process_html(html, max_length)


__all__ = [
    'get_markitdown',
    'process_html',
    'process_content',
    'is_html_content',
    'get_content_stats',
    'clean_html'
]
