import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type InvestorProfileData } from '../api/client'

const INPUT =
  'w-full bg-[var(--fd-surface)] border border-[var(--fd-rule)] text-[var(--fd-text)] text-sm px-2 py-1.5 ' +
  'focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]'

const RISK = ['', 'conservative', 'moderate', 'aggressive']
const HORIZON = ['', 'day', 'swing', 'long_term']
const STYLE = ['', 'value', 'growth', 'income', 'momentum', 'mixed']

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-[var(--fd-text-faint)]">{label}</span>
      {children}
    </label>
  )
}

const csv = (a?: string[] | null) => (a && a.length ? a.join(', ') : '')
const toArr = (s: string) =>
  s.split(',').map(x => x.trim()).filter(Boolean)

/** View + edit the investor profile NOVA uses to tailor analysis. User edits
 *  always win over the AI-distilled version. */
export default function InvestorProfilePanel() {
  const { t } = useTranslation()
  const [p, setP] = useState<InvestorProfileData | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let alive = true
    api.getInvestorProfile().then(d => { if (alive) setP(d) }).catch(() => { if (alive) setP({ source: 'none' }) })
    return () => { alive = false }
  }, [])

  if (!p) return null

  const set = <K extends keyof InvestorProfileData>(k: K, v: InvestorProfileData[K]) =>
    setP(prev => ({ ...(prev as InvestorProfileData), [k]: v }))

  const save = async () => {
    setSaving(true); setSaved(false)
    try {
      const next = await api.setInvestorProfile({
        risk_tolerance: p.risk_tolerance || null,
        horizon: p.horizon || null,
        style: p.style || null,
        preferred_sectors: p.preferred_sectors || null,
        avoided_sectors: p.avoided_sectors || null,
        constraints: p.constraints || null,
        goals: p.goals || null,
      })
      setP(next)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch { /* noop */ } finally { setSaving(false) }
  }

  return (
    <div className="flex flex-col gap-3 pt-1">
      <p className="text-xs text-[var(--fd-text-dim)]">
        {t('settings.profileIntro', 'NOVA tailors its analysis to this profile. It is guidance, not a directive to recommend anything.')}
      </p>

      {p.source === 'distilled' && (
        <div className="text-[10px] text-[var(--fd-text-faint)] bg-[var(--fd-surface)] border border-[var(--fd-rule)] px-2 py-1">
          {t('settings.profileDistilled', 'These were learned from your conversations. Edit and save to make them yours.')}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        <Field label={t('settings.profileRisk', 'Risk')}>
          <select className={INPUT} value={p.risk_tolerance || ''} onChange={e => set('risk_tolerance', e.target.value || null)}>
            {RISK.map(v => <option key={v} value={v}>{v ? t(`settings.risk_${v}`, v) : '—'}</option>)}
          </select>
        </Field>
        <Field label={t('settings.profileHorizon', 'Horizon')}>
          <select className={INPUT} value={p.horizon || ''} onChange={e => set('horizon', e.target.value || null)}>
            {HORIZON.map(v => <option key={v} value={v}>{v ? t(`settings.horizon_${v}`, v) : '—'}</option>)}
          </select>
        </Field>
        <Field label={t('settings.profileStyle', 'Style')}>
          <select className={INPUT} value={p.style || ''} onChange={e => set('style', e.target.value || null)}>
            {STYLE.map(v => <option key={v} value={v}>{v ? t(`settings.style_${v}`, v) : '—'}</option>)}
          </select>
        </Field>
      </div>

      <Field label={t('settings.profilePreferred', 'Preferred sectors (comma-separated)')}>
        <input className={INPUT} value={csv(p.preferred_sectors)} onChange={e => set('preferred_sectors', toArr(e.target.value))} placeholder="Technology, Health Care" />
      </Field>
      <Field label={t('settings.profileAvoided', 'Avoided sectors (comma-separated)')}>
        <input className={INPUT} value={csv(p.avoided_sectors)} onChange={e => set('avoided_sectors', toArr(e.target.value))} placeholder="Energy" />
      </Field>
      <Field label={t('settings.profileGoals', 'Goals')}>
        <textarea className={INPUT} rows={2} value={p.goals || ''} onChange={e => set('goals', e.target.value)} placeholder={t('settings.profileGoalsPh', 'e.g. long-term retirement growth')} />
      </Field>
      <Field label={t('settings.profileConstraints', 'Constraints')}>
        <textarea className={INPUT} rows={2} value={p.constraints || ''} onChange={e => set('constraints', e.target.value)} placeholder={t('settings.profileConstraintsPh', 'e.g. no leverage, ESG-conscious')} />
      </Field>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="text-sm px-3 py-1.5 bg-[var(--color-accent)] text-white disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {saving ? t('common.saving', 'Saving…') : t('common.save', 'Save')}
        </button>
        {saved && <span className="text-xs text-[var(--color-accent)]">{t('settings.profileSaved', 'Saved')}</span>}
      </div>
    </div>
  )
}
