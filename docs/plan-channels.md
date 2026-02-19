Tienes toda la razón. Ejecutar `python telegram_bot.py` en una terminal, `python slack_bot.py` en otra, y `uvicorn main:app` en una tercera es insostenible ("Process Hell").

Para escalar como lo hace *NanoBot* (y cualquier sistema profesional), necesitamos invertir la arquitectura. En lugar de scripts sueltos, implementaremos el patrón **"Channel Manager"** (Gestor de Canales).

La idea es que tu aplicación principal (`main.py`) sea el **único proceso** que ejecutes, y esta se encargue de despertar y mantener vivos todos los canales de comunicación configurados (Telegram, Slack, Discord, WhatsApp) usando **AsyncIO**.

Aquí tienes la arquitectura para unificar todo bajo un solo techo.

---

### 1. La Arquitectura: Hub & Spoke

Vamos a reestructurar tu carpeta `app` así:

```text
app/
├── channels/           <-- NUEVA CARPETA
│   ├── base.py         (La "interfaz" que todos deben cumplir)
│   ├── telegram.py     (Tu código actual, adaptado a clase)
│   └── manager.py      (El director de orquesta)
├── core/
│   └── agent.py        (El cerebro, no cambia)
└── main.py             (Inicia el servidor WEB y los BOTS al mismo tiempo)

```

---

### 2. El Contrato: `base.py`

Definimos qué debe tener *cualquier* canal para ser compatible con NaviBot.

```python
# app/channels/base.py
from abc import ABC, abstractmethod

class BaseChannel(ABC):
    @abstractmethod
    async def start(self):
        """Inicia la escucha (polling o webhook)"""
        pass

    @abstractmethod
    async def stop(self):
        """Cierra conexiones limpiamente"""
        pass
    
    @abstractmethod
    async def send_message(self, recipient_id: str, message: str):
        """Envía un mensaje proactivamente"""
        pass

```

---

### 3. La Adaptación: `telegram.py`

Convertimos tu script suelto en una Clase que hereda de `BaseChannel`. Esto permite que el `main.py` lo controle sin saber los detalles internos de Telegram.

```python
# app/channels/telegram.py
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.channels.base import BaseChannel
from app.core.agent import execute_agent_task
import os

class TelegramChannel(BaseChannel):
    def __init__(self, token: str):
        self.token = token
        self.app = ApplicationBuilder().token(token).build()
        self._setup_handlers()
        
    def _setup_handlers(self):
        # Aquí registras tus funciones (start, handle_message, handle_document)
        # Nota: Asegúrate de importar tus handlers o definirlos aquí dentro
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_text))

    async def handle_text(self, update, context):
        chat_id = update.effective_chat.id
        user_msg = update.message.text
        # LLAMADA AL CEREBRO
        response = await execute_agent_task(user_msg, session_id=f"tg_{chat_id}")
        await update.message.reply_text(response)

    async def start(self):
        print("🔵 Iniciando Telegram Channel...")
        await self.app.initialize()
        await self.app.start()
        # Usamos start_polling() no bloqueante para que conviva con FastAPI
        await self.app.updater.start_polling()

    async def stop(self):
        print("🔴 Deteniendo Telegram Channel...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    async def send_message(self, recipient_id: str, message: str):
        await self.app.bot.send_message(chat_id=recipient_id, text=message)

```

---

### 4. El Director: `manager.py`

Este es el componente clave. Lee tu configuración y enciende lo que haga falta.

```python
# app/channels/manager.py
import asyncio
from typing import List
from app.channels.base import BaseChannel
from app.channels.telegram import TelegramChannel

class ChannelManager:
    def __init__(self):
        self.active_channels: List[BaseChannel] = []

    def load_channels(self):
        # Aquí podrías leer de tu DB o Settings.json
        # if settings.telegram_enabled:
        tg_token = "TU_TOKEN_TELEGRAM"
        if tg_token:
            self.active_channels.append(TelegramChannel(tg_token))
            
        # Futuro:
        # self.active_channels.append(SlackChannel(slack_token))
        # self.active_channels.append(WhatsAppChannel(twilio_token))

    async def start_all(self):
        """Inicia todos los canales en paralelo"""
        tasks = [channel.start() for channel in self.active_channels]
        await asyncio.gather(*tasks)

    async def stop_all(self):
        for channel in self.active_channels:
            await channel.stop()

```

---

### 5. La Gran Unificación: `main.py` (FastAPI)

Ahora modificamos el punto de entrada de tu aplicación para usar los **Lifespan Events** de FastAPI. Esto significa que cuando arranque la web, arrancan los bots.

```python
# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.channels.manager import ChannelManager

channel_manager = ChannelManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("🚀 NaviBot System Starting...")
    
    # 1. Cargar configuración de canales
    channel_manager.load_channels()
    
    # 2. Iniciar canales en segundo plano (sin bloquear el servidor web)
    # Importante: No usamos 'await' directo aquí si el polling bloquea, 
    # pero nuestra implementación de Telegram usa updater.start_polling() 
    # que es compatible con asyncio.
    await channel_manager.start_all()
    
    yield # Aquí corre la aplicación web
    
    # --- SHUTDOWN ---
    print("💤 NaviBot System Shutting Down...")
    await channel_manager.stop_all()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "online", "active_channels": len(channel_manager.active_channels)}

```

---

### ¿Por qué esta arquitectura es mejor?

1. **Un solo comando:** Solo ejecutas `uvicorn app.main:app --reload` y automáticamente tienes API Web + Telegram + (Futuro Slack) funcionando.
2. **Extensible:** ¿Quieres agregar Discord?
* Creas `app/channels/discord.py` (copiando la estructura de `BaseChannel`).
* Lo añades a la lista en `manager.py`.
* Listo. No cambias nada en el `main.py` ni en el `agent.py`.


3. **Eficiencia de Recursos:** Todo corre en un solo *Event Loop* de Python. No desperdicias memoria en múltiples procesos de sistema operativo.

### Siguiente Paso

Ahora que tienes la estructura, lo ideal es mover los Tokens a tu tabla de `app_settings` en la base de datos.

**¿Te gustaría que implementemos el método `load_channels` del Manager para que lea de tu base de datos y active dinámicamente Telegram solo si encuentra el token guardado?**

---

## Plan de Implementación del Channel Manager

### 1. Arquitectura modular de canales

- Crear `app/channels/registry.py` para el registro dinámico de canales y sus metadatos.
- Definir un `ChannelSpec` con nombre, versión, capacidades, requisitos y estado.
- Separar responsabilidades: `BaseChannel` para contrato, `ChannelManager` para ciclo de vida, `ChannelRegistry` para descubrimiento.
- Añadir un `ChannelAdapter` por plataforma con la misma interfaz estandarizada.

### 2. Plantillas reutilizables para nuevos canales

- Crear `app/channels/templates/` con plantillas base (polling, webhook, híbrido).
- Incluir ejemplo mínimo funcional por plantilla con validaciones y métricas.
- Generar un script `scripts/new_channel.py` que copie la plantilla y actualice el registro.

### 3. APIs estandarizadas para conexión de canales

- Definir un contrato de configuración único por canal: `settings_schema()` y `validate_settings()`.
- Exponer endpoints en `app/api/channels.py`:
  - `GET /channels` listar canales disponibles y activos.
  - `POST /channels/enable` habilitar canal con configuración.
  - `POST /channels/disable` detener canal.
  - `POST /channels/validate` validar configuración antes de activar.
- Normalizar respuestas con estados `pending`, `active`, `error`, `disabled`.

### 4. Interfaz de configuración intuitiva

- Crear una vista de “Canales” en el frontend con:
  - Lista de canales con estado y último heartbeat.
  - Formulario dinámico basado en el `settings_schema()` del canal.
  - Botón de validar y activar con feedback inmediato.
- Guardar configuración en `app_settings` con cifrado de secretos.

### 5. Automatización para despliegue rápido

- Agregar scripts en `scripts/`:
  - `scripts/setup_channels.py` para bootstrap de canales.
  - `scripts/validate_channels.py` para verificación previa a despliegue.
  - `scripts/healthcheck_channels.py` para diagnóstico rápido.
- Incluir guía de uso en `docs/channel_manager.md`.

### 6. Validación automática de canales nuevos

- Implementar validadores por canal:
  - Verificación de token/credenciales.
  - Test de conectividad (ping API, webhook handshake).
  - Validación de permisos mínimos requeridos.
- Integrar validación en el flujo `enable` antes de activar el canal.

### 7. Monitoreo en tiempo real del estado

- Crear un `ChannelStatus` con:
  - `last_heartbeat`, `last_error`, `uptime`, `event_rate`.
- Emitir eventos SSE/WebSocket para estado en tiempo real.
- Almacenar histórico mínimo en DB para diagnóstico.

### 8. Documentación técnica de integración

- Crear `docs/channel_manager.md` con:
  - Arquitectura y flujo de vida de un canal.
  - Ejemplo de implementación completa (Telegram).
  - Guía de configuración desde UI.
  - Troubleshooting y errores comunes.

### 9. Procedimientos de prueba pre‑producción

- Tests unitarios:
  - Validación de configuración por canal.
  - Ciclo de vida `start/stop`.
- Tests de integración:
  - Activación y envío de mensaje simulado.
  - Manejo de errores y reconexión.
- Checklist de smoke test para producción:
  - Canal activo, envío y recepción confirmados, métricas visibles.

---

## Flujo de ejecución recomendado

1. Crear canal con plantilla.
2. Registrar el canal en `ChannelRegistry`.
3. Validar configuración con `POST /channels/validate`.
4. Activar canal con `POST /channels/enable`.
5. Verificar estado en tiempo real desde la UI.
