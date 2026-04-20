export type SoulResponse = {
  status: string
  soul: string
}

function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string) {
  return new URL(path, `${getApiBaseUrl()}/`).toString()
}

export async function fetchSoulPrompt(): Promise<string> {
  const response = await fetch(buildUrl('/config/soul'), { method: 'GET' })
  if (!response.ok) {
    throw new Error(`Failed to fetch soul prompt: ${response.status}`)
  }
  const data = (await response.json()) as SoulResponse
  return data.soul
}

export async function updateSoulPrompt(soul: string): Promise<string> {
  const response = await fetch(buildUrl('/config/soul'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ soul }),
  })
  if (!response.ok) {
    throw new Error(`Failed to update soul prompt: ${response.status}`)
  }
  const data = (await response.json()) as SoulResponse
  return data.soul
}
