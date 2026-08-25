import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Package, CheckCircle, Truck, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import client from '../api/client'
import './Orders.css'

const STATUS_CONFIG = {
  processing: { icon: <Clock size={14} />, label: 'Processing', badge: 'badge-warning' },
  shipped:    { icon: <Truck size={14} />, label: 'Shipped',    badge: 'badge-accent' },
  delivered:  { icon: <CheckCircle size={14} />, label: 'Delivered', badge: 'badge-success' },
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})
  const [searchParams] = useSearchParams()
  const successOrderId = searchParams.get('success')

  useEffect(() => {
    client.get('/orders/me')
      .then(({ data }) => {
        setOrders(data)
        if (data.length > 0) {
          setExpanded({ [data[0].id]: true })
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = (id) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))

  const formatDate = (dt) =>
    new Date(dt).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })

  if (loading) return <div className="loading-spinner page"><div className="spinner" /></div>

  return (
    <div className="orders-page page page-fade">
      <div className="container">
        {successOrderId && (
          <div className="order-success-banner">
            <CheckCircle size={20} />
            <div>
              <p className="order-success-title">Order #{successOrderId} placed successfully!</p>
              <p className="order-success-sub">We'll start processing it right away. Thank you for shopping with ShopWave!</p>
            </div>
          </div>
        )}

        <div className="section-header">
          <div>
            <h1 className="section-title">My Orders</h1>
            <p className="section-subtitle">{orders.length} order{orders.length !== 1 ? 's' : ''}</p>
          </div>
        </div>

        {orders.length === 0 ? (
          <div className="empty-state">
            <Package size={64} style={{ margin: '0 auto 16px', color: 'var(--text-muted)' }} />
            <h3>No orders yet</h3>
            <p>Your order history will appear here after you make your first purchase</p>
            <Link to="/products" className="btn btn-primary" style={{ marginTop: 20 }}>
              Start Shopping
            </Link>
          </div>
        ) : (
          <div className="orders-list">
            {orders.map((order) => {
              const statusCfg = STATUS_CONFIG[order.status] || STATUS_CONFIG.processing
              const isExpanded = expanded[order.id]

              return (
                <div
                  key={order.id}
                  className={`order-card card ${order.id == successOrderId ? 'highlighted' : ''}`}
                  id={`order-${order.id}`}
                >
                  <div className="order-header" onClick={() => toggleExpand(order.id)}>
                    <div className="order-header-left">
                      <div className="order-id-badge">#{order.id}</div>
                      <div>
                        <p className="order-date">{formatDate(order.created_at)}</p>
                        <p className="order-items-count">{order.items.length} item{order.items.length !== 1 ? 's' : ''}</p>
                      </div>
                    </div>
                    <div className="order-header-right">
                      <span className={`badge ${statusCfg.badge}`}>
                        {statusCfg.icon} {statusCfg.label}
                      </span>
                      <span className="order-total">${order.total_amount.toFixed(2)}</span>
                      <button className="btn btn-ghost btn-sm">
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="order-details">
                      <div className="divider" style={{ margin: '0 0 16px' }} />

                      {/* Items */}
                      <div className="order-items">
                        {order.items.map((item) => (
                          <Link
                            key={item.id}
                            to={`/products/${item.product_id}`}
                            className="order-item"
                          >
                            <img
                              src={item.product.image_url}
                              alt={item.product.name}
                              className="order-item-img"
                            />
                            <div className="order-item-info">
                              <p className="order-item-name">{item.product.name}</p>
                              <p className="order-item-meta">
                                ×{item.quantity} &nbsp;·&nbsp; ${item.unit_price.toFixed(2)} each
                              </p>
                            </div>
                            <span className="order-item-subtotal">
                              ${(item.quantity * item.unit_price).toFixed(2)}
                            </span>
                          </Link>
                        ))}
                      </div>

                      {/* Shipping */}
                      <div className="order-shipping">
                        <p className="order-shipping-label">Shipping to</p>
                        <p className="order-shipping-addr">
                          {order.shipping_name} — {order.shipping_address}, {order.shipping_city} {order.shipping_zip}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
