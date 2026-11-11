import { useTranslation } from 'react-i18next'
import { useLLMContext } from '../../contexts/useLLMContext'

export default function ProviderBadge() {
  const { t } = useTranslation()
  const { mode, provider, providers, selectedModel } = useLLMContext()

  if (mode === 'flowdesktop') {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--fd-rule)] rounded">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--fd-text-dim)]">
          {t('chat.modePlatform')}
        </span>
      </div>
    )
  }

  if (!provider) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1 bg-[#3a2020] rounded">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-red-400">
          {t('chat.notConfigured')}
        </span>
      </div>
    )
  }

  const meta = providers.find(p => p.name === provider)
  const modelLabel = meta?.models.find(m => m.id === selectedModel)?.label ?? selectedModel

  return (
    <div className="flex items-center gap-1.5 px-3 py-1 bg-[#002a4d] rounded">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-nova)]">
        {t(`settings.aiProvider${provider.charAt(0).toUpperCase() + provider.slice(1)}`)}
      </span>
      <span className="text-[10px] text-[var(--fd-text-dim)]">/</span>
      <span className="text-[10px] text-[var(--fd-text-dim)]">{modelLabel}</span>
    </div>
  )
}
