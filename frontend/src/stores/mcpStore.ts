import { defineStore } from 'pinia'
import { fetchJson } from '../lib/api'

export interface McpServer {
  id: string
  name: string
  description?: string
  type: string
  enabled: boolean
  params: Record<string, any>
  env_vars: Record<string, string>
  status: string
  server_id?: string
}

export interface McpMarketplaceItem {
  name: string
  description: string
  command: string
  args: string[]
  params?: string[]
  env_vars?: string[]
  source?: string
}

export interface McpConnectionResult {
  success: boolean
  message: string
  tools_count?: number
}

export interface McpServerDefinition {
  server_id: string
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
    error: null as string | null,
  }),

  actions: {
    async fetchServers() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<McpServer[]>('/api/mcp/servers')
        this.servers = data
      } catch (e: any) {
        this.error = e.message || 'Error fetching servers'
      } finally {
        this.loading = false
      }
    },

    async fetchMarketplace() {
      try {
        const data = await fetchJson<Record<string, McpMarketplaceItem>>('/api/mcp/marketplace')
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
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(server),
        })
        await this.fetchServers()
      } catch (e: any) {
        this.error = e.message || 'Error saving server'
        throw e
      } finally {
        this.loading = false
      }
    },

    async importMarketplace(sourceUrl: string) {
      this.loading = true
      try {
        await fetchJson('/api/mcp/marketplace/import', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ source_url: sourceUrl }),
        })
        await this.fetchMarketplace()
      } catch (e: any) {
        this.error = e.message || 'Error importing marketplace'
        throw e
      } finally {
        this.loading = false
      }
    },

    async deleteCustomDefinition(serverId: string) {
      this.loading = true
      try {
        await fetchJson(`/api/mcp/marketplace/custom/${serverId}`, {
          method: 'DELETE',
        })
        await this.fetchMarketplace()
      } catch (e: any) {
        this.error = e.message || 'Error deleting definition'
        throw e
      } finally {
        this.loading = false
      }
    },

    async deleteServer(serverId: string) {
      this.loading = true
      try {
        await fetchJson(`/api/mcp/servers/${serverId}`, {
          method: 'DELETE',
        })
        await this.fetchServers()
      } catch (e: any) {
        this.error = e.message || 'Error deleting server'
        throw e
      } finally {
        this.loading = false
      }
    },

    async testConnection(
      serverId: string,
      params: any,
      envVars: any,
      definition?: McpServerDefinition,
    ): Promise<McpConnectionResult> {
      try {
        return await fetchJson<McpConnectionResult>('/api/mcp/test-connection', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            server_id: serverId,
            params: params,
            env_vars: envVars,
            definition,
          }),
        })
      } catch (e: any) {
        return { success: false, message: e.message }
      }
    },
  },
})
