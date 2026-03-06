import { createPinia, setActivePinia } from 'pinia'

export function initPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}
