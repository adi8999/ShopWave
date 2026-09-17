import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ShoppingCart, ArrowLeft, Package, Star, CheckCircle, MessageSquare, Send } from 'lucide-react'
import toast from 'react-hot-toast'
import client from '../api/client'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import './ProductDetail.css'

export default function ProductDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToCart } = useCart()
  const { isLoggedIn, user } = useAuth()

  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [quantity, setQuantity] = useState(1)
  const [adding, setAdding] = useState(false)

  // Reviews state
  const [reviewsData, setReviewsData] = useState({ reviews: [], total: 0, average_rating: 0 })
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [rating, setRating] = useState(5)
  const [hoverRating, setHoverRating] = useState(0)
  const [comment, setComment] = useState('')
  const [submittingReview, setSubmittingReview] = useState(false)

  const fetchProduct = () => {
    client.get(`/products/${id}`)
      .then(({ data }) => setProduct(data))
      .catch(() => navigate('/products'))
  }

  const fetchReviews = () => {
    setReviewsLoading(true)
    client.get(`/products/${id}/reviews`)
      .then(({ data }) => setReviewsData(data))
      .catch(() => {})
      .finally(() => setReviewsLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    client.get(`/products/${id}`)
      .then(({ data }) => setProduct(data))
      .catch(() => navigate('/products'))
      .finally(() => setLoading(false))

    fetchReviews()
  }, [id])

  const renderStars = (score) => {
    const rounded = Math.round(score || 0)
    return '★'.repeat(Math.min(5, Math.max(0, rounded))) + '☆'.repeat(Math.max(0, 5 - rounded))
  }

  const handleAddToCart = async () => {
    setAdding(true)
    await addToCart(product.id, quantity)
    setAdding(false)
  }

  const handleSubmitReview = async (e) => {
    e.preventDefault()
    if (!isLoggedIn) {
      toast.error('Please log in to submit a review')
      return
    }
    if (!comment.trim()) {
      toast.error('Please write a comment for your review')
      return
    }

    try {
      setSubmittingReview(true)
      await client.post(`/products/${id}/reviews`, {
        rating: Number(rating),
        comment: comment.trim(),
      })
      toast.success('Review submitted successfully!')
      setComment('')
      fetchReviews()
      fetchProduct()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit review')
    } finally {
      setSubmittingReview(false)
    }
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
              <span className="rating-value">{product.rating.toFixed(1)}</span>
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

        {/* ── Customer Reviews Section ── */}
        <section className="reviews-section" id="reviews">
          <div className="reviews-header">
            <div>
              <h2 className="reviews-title">Customer Reviews</h2>
              <p className="reviews-subtitle">Real feedback from verified ShopWave shoppers</p>
            </div>
            <div className="reviews-summary-badge">
              <span className="summary-rating-num">{product.rating.toFixed(1)}</span>
              <div className="summary-rating-meta">
                <span className="stars" style={{ fontSize: '18px' }}>{renderStars(product.rating)}</span>
                <span className="summary-count">{product.review_count} total {product.review_count === 1 ? 'review' : 'reviews'}</span>
              </div>
            </div>
          </div>

          <div className="reviews-layout">
            {/* Left: Write a review form */}
            <div className="review-form-card">
              <h3 className="review-form-title">
                <MessageSquare size={18} /> Write a Review
              </h3>
              {isLoggedIn ? (
                <form onSubmit={handleSubmitReview} className="review-form">
                  <div className="form-group">
                    <label className="form-label">Rating</label>
                    <div className="star-picker">
                      {[1, 2, 3, 4, 5].map((starVal) => (
                        <button
                          key={starVal}
                          type="button"
                          className={`star-btn ${starVal <= (hoverRating || rating) ? 'active' : ''}`}
                          onClick={() => setRating(starVal)}
                          onMouseEnter={() => setHoverRating(starVal)}
                          onMouseLeave={() => setHoverRating(0)}
                          title={`${starVal} star${starVal > 1 ? 's' : ''}`}
                        >
                          ★
                        </button>
                      ))}
                      <span className="star-label">{hoverRating || rating} / 5 Stars</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="review-comment">
                      Your Review
                    </label>
                    <textarea
                      id="review-comment"
                      className="form-input review-textarea"
                      rows={4}
                      placeholder="What did you like or dislike? How was the quality and fit?"
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-md"
                    disabled={submittingReview}
                  >
                    <Send size={15} />
                    {submittingReview ? 'Submitting...' : 'Post Review'}
                  </button>
                </form>
              ) : (
                <div className="review-login-prompt">
                  <p>Only verified accounts can post product feedback.</p>
                  <Link to="/login" className="btn btn-outline btn-sm">
                    Log in to Write a Review
                  </Link>
                </div>
              )}
            </div>

            {/* Right: Reviews list */}
            <div className="reviews-list-card">
              {reviewsLoading ? (
                <div className="reviews-loading">Loading customer reviews...</div>
              ) : reviewsData.reviews.length === 0 ? (
                <div className="reviews-empty">
                  <Star size={36} className="empty-icon" />
                  <h4>No reviews yet</h4>
                  <p>Be the first customer to share your thoughts on this item!</p>
                </div>
              ) : (
                <div className="reviews-list">
                  {reviewsData.reviews.map((rev) => (
                    <div key={rev.id} className="review-item">
                      <div className="review-item-header">
                        <div className="reviewer-info">
                          <span className="reviewer-avatar">
                            {rev.user_name.charAt(0).toUpperCase()}
                          </span>
                          <div>
                            <div className="reviewer-name-row">
                              <span className="reviewer-name">{rev.user_name}</span>
                              {rev.verified_purchase && (
                                <span className="verified-badge">
                                  <CheckCircle size={13} /> Verified Purchase
                                </span>
                              )}
                            </div>
                            <span className="review-date">
                              {new Date(rev.created_at).toLocaleDateString(undefined, {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                              })}
                            </span>
                          </div>
                        </div>
                        <span className="stars review-stars">{renderStars(rev.rating)}</span>
                      </div>
                      <p className="review-comment">{rev.comment}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

