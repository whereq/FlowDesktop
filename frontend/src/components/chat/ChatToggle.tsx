import { useTranslation } from 'react-i18next'
import { useLLMContext } from '../../contexts/useLLMContext'
import novaUrl from '../../assets/nova.png'

interface ChatToggleProps {
  onClick: () => void
  isOpen: boolean
}

export default function ChatToggle({ onClick, isOpen }: ChatToggleProps) {
  const { t } = useTranslation()
  const { provider, getApiKeyForProvider } = useLLMContext()

  if (isOpen) return null

  const isActivated = provider ? !!getApiKeyForProvider(provider) : false

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={t('chat.title')}
      title={t('chat.title')}
      style={{
        position: 'fixed',
        zIndex: 50,
        bottom: 76,
        right: 16,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        borderRadius: 2,
        background: 'var(--color-nova)',
        color: '#0A0B0D',
        fontFamily: 'var(--font-ui)',
        fontWeight: 600,
        fontSize: 13,
        boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        border: 'none',
        cursor: 'pointer',
      }}
    >
      <img
        src={novaUrl}
        alt=""
        aria-hidden="true"
        style={{ width: 18, height: 18, borderRadius: 2, objectFit: 'cover', display: 'block' }}
      />
      NOVA
      <kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10, padding: '1px 5px', background: 'rgba(0,0,0,0.15)', borderRadius: 2 }}>⌘K</kbd>

      {isActivated && (
        <span style={{
          position: 'absolute', top: 2, right: 2,
          width: 8, height: 8,
          background: 'var(--color-stock-up)',
          borderRadius: '50%',
          border: '2px solid var(--color-nova)',
        }} />
      )}
    </button>
  )
}
