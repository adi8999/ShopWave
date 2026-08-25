import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ShoppingCart, ArrowLeft, Package, Star } from 'lucide-react'
import client from '../api/client'
import { useCart } from '../context/CartContext'
import './ProductDetail.css'

export default function ProductDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToCart } = useCart()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [quantity, setQuantity] = useState(1)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    setLoading(true)
    client.get(`/products/${id}`)
      .then(({ data }) => setProduct(data))
      .catch(() => navigate('/products'))
      .finally(() => setLoading(false))
  }, [id])

  const renderStars = (rating) => '★'.repeat(Math.floor(rating)) + '☆'.repeat(5 - Math.floor(rating))

  const handleAddToCart = async () => {
    setAdding(true)
    await addToCart(product.id, quantity)
    setAdding(false)
  }

  if (loading) return <div className="loading-spinner page"><div className="spinner" /></div>
  if (!product) return null

  const isOutOfStock = product.stock === 0

  return (
    <div className="product-detail-page page page-fade">
      <div className="container">
        <button className="btn btn-ghost btn-sm back-btn" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} /> Back
        </button>

        <div className="product-detail-grid">
          {/* Image */}
          <div className="product-detail-image-wrap">
            <img
              src={product.image_url}
              alt={product.name}
              className="product-detail-image"
            />
            <div className="product-detail-badges">
              <span className="badge badge-accent">{product.category}</span>
              {isOutOfStock && (
                <span className="badge" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid rgba(239,68,68,0.2)' }}>
                  Out of Stock
                </span>
              )}
            </div>
          </div>

          {/* Info */}
          <div className="product-detail-info">
            <h1 className="product-detail-name">{product.name}</h1>

            <div className="product-detail-rating">
              <span className="stars">{renderStars(product.rating)}</span>
              <span className="rating-value">{product.rating}</span>
              <span className="rating-count">({product.review_count.toLocaleString()} reviews)</span>
            </div>

            <div className="product-detail-price">${product.price.toFixed(2)}</div>

            <p className="product-detail-desc">{product.description}</p>

            <div className="divider" />

            <div className="product-detail-stock">
              <Package size={16} />
              {isOutOfStock ? (
                <span style={{ color: 'var(--danger)' }}>Out of stock</span>
              ) : (
                <span style={{ color: 'var(--success)' }}>
                  In stock — {product.stock} available
                </span>
              )}
            </div>

            {/* Quantity selector */}
            {!isOutOfStock && (
              <div className="quantity-selector">
                <label className="form-label">Quantity</label>
                <div className="quantity-controls">
                  <button
                    className="qty-btn"
                    onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  >−</button>
                  <span className="qty-value">{quantity}</span>
                  <button
                    className="qty-btn"
                    onClick={() => setQuantity((q) => Math.min(product.stock, q + 1))}
                  >+</button>
                </div>
              </div>
            )}

            <button
              className="btn btn-primary btn-lg btn-full"
              id="add-to-cart-detail-btn"
              onClick={handleAddToCart}
              disabled={isOutOfStock || adding}
            >
              <ShoppingCart size={18} />
              {adding ? 'Adding...' : isOutOfStock ? 'Out of Stock' : 'Add to Cart'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
