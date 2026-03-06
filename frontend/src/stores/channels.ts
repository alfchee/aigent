import { defineStore } from 'pinia'

import { fetchJson } from '../lib/api'

export type ChannelStatus = {
  channel_id: string
  state: string
  last_heartbeat: string | null
  last_error: string | null
  started_at: string | null
  event_rate: number
}

export type ChannelSpec = {
  channel_id: string
  display_name: string
  version: string
  capabilities: string[]
  supports_polling: boolean
  supports_webhook: boolean
  settings_schema: {
    fields?: Array<{ key: string; label: string; type: string; required?: boolean }>
  }
  enabled: boolean
  settings: Record<string, any>
  status?: ChannelStatus | null
}

type ListChannelsResponse = {
  channels: ChannelSpec[]
}

type ValidateResponse = {
  channel_id: string
  valid: boolean
  errors: string[]
}

type ToggleResponse = {
  status: string
  channel_id?: string
  errors?: string[]
}

export const useChannelsStore = defineStore('channels', {
  state: () => ({
    channels: [] as ChannelSpec[],
    loading: false as boolean,
    error: null as string | null,
    validating: {} as Record<string, boolean>,
    validationErrors: {} as Record<string, string[]>,
    _eventSource: null as EventSource | null,
  }),
  actions: {
    async loadChannels() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<ListChannelsResponse>('/api/channels')
        this.channels = data.channels || []
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },
    async validateChannel(
      channelId: string,
      settings: Record<string, any>,
      checkConnection = false,
    ) {
      this.validationErrors[channelId] = []
      this.validating[channelId] = true
      try {
        const data = await fetchJson<ValidateResponse>('/api/channels/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            channel_id: channelId,
            settings,
            check_connection: checkConnection,
          }),
        })
        this.validationErrors[channelId] = data.errors || []
        return data
      } catch (e) {
        this.validationErrors[channelId] = [e instanceof Error ? e.message : String(e)]
        throw e
      } finally {
        this.validating[channelId] = false
      }
    },
    async enableChannel(channelId: string, settings: Record<string, any>) {
      const data = await fetchJson<ToggleResponse>('/api/channels/enable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: channelId, settings }),
      })
      await this.loadChannels()
      return data
    },
    async disableChannel(channelId: string) {
      const data = await fetchJson<ToggleResponse>('/api/channels/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: channelId }),
      })
      await this.loadChannels()
      return data
    },
    connectSse() {
      this.disconnectSse()
      const es = new EventSource('/api/channels/events')
      this._eventSource = es
      es.addEventListener('status', (evt) => {
        try {
          const payload = JSON.parse((evt as MessageEvent).data) as ChannelStatus
          const channel = this.channels.find((c) => c.channel_id === payload.channel_id)
          if (channel) {
            channel.status = payload
          }
        } catch (error) {
          void error
        }
      })
      es.addEventListener('heartbeat', (evt) => {
        try {
          const payload = JSON.parse((evt as MessageEvent).data) as ChannelStatus
          const channel = this.channels.find((c) => c.channel_id === payload.channel_id)
          if (channel) {
            channel.status = payload
          }
        } catch (error) {
          void error
        }
      })
      es.addEventListener('error', () => {
        this.error = 'Conexión SSE falló. Reintentando…'
      })
    },
    disconnectSse() {
      if (this._eventSource) {
        this._eventSource.close()
        this._eventSource = null
      }
    },
  },
})
