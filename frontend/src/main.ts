import { createApp } from 'vue'
import App from './App.vue'
import { createPinia } from 'pinia'
import { router } from './router'

function applyExternalLinkPolicy(root: ParentNode) {
  const anchors = Array.from(root.querySelectorAll('a'))
  anchors.forEach((anchor) => {
    anchor.setAttribute('target', '_blank')
    anchor.setAttribute('rel', 'noopener noreferrer')
    anchor.classList.add('external-link')
    const baseLabel = anchor.getAttribute('aria-label') || anchor.textContent?.trim() || anchor.getAttribute('href') || 'Link'
    const suffix = ' (opens in a new tab)'
    if (!baseLabel.includes('opens in a new tab')) {
      anchor.setAttribute('aria-label', `${baseLabel}${suffix}`)
    }
  })
}

const app = createApp(App).use(createPinia()).use(router)
app.mount('#app')
applyExternalLinkPolicy(document)

const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    mutation.addedNodes.forEach((node) => {
      if (node instanceof Element) {
        if (node.tagName.toLowerCase() === 'a') {
          applyExternalLinkPolicy(node.parentNode || document)
        } else {
          applyExternalLinkPolicy(node)
        }
      }
    })
  }
})

observer.observe(document.body, { childList: true, subtree: true })
