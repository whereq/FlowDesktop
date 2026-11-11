export type LLMMode = 'flowdesktop' | 'byok'

export type LLMProviderName =
  | 'openai'
  | 'anthropic'
  | 'google'
  | 'deepseek'
  | 'qwen'
  | 'minimax'

export interface LLMProviderMeta {
  id: LLMProviderName
  labelKey: string
}

// Ordered list — add new providers here; UI adapts automatically
export const LLM_PROVIDERS: LLMProviderMeta[] = [
  { id: 'openai',    labelKey: 'settings.aiProviderOpenAI' },
  { id: 'anthropic', labelKey: 'settings.aiProviderAnthropic' },
  { id: 'google',    labelKey: 'settings.aiProviderGoogle' },
  { id: 'deepseek',  labelKey: 'settings.aiProviderDeepSeek' },
  { id: 'qwen',      labelKey: 'settings.aiProviderQwen' },
  { id: 'minimax',   labelKey: 'settings.aiProviderMiniMax' },
]

// Default models per provider (used as fallback when backend not available)
export const DEFAULT_MODELS: Record<LLMProviderName, string> = {
  openai:    'gpt-4o-mini',
  anthropic: 'claude-sonnet-4-20250514',
  google:    'gemini-2.0-flash',
  deepseek:  'deepseek-chat',
  qwen:      'qwen-plus',
  minimax:   'MiniMax-M3',
}
