import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react'
import keycloak from '../auth/keycloak'
import { api } from '../api/client'
import { resolveAvatarValue, ANON_DEFAULT } from '../utils/avatars'

export interface AvatarContextValue {
  /** Raw stored value (uploaded URL/data, `fd:<key>`, or null). */
  value: string | null
  /** SSO picture from the identity provider (Google etc.), if any. */
  ssoPicture: string | null
  /** Effective avatar URL to display for the signed-in user. */
  effectiveUrl: string
  /** Update locally after a save so the header/chat reflect it immediately. */
  setValue: (v: string | null) => void
}

export const AvatarContext = createContext<AvatarContextValue | null>(null)

function ssoPictureFromToken(): string | null {
  const tp = keycloak.tokenParsed as Record<string, unknown> | undefined
  const raw = (tp?.['avatar'] || tp?.['picture']) as string | undefined
  return resolveAvatarValue(raw)
}

export function AvatarProvider({ children }: { children: ReactNode }) {
  const [value, setValueState] = useState<string | null>(null)
  const ssoPicture = ssoPictureFromToken()

  useEffect(() => {
    let alive = true
    if (!keycloak.authenticated) return
    api.getAccount()
      .then((a) => { if (alive) setValueState(a.avatar ?? null) })
      .catch(() => { /* keep null → falls back to SSO/anon */ })
    return () => { alive = false }
  }, [])

  const setValue = useCallback((v: string | null) => setValueState(v || null), [])

  const effectiveUrl = resolveAvatarValue(value) ?? ssoPicture ?? ANON_DEFAULT

  return (
    <AvatarContext.Provider value={{ value, ssoPicture, effectiveUrl, setValue }}>
      {children}
    </AvatarContext.Provider>
  )
}
