import { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import {
  BarChart2, Package, ShoppingCart, Users, TrendingUp,
  Plus, Edit2, Trash2, X, AlertTriangle, ChevronUp, ChevronDown,
} from 'lucide-react'
import client from '../api/client'
import ProductForm from '../components/ProductForm'

/* ─── Status badge ────────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const map = {
    processing: { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
    shipped:    { color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
    delivered:  { color: '#10d97e', bg: 'rgba(16,217,126,0.15)' },
    cancelled:  { color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  }
  const { color, bg } = map[status] || { color: '#aaa', bg: 'rgba(170,170,170,0.1)' }
  return (
    <span style={{
      color, background: bg,
      padding: '2px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
      textTransform: 'capitalize',
    }}>
      {status}
    </span>
  )
}

/* ─── Metric card ────────────────────────────────────────────────── */
function MetricCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="admin-metric-card">
      <div className="metric-icon" style={{ background: `${color}22`, color }}><Icon size={22} /></div>
      <div>
        <div className="metric-value">{value}</div>
        <div className="metric-label">{label}</div>
        {sub && <div className="metric-sub">{sub}</div>}
      </div>
    </div>
  )
}

/* ─── Confirm modal ──────────────────────────────────────────────── */
function ConfirmModal({ product, onConfirm, onCancel }) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <AlertTriangle size={40} color="#ef4444" />
        <h3>Delete Product?</h3>
        <p>Are you sure you want to delete <strong>"{product.name}"</strong>? This action cannot be undone.</p>
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn-danger" onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  )
}

/* ─── Main page ──────────────────────────────────────────────────── */
export default function AdminDashboard() {
  const [tab, setTab] = useState('sales')
  const [sales, setSales] = useState(null)
  const [products, setProducts] = useState([])
  const [loadingSales, setLoadingSales] = useState(true)
  const [loadingProducts, setLoadingProducts] = useState(true)

  const [showAddForm, setShowAddForm] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deletingProduct, setDeletingProduct] = useState(null)

  const [sortKey, setSortKey] = useState('id')
  const [sortDir, setSortDir] = useState('asc')
  const [search, setSearch] = useState('')

  const fetchSales = useCallback(async () => {
    setLoadingSales(true)
    try {
      const res = await client.get('/admin/sales')
      setSales(res.data)
    } catch {
      toast.error('Failed to load sales data')
    } finally {
      setLoadingSales(false)
    }
  }, [])

  const fetchProducts = useCallback(async () => {
    setLoadingProducts(true)
    try {
      const res = await client.get('/admin/products')
      setProducts(res.data)
    } catch {
      toast.error('Failed to load products')
    } finally {
      setLoadingProducts(false)
    }
  }, [])

  useEffect(() => {
    fetchSales()
    fetchProducts()
  }, [fetchSales, fetchProducts])

  async function handleDelete() {
    try {
      await client.delete(`/admin/products/${deletingProduct.id}`)
      toast.success(`"${deletingProduct.name}" deleted`)
      setDeletingProduct(null)
      fetchProducts()
      fetchSales()
    } catch {
      toast.error('Delete failed')
    }
  }

  function toggleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('asc') }
  }

  function SortIcon({ k }) {
    if (sortKey !== k) return <ChevronUp size={12} style={{ opacity: 0.3 }} />
    return sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  const filtered = products
    .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const v = sortDir === 'asc' ? 1 : -1
      return a[sortKey] > b[sortKey] ? v : a[sortKey] < b[sortKey] ? -v : 0
    })

  return (
    <div className="admin-page">
      <div className="admin-header">
        <div>
          <h1>Admin Panel</h1>
          <p className="admin-subtitle">Manage your store products and monitor sales</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="admin-tabs">
        <button className={`admin-tab ${tab === 'sales' ? 'active' : ''}`} onClick={() => setTab('sales')}>
          <BarChart2 size={16} /> Sales Dashboard
        </button>
        <button className={`admin-tab ${tab === 'products' ? 'active' : ''}`} onClick={() => setTab('products')}>
          <Package size={16} /> Products ({products.length})
        </button>
      </div>

      {/* ── SALES TAB ── */}
      {tab === 'sales' && (
        <div className="admin-sales">
          {loadingSales ? (
            <div className="admin-loading">Loading analytics…</div>
          ) : sales ? (
            <>
              {/* Metric cards */}
              <div className="admin-metrics-grid">
                <MetricCard icon={TrendingUp} label="Total Revenue" value={`$${sales.total_revenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} color="#10d97e" />
                <MetricCard icon={ShoppingCart} label="Total Orders" value={sales.total_orders.toLocaleString()} color="#8b5cf6" />
                <MetricCard icon={Package} label="Products" value={sales.total_products} color="#3b82f6" />
                <MetricCard icon={Users} label="Customers" value={sales.total_users} color="#f59e0b" />
              </div>

              <div className="admin-two-col">
                {/* Top products */}
                <div className="admin-card">
                  <h3 className="admin-card-title">🏆 Top Products by Units Sold</h3>
                  {sales.top_products.length === 0 ? (
                    <p className="admin-empty">No sales data yet. Products will appear here after customers place orders.</p>
                  ) : (
                    <div className="top-products-list">
                      {sales.top_products.map((p, i) => (
                        <div key={p.product_id} className="top-product-row">
                          <span className="rank">#{i + 1}</span>
                          <div className="top-product-info">
                            <div className="top-product-name">{p.product_name}</div>
                            <div className="top-product-meta">{p.total_sold} units · ${p.total_revenue.toFixed(2)} revenue</div>
                          </div>
                          <div className="top-product-bar-wrap">
                            <div
                              className="top-product-bar"
                              style={{ width: `${(p.total_sold / (sales.top_products[0]?.total_sold || 1)) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Recent orders */}
                <div className="admin-card">
                  <h3 className="admin-card-title">📦 Recent Orders</h3>
                  {sales.recent_orders.length === 0 ? (
                    <p className="admin-empty">No orders yet.</p>
                  ) : (
                    <div className="recent-orders-list">
                      {sales.recent_orders.map((o) => (
                        <div key={o.id} className="recent-order-row">
                          <div>
                            <div className="recent-order-id">Order #{o.id}</div>
                            <div className="recent-order-meta">{o.shipping_name} · {o.shipping_city} · {o.item_count} items</div>
                          </div>
                          <div className="recent-order-right">
                            <div className="recent-order-amount">${o.total_amount.toFixed(2)}</div>
                            <StatusBadge status={o.status} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ── PRODUCTS TAB ── */}
      {tab === 'products' && (
        <div className="admin-products">
          {/* Toolbar */}
          <div className="admin-toolbar">
            <input
              className="admin-search"
              placeholder="Search products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button className="btn-primary admin-add-btn" onClick={() => { setShowAddForm(true); setEditingProduct(null) }}>
              <Plus size={16} /> Add Product
            </button>
          </div>

          {/* Add / Edit Form */}
          {(showAddForm || editingProduct) && (
            <div className="admin-card" style={{ marginBottom: 24 }}>
              <div className="admin-card-header">
                <h3 className="admin-card-title">{editingProduct ? `Edit: ${editingProduct.name}` : 'Add New Product'}</h3>
                <button className="icon-btn" onClick={() => { setShowAddForm(false); setEditingProduct(null) }}>
                  <X size={18} />
                </button>
              </div>
              <ProductForm
                product={editingProduct}
                onSuccess={() => {
                  setShowAddForm(false)
                  setEditingProduct(null)
                  fetchProducts()
                  fetchSales()
                }}
                onCancel={() => { setShowAddForm(false); setEditingProduct(null) }}
              />
            </div>
          )}

          {/* Products Table */}
          <div className="admin-card">
            {loadingProducts ? (
              <div className="admin-loading">Loading products…</div>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th onClick={() => toggleSort('id')} className="sortable">ID <SortIcon k="id" /></th>
                      <th style={{ minWidth: 200 }}>Product</th>
                      <th onClick={() => toggleSort('category')} className="sortable">Category <SortIcon k="category" /></th>
                      <th onClick={() => toggleSort('price')} className="sortable">Price <SortIcon k="price" /></th>
                      <th onClick={() => toggleSort('stock')} className="sortable">Stock <SortIcon k="stock" /></th>
                      <th onClick={() => toggleSort('rating')} className="sortable">Rating <SortIcon k="rating" /></th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((p) => (
                      <tr key={p.id} className={p.stock === 0 ? 'out-of-stock' : ''}>
                        <td className="text-muted">#{p.id}</td>
                        <td>
                          <div className="product-cell">
                            {p.image_url && (
                              <img src={p.image_url} alt={p.name} className="product-thumb" />
                            )}
                            <span className="product-cell-name">{p.name}</span>
                          </div>
                        </td>
                        <td><span className="cat-badge">{p.category}</span></td>
                        <td className="price-cell">${p.price.toFixed(2)}</td>
                        <td>
                          <span style={{ color: p.stock < 10 ? '#ef4444' : p.stock < 30 ? '#f59e0b' : '#10d97e', fontWeight: 600 }}>
                            {p.stock}
                          </span>
                        </td>
                        <td>⭐ {p.rating}</td>
                        <td>
                          <div className="action-btns">
                            <button
                              className="icon-btn edit-btn"
                              title="Edit"
                              onClick={() => { setEditingProduct(p); setShowAddForm(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                            >
                              <Edit2 size={15} />
                            </button>
                            <button
                              className="icon-btn delete-btn"
                              title="Delete"
                              onClick={() => setDeletingProduct(p)}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filtered.length === 0 && (
                      <tr><td colSpan={7} className="admin-empty" style={{ textAlign: 'center', padding: 40 }}>No products found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deletingProduct && (
        <ConfirmModal
          product={deletingProduct}
          onConfirm={handleDelete}
          onCancel={() => setDeletingProduct(null)}
        />
      )}
    </div>
  )
}
