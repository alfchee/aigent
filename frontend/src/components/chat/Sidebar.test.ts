import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { initPinia } from '../../test/utils'
import { useSessionsStore } from '../../stores/sessions'
import Sidebar from './Sidebar.vue'

describe('Sidebar', () => {
  it('renders sessions and emits select', async () => {
    const pinia = initPinia()
    const sessions = useSessionsStore()
    sessions.sessions = [{ id: 's1', title: 'T1', created_at: null, updated_at: null }]
    vi.spyOn(sessions, 'fetchSessions').mockResolvedValue(undefined as any)

    const wrapper = mount(Sidebar, {
      props: { activeSessionId: 's0', sidebarState: 'medium' },
      global: { plugins: [pinia] }
    })

    expect(wrapper.text()).toContain('T1')

    await wrapper.find('[role="button"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['s1'])
  })

  it('applies collapsed width', async () => {
    const pinia = initPinia()
    const sessions = useSessionsStore()
    sessions.sessions = [{ id: 's1', title: 'T1', created_at: null, updated_at: null }]
    vi.spyOn(sessions, 'fetchSessions').mockResolvedValue(undefined as any)

    const wrapper = mount(Sidebar, {
      props: { activeSessionId: 's0', sidebarState: 'collapsed' },
      global: { plugins: [pinia] }
    })

    expect(wrapper.get('[data-testid="sessions-sidebar"]').attributes('style')).toContain('width: 50px')
    expect(wrapper.text()).toContain('💬')
  })
})
