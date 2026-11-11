import { createContext, useEffect, useRef, useState, type ReactNode } from 'react'
import keycloak from './keycloak'

interface AuthContextValue {
  isAuthenticated: boolean
  token: string | undefined
  username: string | undefined
  displayName: string | undefined
  avatar: string | undefined
  roles: string[]
  isAdmin: boolean
  login: () => void
  register: () => void
  logout: () => void
}

function extractRoles(tokenParsed: Record<string, unknown> | undefined): string[] {
  const realmAccess = tokenParsed?.['realm_access'] as { roles?: string[] } | undefined
  return realmAccess?.roles ?? []
}

function buildDisplayName(
  tokenParsed: Record<string, unknown> | undefined,
  username: string | undefined,
): string | undefined {
  const first = (tokenParsed?.['given_name'] as string | undefined)?.trim()
  const last = (tokenParsed?.['family_name'] as string | undefined)?.trim()
  const fullName = [first, last].filter(Boolean).join(' ')
  return fullName || username
}

function resolveAvatarUrl(raw: string | undefined): string | undefined {
  if (!raw) return undefined
  // Base64 data URL — use as-is
  if (raw.startsWith('data:')) return raw
  // Already absolute — use as-is
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw
  // Relative path from Keycloak — prepend the auth server base URL
  const base = (keycloak.authServerUrl || '').replace(/\/+$/, '')
  return base ? `${base}${raw.startsWith('/') ? '' : '/'}${raw}` : undefined
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(keycloak.authenticated ?? false)
  const [token, setToken] = useState<string | undefined>(keycloak.token)
  const [username, setUsername] = useState<string | undefined>(
    keycloak.tokenParsed?.['preferred_username'] as string | undefined,
  )
  const [displayName, setDisplayName] = useState<string | undefined>(() =>
    buildDisplayName(keycloak.tokenParsed, keycloak.tokenParsed?.['preferred_username'] as string | undefined),
  )
  const [avatar, setAvatar] = useState<string | undefined>(
    resolveAvatarUrl(keycloak.tokenParsed?.['avatar'] as string | undefined),
  )
  const [roles, setRoles] = useState<string[]>(() =>
    extractRoles(keycloak.tokenParsed),
  )
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!keycloak.authenticated) return

    // Schedule proactive token refresh every 60 s, refreshing when < 30 s left
    refreshTimer.current = setInterval(async () => {
      try {
        const refreshed = await keycloak.updateToken(30)
        if (refreshed) {
          const newUsername = keycloak.tokenParsed?.['preferred_username'] as string | undefined
          setToken(keycloak.token)
          setUsername(newUsername)
          setDisplayName(buildDisplayName(keycloak.tokenParsed, newUsername))
          setAvatar(resolveAvatarUrl(keycloak.tokenParsed?.['avatar'] as string | undefined))
          setRoles(extractRoles(keycloak.tokenParsed))
        }
      } catch {
        // Refresh failed — clear auth state, let user re-login manually
        setIsAuthenticated(false)
        setToken(undefined)
        setUsername(undefined)
        setDisplayName(undefined)
        setAvatar(undefined)
        setRoles([])
      }
    }, 60_000)

    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current)
    }
  }, [])

  const login = () => keycloak.login()
  const register = () => keycloak.register()
  const logout = () => keycloak.logout()

  const isAdmin = roles.includes('fd-admin')

  return (
    <AuthContext.Provider value={{ isAuthenticated, token, username, displayName, avatar, roles, isAdmin, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// Hook re-exported via ./useAuthContext.ts to satisfy react-refresh/only-export-components
export { AuthContext }
export type { AuthContextValue }
