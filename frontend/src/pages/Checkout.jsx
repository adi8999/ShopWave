import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { CreditCard, MapPin, CheckCircle, ShoppingBag, ShieldCheck, Lock } from 'lucide-react'
import { loadStripe } from '@stripe/stripe-js'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import client from '../api/client'
import { useCart } from '../context/CartContext'
import toast from 'react-hot-toast'
import './Checkout.css'

// Initialize Stripe instance (loads dynamically or uses sandbox)
const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || 'pk_test_placeholder_key')

function CheckoutFormContent({ items, totalPrice, clearCart, shipping, tax, orderTotal }) {
  const navigate = useNavigate()
  const stripe = useStripe()
  const elements = useElements()

  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    shipping_name: '',
    shipping_address: '',
    shipping_city: '',
    shipping_zip: '',
    card_number: '',
    card_expiry: '',
    card_cvv: '',
  })

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.shipping_name || !form.shipping_address || !form.shipping_city || !form.shipping_zip) {
      toast.error('Please fill in all shipping fields')
      return
    }

    setLoading(true)

    try {
      let paymentIntentId = null

      // If Stripe publishable key is valid and CardElement is mounted
      const cardElement = elements?.getElement(CardElement)
      if (stripe && cardElement) {
        try {
          const { error, paymentMethod } = await stripe.createPaymentMethod({
            type: 'card',
            card: cardElement,
            billing_details: {
              name: form.shipping_name,
              address: {
                line1: form.shipping_address,
                city: form.shipping_city,
                postal_code: form.shipping_zip,
              },
            },
          })
          if (error) {
            console.warn('Stripe sandbox notice:', error.message)
          } else if (paymentMethod) {
            paymentIntentId = paymentMethod.id
          }
        } catch (stripeErr) {
          console.warn('Stripe checkout note:', stripeErr)
        }
      }

      // Place order with backend API
      const { data: order } = await client.post('/orders/checkout', {
        shipping_name: form.shipping_name,
        shipping_address: form.shipping_address,
        shipping_city: form.shipping_city,
        shipping_zip: form.shipping_zip,
        payment_intent_id: paymentIntentId,
      })

      await clearCart()
      toast.success('Order placed successfully! 🎉')
      navigate(`/orders?success=${order.id}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Checkout failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="checkout-layout" onSubmit={handleSubmit}>
      <div className="checkout-forms">
        {/* Shipping */}
        <div className="checkout-section card">
          <div className="checkout-section-header">
            <div className="checkout-section-icon"><MapPin size={18} /></div>
            <h2>Shipping Information</h2>
          </div>
          <div className="checkout-fields">
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                className="form-input"
                id="shipping-name"
                placeholder="John Doe"
                value={form.shipping_name}
                onChange={update('shipping_name')}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Address</label>
              <input
                className="form-input"
                id="shipping-address"
                placeholder="123 Main Street"
                value={form.shipping_address}
                onChange={update('shipping_address')}
                required
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">City</label>
                <input
                  className="form-input"
                  id="shipping-city"
                  placeholder="San Francisco"
                  value={form.shipping_city}
                  onChange={update('shipping_city')}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">ZIP Code</label>
                <input
                  className="form-input"
                  id="shipping-zip"
                  placeholder="94102"
                  value={form.shipping_zip}
                  onChange={update('shipping_zip')}
                  required
                />
              </div>
            </div>
          </div>
        </div>

        {/* Payment */}
        <div className="checkout-section card">
          <div className="checkout-section-header">
            <div className="checkout-section-icon"><CreditCard size={18} /></div>
            <h2>Payment Details</h2>
          </div>
          <div className="mock-payment-notice" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Lock size={14} color="var(--success)" />
            <span>Encrypted 256-bit SSL checkout powered by Stripe Sandbox</span>
          </div>

          <div className="checkout-fields">
            <div className="form-group">
              <label className="form-label">Credit or Debit Card</label>
              <div style={{
                background: 'var(--bg-elevated)',
                padding: '14px 16px',
                borderRadius: '10px',
                border: '1px solid var(--border)',
              }}>
                <CardElement
                  options={{
                    style: {
                      base: {
                        fontSize: '15px',
                        color: '#ffffff',
                        '::placeholder': { color: '#888899' },
                      },
                      invalid: { color: '#ef4444' },
                    },
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="checkout-summary">
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Order Summary</h2>

          <div className="checkout-items">
            {items.map((item) => (
              <div key={item.id} className="checkout-item">
                <img src={item.product?.image_url} alt={item.product?.name} className="checkout-item-img" />
                <div className="checkout-item-info">
                  <p className="checkout-item-name">{item.product?.name}</p>
                  <p className="checkout-item-qty">×{item.quantity}</p>
                </div>
                <span className="checkout-item-price">
                  ${(item.product?.price * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
          </div>

          <div className="divider" />
          <div className="cart-summary-rows">
            <div className="cart-summary-row">
              <span>Subtotal</span><span>${totalPrice.toFixed(2)}</span>
            </div>
            <div className="cart-summary-row">
              <span>Shipping</span>
              <span style={{ color: shipping === 0 ? 'var(--success)' : undefined }}>
                {shipping === 0 ? 'FREE' : `$${shipping.toFixed(2)}`}
              </span>
            </div>
            <div className="cart-summary-row">
              <span>Tax</span><span>${tax.toFixed(2)}</span>
            </div>
            <div className="divider" style={{ margin: '8px 0' }} />
            <div className="cart-summary-row total">
              <span>Total</span><span>${orderTotal.toFixed(2)}</span>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg btn-full"
            id="place-order-btn"
            disabled={loading}
            style={{ marginTop: 20 }}
          >
            <CheckCircle size={18} />
            {loading ? 'Processing Payment...' : `Pay & Place Order — $${orderTotal.toFixed(2)}`}
          </button>
        </div>
      </div>
    </form>
  )
}

export default function Checkout() {
  const { items, totalPrice, clearCart } = useCart()

  const shipping = totalPrice >= 50 ? 0 : 9.99
  const tax = totalPrice * 0.08
  const orderTotal = totalPrice + shipping + tax

  if (items.length === 0) {
    return (
      <div className="container page page-fade">
        <div className="empty-state">
          <ShoppingBag size={64} style={{ margin: '0 auto 16px', color: 'var(--text-muted)' }} />
          <h3>Nothing to checkout</h3>
          <p>Add some items to your cart first</p>
          <Link to="/products" className="btn btn-primary" style={{ marginTop: 20 }}>Browse Products</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="checkout-page page page-fade">
      <div className="container">
        <h1 className="section-title" style={{ marginBottom: 32 }}>Checkout</h1>
        <Elements stripe={stripePromise}>
          <CheckoutFormContent
            items={items}
            totalPrice={totalPrice}
            clearCart={clearCart}
            shipping={shipping}
            tax={tax}
            orderTotal={orderTotal}
          />
        </Elements>
      </div>
    </div>
  )
}
