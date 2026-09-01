import { useState, useEffect, useRef, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`

/**
 * useOrderTracking(orderId)
 * Opens a WebSocket to /api/orders/ws/<orderId>?token=<jwt>
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
  const MAX_RETRIES = 8

  const connect = useCallback(() => {
    if (!orderId) return

    const token = localStorage.getItem('token')
    if (!token) return

    // Build WebSocket URL
    const wsUrl = `${WS_BASE}/api/orders/ws/${orderId}?token=${token}`

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
      if (retryCount.current < MAX_RETRIES) {
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
    connect()
    return () => {
      clearTimeout(retryRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
      }
    }
  }, [connect])

  return { status, paymentStatus, connected, lastUpdate }
}
