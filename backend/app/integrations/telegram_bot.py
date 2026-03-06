import os
import asyncio
import logging
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from app.core.agent import execute_agent_task  # Importamos tu cerebro existente
from app.core.filesystem import SessionWorkspace # Tu gestor de archivos
from dotenv import load_dotenv

load_dotenv()

# Configuración básica de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI_O_DESDE_ENV")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 ¡Hola! Soy NaviBot en Telegram. Envíame texto o archivos para analizar.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = str(update.effective_chat.id)
    session_id = f"tg_{chat_id}"  # Prefijo para distinguir sesiones de Telegram
    
    # 1. Indicador de "Escribiendo..." para UX
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # 2. Ejecutar el Agente (El mismo que usas en la Web)
        response_text = await execute_agent_task(user_text, session_id=session_id)
        
        # 3. Responder con texto
        # Telegram tiene límite de 4096 caracteres, cortamos si es necesario
        if len(response_text) > 4000:
            for x in range(0, len(response_text), 4000):
                await update.message.reply_text(response_text[x:x+4000])
        else:
            await update.message.reply_text(response_text)

        # 4. CHEQUEO DE ARTEFACTOS (La magia visual)
        # Verificamos si el agente generó imágenes o archivos nuevos recientemente
        await check_and_send_artifacts(chat_id, session_id, context)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error procesando tu solicitud: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la recepción de archivos (PDF, CSV, Imágenes, etc.)"""
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
    
    if not file:
        return

    # 1. Preparar el Workspace
    workspace = SessionWorkspace(session_id)
    file_path = os.path.join(workspace.root, file_name)
    
    # 2. Descargar el archivo
    await file.download_to_drive(file_path)
    
    # 3. Notificar al Agente que el archivo existe
    # Esto es clave: Inyectamos un prompt de sistema invisible
    msg = f"📥 He recibido el archivo '{file_name}'. Lo he guardado en tu workspace. Analízalo si te lo pido."
    await update.message.reply_text(msg)
    
    # Opcional: Ejecutar una tarea automática al recibir archivo
    # await execute_agent_task(f"Analiza el archivo {file_name} que acabo de subir", session_id)

async def check_and_send_artifacts(chat_id: str, session_id: str, context: ContextTypes.DEFAULT_TYPE):
    """
    Busca archivos generados recientemente (PNG, PDF, XLSX) en el workspace
    y los envía al chat.
    """
    workspace = SessionWorkspace(session_id)
    supported_extensions = ('.png', '.jpg', '.pdf', '.csv', '.xlsx')
    
    # Listar archivos en el workspace
    if not os.path.exists(workspace.root): return

    files = [f for f in os.listdir(workspace.root) if f.endswith(supported_extensions)]
    
    # Lógica simple: Enviar archivos modificados en los últimos 30 segundos
    # (Opcional: Podrías llevar un registro de qué archivos ya se enviaron)
    import time
    current_time = time.time()
    
    for f in files:
        file_path = os.path.join(workspace.root, f)
        mod_time = os.path.getmtime(file_path)
        
        # Si el archivo fue creado/modificado hace menos de 20 segundos
        if current_time - mod_time < 20:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
            with open(file_path, 'rb') as doc:
                await context.bot.send_document(chat_id=chat_id, document=doc, caption=f"📂 Generado: {f}")

# Configuración del Runner
def run_telegram_bot():
    if TELEGRAM_TOKEN == "TU_TOKEN_AQUI_O_DESDE_ENV":
        print("⚠️ Warning: TELEGRAM_TOKEN not set. Please set it in .env or update the code.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    
    print("🤖 NaviBot Telegram está escuchando...")
    app.run_polling()

if __name__ == '__main__':
    run_telegram_bot()
