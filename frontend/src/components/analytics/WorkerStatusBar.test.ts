import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkerStatusBar from './WorkerStatusBar.vue'
import type { WorkerStatusInfo } from '@/types/chat'

const createWorker = (overrides: Partial<WorkerStatusInfo> = {}): WorkerStatusInfo => ({
  role_id: 'researcher',
  name: 'Researcher',
  status: 'idle',
  ...overrides,
})

describe('WorkerStatusBar', () => {
  it('renders idle worker correctly', () => {
    const wrapper = mount(WorkerStatusBar, {
      props: { worker: createWorker({ status: 'idle' }) },
    })
    expect(wrapper.find('.bg-muted\\/40').exists()).toBe(true)
    expect(wrapper.text()).toContain('Researcher')
    expect(wrapper.text()).toContain('idle')
  })

  it('renders working worker with progress bar', () => {
    const wrapper = mount(WorkerStatusBar, {
      props: {
        worker: createWorker({
          status: 'working',
          current_task: 'Searching web',
        }),
      },
    })
    expect(wrapper.find('.bg-brand').exists()).toBe(true)
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
  })

  it('renders error worker with danger color', () => {
    const wrapper = mount(WorkerStatusBar, {
      props: { worker: createWorker({ status: 'error' }) },
    })
    expect(wrapper.find('.bg-danger').exists()).toBe(true)
  })

  it('shows worker name', () => {
    const wrapper = mount(WorkerStatusBar, {
      props: { worker: createWorker({ name: 'Coder' }) },
    })
    expect(wrapper.text()).toContain('Coder')
  })
})
