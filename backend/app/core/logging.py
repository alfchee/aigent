import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

import httpx

from app.core.runtime_context import get_request_id, get_session_id


def _utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        output = {}
        for k, v in value.items():
            key = str(k).lower()
            if any(token in key for token in ["authorization", "api_key", "apikey", "token", "password", "secret", "key"]):
                output[k] = "[REDACTED]"
            else:
                output[k] = _redact(v)
        return output
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": _utc_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("SERVICE_NAME", "navibot-backend"),
            "request_id": get_request_id(),
            "session_id": get_session_id(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "payload"):
            payload["payload"] = _safe_json(_redact(record.payload))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class HttpLogHandler(logging.Handler):
    def __init__(self, url: str):
        super().__init__()
        self.url = url

    async def _post(self, data: dict):
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(self.url, json=data)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(self.format(record))
        except Exception:
            payload = {"message": record.getMessage(), "level": record.levelname}
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._post(payload))
        except RuntimeError:
            try:
                asyncio.run(self._post(payload))
            except Exception:
                return


def setup_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_path = os.getenv("LOG_FILE_PATH", "logs/navibot.log")
    aggregation_url = os.getenv("LOG_AGGREGATION_URL")

    logger = logging.getLogger()
    if getattr(logger, "_navibot_configured", False):
        return

    logger.setLevel(log_level)
    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if aggregation_url:
        http_handler = HttpLogHandler(aggregation_url)
        http_handler.setFormatter(formatter)
        logger.addHandler(http_handler)

    logger._navibot_configured = True


async def notify_alert(event: dict) -> None:
    url = os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return
    payload = {
        "timestamp": _utc_iso(),
        "service": os.getenv("SERVICE_NAME", "navibot-backend"),
        "event": _redact(event),
    }
    async with httpx.AsyncClient(timeout=4.0) as client:
        await client.post(url, json=payload)
