import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import Combobox from './Combobox.vue'

describe('Combobox.vue', () => {
  const options = ['gemini-2.0-flash', 'gemini-2.5-pro', 'gpt-4o', 'claude-3-opus']

  // Mock scrollIntoView
  Element.prototype.scrollIntoView = vi.fn()

  it('renders input with initial value', () => {
    const wrapper = mount(Combobox, {
      props: {
        modelValue: 'gemini-2.0-flash',
        options,
      },
    })
    const input = wrapper.find('input')
    expect(input.element.value).toBe('gemini-2.0-flash')
  })

  it('filters options based on input', async () => {
    const wrapper = mount(Combobox, {
      props: {
        modelValue: '',
        options,
      },
    })

    const input = wrapper.find('input')
    await input.setValue('gpt')

    // Check if dropdown is open (v-show checks display style)
    const listbox = wrapper.find('[role="listbox"]')
    expect(listbox.isVisible()).toBe(true)

    // Check filtered options
    const listItems = wrapper.findAll('[role="option"]')
    // Should contain "gpt-4o"
    expect(listItems.length).toBe(1)
    expect(listItems[0].text()).toContain('gpt-4o')
  })

  it('selects option on click', async () => {
    const wrapper = mount(Combobox, {
      props: {
        modelValue: '',
        options,
      },
    })

    const input = wrapper.find('input')
    await input.trigger('focus') // Open dropdown

    const listItems = wrapper.findAll('[role="option"]')
    // Click second option (gemini-2.5-pro)
    await listItems[1].trigger('mousedown')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['gemini-2.5-pro'])

    // Check if dropdown is closed
    const listbox = wrapper.find('[role="listbox"]')
    expect(listbox.isVisible()).toBe(false)
  })

  it('clears selection', async () => {
    const wrapper = mount(Combobox, {
      props: {
        modelValue: 'gpt-4o',
        options,
      },
    })

    // Find clear button (it appears when modelValue is present)
    const button = wrapper.find('button[aria-label="Clear selection"]')
    expect(button.exists()).toBe(true)

    await button.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([''])
    const input = wrapper.find('input')
    expect(input.element.value).toBe('')
  })

  it('handles keyboard navigation', async () => {
    const wrapper = mount(Combobox, {
      props: {
        modelValue: '',
        options,
      },
    })

    const input = wrapper.find('input')
    await input.trigger('keydown', { key: 'ArrowDown' })

    const listbox = wrapper.find('[role="listbox"]')
    expect(listbox.isVisible()).toBe(true)

    // Check highlighting via class
    const optionsList = wrapper.findAll('[role="option"]')
    expect(optionsList[0].classes()).toContain('bg-sky-50')
    expect(optionsList[0].classes()).toContain('border-sky-500')

    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(optionsList[1].classes()).toContain('bg-sky-50')
    expect(optionsList[0].classes()).not.toContain('bg-sky-50')

    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['gemini-2.5-pro'])
  })

  it('highlights matches correctly', async () => {
    const wrapper = mount(Combobox, {
      props: { modelValue: '', options },
    })

    const input = wrapper.find('input')
    await input.setValue('flash')

    const optionsList = wrapper.findAll('[role="option"]')
    const flashOption = optionsList.find((opt) => opt.text().includes('gemini-2.0-flash'))

    expect(flashOption).toBeDefined()
    // Check innerHTML for span with highlighting class
    expect(flashOption?.html()).toContain(
      '<span class="bg-sky-100 text-sky-700 font-medium">flash</span>',
    )
  })
})
