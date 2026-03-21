import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import QualityCriterionBar from './QualityCriterionBar.vue'

describe('QualityCriterionBar', () => {
  it('renders with default score', () => {
    const wrapper = mount(QualityCriterionBar, {
      props: { label: 'relevance' },
    })
    expect(wrapper.find('.text-muted').text()).toContain('relevance')
    expect(wrapper.find('.bg-muted').exists()).toBe(true)
  })

  it('renders high score with brand color', () => {
    const wrapper = mount(QualityCriterionBar, {
      props: { label: 'accuracy', score: 85 },
    })
    expect(wrapper.find('.bg-brand').exists()).toBe(true)
  })

  it('renders medium score with warning color', () => {
    const wrapper = mount(QualityCriterionBar, {
      props: { label: 'accuracy', score: 60 },
    })
    expect(wrapper.find('.bg-warning').exists()).toBe(true)
  })

  it('renders low score with muted color', () => {
    const wrapper = mount(QualityCriterionBar, {
      props: { label: 'clarity', score: 30 },
    })
    expect(wrapper.find('.bg-muted').exists()).toBe(true)
  })

  it('caps width at 100%', () => {
    const wrapper = mount(QualityCriterionBar, {
      props: { label: 'test', score: 150 },
    })
    const inner = wrapper.find('.h-full')
    expect(inner.attributes('style')).toContain('width: 100%')
  })
})
