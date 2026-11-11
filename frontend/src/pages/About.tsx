import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useLLMContext } from '../contexts/useLLMContext'
import novaUrl from '../assets/nova.png'

const CAPABILITIES = [
  { key: 'analyze',   icon: '📈' },
  { key: 'committee', icon: '⚖️' },
  { key: 'macro',     icon: '🌐' },
  { key: 'strategy',  icon: '🧪' },
  { key: 'screen',    icon: '🔍' },
  { key: 'portfolio', icon: '💼' },
]

const PROVIDERS = ['OpenAI GPT-4o', 'Anthropic Claude', 'Google Gemini', 'DeepSeek', 'Alibaba Qwen', 'MiniMax']

export default function About() {
  const { t } = useTranslation()
  const { openChat } = useLLMContext()

  return (
    <div className="max-w-3xl mx-auto py-8 space-y-12">

      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <div className="flex items-start gap-6">
        <div className="relative shrink-0">
          <img
            src={novaUrl}
            alt="NOVA"
            className="avatar-circle"
            style={{ width: 96, height: 96, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--color-accent)' }}
          />
          <span className="absolute -bottom-1 -right-1 text-[10px] font-bold bg-[var(--color-accent)] text-white px-1.5 py-0.5">AI</span>
        </div>
        <div className="min-w-0">
          <h1 className="text-3xl font-bold text-[var(--fd-text-primary)] tracking-tight">{t('about.headline')}</h1>
          <p className="text-[var(--color-accent)] text-sm font-semibold tracking-widest uppercase mt-1">{t('about.tagline')}</p>
          <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mt-3">{t('about.intro')}</p>
        </div>
      </div>

      {/* ── Capabilities ─────────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 mb-4">
          {t('about.capTitle')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--fd-rule)]">
          {CAPABILITIES.map(({ key, icon }) => (
            <div key={key} className="bg-[var(--fd-bg)] px-4 py-3 flex gap-3 items-start">
              <span className="text-xl shrink-0 mt-0.5">{icon}</span>
              <div>
                <p className="text-sm font-semibold text-[#c8d8ea]">{t(`commands.${key}.label`)}</p>
                <p className="text-[11px] text-[#5a8aaa] leading-snug mt-0.5">{t(`commands.${key}.desc`)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Powered by ───────────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 mb-4">
          {t('about.poweredTitle')}
        </h2>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{t('about.poweredBody')}</p>
        <div className="flex flex-wrap gap-2">
          {PROVIDERS.map(p => (
            <span key={p} className="text-[11px] px-2.5 py-1 bg-[var(--fd-bg-elev)] border border-[var(--fd-rule-strong)] text-[#7ab0d8]">
              {p}
            </span>
          ))}
        </div>
      </section>

      {/* ── Privacy ──────────────────────────────────────────────────────────── */}
      <section className="bg-[#080f18] border border-[var(--fd-rule)] px-5 py-4">
        <h2 className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 mb-3">
          {t('about.privacyTitle')}
        </h2>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{t('about.privacyBody')}</p>
      </section>

      {/* ── Name origin ──────────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 mb-3">
          {t('about.nameTitle')}
        </h2>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{t('about.nameBody')}</p>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-center pt-2">
        <button
          onClick={openChat}
          className="px-6 py-2.5 bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-sm font-semibold transition-colors"
        >
          {t('about.getStarted')}
        </button>
        <Link to="/pricing" className="px-6 py-2.5 border border-[var(--color-accent)]/50 hover:border-[var(--color-accent)] text-[var(--color-accent)] text-sm font-semibold transition-colors">
          {t('nav.pricing')}
        </Link>
      </div>
    </div>
  )
}
