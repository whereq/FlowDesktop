/**
 * Encoded localStorage helpers.
 *
 * All values are stored as base64(encodeURIComponent(value)) so:
 *  - The browser console and DevTools Storage tab show no plain text.
 *  - Unicode (Chinese, emoji, etc.) is handled safely.
 *  - A migration fallback lets old plain-text values decode gracefully.
 */

function encode(value: string): string {
  try {
    return btoa(encodeURIComponent(value))
  } catch {
    return ''
  }
}

function decode(raw: string): string {
  try {
    // Primary: URI-safe base64 (new format)
    return decodeURIComponent(atob(raw))
  } catch {
    // Fallback: plain base64 without encodeURIComponent (old API-key format)
    try { return atob(raw) } catch { /* not base64 at all */ }
    // Last resort: return as-is (migration from pre-encoding era)
    return raw
  }
}

export function lsSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, encode(value))
  } catch { /* storage quota */ }
}

export function lsGet(key: string): string | null {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return null
    return decode(raw)
  } catch {
    return null
  }
}

export function lsRemove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch { /* noop */ }
}
