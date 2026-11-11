/**
 * useNotificationSocket — connects to the real-time notification WebSocket.
 *
 * Returns:
 *   notifications  – full list fetched from the REST API + live updates appended
 *   unreadCount    – number of is_read=false items
 *   markRead       – mark one notification as read
 *   markAllRead    – mark all notifications as read
 *   isConnected    – WebSocket connection state
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import keycloak from '../auth/keycloak'
import { apiClient } from '../api/client'

export interface Notification {
  id: number
  notification_type: 'alert_triggered' | 'volume_spike' | 'sentiment_shift' | 'news_signal'
  title: string
  body: string | null
  metadata: Record<string, unknown> | null
  is_read: boolean
  created_at: string
}

const WS_URL =
  (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
  window.location.host +
  '/api/v1/me/notifications/ws'

export function useNotificationSocket(enabled: boolean) {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Initial REST fetch ───────────────────────────────────────────────────
  useEffect(() => {
    if (!enabled) return
    apiClient
      .get<Notification[]>('/me/notifications', { params: { limit: 50 } })
      .then((r) => setNotifications(r.data))
      .catch(() => {/* silently ignore — WS will deliver live updates */})
  }, [enabled])

  // ── WebSocket connection ─────────────────────────────────────────────────
  useEffect(() => {
    if (!enabled) return

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let cancelled = false

    async function connect() {
      if (cancelled) return
      try {
        // Ensure token is fresh
        if (keycloak.authenticated) {
          await keycloak.updateToken(30)
        }
        const token = keycloak.token
        if (!token) return

        const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`)
        wsRef.current = ws

        ws.onopen = () => {
          if (cancelled) { ws.close(); return }
          setIsConnected(true)
          // Heartbeat: send ping every 25 s to keep the connection alive
          pingRef.current = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('ping'), 25_000)
        }

        ws.onmessage = (evt) => {
          if (evt.data === 'pong') return
          try {
            const notif: Notification = JSON.parse(evt.data)
            setNotifications((prev) => {
              // Deduplicate by id
              if (prev.some((n) => n.id === notif.id)) return prev
              return [notif, ...prev]
            })
          } catch {/* ignore malformed */}
        }

        ws.onclose = () => {
          setIsConnected(false)
          if (pingRef.current) clearInterval(pingRef.current)
          if (!cancelled) {
            reconnectTimer = setTimeout(connect, 5_000)
          }
        }

        ws.onerror = () => ws.close()
      } catch {
        if (!cancelled) reconnectTimer = setTimeout(connect, 5_000)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (pingRef.current) clearInterval(pingRef.current)
      wsRef.current?.close()
    }
  }, [enabled])

  // ── Actions ──────────────────────────────────────────────────────────────
  const markRead = useCallback(async (id: number) => {
    await apiClient.post(`/me/notifications/${id}/read`)
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    )
  }, [])

  const markAllRead = useCallback(async () => {
    await apiClient.post('/me/notifications/read-all')
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }, [])

  const unreadCount = notifications.filter((n) => !n.is_read).length

  return { notifications, unreadCount, markRead, markAllRead, isConnected }
}
