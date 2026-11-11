import { useContext } from 'react'
import { AvatarContext, type AvatarContextValue } from './AvatarContext'

/** Access the resolved current-user avatar. Must be used inside <AvatarProvider>. */
export function useAvatar(): AvatarContextValue {
  const ctx = useContext(AvatarContext)
  if (!ctx) throw new Error('useAvatar must be used inside <AvatarProvider>')
  return ctx
}
