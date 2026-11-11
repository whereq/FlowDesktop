import { type ReactNode, useEffect, useRef } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { WatchlistProvider } from './contexts/WatchlistContext'
import { LLMProvider } from './contexts/LLMContext'
import { useLLMContext } from './contexts/useLLMContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import StockDetail from './pages/StockDetail'
import Watchlist from './pages/Watchlist'
import Settings from './pages/Settings'
import Pricing from './pages/Pricing'
import About from './pages/About'
import Guide from './pages/Guide'
import ConversationHistoryPage from './pages/ConversationHistoryPage'
import SystemStatus from './pages/SystemStatus'
import AdminDashboard from './pages/AdminDashboard'
import Sectors from './pages/Sectors'
import Simulator from './pages/Simulator'
import Intelligence from './pages/Intelligence'
import Agents from './pages/Agents'
import Calendar from './pages/Calendar'
import { useAuth } from './auth/useAuth'
import ChatToggle from './components/chat/ChatToggle'
import ChatPanel from './components/chat/ChatPanel'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, login, register } = useAuth()
  const { t } = useTranslation()

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-5 text-center">
        <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true" style={{ color: 'var(--fd-text-faint)' }}>
          <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1}
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <p className="text-sm" style={{ color: 'var(--fd-text-dim)' }}>{t('auth.signInRequired')}</p>
        <div className="flex gap-3">
          <button
            onClick={login}
            className="px-4 py-2 text-sm font-semibold transition-colors"
            style={{ background: 'var(--color-accent)', color: '#0A0B0D' }}
          >
            {t('auth.signIn')}
          </button>
          <button
            onClick={register}
            className="px-4 py-2 text-sm font-semibold transition-colors"
            style={{ color: 'var(--color-accent)', border: '1px solid var(--color-accent)' }}
          >
            {t('auth.signUp')}
          </button>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

function AdminRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, roles } = useAuth()
  const { t } = useTranslation()

  if (!isAuthenticated || !roles.includes('fd-admin')) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
        <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true" style={{ color: 'var(--fd-text-faint)' }}>
          <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1}
            d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        <p className="text-sm" style={{ color: 'var(--fd-text-dim)' }}>{t('auth.adminRequired')}</p>
      </div>
    )
  }

  return <>{children}</>
}

/** Pages where the NOVA chat panel may be opened. */
const CHAT_ELIGIBLE_PATHS = ['/', '/watchlist', '/sectors', '/intelligence', '/agents']

function AppInner() {
  const { isAuthenticated } = useAuth()
  const { chatOpen, closeChat, toggleChat, openChat, sendMessage } = useLLMContext()
  const { pathname } = useLocation()
  const askedRef = useRef(false)

  const isChatEligible = CHAT_ELIGIBLE_PATHS.includes(pathname)

  // Auto-close the chat panel when navigating away from eligible pages
  useEffect(() => {
    if (!isChatEligible && chatOpen) closeChat()
  }, [pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  // Deep link: /?ask=<text> (e.g. from a proactive NOVA Pulse push) opens NOVA
  // pre-seeded with that question, then strips the param so refreshes are clean.
  useEffect(() => {
    if (askedRef.current || !isAuthenticated) return
    const params = new URLSearchParams(window.location.search)
    const ask = params.get('ask')
    if (!ask) return
    askedRef.current = true
    window.history.replaceState({}, '', window.location.pathname)
    const id = setTimeout(() => {
      openChat()
      sendMessage(ask)
    }, 0)
    return () => clearTimeout(id)
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {isAuthenticated && isChatEligible && chatOpen && <ChatPanel onClose={closeChat} />}
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="stock/:symbol" element={<StockDetail />} />
          <Route path="watchlist" element={<ProtectedRoute><Watchlist /></ProtectedRoute>} />
          <Route path="settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="pricing" element={<Pricing />} />
          <Route path="about" element={<About />} />
          <Route path="guide" element={<Guide />} />
          <Route path="sectors" element={<ProtectedRoute><Sectors /></ProtectedRoute>} />
          <Route path="simulator" element={<ProtectedRoute><Simulator /></ProtectedRoute>} />
          <Route path="intelligence" element={<ProtectedRoute><Intelligence /></ProtectedRoute>} />
          <Route path="agents" element={<Agents />} />
          <Route path="calendar" element={<ProtectedRoute><Calendar /></ProtectedRoute>} />
          <Route path="history" element={<ProtectedRoute><ConversationHistoryPage /></ProtectedRoute>} />
          <Route path="system-status" element={<AdminRoute><SystemStatus /></AdminRoute>} />
          <Route path="admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
        </Route>
      </Routes>
      {isAuthenticated && isChatEligible && <ChatToggle onClick={toggleChat} isOpen={chatOpen} />}
    </>
  )
}

function App() {
  return (
    <WatchlistProvider>
      <LLMProvider>
        <AppInner />
      </LLMProvider>
    </WatchlistProvider>
  )
}

export default App
