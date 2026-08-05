import type { ChatBubble, ChatMessage, InterruptInfo } from '../types'

/** Build conversation bubbles from checkpoint messages (+ optional ask interrupt). */
export function buildChatBubbles(
  messages: ChatMessage[] | undefined,
  interrupt?: InterruptInfo | null,
): ChatBubble[] {
  const out: ChatBubble[] = []
  let i = 0
  for (const m of messages || []) {
    const role = String(m.role || '').toLowerCase()
    const content = String(m.content || '').trim()
    if (!content) continue
    if (role === 'user' || role === 'human') {
      out.push({ id: `u-${i++}`, role: 'user', content })
    } else if (role === 'assistant' || role === 'ai') {
      out.push({ id: `a-${i++}`, role: 'assistant', content })
    }
  }
  if (interrupt?.type === 'ask' && interrupt.question) {
    const q = interrupt.question.trim()
    const last = out[out.length - 1]
    if (!(last?.role === 'assistant' && last.content === q)) {
      out.push({
        id: `ask-${i++}`,
        role: 'assistant',
        content: q,
        pendingAsk: true,
      })
    } else if (last) {
      last.pendingAsk = true
    }
  }
  return out
}

export function shortThreadLabel(threadId: string, preview?: string): string {
  const p = (preview || '').trim()
  if (p) return p.length > 42 ? `${p.slice(0, 42)}…` : p
  return threadId.slice(0, 8)
}
