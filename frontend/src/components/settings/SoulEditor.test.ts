import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SoulEditor from './SoulEditor.vue'
import * as configApi from '@/services/configApi'

vi.mock('@/services/configApi')

describe('SoulEditor.vue', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('loads and displays soul prompt', async () => {
    vi.mocked(configApi.fetchSoulPrompt).mockResolvedValue('Test soul prompt')

    const wrapper = mount(SoulEditor)

    // Shows loading state initially
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)

    await flushPromises()

    // Shows textarea with content
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Test soul prompt')
  })

  it('handles load error', async () => {
    vi.mocked(configApi.fetchSoulPrompt).mockRejectedValue(new Error('Network error'))

    const wrapper = mount(SoulEditor)
    await flushPromises()

    expect(wrapper.text()).toContain('Network error')
  })

  it('saves updated soul prompt', async () => {
    vi.mocked(configApi.fetchSoulPrompt).mockResolvedValue('Old')
    vi.mocked(configApi.updateSoulPrompt).mockResolvedValue('New')

    const wrapper = mount(SoulEditor)
    await flushPromises()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('New')

    const saveBtn = wrapper.find('button')
    await saveBtn.trigger('click')

    expect(configApi.updateSoulPrompt).toHaveBeenCalledWith('New')
    await flushPromises()

    expect(wrapper.text()).toContain('Guardado')
  })
})

// helper
async function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}
