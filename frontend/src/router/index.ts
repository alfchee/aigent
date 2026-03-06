import { createRouter, createWebHistory } from 'vue-router'

import ArtifactPanel from '../components/artifacts/ArtifactPanel.vue'
import SettingsView from '../views/SettingsView.vue'
import ChannelsView from '../views/ChannelsView.vue'
import SchedulerView from '../views/SchedulerView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: ArtifactPanel },
    { path: '/settings', name: 'settings', component: SettingsView },
    { path: '/channels', name: 'channels', component: ChannelsView },
    { path: '/scheduler', name: 'scheduler', component: SchedulerView },
  ],
})
