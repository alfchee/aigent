import os
from fastapi import APIRouter, Header, HTTPException, Request
from app.channels.telegram import telegram_bot

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    payload = await request.json()
    processed = await telegram_bot.process_webhook_update(payload)
    return {"ok": True, "processed": processed}
