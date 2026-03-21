import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RefinerStatusBadge from './RefinerStatusBadge.vue'

describe('RefinerStatusBadge', () => {
  it('renders idle status', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'idle' },
    })
    expect(wrapper.text()).toContain('Idle')
  })

  it('renders approved status with brand color', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'approved' },
    })
    expect(wrapper.text()).toContain('Aprobado')
    expect(wrapper.find('.text-brand').exists()).toBe(true)
  })

  it('renders refining status', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'refining' },
    })
    expect(wrapper.text()).toContain('Refinando')
  })

  it('renders revised status with warning color', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'revised' },
    })
    expect(wrapper.text()).toContain('Revisado')
    expect(wrapper.find('.text-warning').exists()).toBe(true)
  })

  it('renders incomplete status', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'incomplete' },
    })
    expect(wrapper.text()).toContain('Incompleto')
  })

  it('renders error status with danger color', () => {
    const wrapper = mount(RefinerStatusBadge, {
      props: { status: 'error' },
    })
    expect(wrapper.text()).toContain('Error')
    expect(wrapper.find('.text-danger').exists()).toBe(true)
  })
})
