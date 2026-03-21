import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ActiveRulesPanel from './ActiveRulesPanel.vue'

async function expandPanel(wrapper: ReturnType<typeof mount>) {
  const btn = wrapper.find('button')
  if (btn.exists()) await btn.trigger('click')
  await wrapper.vm.$nextTick()
}

describe('ActiveRulesPanel', () => {
  it('does not render when no message and autoDetect is true', () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: '', autoDetect: true },
    })
    expect(wrapper.findAll('*').length).toBe(0)
  })

  it('shows header when financial keywords detected', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: 'Necesito registrar mis gastos del mes', autoDetect: true },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Reglas activas')
    expect(wrapper.text()).toContain('1')
  })

  it('shows financial chip when expanded', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: 'Necesito registrar mis gastos del mes', autoDetect: true },
    })
    await wrapper.vm.$nextTick()
    await expandPanel(wrapper)
    expect(wrapper.text()).toContain('Financiero')
  })

  it('shows research chip when expanded', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: {
        userMessage: 'Investigar las causas del cambio climatico',
        autoDetect: true,
      },
    })
    await wrapper.vm.$nextTick()
    await expandPanel(wrapper)
    expect(wrapper.text()).toContain('Investigación')
  })

  it('shows coding chip when expanded', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: 'Ejecuta este script de python por favor', autoDetect: true },
    })
    await wrapper.vm.$nextTick()
    await expandPanel(wrapper)
    expect(wrapper.text()).toContain('Código')
  })

  it('shows social chip when expanded', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: {
        userMessage: 'Publicar esto en Instagram con hashtag relevant',
        autoDetect: true,
      },
    })
    await wrapper.vm.$nextTick()
    await expandPanel(wrapper)
    expect(wrapper.text()).toContain('Social')
  })

  it('toggles expanded state on click', async () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: 'gastos', autoDetect: true },
    })
    await wrapper.vm.$nextTick()
    const btn = wrapper.find('button')
    await btn.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Financiero')
  })

  it('returns nothing when autoDetect is false', () => {
    const wrapper = mount(ActiveRulesPanel, {
      props: { userMessage: 'gastos', autoDetect: false },
    })
    expect(wrapper.findAll('*').length).toBe(0)
  })
})
