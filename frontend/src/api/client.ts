/** Dev: hit API directly. Production/Docker: same-origin via nginx `/api` + `/health`. */
export const API = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
const ADMIN_TOKEN = String(import.meta.env.VITE_ADMIN_TOKEN || '')

export function apiHeaders(extra?: HeadersInit): HeadersInit {
  const h: Record<string, string> = { ...(extra as Record<string, string> | undefined) }
  if (ADMIN_TOKEN) h['X-Admin-Token'] = ADMIN_TOKEN
  return h
}

export async function apiJson<T = Record<string, unknown>>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || res.statusText)
  }
  return (await res.json()) as T
}
