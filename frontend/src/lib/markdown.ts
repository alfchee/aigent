import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css' // Or any other style

export const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
})

const defaultLinkRender =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  const existingClass = token.attrGet('class')
  token.attrSet('class', existingClass ? `${existingClass} external-link` : 'external-link')
  const href = token.attrGet('href') || ''
  const existingLabel = token.attrGet('aria-label') || ''
  const baseLabel = existingLabel || href || 'Link'
  const suffix = ' (opens in a new tab)'
  const nextLabel = baseLabel.includes('opens in a new tab') ? baseLabel : `${baseLabel}${suffix}`
  token.attrSet('aria-label', nextLabel)
  return defaultLinkRender(tokens, idx, options, env, self)
}

md.set({
  highlight: (str: string, lang?: string): string => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return (
          '<pre class="hljs p-3 rounded-md overflow-x-auto text-xs my-2"><code>' +
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
          '</code></pre>'
        )
      } catch {
        return (
          '<pre class="hljs p-3 rounded-md overflow-x-auto text-xs my-2"><code>' +
          md.utils.escapeHtml(str) +
          '</code></pre>'
        )
      }
    }

    return (
      '<pre class="hljs p-3 rounded-md overflow-x-auto text-xs my-2"><code>' +
      md.utils.escapeHtml(str) +
      '</code></pre>'
    )
  },
})
