import { describe, expect, it } from 'vitest'
import { sanitizeText } from './sanitize'

describe('sanitizeText', () => {
  it('elimina HTML y atributos', () => {
    const out = sanitizeText('<img src=x onerror=alert(1) />hola<b>!</b>')
    expect(out).toBe('hola!')
  })
})
