/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL?: string
  readonly VITE_WS_BASE_PATH?: string
  readonly VITE_ENABLE_MOCK_WS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
