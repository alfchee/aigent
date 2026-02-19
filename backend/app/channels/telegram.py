import asyncio
import fcntl
import logging
import os
import time
from typing import Any

from telegram import Update
from telegram.error import Conflict, BadRequest, Forbidden, TelegramError
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from app.channels.base import BaseChannel
from app.core.agent import execute_agent_task
from app.core.filesystem import SessionWorkspace


logger = logging.getLogger("navibot.telegram")

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
        self._queue_maxsize = int(os.getenv("NAVIBOT_TELEGRAM_QUEUE_SIZE", "100"))
        self._task_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._worker_task: asyncio.Task | None = None
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
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else chat_id
        session_id = f"tg_{chat_id}"
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._task_worker())
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        payload = {
            "chat_id": chat_id,
            "user_text": user_text,
            "session_id": session_id,
            "user_id": user_id,
            "context": context,
        }
        try:
            self._task_queue.put_nowait(payload)
        except asyncio.QueueFull:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Cola de tareas llena. Intenta nuevamente en unos segundos.")

    async def _task_worker(self):
        while True:
            payload = await self._task_queue.get()
            if payload is None:
                self._task_queue.task_done()
                break
            await self._process_message_background(
                payload["chat_id"],
                payload["user_text"],
                payload["session_id"],
                payload["user_id"],
                payload["context"],
            )
            self._task_queue.task_done()

    async def _process_message_background(self, chat_id, user_text, session_id, user_id, context):
        start_ts = time.time()
        chat_id_int = chat_id
        user_id_int = user_id
        try:
            try:
                chat_id_int = int(chat_id)
            except Exception:
                pass
            try:
                user_id_int = int(user_id)
            except Exception:
                pass

            logger.info(
                "telegram_request_start",
                extra={
                    "chat_id": chat_id_int,
                    "user_id": user_id_int,
                    "session_id": session_id,
                    "text_len": len(user_text or ""),
                },
            )

            try:
                await context.bot.send_chat_action(chat_id=chat_id_int, action="typing")
            except Exception:
                pass

            response_text = await execute_agent_task(
                user_text,
                session_id=session_id,
                memory_user_id=f"tg_user_{user_id_int}",
            )
            if not response_text:
                logger.warning(
                    "telegram_agent_empty_response",
                    extra={"chat_id": chat_id_int, "session_id": session_id},
                )
                response_text = "✅ Tarea completada (sin respuesta de texto)."

            logger.info(
                "telegram_agent_response",
                extra={
                    "chat_id": chat_id_int,
                    "session_id": session_id,
                    "response_len": len(response_text),
                    "snippet": response_text[:120],
                },
            )

            # DEBUG: Log before attempting to send response
            logger.info(
                "telegram_about_to_send_response",
                extra={
                    "chat_id": chat_id_int,
                    "session_id": session_id,
                    "has_response": bool(response_text),
                },
            )

            async def send_text_once(target_id: int | str) -> None:
                # Truncate very long messages to avoid Telegram timeouts
                max_length = 4000
                if len(response_text) > max_length:
                    logger.info(
                        "telegram_response_truncated",
                        extra={
                            "chat_id": target_id,
                            "original_length": len(response_text),
                            "truncated_to": max_length,
                        },
                    )
                    truncated = response_text[:max_length] + f"\n\n[... Respuesta truncada ({len(response_text)} chars)]"
                    for x in range(0, len(truncated), 4000):
                        await context.bot.send_message(
                            chat_id=target_id, text=truncated[x : x + 4000]
                        )
                else:
                    await context.bot.send_message(chat_id=target_id, text=response_text)

            async def send_text_with_retry(target_id: int | str, max_retries: int = 3) -> None:
                delay = 1.0
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        logger.info(
                            "telegram_send_attempt",
                            extra={
                                "chat_id": target_id,
                                "session_id": session_id,
                                "attempt": attempt,
                            },
                        )
                        await send_text_once(target_id)
                        logger.info(
                            "telegram_send_success",
                            extra={
                                "chat_id": target_id,
                                "session_id": session_id,
                                "attempt": attempt,
                            },
                        )
                        return
                    except (BadRequest, Forbidden) as e:
                        # Let outer logic decide how to handle these
                        logger.warning(
                            "telegram_send_auth_error",
                            extra={
                                "chat_id": target_id,
                                "session_id": session_id,
                                "attempt": attempt,
                                "error": str(e),
                            },
                        )
                        raise
                    except TelegramError as e:
                        logger.warning(
                            "telegram_send_retry",
                            extra={
                                "chat_id": target_id,
                                "session_id": session_id,
                                "attempt": attempt,
                                "delay": delay,
                                "error": str(e),
                            },
                        )
                        if attempt >= max_retries:
                            logger.error(
                                "telegram_send_all_retries_failed",
                                extra={
                                    "chat_id": target_id,
                                    "session_id": session_id,
                                    "max_retries": max_retries,
                                    "last_error": str(e),
                                },
                            )
                            raise
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 8.0)

            try:
                await send_text_with_retry(chat_id_int)
                
                # Log successful delivery
                logger.info(
                    "telegram_response_delivered",
                    extra={
                        "chat_id": chat_id_int,
                        "session_id": session_id,
                    },
                )
                
            except BadRequest as e:
                logger.error(
                    "telegram_delivery_badrequest",
                    extra={
                        "chat_id": chat_id_int,
                        "user_id": user_id_int,
                        "session_id": session_id,
                        "error": str(e),
                    },
                )
                if "Chat not found" in str(e) and user_id_int != chat_id_int:
                    logger.warning(
                        "telegram_chat_not_found_fallback",
                        extra={
                            "chat_id": chat_id_int,
                            "user_id": user_id_int,
                            "session_id": session_id,
                        },
                    )
                    try:
                        await send_text_with_retry(user_id_int)
                    except Exception as fallback_error:
                        logger.error(
                            "telegram_fallback_send_failed",
                            extra={
                                "chat_id": chat_id_int,
                                "user_id": user_id_int,
                                "session_id": session_id,
                                "error": str(fallback_error),
                            },
                        )
                else:
                    raise
            except Forbidden as e:
                logger.error(
                    "telegram_delivery_forbidden",
                    extra={
                        "chat_id": chat_id_int,
                        "user_id": user_id_int,
                        "session_id": session_id,
                        "error": str(e),
                    },
                )
            except Exception as e:
                # Catch-all for any other errors during send
                logger.error(
                    "telegram_send_catchall_error",
                    exc_info=True,
                    extra={
                        "chat_id": chat_id_int,
                        "session_id": session_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

            if self.auto_send_artifacts:
                await self.check_and_send_artifacts(str(chat_id_int), session_id, context)
            await self._heartbeat()

            duration = time.time() - start_ts
            logger.info(
                "telegram_request_complete",
                extra={
                    "chat_id": chat_id_int,
                    "user_id": user_id_int,
                    "session_id": session_id,
                    "duration_seconds": round(duration, 3),
                },
            )
        except (BadRequest, Forbidden) as e:
            logger.warning(
                "telegram_delivery_error",
                extra={
                    "chat_id": chat_id_int,
                    "user_id": user_id_int,
                    "session_id": session_id,
                    "error": str(e),
                },
            )
        except Exception as e:
            logger.error(
                "telegram_unexpected_error",
                exc_info=True,
                extra={
                    "chat_id": chat_id_int,
                    "user_id": user_id_int,
                    "session_id": session_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            try:
                await context.bot.send_message(chat_id=chat_id_int, text=f"⚠️ Error: {str(e)}")
            except Exception as notify_error:
                logger.error(
                    "telegram_error_notification_failed",
                    extra={
                        "chat_id": chat_id_int,
                        "error": str(notify_error),
                    },
                )

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
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._task_worker())
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
        if self._worker_task and not self._worker_task.done():
            while self._task_queue.full():
                await asyncio.sleep(0)
            await self._task_queue.put(None)
            await self._worker_task
            self._worker_task = None
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
