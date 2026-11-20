// Incremental parser for server-sent events delivered over a fetch() body.

export interface StreamEvent {
  event: string
  data: Record<string, any>
}

/**
 * Feed text chunks in; complete events come out. Partial events stay buffered
 * until the blank line that ends them arrives.
 */
export function createEventParser() {
  let buffer = ''

  function parseBlock(block: string): StreamEvent | null {
    let event = 'message'
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
    }
    if (!data.length) return null
    try {
      return { event, data: JSON.parse(data.join('\n')) }
    }
    catch {
      return { event, data: { text: data.join('\n') } }
    }
  }

  return {
    push(chunk: string): StreamEvent[] {
      buffer += chunk.replace(/\r\n/g, '\n')
      const events: StreamEvent[] = []
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const parsed = parseBlock(buffer.slice(0, boundary))
        if (parsed) events.push(parsed)
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
      }
      return events
    },
    flush(): StreamEvent[] {
      const rest = buffer.trim()
      buffer = ''
      const parsed = rest ? parseBlock(rest) : null
      return parsed ? [parsed] : []
    },
  }
}

export async function readEventStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createEventParser()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    for (const event of parser.push(decoder.decode(value, { stream: true }))) onEvent(event)
  }
  for (const event of parser.flush()) onEvent(event)
}
