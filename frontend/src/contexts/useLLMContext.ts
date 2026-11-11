import { useContext } from 'react'
import { LLMContext, type LLMContextValue } from './LLMContext'

export type { LLMContextValue }

/** Access the LLM configuration context. Must be used inside <LLMProvider>. */
export function useLLMContext(): LLMContextValue {
  const ctx = useContext(LLMContext)
  if (!ctx) throw new Error('useLLMContext must be used inside <LLMProvider>')
  return ctx
}
