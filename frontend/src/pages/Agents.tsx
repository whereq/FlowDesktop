import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type AgentInfo, type AgentSchedule, type Entitlements } from '../api/client'
import { useLLMContext } from '../contexts/useLLMContext'
import { useAuth } from '../auth/useAuth'

const LOCAL_TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' } catch { return 'UTC' } })()
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const pad = (n: number) => String(n).padStart(2, '0')

function badge(maturity: string): { label: string; color: string; bg: string } {
  if (maturity === 'stable') return { label: 'Stable', color: '#0A0B0D', bg: 'var(--color-nova)' }
  if (maturity === 'custom') return { label: 'Custom', color: '#0A0B0D', bg: 'var(--color-accent)' }
  if (maturity === 'planned') return { label: 'Planned', color: 'var(--fd-text-dim)', bg: 'var(--fd-bg-elev)' }
  return { label: 'Beta', color: 'var(--color-nova)', bg: 'var(--fd-bg-elev)' }
}

const TIER_OPTS = [
  { v: 'auto', label: 'Auto (route by question)' },
  { v: 'light', label: 'Light (fast/cheap)' },
  { v: 'heavy', label: 'Heavy (deep reasoning)' },
]

export default function Agents() {
  const { t } = useTranslation()
  const { openChat, sendMessage, setSelectedAgent } = useLLMContext()
  const { isAuthenticated, login } = useAuth()
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [mine, setMine] = useState<AgentInfo[]>([])
  const [allTools, setAllTools] = useState<{ name: string; description: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [builderOpen, setBuilderOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  // Builder form
  const [fTitle, setFTitle] = useState('')
  const [fIcon, setFIcon] = useState('🤖')
  const [fCategory, setFCategory] = useState('Custom')
  const [fDesc, setFDesc] = useState('')
  const [fPrompt, setFPrompt] = useState('')
  const [fTier, setFTier] = useState('auto')
  const [fTools, setFTools] = useState<string[]>([])
  const [fPublic, setFPublic] = useState(false)

  // Community
  const [community, setCommunity] = useState<import('../api/client').CommunityAgent[]>([])

  // Scheduling
  const [ent, setEnt] = useState<Entitlements | null>(null)
  const [schedules, setSchedules] = useState<AgentSchedule[]>([])
  const [scheduleFor, setScheduleFor] = useState<AgentInfo | null>(null)
  const [sCadence, setSCadence] = useState('daily')
  const [sWeekday, setSWeekday] = useState(0)
  const [sTime, setSTime] = useState('08:00')
  const [sPrompt, setSPrompt] = useState('')
  const [sSaving, setSSaving] = useState(false)
  const [sErr, setSErr] = useState('')

  const loadMine = () => {
    if (!isAuthenticated) return
    api.getMyAgents().then(setMine).catch(() => { /* none */ })
    api.getEntitlements().then(setEnt).catch(() => { /* ignore */ })
  }
  const loadCommunity = () => {
    api.getCommunityAgents().then(setCommunity).catch(() => { /* none */ })
  }
  const loadSchedules = () => {
    if (!isAuthenticated) return
    api.getMySchedules().then(setSchedules).catch(() => { /* none */ })
    api.getEntitlements().then(setEnt).catch(() => { /* ignore */ })
  }

  useEffect(() => {
    let alive = true
    api.getAgents().then(r => { if (alive) setAgents(r.agents) }).catch(() => {}).finally(() => { if (alive) setLoading(false) })
    api.getCommunityAgents().then(c => { if (alive) setCommunity(c) }).catch(() => {})
    if (isAuthenticated) {
      api.getAgentTools().then(ts => { if (alive) setAllTools(ts) }).catch(() => {})
      api.getMyAgents().then(a => { if (alive) setMine(a) }).catch(() => {})
      api.getMySchedules().then(s => { if (alive) setSchedules(s) }).catch(() => {})
      api.getEntitlements().then(e => { if (alive) setEnt(e) }).catch(() => {})
    }
    return () => { alive = false }
  }, [isAuthenticated])

  const openScheduler = (a: AgentInfo) => {
    if (!isAuthenticated) { login(); return }
    setScheduleFor(a)
    setSCadence('daily'); setSWeekday(0); setSTime('08:00'); setSErr('')
    setSPrompt(a.example_prompts[0] || `Run the ${a.title}.`)
  }

  const saveSchedule = async () => {
    if (!scheduleFor) return
    setSErr('')
    if (!sPrompt.trim()) { setSErr(t('agents.schedPromptReq', 'A prompt is required.')); return }
    const [hh, mm] = sTime.split(':').map(n => parseInt(n, 10))
    setSSaving(true)
    try {
      await api.createSchedule({
        agent_name: scheduleFor.name,
        prompt: sPrompt,
        cadence: sCadence,
        weekday: sCadence === 'weekly' ? sWeekday : null,
        hour: hh || 0,
        minute: mm || 0,
        tz: LOCAL_TZ,
      })
      setScheduleFor(null)
      loadSchedules()
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSErr(msg || t('agents.schedFailed', 'Could not create schedule.'))
    } finally {
      setSSaving(false)
    }
  }

  const toggleSchedule = async (s: AgentSchedule) => {
    try {
      await api.updateSchedule(s.id, {
        agent_name: s.agent_name, prompt: s.prompt, symbols: s.symbols,
        cadence: s.cadence, weekday: s.weekday, hour: s.hour, minute: s.minute,
        tz: s.tz, is_active: !s.is_active,
      })
      loadSchedules()
    } catch { /* noop */ }
  }

  const removeSchedule = async (id: number) => {
    if (!confirm(t('agents.schedDeleteConfirm', 'Delete this scheduled run?'))) return
    try { await api.deleteSchedule(id); loadSchedules() } catch { /* noop */ }
  }

  const fmtSchedule = (s: AgentSchedule) => {
    const when = s.cadence === 'weekly' ? (DAYS[s.weekday ?? 0]) : t('agents.schedDaily', 'Daily')
    return `${when} · ${pad(s.hour)}:${pad(s.minute)}`
  }

  const tryIt = (agentName: string, prompt: string) => {
    if (!isAuthenticated) { login(); return }
    setSelectedAgent(agentName)
    openChat()
    sendMessage(prompt, agentName)
  }

  const toggleTool = (name: string) =>
    setFTools(prev => prev.includes(name) ? prev.filter(t => t !== name) : (prev.length < 10 ? [...prev, name] : prev))

  const save = async () => {
    setErr('')
    if (!fTitle.trim() || !fPrompt.trim()) { setErr(t('agents.builderRequired', 'Title and instructions are required.')); return }
    setSaving(true)
    try {
      await api.createMyAgent({
        name: fTitle, title: fTitle, category: fCategory || 'Custom',
        description: fDesc, system_prompt: fPrompt, tools: fTools, model_tier: fTier, icon: fIcon,
        visibility: fPublic ? 'public' : 'private',
      })
      setBuilderOpen(false)
      setFTitle(''); setFDesc(''); setFPrompt(''); setFTools([]); setFTier('auto'); setFIcon('🤖'); setFCategory('Custom'); setFPublic(false)
      loadMine(); loadCommunity()
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErr(msg || t('agents.builderFailed', 'Could not create agent.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (name: string) => {
    if (!confirm(t('agents.deleteConfirm', 'Delete this agent?'))) return
    try { await api.deleteMyAgent(name); loadMine(); loadCommunity() } catch { /* noop */ }
  }

  const togglePublish = async (a: AgentInfo) => {
    const next = a.visibility === 'public' ? 'private' : 'public'
    try { await api.setAgentVisibility(a.name, next); loadMine(); loadCommunity() } catch { /* noop */ }
  }

  const clone = async (sourceId: number) => {
    if (!isAuthenticated) { login(); return }
    try { await api.cloneAgent(sourceId); loadMine(); loadCommunity() } catch (e) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not clone agent.')
    }
  }

  // Native agent metadata comes from the backend in English; localize it here
  // by name. Custom agents keep whatever text the user typed.
  const locTitle = (a: AgentInfo) => a.custom ? a.title : t(`agents.catalog.${a.name}.title`, a.title)
  const locDesc = (a: AgentInfo) => a.custom ? (a.description || '') : t(`agents.catalog.${a.name}.description`, a.description || '')
  const locCat = (cat: string) => t(`agents.cat.${cat}`, cat)

  // Group native agents by category
  const cats: string[] = []
  const byCat: Record<string, AgentInfo[]> = {}
  for (const a of agents) {
    if (!byCat[a.category]) { byCat[a.category] = []; cats.push(a.category) }
    byCat[a.category].push(a)
  }

  const Card = ({ a, onDelete, onPublish }: { a: AgentInfo; onDelete?: () => void; onPublish?: () => void }) => {
    const b = badge(a.maturity)
    const isPublic = a.visibility === 'public'
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--fd-bg-panel)', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>{a.icon}</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fd-text)', flex: 1 }}>{locTitle(a)}</span>
          {onPublish && isPublic && (
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-nova)', border: '1px solid var(--color-nova)', borderRadius: 2, padding: '2px 5px' }}>{t('agents.public', 'Public')}</span>
          )}
          <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: b.color, background: b.bg, border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '2px 5px' }}>{b.label}</span>
        </div>
        {locDesc(a) && <p style={{ fontSize: 12, color: 'var(--fd-text-dim)', lineHeight: 1.45, flex: 1 }}>{locDesc(a)}</p>}
        <div style={{ fontSize: 10, color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)' }}>
          {t('agents.usesTools', 'uses')} {a.tools.length} {t('agents.dataTools', 'data tools')}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button onClick={() => tryIt(a.name, a.example_prompts[0] || `Use the ${locTitle(a)}.`)}
            style={{ fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-nova)', border: 'none', borderRadius: 2, padding: '6px 14px', cursor: 'pointer' }}>
            {t('agents.tryIt', 'Try it')}
          </button>
          {isAuthenticated && (
            <button onClick={() => openScheduler(a)} title={t('agents.schedule', 'Schedule')}
              style={{ fontSize: 12, fontWeight: 600, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '6px 10px', cursor: 'pointer' }}>
              ⏰ {t('agents.schedule', 'Schedule')}
            </button>
          )}
          {onPublish && (
            <button onClick={onPublish} title={isPublic ? t('agents.unpublish', 'Unpublish') : t('agents.publish', 'Publish')}
              style={{ fontSize: 11, color: isPublic ? 'var(--color-nova)' : 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '6px 10px', cursor: 'pointer' }}>
              {isPublic ? t('agents.unpublish', 'Unpublish') : t('agents.publish', 'Publish')}
            </button>
          )}
          {onDelete && (
            <button onClick={onDelete} title={t('agents.delete', 'Delete')}
              style={{ fontSize: 11, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '6px 10px', cursor: 'pointer' }}>✕</button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, fontFamily: 'var(--font-ui)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--fd-text)' }}>{t('agents.title', 'FlowDesktop Agents')}</h1>
          <p style={{ fontSize: 13, color: 'var(--fd-text-dim)', marginTop: 2 }}>
            {t('agents.subtitle', 'Native AI agents that work off FlowDesktop’s live market data. Pick one and NOVA runs it for you.')}
          </p>
        </div>
        {isAuthenticated && (
          <button onClick={() => setBuilderOpen(o => !o)}
            style={{ fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-accent)', border: 'none', borderRadius: 2, padding: '7px 14px', cursor: 'pointer' }}>
            {builderOpen ? t('agents.builderClose', 'Close builder') : `+ ${t('agents.build', 'Build your own')}`}
          </button>
        )}
      </div>

      {/* Builder */}
      {builderOpen && isAuthenticated && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, background: 'var(--fd-bg-panel)', border: '1px solid var(--color-accent)', borderRadius: 2, padding: 14 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--fd-text)' }}>{t('agents.build', 'Build your own agent')}</h2>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input value={fIcon} onChange={e => setFIcon(e.target.value)} maxLength={4} placeholder="🤖" style={inp(48)} />
            <input value={fTitle} onChange={e => setFTitle(e.target.value)} placeholder={t('agents.fTitle', 'Agent name (e.g. Dividend Hunter)')} style={inp(260)} />
            <input value={fCategory} onChange={e => setFCategory(e.target.value)} placeholder={t('agents.fCategory', 'Category')} style={inp(140)} />
            <select value={fTier} onChange={e => setFTier(e.target.value)} style={inp(220)}>
              {TIER_OPTS.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
            </select>
          </div>
          <input value={fDesc} onChange={e => setFDesc(e.target.value)} placeholder={t('agents.fDesc', 'One-line description (optional)')} style={inp()} />
          <textarea value={fPrompt} onChange={e => setFPrompt(e.target.value)} rows={4}
            placeholder={t('agents.fPrompt', 'Instructions: how should this agent behave? What should it focus on?')}
            style={{ ...inp(), resize: 'vertical', fontFamily: 'var(--font-ui)' }} />
          <div>
            <div style={{ fontSize: 11, color: 'var(--fd-text-dim)', marginBottom: 4 }}>
              {t('agents.fTools', 'Data tools')} ({fTools.length}/10)
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 120, overflowY: 'auto' }}>
              {allTools.map(tool => (
                <label key={tool.name} title={tool.description}
                  style={{ fontSize: 10, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px', border: '1px solid var(--fd-rule)', borderRadius: 2, cursor: 'pointer', background: fTools.includes(tool.name) ? 'var(--fd-bg-elev)' : 'transparent', color: fTools.includes(tool.name) ? 'var(--color-nova)' : 'var(--fd-text-dim)' }}>
                  <input type="checkbox" checked={fTools.includes(tool.name)} onChange={() => toggleTool(tool.name)} style={{ width: 12, height: 12 }} />
                  {tool.name}
                </label>
              ))}
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fd-text-dim)', cursor: 'pointer' }}>
            <input type="checkbox" checked={fPublic} onChange={() => setFPublic(v => !v)} />
            {t('agents.makePublic', 'Publish to the community (others can clone it)')}
          </label>
          {err && <p style={{ fontSize: 11, color: '#c8a84a' }}>{err}</p>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={save} disabled={saving}
              style={{ fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-nova)', border: 'none', borderRadius: 2, padding: '7px 16px', cursor: 'pointer', opacity: saving ? 0.6 : 1 }}>
              {saving ? t('agents.saving', 'Saving…') : t('agents.create', 'Create agent')}
            </button>
          </div>
        </div>
      )}

      {loading && <p style={{ color: 'var(--fd-text-dim)', fontSize: 13 }}>{t('common.loading', 'Loading…')}</p>}

      {/* Scheduler modal */}
      {scheduleFor && (
        <div onClick={() => setScheduleFor(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16 }}>
          <div onClick={e => e.stopPropagation()}
            style={{ display: 'flex', flexDirection: 'column', gap: 10, background: 'var(--fd-bg-panel)', border: '1px solid var(--color-accent)', borderRadius: 2, padding: 16, width: 420, maxWidth: '100%' }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--fd-text)' }}>
              {scheduleFor.icon} {t('agents.scheduleAgent', 'Schedule')} · {locTitle(scheduleFor)}
            </h2>
            {ent && ent.limits.schedules === 0 ? (
            <>
              <p style={{ fontSize: 13, color: 'var(--fd-text-dim)', lineHeight: 1.5 }}>
                {t('agents.schedUpsell', 'Scheduled agents run automatically and deliver briefs to you — a paid feature. Upgrade to Basic or higher to let NOVA work for you on a schedule.')}
              </p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button onClick={() => setScheduleFor(null)}
                  style={{ fontSize: 12, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '7px 14px', cursor: 'pointer' }}>
                  {t('common.close', 'Close')}
                </button>
                <a href="/pricing"
                  style={{ fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-accent)', borderRadius: 2, padding: '7px 16px', cursor: 'pointer', textDecoration: 'none' }}>
                  {t('agents.upgrade', 'Upgrade')}
                </a>
              </div>
            </>
            ) : (
            <>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select value={sCadence} onChange={e => setSCadence(e.target.value)} style={inp(130)}>
                <option value="daily">{t('agents.schedDaily', 'Daily')}</option>
                <option value="weekly">{t('agents.schedWeekly', 'Weekly')}</option>
              </select>
              {sCadence === 'weekly' && (
                <select value={sWeekday} onChange={e => setSWeekday(parseInt(e.target.value, 10))} style={inp(110)}>
                  {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                </select>
              )}
              <input type="time" value={sTime} onChange={e => setSTime(e.target.value)} style={inp(110)} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)' }}>
              {t('agents.schedTz', 'Times are in your timezone')}: {LOCAL_TZ}
            </div>
            <textarea value={sPrompt} onChange={e => setSPrompt(e.target.value)} rows={3}
              placeholder={t('agents.schedPrompt', 'What should this agent do each run?')}
              style={{ ...inp(), resize: 'vertical', fontFamily: 'var(--font-ui)' }} />
            <div style={{ fontSize: 11, color: 'var(--fd-text-dim)' }}>
              {t('agents.schedDeliver', 'The brief is delivered via browser push (enable it in Settings → Notifications).')}
            </div>
            {sErr && <p style={{ fontSize: 11, color: '#c8a84a' }}>{sErr}</p>}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setScheduleFor(null)}
                style={{ fontSize: 12, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '7px 14px', cursor: 'pointer' }}>
                {t('common.cancel', 'Cancel')}
              </button>
              <button onClick={saveSchedule} disabled={sSaving}
                style={{ fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-nova)', border: 'none', borderRadius: 2, padding: '7px 16px', cursor: 'pointer', opacity: sSaving ? 0.6 : 1 }}>
                {sSaving ? t('agents.saving', 'Saving…') : t('agents.schedCreate', 'Schedule')}
              </button>
            </div>
            </>
            )}
          </div>
        </div>
      )}

      {/* Scheduled runs */}
      {schedules.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 style={catHdr}>{t('agents.scheduledRuns', 'Scheduled runs')}</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {schedules.map(s => (
              <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--fd-bg-panel)', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '8px 12px', opacity: s.is_active ? 1 : 0.55 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fd-text)' }}>
                    {s.agent_title} <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-accent)' }}>· {fmtSchedule(s)}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fd-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.prompt}</div>
                </div>
                {s.last_status && (
                  <span title={s.last_run_at || ''} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: s.last_status === 'ok' ? 'var(--color-nova)' : 'var(--fd-text-faint)' }}>{s.last_status}</span>
                )}
                <button onClick={() => toggleSchedule(s)}
                  style={{ fontSize: 11, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '4px 8px', cursor: 'pointer' }}>
                  {s.is_active ? t('agents.schedPause', 'Pause') : t('agents.schedResume', 'Resume')}
                </button>
                <button onClick={() => removeSchedule(s.id)} title={t('agents.delete', 'Delete')}
                  style={{ fontSize: 11, color: 'var(--fd-text-dim)', background: 'transparent', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '4px 8px', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* My Agents */}
      {mine.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 style={catHdr}>{t('agents.mine', 'My Agents')}</h2>
          <div style={grid}>{mine.map(a => <Card key={a.name} a={a} onDelete={() => remove(a.name)} onPublish={() => togglePublish(a)} />)}</div>
        </section>
      )}

      {/* Native catalog */}
      {!loading && cats.map(cat => (
        <section key={cat} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 style={catHdr}>{locCat(cat)}</h2>
          <div style={grid}>{byCat[cat].map(a => <Card key={a.name} a={a} />)}</div>
        </section>
      ))}

      {/* Community catalog (clone-to-run) */}
      {community.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 style={catHdr}>{t('agents.community', 'Community')}</h2>
          <div style={grid}>
            {community.map(c => (
              <div key={c.id} style={{ display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--fd-bg-panel)', border: '1px solid var(--fd-rule)', borderRadius: 2, padding: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 20, lineHeight: 1 }}>{c.icon}</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fd-text)', flex: 1 }}>{c.title}</span>
                  {c.clone_count > 0 && (
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--fd-text-faint)' }}>⎘ {c.clone_count}</span>
                  )}
                </div>
                {c.description && <p style={{ fontSize: 12, color: 'var(--fd-text-dim)', lineHeight: 1.45, flex: 1 }}>{c.description}</p>}
                <div style={{ fontSize: 10, color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)' }}>
                  {t('agents.usesTools', 'uses')} {c.tools.length} {t('agents.dataTools', 'data tools')}
                </div>
                <button onClick={() => clone(c.id)}
                  style={{ alignSelf: 'flex-start', fontSize: 12, fontWeight: 600, color: '#0A0B0D', background: 'var(--color-accent)', border: 'none', borderRadius: 2, padding: '6px 14px', cursor: 'pointer' }}>
                  {t('agents.clone', 'Clone to My Agents')}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

const grid: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }
const catHdr: React.CSSProperties = { fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--fd-text-faint)', borderLeft: '2px solid var(--color-accent)', paddingLeft: 8 }
function inp(width?: number): React.CSSProperties {
  return {
    fontSize: 12, color: 'var(--fd-text)', background: 'var(--fd-bg)', border: '1px solid var(--fd-rule)',
    borderRadius: 2, padding: '6px 8px', width: width ?? '100%', flex: width ? '0 0 auto' : undefined,
  }
}
