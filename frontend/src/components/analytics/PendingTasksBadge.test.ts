import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PendingTasksBadge from './PendingTasksBadge.vue'

describe('PendingTasksBadge', () => {
  it('renders with no tasks', () => {
    const wrapper = mount(PendingTasksBadge, {
      props: { tasks: [] },
    })
    expect(wrapper.text()).toContain('Sin tareas')
  })

  it('shows count badge when tasks exist', () => {
    const wrapper = mount(PendingTasksBadge, {
      props: { tasks: ['Task 1', 'Task 2'] },
    })
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('Tareas pendientes')
  })

  it('toggles expanded on click', async () => {
    const wrapper = mount(PendingTasksBadge, {
      props: { tasks: ['Task 1', 'Task 2'], expanded: false },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })

  it('shows warning color when tasks exist', () => {
    const wrapper = mount(PendingTasksBadge, {
      props: { tasks: ['Task 1'] },
    })
    expect(wrapper.find('.text-warning').exists()).toBe(true)
  })

  it('shows tasks when expanded', async () => {
    const wrapper = mount(PendingTasksBadge, {
      props: { tasks: ['Task A', 'Task B'], expanded: true },
    })
    expect(wrapper.text()).toContain('Task A')
    expect(wrapper.text()).toContain('Task B')
  })
})
