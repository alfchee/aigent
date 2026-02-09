import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatMessage from './ChatMessage.vue'

describe('ChatMessage', () => {
  it('renders simple text', () => {
    const wrapper = mount(ChatMessage, {
      props: { role: 'assistant', content: 'Hello' }
    })
    expect(wrapper.text()).toContain('Hello')
  })

  it('renders tool call', () => {
    const content = 'Some text [tool_call] {"name": "test_tool"} [/tool_call]'
    const wrapper = mount(ChatMessage, {
      props: { role: 'assistant', content }
    })
    expect(wrapper.text()).toContain('Some text')
    expect(wrapper.text()).toContain('Ejecutar: test_tool')
    const toolCall = wrapper.get('[data-testid="tool-call"]')
    const toolCallDetails = toolCall.find('details')
    expect(toolCallDetails.attributes('open')).toBeUndefined()
    expect(toolCall.classes()).toContain('bg-slate-50')
  })

  it('renders tool result', () => {
    const content = '[tool_result] success [/tool_result]'
    const wrapper = mount(ChatMessage, {
      props: { role: 'assistant', content }
    })
    expect(wrapper.text()).toContain('Resultado del Agente')
    expect(wrapper.text()).toContain('success')
    const toolResult = wrapper.get('[data-testid="tool-result"]')
    const toolResultDetails = toolResult.find('details')
    expect(toolResultDetails.attributes('open')).toBeUndefined()
    expect(toolResult.classes()).toContain('bg-slate-50')
  })
})
