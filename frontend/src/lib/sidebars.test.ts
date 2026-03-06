import { describe, expect, it } from 'vitest'

import { isCollapsed, nextSidebarState, normalizeSidebarState, sidebarWidthPx } from './sidebars'

describe('sidebars', () => {
  it('maps width correctly', () => {
    expect(sidebarWidthPx('collapsed')).toBe(50)
    expect(sidebarWidthPx('normal')).toBe(250)
  })

  it('cycles states', () => {
    expect(nextSidebarState('collapsed')).toBe('normal')
    expect(nextSidebarState('normal')).toBe('collapsed')
  })

  it('normalizes state values', () => {
    expect(normalizeSidebarState('collapsed')).toBe('collapsed')
    expect(normalizeSidebarState('nope')).toBe('normal')
    expect(normalizeSidebarState('nope', 'normal')).toBe('normal')
  })

  it('detects collapsed state', () => {
    expect(isCollapsed('collapsed')).toBe(true)
    expect(isCollapsed('normal')).toBe(false)
  })
})
