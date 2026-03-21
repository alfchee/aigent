import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CostDashboard from './CostDashboard.vue'
import { useCostStore } from '@/stores/cost'
import type { SessionCostSummaryDto } from '@/services/costApi'

const createMockSummary = (
  overrides: Partial<SessionCostSummaryDto> = {},
): SessionCostSummaryDto => ({
  session_id: 'test_session',
  user_id: 'test_user',
  total_calls: 10,
  total_input_tokens: 50000,
  total_output_tokens: 25000,
  total_cost_usd: 0.125,
  daily_limit_usd: 10.0,
  remaining_budget_usd: 9.875,
  budget_exceeded: false,
  last_call_at: new Date().toISOString(),
  currency: 'USD',
  ...overrides,
})

describe('CostDashboard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders loading skeleton when loading', () => {
    const store = useCostStore()
    store.loading = true

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
  })

  it('renders error banner when error is set', () => {
    const store = useCostStore()
    store.loading = false
    store.error = 'Network failure'

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    expect(wrapper.find('.border-danger\\/30').exists()).toBe(true)
    expect(wrapper.text()).toContain('Network failure')
  })

  it('renders "no data" state when summary is null and not loading', () => {
    const store = useCostStore()
    store.loading = false
    store.error = null
    store.currentSessionId = null

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    expect(wrapper.text()).toContain('Sin datos de costos disponibles')
  })

  it('renders summary data when available', async () => {
    const store = useCostStore()
    store.loading = false
    store.error = null
    store.currentSessionId = 'test_session'
    store.summariesBySession = { test_session: createMockSummary() }

    const wrapper = mount(CostDashboard, {
      props: { sessionId: 'test_session' },
      global: { stubs: { BudgetGauge: false, CostCallList: false } },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('10')
    expect(wrapper.text()).toContain('50.0K')
    expect(wrapper.text()).toContain('$0.125000')
  })

  it('shows budget exceeded alert when budget_exceeded is true', async () => {
    const store = useCostStore()
    store.loading = false
    store.error = null
    store.currentSessionId = 'test_session'
    store.summariesBySession = {
      test_session: createMockSummary({
        budget_exceeded: true,
        remaining_budget_usd: -0.5,
        daily_limit_usd: 10,
        total_cost_usd: 10.5,
      }),
    }

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: false, CostCallList: false } },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('excedido')
  })

  it('calls store.loadSummary on mount with sessionId', async () => {
    const loadSummarySpy = vi.fn().mockResolvedValue(undefined)
    const store = useCostStore()
    store.loadSummary = loadSummarySpy

    mount(CostDashboard, {
      props: { sessionId: 'test_session' },
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    expect(loadSummarySpy).toHaveBeenCalledWith('test_session')
  })

  it('calls store.loadSummary on mount without sessionId when prop not provided', async () => {
    const loadSummarySpy = vi.fn().mockResolvedValue(undefined)
    const store = useCostStore()
    store.loadSummary = loadSummarySpy

    mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    expect(loadSummarySpy).toHaveBeenCalledWith(undefined)
  })

  it('triggers reload on refresh button click', async () => {
    const store = useCostStore()
    store.loading = false
    store.error = null
    store.currentSessionId = 'test_session'
    store.summariesBySession = { test_session: createMockSummary() }

    const loadSpy = vi.fn().mockResolvedValue(undefined)
    store.loadSummary = loadSpy

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    const refreshBtn = wrapper.findAll('button').find((b) => b.text().includes('Refresh'))
    await refreshBtn?.trigger('click')
    expect(loadSpy).toHaveBeenCalled()
  })

  it('exposes load method via defineExpose', async () => {
    const store = useCostStore()
    store.loading = false
    store.error = null
    store.currentSessionId = null

    const wrapper = mount(CostDashboard, {
      global: { stubs: { BudgetGauge: true, CostCallList: true } },
    })

    expect(typeof wrapper.vm.load).toBe('function')
  })
})
