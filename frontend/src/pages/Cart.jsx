import { Link } from 'react-router-dom'
import { Minus, Plus, Trash2, ShoppingBag, ArrowRight } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import './Cart.css'

export default function Cart() {
  const { items, loading, updateQuantity, removeItem, totalPrice } = useCart()
  const { isLoggedIn } = useAuth()

  if (!isLoggedIn) {
    return (
      <div className="container page page-fade">
        <div className="empty-state">
          <ShoppingBag size={64} style={{ margin: '0 auto 16px', color: 'var(--text-muted)' }} />
          <h3>Your cart awaits</h3>
          <p>Sign in to save items and check out</p>
          <Link to="/login" className="btn btn-primary" style={{ marginTop: 20 }}>
            Log In to Shop
          </Link>
        </div>
      </div>
    )
  }

  if (loading) return <div className="loading-spinner page"><div className="spinner" /></div>

  if (items.length === 0) {
    return (
      <div className="container page page-fade">
        <div className="empty-state">
          <ShoppingBag size={64} style={{ margin: '0 auto 16px', color: 'var(--text-muted)' }} />
          <h3>Your cart is empty</h3>
          <p>Looks like you haven't added anything yet</p>
          <Link to="/products" className="btn btn-primary" style={{ marginTop: 20 }}>
            Browse Products
          </Link>
        </div>
      </div>
    )
  }

  const shipping = totalPrice >= 50 ? 0 : 9.99
  const tax = totalPrice * 0.08
  const orderTotal = totalPrice + shipping + tax

  return (
    <div className="cart-page page page-fade">
      <div className="container">
        <h1 className="section-title" style={{ marginBottom: 32 }}>Your Cart</h1>

        <div className="cart-layout">
          {/* Items */}
          <div className="cart-items">
            {items.map((item) => (
              <div key={item.id} className="cart-item" id={`cart-item-${item.id}`}>
                <Link to={`/products/${item.product.id}`}>
                  <img
                    src={item.product.image_url}
                    alt={item.product.name}
                    className="cart-item-image"
                  />
                </Link>
                <div className="cart-item-details">
                  <Link to={`/products/${item.product.id}`} className="cart-item-name">
                    {item.product.name}
                  </Link>
                  <span className="badge badge-accent cart-item-category">{item.product.category}</span>
                  <div className="cart-item-bottom">
                    <div className="cart-item-qty-controls">
                      <button
                        className="qty-btn-sm"
                        onClick={() => updateQuantity(item.id, item.quantity - 1)}
                        id={`decrease-qty-${item.id}`}
                      >
                        <Minus size={12} />
                      </button>
                      <span className="qty-display">{item.quantity}</span>
                      <button
                        className="qty-btn-sm"
                        onClick={() => updateQuantity(item.id, item.quantity + 1)}
                        id={`increase-qty-${item.id}`}
                      >
                        <Plus size={12} />
                      </button>
                    </div>
                    <span className="cart-item-price">
                      ${(item.product.price * item.quantity).toFixed(2)}
                    </span>
                    <button
                      className="btn btn-ghost btn-sm remove-btn"
                      onClick={() => removeItem(item.id)}
                      id={`remove-item-${item.id}`}
                      title="Remove item"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Order summary */}
          <div className="cart-summary card">
            <h2 className="cart-summary-title">Order Summary</h2>

            <div className="cart-summary-rows">
              <div className="cart-summary-row">
                <span>Subtotal</span>
                <span>${totalPrice.toFixed(2)}</span>
              </div>
              <div className="cart-summary-row">
                <span>Shipping</span>
                <span className={shipping === 0 ? 'free-shipping' : ''}>
                  {shipping === 0 ? 'FREE' : `$${shipping.toFixed(2)}`}
                </span>
              </div>
              {shipping > 0 && (
                <p className="free-shipping-hint">Add ${(50 - totalPrice).toFixed(2)} more for free shipping</p>
              )}
              <div className="cart-summary-row">
                <span>Tax (8%)</span>
                <span>${tax.toFixed(2)}</span>
              </div>
              <div className="divider" />
              <div className="cart-summary-row total">
                <span>Total</span>
                <span>${orderTotal.toFixed(2)}</span>
              </div>
            </div>

            <Link to="/checkout" className="btn btn-primary btn-lg btn-full" id="checkout-btn">
              Proceed to Checkout <ArrowRight size={18} />
            </Link>
            <Link to="/products" className="btn btn-secondary btn-full" style={{ marginTop: 8 }}>
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
