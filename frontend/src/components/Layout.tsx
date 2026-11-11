import { type ReactNode } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, useRef, useEffect, startTransition } from 'react'
import { useTranslation } from 'react-i18next'
import { FDLogo } from './ui'
import SearchBar from './SearchBar'
import AlertNotificationBell from './AlertNotificationBell'
import NotificationCentre from './NotificationCentre'
import UserAvatar from './icons/UserAvatar'
import { useAuth } from '../auth/useAuth'
import { useAvatar } from '../contexts/useAvatarContext'
import { useTheme } from '../contexts/ThemeContext'
import { useSystemStatus } from '../hooks/useStocks'

// ── Nav items matching Direction A ───────────────────────────────────────────

const NAV_ITEMS = [
  { id: '/',             en: 'Dashboard', zh: '概览',   icon: 'grid' },
  { id: '/watchlist',    en: 'Watchlist',  zh: '自选',   icon: 'star' },
  { id: '/sectors',      en: 'Sectors',   zh: '板块',   icon: 'layers' },
  { id: '/intelligence', en: 'Intel',     zh: '情报',   icon: 'newspaper' },
  { id: '/calendar',     en: 'Calendar',  zh: '日历',   icon: 'calendar' },
  { id: '/agents',       en: 'Agents',    zh: '智能体', icon: 'sparkles' },
  { id: '/simulator',    en: 'Simulator', zh: '模拟盘', icon: 'trending' },
  { id: '/history',      en: 'History',   zh: '历史',   icon: 'history' },
] as const

// Simple SVG icons for nav (matching design's icon set)
function NavIcon({ name, size = 14 }: { name: string; size?: number }) {
  const s = { width: size, height: size, display: 'inline-block', flexShrink: 0 } as const
  switch (name) {
    case 'grid':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
    case 'star':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
    case 'layers':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
    case 'newspaper':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1m2 13a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2Z"/><line x1="5" y1="10" x2="13" y2="10"/><line x1="5" y1="14" x2="8" y2="14"/></svg>
    case 'history':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
    case 'calendar':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
    case 'search':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    case 'sparkles':
      return <svg style={s} viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/></svg>
    case 'trending':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
    case 'bell':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
    case 'sun':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
    case 'moon':
      return <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    default:
      return <span style={s} />
  }
}

// ── Dropdown menu components ─────────────────────────────────────────────────

function MenuItem({
  to, onClick, icon, label, highlight,
}: {
  to?: string; onClick?: () => void; icon?: ReactNode; label: string; highlight?: boolean
}) {
  const cls = `flex items-center gap-2.5 w-full px-4 py-2 text-[12px] transition-colors ${
    highlight ? 'text-[var(--color-stock-down)]' : 'text-[var(--fd-text)]'
  }`
  const hoverStyle = { background: 'var(--fd-hover-bg)' }
  if (to) {
    return (
      <Link to={to} onClick={onClick} className={cls}
        onMouseEnter={e => Object.assign(e.currentTarget.style, hoverStyle)}
        onMouseLeave={e => { e.currentTarget.style.background = '' }}>
        {icon && <span style={{ color: 'var(--fd-text-faint)', flexShrink: 0 }}>{icon}</span>}
        {label}
      </Link>
    )
  }
  return (
    <button type="button" onClick={onClick} className={cls}
      onMouseEnter={e => Object.assign(e.currentTarget.style, hoverStyle)}
      onMouseLeave={e => { e.currentTarget.style.background = '' }}>
      {icon && <span style={{ color: highlight ? 'var(--color-stock-down)' : 'var(--fd-text-faint)', flexShrink: 0 }}>{icon}</span>}
      {label}
    </button>
  )
}

// ── Inline icons ─────────────────────────────────────────────────────────────

const IconSettings = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)
const IconGuide = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
)
const IconPricing = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 1 0 0 7h5a3.5 3.5 0 1 1 0 7H6"/>
  </svg>
)
const IconNova = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/>
  </svg>
)
const IconStatus = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
  </svg>
)
const IconAdmin = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
)
const IconProfile = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
)
const IconSignOut = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)
const IconSignIn = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>
  </svg>
)

// ── Layout ────────────────────────────────────────────────────────────────────

export default function Layout() {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const lang = i18n.language

  const { isAuthenticated, displayName, login, logout, register, roles } = useAuth()
  const { effectiveUrl } = useAvatar()
  const avatar = isAuthenticated ? effectiveUrl : null
  const isAdmin = roles.includes('fd-admin')
  const { toggleTheme, isDark } = useTheme()

  const { data: statusData } = useSystemStatus({ enabled: isAuthenticated })
  const lastQuote = statusData?.db?.last_quote
  const fmtLastUpdate = (iso: string | null | undefined) => {
    if (!iso) return null
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    startTransition(() => {
      setUserMenuOpen(false)
      setMobileMenuOpen(false)
    })
  }, [location.pathname])

  const closeAll = () => {
    setUserMenuOpen(false)
    setMobileMenuOpen(false)
  }

  const firstName = displayName?.split(' ')[0] ?? displayName ?? ''

  // Determine which nav item is active
  const activeNav = NAV_ITEMS.find(n => n.id === location.pathname)?.id || '/'

  return (
    <div style={{ background: 'var(--fd-bg)', color: 'var(--fd-text)', fontFamily: 'var(--font-ui)' }}
      className="min-h-screen flex flex-col">

      {/* ── Top Bar (Direction A style) ────────────────────────────────────── */}
      <header style={{ borderBottom: '1px solid var(--fd-rule)', background: 'var(--fd-bg)' }}
        className="sticky top-0 z-50">
        <div className="flex items-center gap-4 px-4 py-2.5 lg:gap-6">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 shrink-0">
            {/* FDLogo forces display:inline-flex inline, which overrides a `hidden`
                utility on its own className — so wrap in spans to toggle responsively
                (otherwise both the word + icon-only marks render at once). */}
            <span className="hidden sm:inline-flex">
              <FDLogo size={18} accent="var(--color-accent)" showWord />
            </span>
            <span className="sm:hidden">
              <FDLogo size={18} accent="var(--color-accent)" showWord={false} />
            </span>
          </Link>
          <span className="hidden xl:block text-[10px] tracking-[0.1em] shrink-0"
            style={{ color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)' }}>
            DEEP STOCK ANALYSIS
          </span>

          {/* Center: desktop nav + command bar */}
          <div className="flex-1 flex items-center gap-2 justify-center">
            {/* Desktop nav pills */}
            <nav className="hidden lg:flex gap-0.5 p-0.5 shrink-0" style={{ border: '1px solid var(--fd-rule)', borderRadius: 4 }}>
              {NAV_ITEMS.map(n => {
                const isActive = activeNav === n.id
                const needsAuth = n.id !== '/'
                return (
                  <Link
                    key={n.id}
                    to={n.id}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium transition-colors"
                    style={{
                      color: isActive ? 'var(--fd-text)' : 'var(--fd-text-dim)',
                      background: isActive ? 'var(--fd-active-bg)' : 'transparent',
                      borderRadius: 3,
                      fontFamily: 'var(--font-ui)',
                      opacity: needsAuth && !isAuthenticated ? 0.5 : 1,
                    }}
                  >
                    <NavIcon name={n.icon} size={13} />
                    {lang === 'zh' ? n.zh : n.en}
                  </Link>
                )
              })}
            </nav>

            {/* Command bar / search */}
            <div className="flex-1 max-w-sm lg:max-w-xs">
              <SearchBar disabled={!isAuthenticated} />
            </div>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
              style={{ border: '1px solid var(--fd-rule)', borderRadius: 4, color: 'var(--fd-text-dim)' }}
              className="w-7 h-7 flex items-center justify-center shrink-0"
            >
              <NavIcon name={isDark ? 'sun' : 'moon'} size={13} />
            </button>

            {/* Language toggle */}
            <div className="flex p-0.5 shrink-0" style={{ border: '1px solid var(--fd-rule)', borderRadius: 4 }}>
              <button
                onClick={() => i18n.changeLanguage('en')}
                className="px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: lang === 'en' ? 'var(--fd-text)' : 'var(--fd-text-faint)',
                  background: lang === 'en' ? 'var(--fd-active-bg)' : 'transparent',
                  borderRadius: 2,
                }}
              >EN</button>
              <button
                onClick={() => i18n.changeLanguage('zh')}
                className="px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: lang === 'zh' ? 'var(--fd-text)' : 'var(--fd-text-faint)',
                  background: lang === 'zh' ? 'var(--fd-active-bg)' : 'transparent',
                  borderRadius: 2,
                }}
              >中</button>
            </div>

            {/* Notifications (desktop) */}
            {isAuthenticated && (
              <div className="hidden md:flex items-center gap-1">
                <AlertNotificationBell />
                <NotificationCentre />
              </div>
            )}

            {/* User menu */}
            <div className="relative hidden md:block" ref={userMenuRef}>
              {isAuthenticated ? (
                <button
                  type="button"
                  onClick={() => setUserMenuOpen(o => !o)}
                  className="flex items-center gap-2 px-1.5 py-1"
                  style={{
                    border: '1px solid var(--fd-rule)',
                    borderRadius: 4,
                    background: userMenuOpen ? 'var(--fd-active-bg)' : 'transparent',
                  }}
                >
                  <UserAvatar avatar={avatar} isAuthenticated={isAuthenticated} size={26} />
                  {firstName && (
                    <span className="text-[12px] max-w-[80px] truncate hidden lg:block"
                      style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)' }}>
                      {firstName}
                    </span>
                  )}
                </button>
              ) : (
                <div className="flex items-center gap-1.5">
                  {/* Guest face icon */}
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen(o => !o)}
                    className="flex items-center justify-center"
                    style={{ width: 30, height: 30, border: '1px solid var(--fd-rule)', borderRadius: 4 }}
                    title={t('auth.guest')}
                  >
                    <UserAvatar avatar={null} isAuthenticated={false} size={22} />
                  </button>
                  {/* Sign-in button */}
                  <button
                    type="button"
                    onClick={login}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-semibold"
                    style={{
                      background: 'var(--color-accent)',
                      color: '#0A0B0D',
                      border: 'none',
                      borderRadius: 4,
                    }}
                  >
                    <IconSignIn />
                    {t('auth.signIn')}
                  </button>
                </div>
              )}

              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-1 w-52 py-1 z-50 shadow-2xl"
                  style={{ background: 'var(--fd-bg-elev)', border: '1px solid var(--fd-rule)' }}>
                  {/* User info */}
                  <div className="flex items-center gap-2.5 px-4 py-2.5" style={{ borderBottom: '1px solid var(--fd-rule)' }}>
                    <UserAvatar avatar={avatar} isAuthenticated={isAuthenticated} size={28} />
                    <div className="min-w-0">
                      <p className="text-[12px] font-semibold truncate" style={{ color: 'var(--fd-text)' }}>
                        {isAuthenticated ? (displayName || t('auth.guest')) : t('auth.guest')}
                      </p>
                      <p className="text-[10px]" style={{ color: 'var(--fd-text-faint)' }}>
                        {isAuthenticated ? t('auth.signedIn') : t('auth.browsingAsGuest')}
                      </p>
                    </div>
                  </div>

                  {isAuthenticated && (
                    <>
                      <div className="py-1">
                        <MenuItem to="/profile" onClick={closeAll} icon={<IconProfile />} label={t('nav.profile')} />
                        <MenuItem to="/settings" onClick={closeAll} icon={<IconSettings />} label={t('settings.title')} />
                        <MenuItem to="/guide" onClick={closeAll} icon={<IconGuide />} label={t('nav.guide')} />
                        <MenuItem to="/pricing" onClick={closeAll} icon={<IconPricing />} label={t('nav.pricing')} />
                        <MenuItem to="/about" onClick={closeAll} icon={<IconNova />} label={t('nav.about')} />
                        {isAdmin && <MenuItem to="/system-status" onClick={closeAll} icon={<IconStatus />} label={t('nav.systemStatus')} />}
                        {isAdmin && <MenuItem to="/admin" onClick={closeAll} icon={<IconAdmin />} label={t('admin.navLabel')} />}
                      </div>
                      <div className="my-1" style={{ borderTop: '1px solid var(--fd-rule)' }} />
                      <div className="py-1">
                        <MenuItem onClick={() => { logout(); closeAll() }} icon={<IconSignOut />} label={t('auth.signOut')} highlight />
                      </div>
                    </>
                  )}

                  {!isAuthenticated && (
                    <div className="py-1">
                      <MenuItem onClick={() => { login(); closeAll() }} icon={<IconSignIn />} label={t('auth.signIn')} />
                      <MenuItem onClick={() => { register(); closeAll() }} icon={<IconSignIn />} label={t('auth.signUp')} />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileMenuOpen(o => !o)}
              className="md:hidden w-8 h-8 flex items-center justify-center"
              style={{ color: 'var(--fd-text-dim)' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {mobileMenuOpen
                  ? <path d="M6 18L18 6M6 6l12 12" />
                  : <path d="M4 6h16M4 12h16M4 18h16" />
                }
              </svg>
            </button>
          </div>
        </div>

        {/* ── Mobile drawer ────────────────────────────────────────────────── */}
        {mobileMenuOpen && (
          <div className="lg:hidden" style={{ borderTop: '1px solid var(--fd-rule)', background: 'var(--fd-bg-elev)' }}>
            {/* User info */}
            <div className="flex items-center gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--fd-rule)' }}>
              <UserAvatar avatar={avatar} isAuthenticated={isAuthenticated} size={32} />
              <div>
                <p className="text-[13px] font-semibold" style={{ color: 'var(--fd-text)' }}>
                  {isAuthenticated ? (displayName || t('auth.guest')) : t('auth.guest')}
                </p>
                <p className="text-[10px]" style={{ color: 'var(--fd-text-faint)' }}>
                  {isAuthenticated ? t('auth.signedIn') : t('auth.browsingAsGuest')}
                </p>
              </div>
            </div>

            <div className="px-2 py-2 space-y-0.5">
              {NAV_ITEMS.map(n => (
                <Link key={n.id} to={n.id} onClick={closeAll}
                  className="flex items-center gap-2.5 px-3 py-2 text-[12px]"
                  style={{
                    color: activeNav === n.id ? 'var(--fd-text)' : 'var(--fd-text-dim)',
                    background: activeNav === n.id ? 'var(--fd-active-bg)' : 'transparent',
                  }}>
                  <NavIcon name={n.icon} size={14} />
                  {lang === 'zh' ? n.zh : n.en}
                </Link>
              ))}

              <div style={{ borderTop: '1px solid var(--fd-rule)' }} className="my-1.5" />

              <Link to="/guide" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                <span style={{ color: 'var(--fd-text-faint)' }}><IconGuide /></span>{t('nav.guide')}
              </Link>
              <Link to="/pricing" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                <span style={{ color: 'var(--fd-text-faint)' }}><IconPricing /></span>{t('nav.pricing')}
              </Link>
              <Link to="/about" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                <span style={{ color: 'var(--fd-text-faint)' }}><IconNova /></span>{t('nav.about')}
              </Link>

              {isAuthenticated && (
                <>
                  <div style={{ borderTop: '1px solid var(--fd-rule)' }} className="my-1.5" />
                  <Link to="/settings" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                    <span style={{ color: 'var(--fd-text-faint)' }}><IconSettings /></span>{t('settings.title')}
                  </Link>
                  {isAdmin && (
                    <Link to="/system-status" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                      <span style={{ color: 'var(--fd-text-faint)' }}><IconStatus /></span>{t('nav.systemStatus')}
                    </Link>
                  )}
                  {isAdmin && (
                    <Link to="/admin" onClick={closeAll} className="flex items-center gap-2.5 px-3 py-2 text-[12px]" style={{ color: 'var(--fd-text-dim)' }}>
                      <span style={{ color: 'var(--fd-text-faint)' }}><IconAdmin /></span>{t('admin.navLabel')}
                    </Link>
                  )}
                </>
              )}

              <div style={{ borderTop: '1px solid var(--fd-rule)' }} className="my-1.5" />

              {isAuthenticated ? (
                <button onClick={() => { logout(); closeAll() }}
                  className="flex items-center gap-2.5 w-full px-3 py-2 text-[12px]"
                  style={{ color: 'var(--color-stock-down)' }}>
                  <IconSignOut />{t('auth.signOut')}
                </button>
              ) : (
                <div className="flex gap-2 px-2 py-1">
                  <button onClick={() => { login(); closeAll() }}
                    className="flex-1 py-2 text-[12px] font-semibold"
                    style={{ background: 'var(--color-accent)', color: '#0A0B0D' }}>
                    {t('auth.signIn')}
                  </button>
                  <button onClick={() => { register(); closeAll() }}
                    className="flex-1 py-2 text-[12px] font-semibold"
                    style={{ color: 'var(--color-accent)', border: '1px solid var(--color-accent)' }}>
                    {t('auth.signUp')}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <Outlet />
        </div>
      </main>

      {/* ── Status Bar (desktop) / Bottom Nav (mobile) ─────────────────────── */}
      {/* Desktop: terminal-style status bar */}
      <footer className="hidden md:flex items-center gap-5 px-4 py-1.5 shrink-0"
        style={{ borderTop: '1px solid var(--fd-rule)', background: 'var(--fd-bg)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.05em', color: 'var(--fd-text-dim)' }}>
        <span className="inline-flex items-center gap-1.5">
          <span style={{ width: 6, height: 6, background: 'var(--color-stock-up)', borderRadius: '50%' }} />
          <span style={{ color: 'var(--fd-text)' }}>{lang === 'zh' ? '市场 · 开盘' : 'MARKET · OPEN'}</span>
          <span style={{ color: 'var(--fd-text-faint)' }}>NY {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York' })} EDT</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span style={{ width: 6, height: 6, background: 'var(--color-nova)', borderRadius: '50%' }} />
          <span style={{ color: 'var(--fd-text)' }}>{lang === 'zh' ? 'NOVA · 就绪' : 'NOVA · READY'}</span>
          <span style={{ color: 'var(--fd-text-faint)' }}>v0.4-preview</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span style={{ width: 6, height: 6, background: 'var(--color-accent)', borderRadius: '50%' }} />
          <span style={{ color: 'var(--fd-text)' }}>{lang === 'zh' ? '数据 · 近实时' : 'DATA · NEAR-RT'}</span>
          {lastQuote && <span style={{ color: 'var(--fd-text-faint)' }}>{fmtLastUpdate(lastQuote)}</span>}
        </span>
        <span className="flex-1" />
        <span>
          {lang === 'zh' ? '提示' : 'TIP'}: <span style={{ color: 'var(--fd-text)' }}>{lang === 'zh' ? '按 ⌘K 在任意页面唤起 NOVA' : 'press ⌘K to summon NOVA from anywhere'}</span>
        </span>
      </footer>

      {/* Mobile: bottom tab bar */}
      <nav className="md:hidden grid grid-cols-5 items-center shrink-0"
        style={{
          borderTop: '1px solid var(--fd-rule)',
          background: 'var(--fd-bg)',
          padding: '6px 6px calc(6px + env(safe-area-inset-bottom, 0px))',
          fontFamily: 'var(--font-ui)',
        }}>
        {NAV_ITEMS.slice(0, 2).map(n => {
          const active = activeNav === n.id
          return (
            <Link key={n.id} to={n.id}
              className="flex flex-col items-center gap-1 py-1"
              style={{ color: active ? 'var(--color-accent)' : 'var(--fd-text-dim)' }}>
              <NavIcon name={n.icon} size={19} />
              <span style={{ fontSize: 9.5, fontWeight: active ? 600 : 400 }}>{lang === 'zh' ? n.zh : n.en}</span>
            </Link>
          )
        })}
        {/* Center NOVA button */}
        <button
          onClick={() => navigate('/about')}
          className="flex justify-center"
        >
          <span style={{
            width: 44, height: 44, marginTop: -18, borderRadius: 14,
            background: 'var(--color-nova)', color: '#0A0B0D',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 6px 16px rgba(0,0,0,0.4)',
          }}>
            <NavIcon name="sparkles" size={20} />
          </span>
        </button>
        {NAV_ITEMS.slice(2, 4).map(n => {
          const active = activeNav === n.id
          return (
            <Link key={n.id} to={n.id}
              className="flex flex-col items-center gap-1 py-1"
              style={{ color: active ? 'var(--color-accent)' : 'var(--fd-text-dim)' }}>
              <NavIcon name={n.icon} size={19} />
              <span style={{ fontSize: 9.5, fontWeight: active ? 600 : 400 }}>{lang === 'zh' ? n.zh : n.en}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
