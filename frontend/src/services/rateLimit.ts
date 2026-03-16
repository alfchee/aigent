export type RateLimiter = {
  canSend: () => boolean
  recordSend: () => void
  reset: () => void
}

export function createRateLimiter(opts: { windowMs: number; max: number }): RateLimiter {
  let events: number[] = []

  const prune = () => {
    const now = Date.now()
    events = events.filter((t) => now - t < opts.windowMs)
  }

  return {
    canSend() {
      prune()
      return events.length < opts.max
    },
    recordSend() {
      prune()
      events.push(Date.now())
    },
    reset() {
      events = []
    },
  }
}
