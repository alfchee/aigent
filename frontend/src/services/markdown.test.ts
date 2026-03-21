import { describe, expect, it } from 'vitest'
import { renderMarkdownSync, isMultilineMarkdown } from './markdown'

describe('markdown service', () => {
  describe('renderMarkdownSync', () => {
    it('escapes HTML tags', () => {
      const result = renderMarkdownSync('<script>alert("xss")</script>')
      expect(result).not.toContain('<script>')
      expect(result).not.toContain('onerror=')
    })

    it('renders bold text', () => {
      const result = renderMarkdownSync('This is **bold** text')
      expect(result).toContain('<strong')
      expect(result).toContain('bold')
    })

    it('renders italic text', () => {
      const result = renderMarkdownSync('This is *italic* text')
      expect(result).toContain('<em')
      expect(result).toContain('italic')
    })

    it('renders inline code', () => {
      const result = renderMarkdownSync('Use `console.log()`')
      expect(result).toContain('<code')
      expect(result).toContain('console.log')
    })

    it('renders code blocks', () => {
      const result = renderMarkdownSync('```\nconst x = 1\n```')
      expect(result).toContain('<pre')
      expect(result).toContain('<code')
      expect(result).toContain('const x = 1')
    })

    it('renders headers h1-h6', () => {
      expect(renderMarkdownSync('# Header 1')).toContain('<h1')
      expect(renderMarkdownSync('## Header 2')).toContain('<h2')
      expect(renderMarkdownSync('### Header 3')).toContain('<h3')
      expect(renderMarkdownSync('#### Header 4')).toContain('<h4')
      expect(renderMarkdownSync('##### Header 5')).toContain('<h5')
      expect(renderMarkdownSync('###### Header 6')).toContain('<h6')
    })

    it('renders unordered lists', () => {
      const result = renderMarkdownSync('* Item one\n* Item two')
      expect(result).toContain('<li')
      expect(result).toContain('Item one')
    })

    it('renders ordered lists', () => {
      const result = renderMarkdownSync('1. First\n2. Second')
      expect(result).toContain('<li')
      expect(result).toContain('First')
    })

    it('renders blockquotes', () => {
      const result = renderMarkdownSync('> This is a quote')
      expect(result).toContain('<blockquote')
      expect(result).toContain('This is a quote')
    })

    it('renders links safely', () => {
      const result = renderMarkdownSync('[Click me](https://example.com)')
      expect(result).toContain('<a')
      expect(result).toContain('href="https://example.com"')
      expect(result).toContain('target="_blank"')
      expect(result).toContain('rel=')
    })

    it('renders horizontal rules', () => {
      const result = renderMarkdownSync('Some text\n\n---\n\nMore text')
      expect(result).toContain('<hr')
    })

    it('renders strikethrough', () => {
      const result = renderMarkdownSync('~~deleted~~')
      expect(result).toContain('<del')
    })

    it('sanitizes javascript hrefs', () => {
      const result = renderMarkdownSync('[XSS](javascript:alert(1))')
      expect(result).not.toContain('javascript:')
    })

    it('handles mixed formatting', () => {
      const result = renderMarkdownSync('**bold** and *italic* and `code`')
      expect(result).toContain('<strong')
      expect(result).toContain('<em')
      expect(result).toContain('<code')
    })

    it('handles special characters', () => {
      const result = renderMarkdownSync('Price: $100 & "quotes"')
      expect(result).toContain('&amp;')
      expect(result).toContain('"quotes"')
    })

    it('handles nested formatting', () => {
      const result = renderMarkdownSync('***bold and italic***')
      expect(result).toContain('<strong')
      expect(result).toContain('<em')
    })
  })

  describe('isMultilineMarkdown', () => {
    it('returns true for headers', () => {
      expect(isMultilineMarkdown('# Hello')).toBe(true)
      expect(isMultilineMarkdown('## Hello')).toBe(true)
    })

    it('returns true for list items', () => {
      expect(isMultilineMarkdown('* item')).toBe(true)
      expect(isMultilineMarkdown('- item')).toBe(true)
      expect(isMultilineMarkdown('1. item')).toBe(true)
    })

    it('returns true for code blocks', () => {
      expect(isMultilineMarkdown('```\ncode\n```')).toBe(true)
    })

    it('returns true for blockquotes', () => {
      expect(isMultilineMarkdown('> quote')).toBe(true)
    })

    it('returns true for single line with formatting', () => {
      expect(isMultilineMarkdown('Hello **world**')).toBe(true)
    })

    it('returns false for plain text', () => {
      expect(isMultilineMarkdown('Hello world')).toBe(false)
    })

    it('returns false for empty string', () => {
      expect(isMultilineMarkdown('')).toBe(false)
    })
  })
})
