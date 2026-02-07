import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { initPinia } from '../../test/utils'
import { useArtifactsStore } from '../../stores/artifacts'
import ArtifactPanel from './ArtifactPanel.vue'

describe('ArtifactPanel', () => {
  it('renders unread badge when unreadCount > 0', async () => {
    const pinia = initPinia()
    const store = useArtifactsStore()
    store.unreadCount = 2
    store.sessionId = 's1'

    const wrapper = mount(ArtifactPanel, {
      global: { plugins: [pinia] }
    })

    expect(wrapper.text()).toContain('2 nuevo(s)')
  })
})

