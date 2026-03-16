import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import { setupMockWsIfEnabled } from '@/mocks/mockWs'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { usePreferencesStore } from '@/stores/preferences'

setupMockWsIfEnabled()

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const prefs = usePreferencesStore(pinia)
prefs.applyThemeToDom()

app.mount('#app')
