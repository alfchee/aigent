import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { initPinia } from '../../test/utils'
import { useArtifactsStore } from '../../stores/artifacts'
import { useChatStore } from '../../stores/chat'
import { useSessionsStore } from '../../stores/sessions'
import ArtifactPanel from './ArtifactPanel.vue'

describe('ArtifactPanel', () => {
  it('renders unread badge when unreadCount > 0', async () => {
    localStorage.clear()
    const pinia = initPinia()
    const store = useArtifactsStore()
    const chat = useChatStore()
    const sessions = useSessionsStore()

    store.connectSse = () => {}
    store.disconnectSse = () => {}
    store.fetchArtifacts = async () => {}
    chat.loadSessionHistory = async () => {}
    sessions.createSession = async () => 's1' as any
    store.unreadCount = 2
    store.sessionId = 's1'

    const wrapper = mount(ArtifactPanel, {
      global: { plugins: [pinia] }
    })

    expect(wrapper.text()).toContain('2 nuevo(s)')
  })

  it('prevents both sidebars from being collapsed on load', async () => {
    localStorage.clear()
    localStorage.setItem('navibot_sidebar_sessions_state', 'collapsed')
    localStorage.setItem('navibot_sidebar_artifacts_state', 'collapsed')

    const pinia = initPinia()
    const store = useArtifactsStore()
    const chat = useChatStore()
    const sessions = useSessionsStore()

    store.connectSse = () => {}
    store.disconnectSse = () => {}
    store.fetchArtifacts = async () => {}
    chat.loadSessionHistory = async () => {}
    sessions.createSession = async () => 's1' as any

    mount(ArtifactPanel, { global: { plugins: [pinia] } })
    expect(localStorage.getItem('navibot_sidebar_artifacts_state')).toBe('normal')
  })

  it('renders stacked layout when matchMedia matches', async () => {
    localStorage.clear()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => {
        return {
          matches: query.includes('max-width: 900px'),
          media: query,
          onchange: null,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          dispatchEvent: () => true
        }
      }
    })

    const pinia = initPinia()
    const store = useArtifactsStore()
    const chat = useChatStore()
    const sessions = useSessionsStore()

    store.connectSse = () => {}
    store.disconnectSse = () => {}
    store.fetchArtifacts = async () => {}
    chat.loadSessionHistory = async () => {}
    sessions.createSession = async () => 's1' as any

    const wrapper = mount(ArtifactPanel, { global: { plugins: [pinia] } })
    expect(wrapper.get('[data-testid=\"sessions-sidebar\"]').attributes('style')).toContain('width: 250px')
  })
})
