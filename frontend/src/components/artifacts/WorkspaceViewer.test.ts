import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { initPinia } from '../../test/utils'
import { useArtifactsStore } from '../../stores/artifacts'
import WorkspaceViewer from './WorkspaceViewer.vue'

describe('WorkspaceViewer sidebar', () => {
  it('applies collapsed width and shows tooltips', async () => {
    const pinia = initPinia()
    const store = useArtifactsStore()
    store.sessionId = 's1'
    store.files = [
      { path: 'a.png', size_bytes: 10, modified_at: 't', mime_type: 'image/png' },
      { path: 'b.txt', size_bytes: 5, modified_at: 't', mime_type: 'text/plain' }
    ]

    const wrapper = mount(WorkspaceViewer, {
      props: { sidebarState: 'collapsed' },
      global: { plugins: [pinia] }
    })

    const sidebar = wrapper.get('[data-testid="artifacts-sidebar"]')
    expect(sidebar.attributes('style')).toContain('width: 50px')

    const buttons = wrapper.findAll('button')
    expect(buttons.some((b) => b.attributes('title') === 'a.png')).toBe(true)
  })
})
