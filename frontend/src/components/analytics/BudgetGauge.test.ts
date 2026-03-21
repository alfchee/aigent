import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BudgetGauge from './BudgetGauge.vue'

describe('BudgetGauge', () => {
  describe('rendering', () => {
    it('renders with default props', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 5, limit: 10 },
      })
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
    })

    it('renders with custom currency', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 5, limit: 10, currency: 'EUR' },
      })
      const text = wrapper.text()
      expect(text).toContain('EUR')
    })

    it('hides labels when showLabels is false', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 5, limit: 10, showLabels: false },
      })
      expect(wrapper.find('.text-xs').exists()).toBe(false)
    })
  })

  describe('percentage calculation', () => {
    it('calculates 50% correctly', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 5, limit: 10 },
      })
      const bar = wrapper.find('[role="progressbar"]')
      const inner = bar.find('div')
      const width = inner.attributes('style')
      expect(width).toMatch(/width:\s*50%/)
    })

    it('caps percentage at 100% when spent exceeds limit', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 15, limit: 10 },
      })
      const bar = wrapper.find('[role="progressbar"]')
      const inner = bar.find('div')
      const width = inner.attributes('style')
      expect(width).toMatch(/width:\s*100%/)
    })

    it('returns 0% when limit is 0', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 5, limit: 0 },
      })
      const bar = wrapper.find('[role="progressbar"]')
      expect(bar.attributes('aria-valuenow')).toBe('0')
    })
  })

  describe('color logic', () => {
    it('shows brand color under 80%', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 50, limit: 100 },
      })
      const bar = wrapper.find('.bg-brand')
      expect(bar.exists()).toBe(true)
    })

    it('shows warning color at 80% or above', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 85, limit: 100 },
      })
      const bar = wrapper.find('.bg-warning')
      expect(bar.exists()).toBe(true)
    })

    it('shows danger color when exceeded', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 15, limit: 10 },
      })
      const bar = wrapper.find('.bg-danger')
      expect(bar.exists()).toBe(true)
    })
  })

  describe('labels', () => {
    it('shows remaining amount when not exceeded', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 3, limit: 10 },
      })
      const text = wrapper.text()
      expect(text).toContain('7.00')
      expect(text).not.toContain('exceeded')
    })

    it('shows exceeded message when over budget', () => {
      const wrapper = mount(BudgetGauge, {
        props: { spent: 15, limit: 10 },
      })
      const text = wrapper.text()
      expect(text).toContain('Límite excedido')
    })
  })
})
