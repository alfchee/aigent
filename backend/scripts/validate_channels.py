import asyncio

from app.channels.config import get_channels_config
from app.channels.manager import channel_manager
from app.core.persistence import init_db


async def run():
    init_db()
    cfg = get_channels_config()
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    failures = []
    for channel_id, entry in channels.items():
        if not isinstance(entry, dict):
            continue
        settings = entry.get("settings") or {}
        errors = await channel_manager.validate_channel(channel_id, settings, check_connection=True)
        if errors:
            failures.append({"channel_id": channel_id, "errors": errors})
    if failures:
        raise SystemExit(str(failures))


if __name__ == "__main__":
    asyncio.run(run())
