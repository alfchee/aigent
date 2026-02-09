export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function parseJsonSafely(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return (await res.json()) as T
}

export async function fetchText(input: RequestInfo | URL, init?: RequestInit): Promise<string> {
  const res = await fetch(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return await res.text()
}

export async function fetchBlob(input: RequestInfo | URL, init?: RequestInit): Promise<Blob> {
  const res = await fetch(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return await res.blob()
}
