import mitt from 'mitt'

export type ArtifactEvent = {
  session_id: string
  op: 'write' | 'update' | 'upload'
  path?: string
  meta?: Record<string, unknown>
}

export type ToastEvent = {
  id: string
  message: string
}

export type Events = {
  'artifact:event': ArtifactEvent
  'toast:push': ToastEvent
}

export const bus = mitt<Events>()
