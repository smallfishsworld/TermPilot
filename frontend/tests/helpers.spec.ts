import { describe, expect, it } from 'vitest'
import { buildUrl } from '../app/utils/http'
import { citedSources, renderAnswer } from '../app/utils/markdown'
import { pointsNeeded, projectGpa } from '../app/utils/gpa'
import { createEventParser } from '../app/utils/sse'
import { formatBytes, formatMinutes, fromLocalInput, relativeTime } from '../app/utils/format'

describe('event stream parser', () => {
  it('assembles events split across chunks', () => {
    const parser = createEventParser()
    expect(parser.push('event: answer\ndata: {"text":"Hel')).toEqual([])
    const events = parser.push('lo"}\n\nevent: done\r\ndata: {}\r\n\r\nevent: step\n')
    expect(events).toEqual([
      { event: 'answer', data: { text: 'Hello' } },
      { event: 'done', data: {} },
    ])
    expect(parser.push('data: {"id":"s1"}')).toEqual([])
    expect(parser.flush()).toEqual([{ event: 'step', data: { id: 's1' } }])
  })
})

describe('answer rendering', () => {
  it('escapes raw HTML from the model', () => {
    const html = renderAnswer('<img src=x onerror=alert(1)> **bold**')
    expect(html).not.toContain('<img')
    expect(html).toContain('<strong>bold</strong>')
  })

  it('turns known citations into badges and leaves others alone', () => {
    const html = renderAnswer('Due Friday [1][2], see [7].', 2)
    expect(html).toContain('data-source="1"')
    expect(html).toContain('data-source="2"')
    expect(html).toContain('[7]')
    expect(citedSources('a [2] b [1] c [2]')).toEqual([1, 2])
  })

  it('opens links in a new tab and refuses script URLs', () => {
    expect(renderAnswer('[site](https://example.edu)')).toContain('target="_blank"')
    expect(renderAnswer('[x](javascript:alert(1))')).not.toContain('href="javascript')
  })
})

describe('GPA arithmetic', () => {
  it('projects a weighted average', () => {
    expect(projectGpa(3.5, 60, [{ name: 'A', credits: 4, points: 4 }, { name: 'B', credits: 0, points: 1 }])).toBe(3.531)
    expect(projectGpa(null, null, [{ name: 'A', credits: 3, points: 3.3 }])).toBe(3.3)
    expect(projectGpa(null, null, [])).toBeNull()
  })

  it('computes the average needed for a target', () => {
    expect(pointsNeeded(3.5, 60, 20, 3.6)).toBe(3.9)
    expect(pointsNeeded(3.5, 60, 0, 3.6)).toBeNull()
  })
})

describe('formatting', () => {
  it('formats sizes, durations and relative times', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 kB')
    expect(formatMinutes(150)).toBe('2 h 30 min')
    const now = new Date('2026-10-14T10:00:00Z')
    expect(relativeTime('2026-10-14T13:00:00Z', now)).toBe('in 3 h')
    expect(relativeTime('2026-10-15T12:00:00Z', now)).toBe('tomorrow')
    expect(relativeTime('2026-10-10T10:00:00Z', now)).toBe('4 days ago')
  })

  it('adds the local offset to datetime-local values', () => {
    expect(fromLocalInput('2026-10-20T23:59')).toMatch(/^2026-10-20T23:59:00[+-]\d{2}:\d{2}$/)
  })

  it('builds URLs without empty query values', () => {
    expect(buildUrl('http://localhost:8000', '/api/tasks', { status: 'open', q: '', page: null })).toBe('http://localhost:8000/api/tasks?status=open')
  })
})
