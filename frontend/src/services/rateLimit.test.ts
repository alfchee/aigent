import { describe, expect, it, vi } from 'vitest'
import { createRateLimiter } from './rateLimit'

describe('createRateLimiter', () => {
  it('permite hasta N eventos en la ventana', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'))

    const rl = createRateLimiter({ windowMs: 1000, max: 2 })
    expect(rl.canSend()).toBe(true)
    rl.recordSend()
    expect(rl.canSend()).toBe(true)
    rl.recordSend()
    expect(rl.canSend()).toBe(false)

    vi.advanceTimersByTime(1100)
    expect(rl.canSend()).toBe(true)
    vi.useRealTimers()
  })
})
