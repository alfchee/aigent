type LogLevel = 'debug' | 'info' | 'warn' | 'error'

export type LogEvent = {
  level: LogLevel
  name: string
  ts: number
  data?: Record<string, unknown>
}

export function logEvent(evt: Omit<LogEvent, 'ts'>) {
  const event: LogEvent = { ...evt, ts: Date.now() }
  if (import.meta.env.DEV) {
    const line = JSON.stringify(event)
    if (event.level === 'error') console.error(line)
    else if (event.level === 'warn') console.warn(line)
    else console.log(line)
  }
}
