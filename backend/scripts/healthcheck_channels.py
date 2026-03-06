import argparse
import asyncio
import json

from app.channels.config import get_channels_config
from app.channels.manager import channel_manager
from app.core.persistence import init_db


async def run(check_connection: bool):
    init_db()
    cfg = get_channels_config()
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    results = []
    for channel_id, entry in channels.items():
        if not isinstance(entry, dict):
            continue
        settings = entry.get("settings") or {}
        errors = await channel_manager.validate_channel(channel_id, settings, check_connection=check_connection)
        results.append({"channel_id": channel_id, "ok": len(errors) == 0, "errors": errors})
    print(json.dumps({"results": results}, ensure_ascii=False))
    if any(not r["ok"] for r in results):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-connection", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.check_connection))


if __name__ == "__main__":
    main()
