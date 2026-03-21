import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RuleChip from './RuleChip.vue'

describe('RuleChip', () => {
  it('renders financial chip with correct icon', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'financial', description: 'Test', isActive: true },
    })
    expect(wrapper.text()).toContain('Financiero')
    expect(wrapper.find('.text-green').exists()).toBe(true)
  })

  it('renders social chip with purple color', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'social', description: 'Test', isActive: true },
    })
    expect(wrapper.text()).toContain('Social')
    expect(wrapper.find('.text-purple').exists()).toBe(true)
  })

  it('renders coding chip with orange color', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'coding', description: 'Test', isActive: true },
    })
    expect(wrapper.text()).toContain('Código')
    expect(wrapper.find('.text-orange').exists()).toBe(true)
  })

  it('renders research chip with blue color', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'research', description: 'Test', isActive: true },
    })
    expect(wrapper.text()).toContain('Investigación')
    expect(wrapper.find('.text-blue').exists()).toBe(true)
  })

  it('shows check icon when active', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'financial', description: 'Test', isActive: true },
    })
    expect(wrapper.find('.text-green').exists()).toBe(true)
  })

  it('shows muted style when inactive', () => {
    const wrapper = mount(RuleChip, {
      props: { ruleType: 'financial', description: 'Test', isActive: false },
    })
    expect(wrapper.find('.text-muted').exists()).toBe(true)
  })
})
