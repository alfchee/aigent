import { afterEach, vi } from 'vitest'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => {
    return {
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }
  },
})

class MockEventSource {
  url: string
  listeners: Record<string, ((evt: MessageEvent) => void)[]> = {}
  readyState = 1

  constructor(url: string) {
    this.url = url
  }

  addEventListener(type: string, cb: any) {
    this.listeners[type] = this.listeners[type] || []
    this.listeners[type].push(cb)
  }

  close() {
    this.readyState = 2
  }

  emit(type: string, data: any) {
    const evt = { data: typeof data === 'string' ? data : JSON.stringify(data) } as MessageEvent
    for (const cb of this.listeners[type] || []) cb(evt)
  }
}

Object.defineProperty(window, 'EventSource', { value: MockEventSource })

afterEach(() => {
  vi.restoreAllMocks()
})
