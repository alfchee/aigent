import argparse
from pathlib import Path

from app.channels.config import get_channels_config, set_channels_config


TEMPLATE_STUBS = {
    "polling": {"supports_polling": True, "supports_webhook": False},
    "webhook": {"supports_polling": False, "supports_webhook": True},
    "hybrid": {"supports_polling": True, "supports_webhook": True},
}


def _class_name(name: str) -> str:
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p.capitalize() for p in parts) + "Channel"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--template", choices=list(TEMPLATE_STUBS.keys()), default="polling")
    args = parser.parse_args()

    name = args.name.strip().lower()
    if not name:
        raise SystemExit("nombre inválido")

    class_name = _class_name(name)
    flags = TEMPLATE_STUBS[args.template]
    supports_polling = "True" if flags["supports_polling"] else "False"
    supports_webhook = "True" if flags["supports_webhook"] else "False"

    content = "\n".join(
        [
            "from typing import Any",
            "",
            "from app.channels.base import BaseChannel",
            "",
            "",
            f"class {class_name}(BaseChannel):",
            "    @classmethod",
            "    def channel_id(cls) -> str:",
            f"        return \"{name}\"",
            "",
            "    @classmethod",
            "    def display_name(cls) -> str:",
            f"        return \"{name.capitalize()}\"",
            "",
            "    @classmethod",
            "    def supports_polling(cls) -> bool:",
            f"        return {supports_polling}",
            "",
            "    @classmethod",
            "    def supports_webhook(cls) -> bool:",
            f"        return {supports_webhook}",
            "",
            "    @classmethod",
            "    def settings_schema(cls) -> dict[str, Any]:",
            "        return {\"fields\": []}",
            "",
            "    async def start(self) -> None:",
            "        raise NotImplementedError",
            "",
            "    async def stop(self) -> None:",
            "        raise NotImplementedError",
            "",
            "    async def send_message(self, recipient_id: str, message: str) -> None:",
            "        raise NotImplementedError",
            "",
            "",
            f"Channel = {class_name}",
            "",
        ]
    )

    target = Path(__file__).resolve().parents[1] / "app" / "channels" / f"{name}.py"
    if target.exists():
        raise SystemExit("archivo ya existe")
    target.write_text(content, encoding="utf-8")

    cfg = get_channels_config()
    modules = cfg.get("registry_modules")
    if not isinstance(modules, list):
        modules = []
    module_path = f"app.channels.{name}"
    if module_path not in modules:
        modules.append(module_path)
    cfg["registry_modules"] = modules
    set_channels_config(cfg)


if __name__ == "__main__":
    main()
