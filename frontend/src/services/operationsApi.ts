type SandboxMetricsBucket = {
  total_runs: number
  success_runs: number
  policy_violations: number
  timeouts: number
  execution_errors: number
  total_duration_ms: number
  avg_duration_ms: number
}

type SandboxMetricsResponse = {
  status: string
  metrics: Record<string, SandboxMetricsBucket>
}

type RoleWorkerDto = {
  id: string
  name: string
  description: string
  system_prompt: string
  skills: string[]
}

type RolesResponse = {
  status: string
  config_path: string
  updated_at: number
  supervisor: {
    name: string
    description: string
    system_prompt: string
  }
  workers: RoleWorkerDto[]
}

export type TechnicalPanelData = {
  metrics: Record<string, SandboxMetricsBucket>
  roles: {
    configPath: string
    updatedAt: number
    supervisorName: string
    workerCount: number
    workers: Array<{
      id: string
      name: string
      skills: string[]
    }>
  }
}

function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string) {
  return new URL(path, `${getApiBaseUrl()}/`).toString()
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(buildUrl(path), { method: 'GET' })
  if (!response.ok) {
    throw new Error(`operations_http_${response.status}`)
  }
  return (await response.json()) as T
}

export async function fetchTechnicalPanelData(): Promise<TechnicalPanelData> {
  const [metrics, roles] = await Promise.all([
    fetchJson<SandboxMetricsResponse>('/sandbox/metrics'),
    fetchJson<RolesResponse>('/roles'),
  ])
  return {
    metrics: metrics.metrics ?? {},
    roles: {
      configPath: roles.config_path,
      updatedAt: roles.updated_at,
      supervisorName: roles.supervisor?.name ?? 'Supervisor',
      workerCount: (roles.workers ?? []).length,
      workers: (roles.workers ?? []).map((w) => ({
        id: w.id,
        name: w.name,
        skills: w.skills ?? [],
      })),
    },
  }
}
