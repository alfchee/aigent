import argparse
import os

from app.channels.config import get_channels_config, set_channels_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_TOKEN", ""))
    parser.add_argument("--enable-telegram", action="store_true")
    args = parser.parse_args()

    cfg = get_channels_config()
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        channels = {}

    if args.enable_telegram:
        token = (args.telegram_token or "").strip()
        if not token:
            raise SystemExit("token requerido")
        channels["telegram"] = {"enabled": True, "settings": {"token": token}}

    cfg["channels"] = channels
    set_channels_config(cfg)


if __name__ == "__main__":
    main()
