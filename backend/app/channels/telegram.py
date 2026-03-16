import os
import logging
from typing import Optional
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logger = logging.getLogger("navibot.channels.telegram")

class TelegramBot:
    """
    Advanced Telegram Bot Integration.
    Supports:
    - Text messaging
    - Typing indicators (ChatAction)
    - Media handling (Photos/Docs -> Sandbox/MarkItDown)
    """
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.app = None
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not found. Bot will not start.")
            return

        self.app = ApplicationBuilder().token(self.token).build()
        self._register_handlers()

    def _register_handlers(self):
        # Commands
        self.app.add_handler(CommandHandler("start", self.start))
        
        # Messages
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_text))
        self.app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, self.handle_media))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I am NaviBot 2.0 (Phoenix). How can I help you today?")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text
        
        # Send typing action
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
        
        # TODO: Route to AgentGraph
        # response = await graph.invoke(text, session_id=str(chat_id))
        
        # Placeholder response
        await update.message.reply_text(f"Received: {text}")

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        # Indicate file processing
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.UPLOAD_DOCUMENT)
        
        file = None
        if update.message.document:
            file = await update.message.document.get_file()
        elif update.message.photo:
            file = await update.message.photo[-1].get_file() # Get highest resolution
            
        if file:
            # Download file to workspace/sessions/{chat_id}/downloads
            # path = ...
            # await file.download_to_drive(path)
            
            await update.message.reply_text("File received. Processing...")
        else:
            await update.message.reply_text("Could not process file.")

    def run_polling(self):
        """Start bot in polling mode (dev)."""
        if self.app:
            logger.info("Starting Telegram Bot (Polling)...")
            self.app.run_polling()

    async def initialize(self):
        """Initialize for webhook mode (prod) or manual polling control."""
        if self.app:
            await self.app.initialize()
            await self.app.start()

    async def shutdown(self):
        if self.app:
            await self.app.stop()
            await self.app.shutdown()

# Singleton
telegram_bot = TelegramBot()
