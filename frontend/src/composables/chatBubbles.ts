import type { ChatBubble, ChatMessage, InterruptInfo } from '../types'

function askQuestionFromToolCalls(toolCalls: unknown[] | undefined): string | null {
  for (const raw of toolCalls || []) {
    const tc = raw as { name?: string; args?: { question?: string } | string }
    if (tc?.name !== 'ask_user') continue
    let args = tc.args
    if (typeof args === 'string') {
      try {
        args = JSON.parse(args) as { question?: string }
      } catch {
        continue
      }
    }
    const q = String((args as { question?: string } | undefined)?.question || '').trim()
    if (q) return q
  }
  return null
}

function pushAssistant(out: ChatBubble[], content: string, pendingAsk: boolean, id: string) {
  const text = content.trim()
  if (!text) return
  const last = out[out.length - 1]
  if (last?.role === 'assistant') {
    if (last.content === text) {
      last.pendingAsk = last.pendingAsk || pendingAsk
      return
    }
    // Streaming / multi-step: keep one Agent bubble per turn segment
    if (last.content.includes(text)) {
      last.pendingAsk = last.pendingAsk || pendingAsk
      return
    }
    if (text.includes(last.content) && text.length > last.content.length) {
      last.content = text
      last.pendingAsk = last.pendingAsk || pendingAsk
      return
    }
    last.content = `${last.content}\n\n${text}`
    last.pendingAsk = last.pendingAsk || pendingAsk
    return
  }
  out.push({ id, role: 'assistant', content: text, pendingAsk })
}

/** Build conversation bubbles from checkpoint messages (+ optional ask interrupt). */
export function buildChatBubbles(
  messages: ChatMessage[] | undefined,
  interrupt?: InterruptInfo | null,
): ChatBubble[] {
  const out: ChatBubble[] = []
  let i = 0
  const pendingQ = interrupt?.type === 'ask' ? (interrupt.question || '').trim() : ''

  for (const m of messages || []) {
    const role = String(m.role || '').toLowerCase()
    const content = String(m.content || '').trim()
    const name = String(m.name || '')

    if (role === 'user' || role === 'human') {
      if (!content) continue
      const last = out[out.length - 1]
      if (last?.role === 'user' && last.content === content) continue
      out.push({ id: `u-${i++}`, role: 'user', content })
      continue
    }

    // ask_user tool return value IS the user's answer — show it as a user bubble
    if (role === 'tool' && name === 'ask_user' && content) {
      const last = out[out.length - 1]
      if (last?.role === 'user' && last.content === content) continue
      out.push({ id: `ans-${i++}`, role: 'user', content })
      continue
    }

    if (role === 'assistant' || role === 'ai') {
      if (content) {
        pushAssistant(out, content, Boolean(pendingQ && content === pendingQ), `a-${i++}`)
      }
      const askQ = askQuestionFromToolCalls(m.tool_calls)
      if (askQ) {
        pushAssistant(out, askQ, Boolean(pendingQ && askQ === pendingQ), `ask-${i++}`)
      }
    }
  }

  if (pendingQ) {
    pushAssistant(out, pendingQ, true, `ask-live-${i++}`)
  }
  return out
}

export function shortThreadLabel(threadId: string, preview?: string): string {
  const p = (preview || '').trim().replace(/\s+/g, ' ')
  if (p) return p.length > 42 ? `${p.slice(0, 42)}…` : p
  return `会话 ${threadId.slice(0, 8)}`
}

/** Prefer the first user utterance as the conversation title. */
export function firstUserPreview(messages: ChatMessage[] | undefined, fallback = ''): string {
  for (const m of messages || []) {
    const role = String(m.role || '').toLowerCase()
    if (role === 'user' || role === 'human') {
      const c = String(m.content || '').trim()
      if (c) return c
    }
  }
  return fallback
}
