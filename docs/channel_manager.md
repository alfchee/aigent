# Channel Manager

## Objetivo
El Channel Manager permite añadir, validar y monitorear canales con un flujo uniforme. Centraliza configuración, estado, validación y automatización para que incorporar un canal nuevo requiera el mínimo esfuerzo.

## Arquitectura
- Registro de canales: `ChannelRegistry` mantiene las especificaciones publicadas por cada canal.
- Contrato base: `BaseChannel` define ciclo de vida, envío y validación.
- Manager: `ChannelManager` orquesta habilitar/deshabilitar, estado y eventos.
- Persistencia: configuraciones en `app_settings` con clave `channels_config`.
- Monitoreo: SSE en `/api/channels/events` con estados y heartbeats.

## Estados estándar
`pending`, `active`, `error`, `disabled`, `starting`

## Estructura de un canal
Un canal debe exponer:
- `channel_id()`, `display_name()`, `version()`
- `supports_polling()` y/o `supports_webhook()`
- `settings_schema()`
- `validate_settings(settings, check_connection)`
- `start()`, `stop()`, `send_message()`

## Registro dinámico
La configuración `channels_config.registry_modules` permite registrar módulos externos:
```json
{
  "registry_modules": ["app.channels.discord", "app.channels.whatsapp"]
}
```
Cada módulo debe exportar `Channel` o `channel_class`.

## API estándar
- `GET /api/channels` lista especificaciones, configuración y estado.
- `POST /api/channels/validate` valida configuración.
- `POST /api/channels/enable` habilita un canal.
- `POST /api/channels/disable` deshabilita un canal.
- `GET /api/channels/events` stream SSE para monitoreo.

## UI
La vista `/channels` genera formularios desde `settings_schema().fields` y muestra estado en tiempo real.

## Automatización
Scripts en `backend/scripts`:
- `setup_channels.py` configura canales (ej. Telegram).
- `validate_channels.py` valida configuraciones.
- `healthcheck_channels.py` valida y genera salida JSON.
- `new_channel.py` crea un nuevo canal y lo registra.

## Ejemplo de creación de canal
```bash
python backend/scripts/new_channel.py discord --template polling
```
Esto genera `app/channels/discord.py` y agrega el módulo al registro.

## Validación y despliegue
1. Definir settings en `/channels`.
2. Ejecutar `python backend/scripts/validate_channels.py`.
3. Ejecutar `python backend/scripts/healthcheck_channels.py --check-connection`.
4. Habilitar el canal desde la UI o API.

## Troubleshooting
- `token requerido`: falta credencial en settings.
- `token inválido o sin conexión`: validar credenciales y conectividad.
- Estado `error`: revisar `last_error` en `/channels`.
*** End Patch}]}function apply_patch code>`

Does this patch look reasonable to you? If so, I can proceed.
