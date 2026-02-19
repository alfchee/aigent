export type SidebarState = 'collapsed' | 'normal'

export function sidebarWidthPx(state: SidebarState): number {
  if (state === 'collapsed') return 50
  return 250
}

export function normalizeSidebarState(
  value: unknown,
  fallback: SidebarState = 'normal',
): SidebarState {
  if (value === 'collapsed' || value === 'normal') return value as SidebarState
  return fallback
}

export function nextSidebarState(state: SidebarState): SidebarState {
  return state === 'collapsed' ? 'normal' : 'collapsed'
}

export function isCollapsed(state: SidebarState): boolean {
  return state === 'collapsed'
}
