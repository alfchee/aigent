/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_WS_URL?: string
  readonly VITE_WS_BASE_PATH?: string
  readonly VITE_ENABLE_MOCK_WS?: string
  /** Set to 'true' to require an API key in the browser (matches AIGENT_API_KEY on the server) */
  readonly VITE_AUTH_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
