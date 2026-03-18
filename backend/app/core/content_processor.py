from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

logger = logging.getLogger("navibot.core.content_processor")


class ContentProcessor:
    def __init__(self):
        self._converter = MarkItDown()

    def _convert_sync(self, file_path: str) -> tuple[str, Optional[str]]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return "", "File not found"
        try:
            result = self._converter.convert_local(path)
            content = (getattr(result, "text_content", "") or "").strip()
            if not content:
                return "", "No extractable content"
            return content, None
        except Exception as exc:
            logger.exception("MarkItDown conversion failed for %s: %s", file_path, exc)
            return "", str(exc)

    async def extract_text(self, file_path: str) -> tuple[str, Optional[str]]:
        return await asyncio.to_thread(self._convert_sync, file_path)


content_processor = ContentProcessor()
