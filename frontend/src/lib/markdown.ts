import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css' // Or any other style

export const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true
})

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
  }
})
