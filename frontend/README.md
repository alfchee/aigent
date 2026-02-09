# Frontend (NaviBot)

## Requisitos
- Node.js 18+
- Backend corriendo en `http://localhost:8231` (en dev, Vite proxea `/api` a ese host)

## Desarrollo
```bash
npm install
npm run dev
```

## Panel de Artefactos
- La UI genera y persiste un `session_id` en `localStorage` (`navibot_session_id`).
- El chat envía `session_id` al backend en `POST /api/chat`.
- El panel de artefactos escucha SSE en `GET /api/artifacts/events?session_id=...`.

## Endpoints usados
- Chat: `POST /api/chat`
- Artefactos:
  - Listado: `GET /api/files/{session_id}`
  - Lectura/preview/descarga: `GET /api/files/{session_id}/{path}` (usar `?download=true` para descargar)
  - Upload: `POST /api/upload` (multipart/form-data con `session_id` + `file`)
  - SSE: `GET /api/artifacts/events?session_id=...`

## Preview y límites
- Archivos > 10MB: se deshabilita la preview completa para evitar degradación; se recomienda descarga.
- HTML: se renderiza en `iframe` con `sandbox` estricto (sin scripts) para mitigar XSS.

## Guía de estilo UI
### Bloques de herramientas (Tool Call / Tool Result)
- Los bloques de herramientas deben usar el mismo contenedor base y tipografía monoespaciada.
- `tool_call` y `tool_result` comparten estructura, colores y espaciado para consistencia visual.
- El bloque `tool_result` usa la etiqueta “Resultado del Agente” y un icono distintivo.
- Ambos bloques se renderizan colapsados por defecto con transición suave al expandir.
- Los resultados deben soportar contenido de texto, código y tablas sin perder formato.

### Accesibilidad y responsividad
- Los modales y bloques colapsables deben ser navegables con teclado y legibles en móvil.
- Evitar anchos fijos; preferir `w-full`, `max-w` y `overflow-x-auto`.

## Tests
Unit + integración SSE (mock EventSource):
```bash
npm test
```

E2E (Playwright):
```bash
npm run e2e
```

## Storybook
```bash
npm run storybook
```
