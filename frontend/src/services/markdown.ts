import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Configure marked options for safer parsing
marked.setOptions({
  gfm: true,
  breaks: true, // Render newlines as <br>
})

/**
 * Parses markdown string to sanitized HTML string.
 */
export async function renderMarkdown(raw: string): Promise<string> {
  if (!raw) return ''

  try {
    // 1. Parse Markdown to raw HTML using marked
    const rawHtml = await marked.parse(raw)

    // 2. Add Tailwind utility classes to generated tags before sanitization
    // Since marked output is standard HTML, we can manipulate it
    let styledHtml = rawHtml
      .replace(/<h1>/g, '<h1 class="text-xl font-bold">')
      .replace(/<h2>/g, '<h2 class="text-lg font-semibold">')
      .replace(/<h3>/g, '<h3 class="text-base font-semibold">')
      .replace(/<h4>/g, '<h4 class="text-sm font-semibold">')
      .replace(/<h5>/g, '<h5 class="text-sm font-bold">')
      .replace(/<h6>/g, '<h6 class="text-xs font-bold">')
      .replace(/<p>/g, '<p class="text-sm leading-[1.2]">')
      .replace(/<ul>/g, '<ul class="ml-5 list-disc text-sm">')
      .replace(/<ol>/g, '<ol class="ml-5 list-decimal text-sm">')
      .replace(/<li>/g, '<li>')
      .replace(/<strong>/g, '<strong class="font-bold">')
      .replace(/<em>/g, '<em class="italic">')
      .replace(/<del>/g, '<del class="line-through opacity-60">')
      .replace(
        /<a href=/g,
        '<a class="text-brand underline hover:no-underline" target="_blank" rel="noopener noreferrer" href=',
      )
      .replace(/<hr>/g, '<hr class="border-border" />')
      .replace(
        /<blockquote>/g,
        '<blockquote class="border-l-3 border-brand/40 pl-3 text-muted italic text-sm">',
      )
      .replace(
        /<pre><code/g,
        '<pre class="bg-surface2 rounded-lg p-2.5 overflow-x-auto text-xs"><code class="font-mono"',
      )
      .replace(
        /<code>/g,
        '<code class="bg-surface2 px-1 py-0.5 rounded text-[13px] font-mono">',
      )

    // 3. Sanitize the result with DOMPurify
    return DOMPurify.sanitize(styledHtml, {
      ALLOWED_TAGS: [
        'p',
        'br',
        'strong',
        'em',
        'del',
        'code',
        'pre',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'ul',
        'ol',
        'li',
        'blockquote',
        'a',
        'hr',
      ],
      ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
    })
  } catch (error) {
    console.error('Error parsing markdown:', error)
    // Fallback to basic text escaping if parser fails
    return DOMPurify.sanitize(raw.replace(/\n/g, '<br/>'))
  }
}

/**
 * Synchronous version for tests or when async is not viable
 */
export function renderMarkdownSync(raw: string): string {
  if (!raw) return ''
  try {
    const rawHtml = marked.parse(raw) as string

    let styledHtml = rawHtml
      .replace(/<h1>/g, '<h1 class="text-xl font-bold">')
      .replace(/<h2>/g, '<h2 class="text-lg font-semibold">')
      .replace(/<h3>/g, '<h3 class="text-base font-semibold">')
      .replace(/<h4>/g, '<h4 class="text-sm font-semibold">')
      .replace(/<h5>/g, '<h5 class="text-sm font-bold">')
      .replace(/<h6>/g, '<h6 class="text-xs font-bold">')
      .replace(/<p>/g, '<p class="text-sm leading-[1.2]">')
      .replace(/<ul>/g, '<ul class="ml-5 list-disc text-sm">')
      .replace(/<ol>/g, '<ol class="ml-5 list-decimal text-sm">')
      .replace(/<li>/g, '<li>')
      .replace(/<strong>/g, '<strong class="font-bold">')
      .replace(/<em>/g, '<em class="italic">')
      .replace(/<del>/g, '<del class="line-through opacity-60">')
      .replace(
        /<a href=/g,
        '<a class="text-brand underline hover:no-underline" target="_blank" rel="noopener noreferrer" href=',
      )
      .replace(/<hr>/g, '<hr class="border-border" />')
      .replace(
        /<blockquote>/g,
        '<blockquote class="border-l-3 border-brand/40 pl-3 text-muted italic text-sm">',
      )
      .replace(
        /<pre><code/g,
        '<pre class="bg-surface2 rounded-lg p-2.5 overflow-x-auto text-xs"><code class="font-mono"',
      )
      .replace(
        /<code>/g,
        '<code class="bg-surface2 px-1 py-0.5 rounded text-[13px] font-mono">',
      )

    return DOMPurify.sanitize(styledHtml, {
      ALLOWED_TAGS: [
        'p',
        'br',
        'strong',
        'em',
        'del',
        'code',
        'pre',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'ul',
        'ol',
        'li',
        'blockquote',
        'a',
        'hr',
      ],
      ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
    })
  } catch (error) {
    console.error('Error parsing markdown:', error)
    return DOMPurify.sanitize(raw.replace(/\n/g, '<br/>'))
  }
}

/**
 * Determine if text contains markdown structures that need rendering
 */
export function isMultilineMarkdown(text: string): boolean {
  if (!text) return false

  // A more robust check for markdown elements
  // Marked handles plain text fine, so we can be more permissive
  // Return true if it contains any common markdown indicators
  return (
    /[*_~`#>\[\]]/.test(text) || // Contains formatting chars
    /^(#{1,6}|\*|-|\d+\.)\s/m.test(text) || // Contains lists or headers
    /\n\n/.test(text) // Contains paragraphs
  )
}
