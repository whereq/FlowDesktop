import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, type Entitlements, type ChatQuotaInfo } from '../api/client'

function Meter({ label, used, limit, t }: { label: string; used: number; limit: number; t: (k: string, d: string) => string }) {
  const included = limit > 0
  const pct = included ? Math.min(100, Math.round((used / limit) * 100)) : 0
  const full = included && used >= limit
  return (
    <div className="flex flex-col gap-1 py-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-[var(--fd-text)]">{label}</span>
        <span className="font-mono text-xs" style={{ color: full ? '#c8a84a' : 'var(--fd-text-dim)' }}>
          {included ? `${used} / ${limit}` : t('plan.notIncluded', 'Not included')}
        </span>
      </div>
      {included && (
        <div style={{ height: 4, background: 'var(--fd-rule)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: full ? '#c8a84a' : 'var(--color-accent)' }} />
        </div>
      )}
    </div>
  )
}

/** Current plan + usage meters + upgrade CTA (Settings → Plan & usage). */
export default function PlanUsagePanel() {
  const { t } = useTranslation()
  const [ent, setEnt] = useState<Entitlements | null>(null)
  const [quota, setQuota] = useState<ChatQuotaInfo | null>(null)

  useEffect(() => {
    let alive = true
    api.getEntitlements().then(e => { if (alive) setEnt(e) }).catch(() => {})
    api.getChatQuota().then(q => { if (alive) setQuota(q) }).catch(() => {})
    return () => { alive = false }
  }, [])

  if (!ent) return null
  const isFree = ent.tier === 'free'
  const tt = (k: string, d: string) => t(k, d)

  return (
    <div className="flex flex-col gap-1 pt-1">
      <div className="flex items-center justify-between py-1.5">
        <span className="text-sm text-[var(--fd-text)]">{t('plan.current', 'Current plan')}</span>
        <span className="text-xs font-semibold px-2 py-1 rounded"
          style={{ background: 'var(--fd-bg-elev)', color: 'var(--color-nova)', border: '1px solid var(--fd-rule)' }}>
          {ent.tier_label}
        </span>
      </div>

      {isFree && quota && quota.limit != null && (
        <div className="text-xs py-1" style={{ color: 'var(--fd-text-dim)' }}>
          {t('plan.trial', 'Free trial')}: {quota.used}/{quota.limit} {t('plan.messages', 'messages')}
          {quota.days_remaining != null && ` · ${quota.days_remaining} ${t('plan.daysLeft', 'days left')}`}
        </div>
      )}

      <Meter label={t('plan.customAgents', 'Custom agents')} used={ent.usage.custom_agents} limit={ent.limits.custom_agents} t={tt} />
      <Meter label={t('plan.schedules', 'Scheduled agents')} used={ent.usage.schedules} limit={ent.limits.schedules} t={tt} />

      <Link to="/pricing"
        className="mt-2 inline-block text-center text-xs font-semibold py-2 rounded transition-colors"
        style={{ background: 'var(--color-accent)', color: '#0A0B0D', textDecoration: 'none' }}>
        {ent.tier === 'unlimited' || ent.tier === 'admin'
          ? t('plan.managePlan', 'Manage plan')
          : t('plan.upgrade', 'Upgrade plan')} →
      </Link>
    </div>
  )
}
