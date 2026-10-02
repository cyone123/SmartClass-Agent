import MarkdownIt from 'markdown-it'
import { katex } from '@mdit/plugin-katex'

const markdownRenderer = MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

markdownRenderer.use(katex, {
  throwOnError: false,
  strict: 'ignore'
})

const defaultLinkOpenRenderer =
  markdownRenderer.renderer.rules.link_open ||
  ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

markdownRenderer.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const targetIndex = token.attrIndex('target')
  const relIndex = token.attrIndex('rel')

  if (targetIndex < 0) {
    token.attrPush(['target', '_blank'])
  } else {
    token.attrs[targetIndex][1] = '_blank'
  }

  if (relIndex < 0) {
    token.attrPush(['rel', 'noopener noreferrer'])
  } else {
    token.attrs[relIndex][1] = 'noopener noreferrer'
  }

  return defaultLinkOpenRenderer(tokens, idx, options, env, self)
}

export const normalizeMarkdownSource = (value = '') => {
  if (typeof value === 'string') {
    return value
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }

        if (item && typeof item === 'object' && typeof item.text === 'string') {
          return item.text
        }

        return ''
      })
      .join('')
  }

  if (value == null) {
    return ''
  }

  return String(value)
}

export const renderMarkdown = (value = '') => {
  const source = normalizeMarkdownSource(value)

  if (!source) {
    return ''
  }

  try {
    return markdownRenderer.render(source)
  } catch (error) {
    console.error('Markdown render failed:', error)
    const escaped = markdownRenderer.utils.escapeHtml(source).replace(/\n/g, '<br>')
    return `<p>${escaped}</p>`
  }
}
