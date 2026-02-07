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
