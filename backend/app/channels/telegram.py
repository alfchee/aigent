import asyncio
import fcntl
import os
import time
from typing import Any

from telegram import Update
from telegram.error import Conflict
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from app.channels.base import BaseChannel
from app.core.agent import execute_agent_task
from app.core.filesystem import SessionWorkspace


class TelegramChannel(BaseChannel):
    @classmethod
    def channel_id(cls) -> str:
        return "telegram"

    @classmethod
    def display_name(cls) -> str:
        return "Telegram"

    @classmethod
    def capabilities(cls) -> list[str]:
        return ["text", "files", "images"]

    @classmethod
    def supports_polling(cls) -> bool:
        return True

    @classmethod
    def settings_schema(cls) -> dict[str, Any]:
        return {
            "fields": [
                {"key": "token", "label": "Token", "type": "secret", "required": True},
                {"key": "auto_send_artifacts", "label": "Enviar artefactos", "type": "boolean", "required": False},
            ]
        }

    @classmethod
    async def validate_settings(cls, settings: dict[str, Any], check_connection: bool = False) -> list[str]:
        errors = []
        token = (settings or {}).get("token") or os.getenv("TELEGRAM_TOKEN")
        if not isinstance(token, str) or not token.strip():
            errors.append("token requerido")
        if check_connection and not errors:
            try:
                from telegram import Bot

                bot = Bot(token=token)
                await bot.get_me()
            except Exception:
                errors.append("token inválido o sin conexión")
        return errors

    def __init__(self, settings: dict[str, Any], status_callback=None):
        super().__init__(settings, status_callback=status_callback)
        self.token = (settings or {}).get("token") or os.getenv("TELEGRAM_TOKEN")
        self.auto_send_artifacts = bool(settings.get("auto_send_artifacts", True))
        self.app = ApplicationBuilder().token(self.token).read_timeout(30).write_timeout(30).build()
        self._lock_file = None
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, self.handle_document))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text("👋 ¡Hola! Soy NaviBot en Telegram. Envíame texto o archivos para analizar.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_chat is None:
            return
        user_text = update.message.text or ""
        chat_id = str(update.effective_chat.id)
        user_id = str(update.effective_user.id) if update.effective_user else chat_id
        session_id = f"tg_{chat_id}"
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            # Si falla el typing action, no bloqueamos el flujo
            pass
            
        try:
            response_text = await execute_agent_task(user_text, session_id=session_id, memory_user_id=f"tg_user_{user_id}")
            if not response_text:
                response_text = "✅ Tarea completada (sin respuesta de texto)."

            if len(response_text) > 4000:
                for x in range(0, len(response_text), 4000):
                    await update.message.reply_text(response_text[x:x + 4000])
            else:
                await update.message.reply_text(response_text)
            if self.auto_send_artifacts:
                await self.check_and_send_artifacts(chat_id, session_id, context)
            await self._heartbeat()
        except Exception as e:
            error_msg = str(e)
            if "Chat not found" in error_msg:
                # Esto sucede si el bot intenta responder pero el chat ya no existe o el usuario bloqueó al bot
                print(f"Telegram Error: Chat {chat_id} not found or user blocked bot.")
                return
            await update.message.reply_text(f"⚠️ Error procesando tu solicitud: {error_msg}")
            await self._error(error_msg)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_chat is None:
            return
        chat_id = str(update.effective_chat.id)
        session_id = f"tg_{chat_id}"
        file = None
        file_name = None

        if update.message.document:
            file = await update.message.document.get_file()
            file_name = update.message.document.file_name
        elif update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_name = f"image_{file.file_unique_id}.jpg"

        if not file or not file_name:
            return

        workspace = SessionWorkspace(session_id)
        file_path = os.path.join(workspace.root, file_name)
        await file.download_to_drive(file_path)
        await update.message.reply_text(f"📥 He recibido el archivo '{file_name}'. Lo he guardado en tu workspace.")
        await self._heartbeat()

    async def check_and_send_artifacts(self, chat_id: str, session_id: str, context: ContextTypes.DEFAULT_TYPE):
        workspace = SessionWorkspace(session_id)
        supported_extensions = (".png", ".jpg", ".pdf", ".csv", ".xlsx")
        if not os.path.exists(workspace.root):
            return
        files = [f for f in os.listdir(workspace.root) if f.endswith(supported_extensions)]
        current_time = time.time()
        for f in files:
            file_path = os.path.join(workspace.root, f)
            mod_time = os.path.getmtime(file_path)
            if current_time - mod_time < 20:
                await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
                with open(file_path, "rb") as doc:
                    await context.bot.send_document(chat_id=chat_id, document=doc, caption=f"📂 Generado: {f}")

    async def start(self) -> None:
        import uuid
        polling_enabled = os.getenv("NAVIBOT_TELEGRAM_POLLING_ENABLED", "true").lower() not in {"0", "false", "no"}
        if not polling_enabled:
            raise RuntimeError("telegram polling disabled via NAVIBOT_TELEGRAM_POLLING_ENABLED")
        instance_id = str(uuid.uuid4())[:8]
        pid = os.getpid()
        print(f"[{pid}] TelegramChannel {instance_id}: Attempting to acquire lock...")
        
        lock_path = os.path.abspath(os.getenv("NAVIBOT_TELEGRAM_LOCK_PATH", "/tmp/navibot_telegram.lock"))
        max_lock_wait = float(os.getenv("NAVIBOT_TELEGRAM_LOCK_WAIT_SECONDS", "15"))
        self._lock_file = open(lock_path, "w")
        deadline = time.monotonic() + max(0.0, max_lock_wait)
        while True:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                print(f"[{pid}] TelegramChannel {instance_id}: Lock acquired.")
                break
            except BlockingIOError as e:
                if time.monotonic() >= deadline:
                    self._lock_file.close()
                    self._lock_file = None
                    print(f"[{pid}] TelegramChannel {instance_id}: Failed to acquire lock (timeout).")
                    raise RuntimeError("telegram polling already active") from e
                await asyncio.sleep(0.5)
        try:
            await self.app.initialize()
            await self.app.start()
            try:
                print(f"[{pid}] TelegramChannel {instance_id}: Starting polling...")
                await self.app.updater.start_polling(drop_pending_updates=True, poll_interval=1.0)
                print(f"[{pid}] TelegramChannel {instance_id}: Polling started successfully.")
            except Conflict as e:
                print(f"[{pid}] TelegramChannel {instance_id}: Conflict detected during start_polling!")
                raise RuntimeError("telegram polling already active") from e
        except Exception:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None
            raise

    async def stop(self) -> None:
        pid = os.getpid()
        print(f"[{pid}] TelegramChannel: Stopping...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None
            print(f"[{pid}] TelegramChannel: Lock released.")


    async def send_message(self, recipient_id: str, message: str) -> None:
        await self.app.bot.send_message(chat_id=recipient_id, text=message)
