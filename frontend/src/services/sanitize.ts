import DOMPurify from 'dompurify'

export function sanitizeText(input: string) {
  const clean = DOMPurify.sanitize(input, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] })
  return clean.replace(/\u0000/g, '')
}
