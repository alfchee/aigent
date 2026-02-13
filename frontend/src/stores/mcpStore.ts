import { defineStore } from 'pinia'
import { fetchJson } from '../lib/api'

export interface McpServer {
  id: string
  name: string
  type: string
  enabled: boolean
  params: Record<string, any>
  env_vars: Record<string, string>
  status: string
}

export interface McpMarketplaceItem {
  name: string
  description: string
  command: string
  args: string[]
  params?: string[]
  env_vars?: string[]
}

export const useMcpStore = defineStore('mcp', {
  state: () => ({
    servers: [] as McpServer[],
    marketplace: {} as Record<string, McpMarketplaceItem>,
    loading: false,
    error: null as string | null
  }),

  actions: {
    async fetchServers() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson('/api/mcp/servers')
        this.servers = data
      } catch (e: any) {
        this.error = e.message || 'Error fetching servers'
      } finally {
        this.loading = false
      }
    },

    async fetchMarketplace() {
      try {
        const data = await fetchJson('/api/mcp/marketplace')
        this.marketplace = data
      } catch (e: any) {
        console.error('Error fetching marketplace:', e)
      }
    },

    async saveServer(server: Partial<McpServer>) {
      this.loading = true
      try {
        await fetchJson('/api/mcp/servers', {
          method: 'POST',
          body: JSON.stringify(server)
        })
        await this.fetchServers()
      } catch (e: any) {
        this.error = e.message || 'Error saving server'
        throw e
      } finally {
        this.loading = false
      }
    },

    async deleteServer(serverId: string) {
      this.loading = true
      try {
        await fetchJson(`/api/mcp/servers/${serverId}`, {
          method: 'DELETE'
        })
        await this.fetchServers()
      } catch (e: any) {
        this.error = e.message || 'Error deleting server'
        throw e
      } finally {
        this.loading = false
      }
    },

    async testConnection(serverId: string, params: any, envVars: any) {
      try {
        return await fetchJson('/api/mcp/test-connection', {
          method: 'POST',
          body: JSON.stringify({
            server_id: serverId,
            params: params,
            env_vars: envVars
          })
        })
      } catch (e: any) {
        return { success: false, message: e.message }
      }
    }
  }
})
