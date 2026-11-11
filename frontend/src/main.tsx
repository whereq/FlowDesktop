import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './i18n'
import App from './App'
import './index.css'
import keycloak from './auth/keycloak'
import { AuthProvider } from './auth/AuthProvider'
import { AvatarProvider } from './contexts/AvatarContext'
import { ThemeProvider } from './contexts/ThemeContext'

// Register the service worker for PWA (installable + offline shell) and Web Push.
// Independent of the Keycloak bootstrap so install criteria are met on every load.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* non-fatal */ })
  })
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      refetchInterval: 60000,
    },
  },
})

// Bootstrap Keycloak before mounting React.
// onLoad: 'login-required' redirects unauthenticated users to Keycloak login page;
// React never renders until a valid session exists.
keycloak
  .init({
    onLoad: 'check-sso',
    pkceMethod: 'S256',
    checkLoginIframe: false,
  })
  .then(() => {
    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <ThemeProvider>
          <AuthProvider>
            <AvatarProvider>
              <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </QueryClientProvider>
            </AvatarProvider>
          </AuthProvider>
        </ThemeProvider>
      </React.StrictMode>,
    )
  })
  .catch(() => {
    // Keycloak failed to initialise — show a minimal fallback without console output
    const root = document.getElementById('root')
    if (root) {
      root.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100vh;background:#0A0B0D'
      root.innerHTML = '<p style="color:#666;font-family:sans-serif;font-size:14px">Unable to connect. Please refresh the page.</p>'
    }
  })
