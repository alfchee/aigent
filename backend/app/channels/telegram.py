import os
import logging
from typing import Optional
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from app.core.agent_graph import graph_app
from app.core.llm import default_llm
from app.memory.controller import MemoryController
from app.sandbox.e2b_sandbox import default_sandbox
from app.core.content_processor import content_processor

logger = logging.getLogger("navibot.channels.telegram")

class TelegramBot:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.app = None
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not found. Bot will not start.")
            return

        self.app = ApplicationBuilder().token(self.token).build()
        self._initialized = False
        self._register_handlers()

    def _register_handlers(self):
        # Commands
        self.app.add_handler(CommandHandler("start", self.start))
        
        # Messages
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_text))
        self.app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, self.handle_media))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I am NaviBot 2.0 (Phoenix). How can I help you today?")

    def _extract_code(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("/python"):
            return stripped.replace("/python", "", 1).strip()
        return ""

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text or ""
        session_id = str(chat_id)

        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

        memory = MemoryController(user_id=session_id)
        memory.add_fact(text, path="facts/telegram_messages.md")

        code = self._extract_code(text)
        if code:
            await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
            execution = await default_sandbox.execute_code(code=code, timeout=15, session_id=session_id, role_id="coder")
            output = (
                f"Resultado:\n\nSTDOUT:\n{execution.stdout or '(vacío)'}\n\n"
                f"STDERR:\n{execution.stderr or '(vacío)'}"
            )
            if execution.error:
                output += f"\n\nERROR: {execution.error}"
            await update.message.reply_text(output[:3500])
            return

        semantic_context = memory.retrieve_context(text)
        prompt_text = text if not semantic_context else f"{semantic_context}\n\nUser input:\n{text}"

        try:
            response_text = await graph_app.run_turn(user_text=prompt_text, user_id=session_id, session_id=session_id)
        except Exception:
            response = await default_llm.generate(messages=[{"role": "user", "content": prompt_text}])
            response_text = response.choices[0].message.content or "No response available."

        await update.message.reply_text(response_text[:3500])

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.UPLOAD_DOCUMENT)

        file = None
        file_name = "unknown"
        if update.message.document:
            file_name = update.message.document.file_name or "document"
            file = await update.message.document.get_file()
        elif update.message.photo:
            file_name = f"photo_{update.message.photo[-1].file_unique_id}.jpg"
            file = await update.message.photo[-1].get_file()

        if file:
            session_path = f"workspace/sessions/{chat_id}/downloads"
            os.makedirs(session_path, exist_ok=True)
            target_path = os.path.join(session_path, file_name)
            await file.download_to_drive(custom_path=target_path)
            memory = MemoryController(user_id=str(chat_id))
            memory.add_fact(
                f"Archivo recibido: {file_name} en {target_path}",
                path="facts/telegram_files.md",
            )
            extracted_text, processing_error = await content_processor.extract_text(target_path)
            if extracted_text:
                memory.add_fact(
                    f"Contenido extraído ({file_name}):\n{extracted_text[:6000]}",
                    path="facts/telegram_file_contents.md",
                )
                prompt = (
                    "Resume en español el siguiente contenido extraído de un archivo enviado por Telegram:\n\n"
                    f"{extracted_text[:10000]}"
                )
                try:
                    summary = await graph_app.run_turn(
                        user_text=prompt,
                        user_id=str(chat_id),
                        session_id=str(chat_id),
                    )
                except Exception:
                    fallback = await default_llm.generate(messages=[{"role": "user", "content": prompt}])
                    summary = fallback.choices[0].message.content or "No fue posible resumir el contenido."
                await update.message.reply_text(f"Archivo procesado: {file_name}\n\nResumen:\n{summary[:3000]}")
                return
            if processing_error:
                await update.message.reply_text(
                    f"Archivo guardado: {file_name}. No se pudo extraer contenido ({processing_error})."
                )
                return
            await update.message.reply_text(f"Archivo recibido y guardado: {file_name}")
        else:
            await update.message.reply_text("Could not process file.")

    def run_polling(self):
        """Start bot in polling mode (dev)."""
        if self.app:
            logger.info("Starting Telegram Bot (Polling)...")
            self.app.run_polling()

    async def initialize(self):
        if self.app:
            if self._initialized:
                return
            await self.app.initialize()
            await self.app.start()
            self._initialized = True

    async def process_webhook_update(self, payload: dict) -> bool:
        if not self.app:
            return False
        await self.initialize()
        update = Update.de_json(payload, self.app.bot)
        await self.app.process_update(update)
        return True

    async def shutdown(self):
        if self.app:
            if not self._initialized:
                return
            await self.app.stop()
            await self.app.shutdown()
            self._initialized = False

# Singleton
telegram_bot = TelegramBot()
