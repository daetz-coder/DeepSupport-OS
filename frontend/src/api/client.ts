/** Dev: hit API directly. Production/Docker: same-origin via nginx `/api` + `/health` (honors Vite `base`). */
const PUBLIC_BASE = String(import.meta.env.BASE_URL || '/').replace(/\/$/, '')
export const API = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : PUBLIC_BASE)
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
  const res = await fetch(`${API}${path}`, {
    credentials: 'same-origin',
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || res.statusText)
  }
  return (await res.json()) as T
}

export async function demoStatus(): Promise<{ required: boolean; ok: boolean }> {
  const res = await fetch(`${API}/api/auth/demo/status`, { credentials: 'include' })
  if (!res.ok) return { required: false, ok: true }
  return (await res.json()) as { required: boolean; ok: boolean }
}

export async function demoLogin(passphrase: string): Promise<void> {
  const res = await fetch(`${API}/api/auth/demo/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passphrase }),
  })
  if (!res.ok) {
    throw new Error('口令不正确')
  }
}
