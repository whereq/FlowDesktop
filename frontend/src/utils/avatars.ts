/* FlowDesktop native avatar system — catalogs + resolution.
 *
 * Native avatars are stored in the user's `avatar` field as `fd:<key>` so no
 * schema change is needed. Resolution priority (computed in AvatarContext):
 *   1. user's `avatar` value  → uploaded image (data/http URL) OR fd:<key>
 *   2. SSO picture from the JWT (Google etc.)
 *   3. anonymous default
 * Anonymous visitors get a (stable) random anonymous pose.
 */
import keycloak from '../auth/keycloak'

export interface NativeAvatar { key: string; url: string; label: string; group: string }

// 8 anonymous poses (guest default — one is picked at random per browser).
export const ANON_POSES: string[] = Array.from({ length: 8 }, (_, i) => `/avatars/anonymous/a${i + 1}.png`)
export const ANON_DEFAULT = ANON_POSES[0]

const ARCHETYPE_KEYS: [string, string][] = [
  ['the-bull', 'The Bull'], ['the-bear', 'The Bear'], ['the-sage', 'The Sage'],
  ['the-navigator', 'The Navigator'], ['the-analyst', 'The Analyst'],
  ['the-trendsetter', 'The Trendsetter'], ['the-quant', 'The Quant'], ['the-custodian', 'The Custodian'],
]

const PORTRAIT_KEYS: string[] = [
  'p-f1-east-asian-30s-straight-black', 'p-f2-south-asian-30s-long-wavy', 'p-f3-black-30s-coily',
  'p-f4-white-30s-auburn-glasses', 'p-f5-latina-30s-long-dark-wavy', 'p-f6-east-asian-50s-grey-reading-glasses',
  'p-f7-black-50s-short-grey', 'p-f8-white-25s-pixie',
  'p-m1-white-30s-short-brown-stubble', 'p-m2-east-asian-30s-short-black-glasses', 'p-m3-black-30s-cropped-beard',
  'p-m4-south-asian-30s-mustache', 'p-m5-white-50s-greying', 'p-m6-middle-eastern-30s-curly-beard',
  'p-a1-east-asian-30s-undercut', 'p-a2-white-30s-medium-wavy-glasses',
]

function portraitLabel(key: string): string {
  // 'p-f1-east-asian-30s-straight-black' → 'F1 · east asian 30s'
  const m = key.match(/^p-([a-z]\d+)-(.+)$/)
  if (!m) return key
  const code = m[1].toUpperCase()
  const desc = m[2].split('-').slice(0, 3).join(' ')
  return `${code} · ${desc}`
}

export const ARCHETYPES: NativeAvatar[] = ARCHETYPE_KEYS.map(([key, label]) => ({
  key, label, group: 'archetype', url: `/avatars/archetypes/${key}.png`,
}))

export const PORTRAITS: NativeAvatar[] = PORTRAIT_KEYS.map((key) => ({
  key, label: portraitLabel(key), group: 'portrait', url: `/avatars/portraits/${key}.png`,
}))

export const NATIVE_AVATARS: NativeAvatar[] = [...ARCHETYPES, ...PORTRAITS]

const NATIVE_URL_BY_KEY: Record<string, string> = Object.fromEntries(
  NATIVE_AVATARS.map((a) => [a.key, a.url]),
)

/** Resolve a stored `avatar` value to a displayable URL, or null if unset. */
export function resolveAvatarValue(value: string | null | undefined): string | null {
  if (!value) return null
  if (value.startsWith('fd:')) return NATIVE_URL_BY_KEY[value.slice(3)] ?? null
  if (value.startsWith('data:') || value.startsWith('http://') || value.startsWith('https://')) return value
  if (value.startsWith('/')) {
    const base = (keycloak.authServerUrl || '').replace(/\/+$/, '')
    return base ? `${base}${value}` : value
  }
  return value
}

/** True if a stored value is a FlowDesktop native avatar (fd:<key>). */
export const isNativeValue = (value: string | null | undefined): boolean => !!value && value.startsWith('fd:')

/** A stable random anonymous pose for this browser (guest visitors). */
export function guestAvatar(): string {
  try {
    const KEY = 'fd_guest_avatar'
    let v = localStorage.getItem(KEY)
    if (!v || !ANON_POSES.includes(v)) {
      v = ANON_POSES[Math.floor(Math.random() * ANON_POSES.length)]
      localStorage.setItem(KEY, v)
    }
    return v
  } catch {
    return ANON_DEFAULT
  }
}
