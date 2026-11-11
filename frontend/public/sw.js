/* FlowDesktop service worker — Web Push delivery + PWA app shell.
 * Push: shows backend notifications and routes clicks.
 * PWA: caches the app shell so FlowDesktop is installable and works offline. */

const SHELL_CACHE = 'flowdesktop-shell-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.add('/')).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  // Navigations: network-first (always fresh online), fall back to cached shell offline.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone()
          caches.open(SHELL_CACHE).then((c) => c.put('/', copy)).catch(() => {})
          return resp
        })
        .catch(() => caches.match('/'))
    )
  }
})

self.addEventListener('push', (event) => {
  let payload
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { title: 'FlowDesktop', body: event.data ? event.data.text() : '' }
  }
  const title = payload.title || 'FlowDesktop'
  const options = {
    body: payload.body || '',
    icon: '/nova.png',
    badge: '/logo.svg',
    data: payload.data || {},
    tag: (payload.data && payload.data.type) || undefined,
    renotify: false,
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ('focus' in w) {
          if ('navigate' in w) { try { w.navigate(url) } catch { /* cross-origin guard */ } }
          return w.focus()
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })
  )
})
