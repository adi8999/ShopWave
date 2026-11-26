import { useState, useEffect, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''
const WS_BASE = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

/**
 * useOrderTracking(orderId)
 * Requests a short-lived single-use WebSocket ticket, then opens a WebSocket
 * to /api/orders/ws/<orderId>?ticket=<ticket>.
 * Auto-reconnects with exponential backoff on disconnect.
 *
 * Returns: { status, paymentStatus, connected, lastUpdate }
 */
export function useOrderTracking(orderId) {
  const [status, setStatus] = useState(null)
  const [paymentStatus, setPaymentStatus] = useState(null)
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)

  const wsRef = useRef(null)
  const retryRef = useRef(null)
  const retryCount = useRef(0)
  const cancelledRef = useRef(false)
  const MAX_RETRIES = 8

  const connect = useCallback(async () => {
    if (!orderId || cancelledRef.current) return

    const token = localStorage.getItem('sw_token')
    if (!token) return

    let ticket
    try {
      const resp = await fetch(`${API_BASE}/api/orders/${orderId}/ws-ticket`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!resp.ok) return
      const data = await resp.json()
      ticket = data.ticket
    } catch {
      return
    }

    if (!ticket || cancelledRef.current) return

    const wsUrl = `${WS_BASE}/api/orders/ws/${orderId}?ticket=${encodeURIComponent(ticket)}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      retryCount.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.status) setStatus(data.status)
        if (data.payment_status) setPaymentStatus(data.payment_status)
        setLastUpdate(new Date())
      } catch {}
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      if (!cancelledRef.current && retryCount.current < MAX_RETRIES) {
        const delay = Math.min(1000 * 2 ** retryCount.current, 30000)
        retryCount.current++
        retryRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [orderId])

  useEffect(() => {
    cancelledRef.current = false
    connect()
    return () => {
      cancelledRef.current = true
      clearTimeout(retryRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
      }
    }
  }, [connect])

  return { status, paymentStatus, connected, lastUpdate }
}
