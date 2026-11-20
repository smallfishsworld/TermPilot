import MarkdownIt from 'markdown-it'

// Raw HTML is disabled, so model output cannot inject markup or scripts;
// markdown-it also refuses javascript: and data: links by default.
const renderer = new MarkdownIt({ html: false, linkify: true, breaks: false, typographer: true })

const defaultLinkOpen = renderer.renderer.rules.link_open
  ?? ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))

renderer.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index]!
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, index, options, env, self)
}

const CITATION = /\[(\d{1,2})\](?!\()/g

/**
 * Render an answer to HTML and turn `[n]` citation markers into badges
 * (only for numbers that match a known source).
 */
export function renderAnswer(markdown: string, sourceCount = 0): string {
  const html = renderer.render(markdown)
  if (!sourceCount) return html
  return html.replace(CITATION, (match, value: string) => {
    const index = Number(value)
    return index >= 1 && index <= sourceCount
      ? `<sup class="cite" data-source="${index}" title="Source ${index}">${index}</sup>`
      : match
  })
}

export function citedSources(markdown: string): number[] {
  return [...new Set([...markdown.matchAll(CITATION)].map(match => Number(match[1])))].sort((a, b) => a - b)
}
