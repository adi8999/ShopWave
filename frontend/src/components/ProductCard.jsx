import { Link } from 'react-router-dom'
import { ShoppingCart, Star, Heart } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import './ProductCard.css'

export default function ProductCard({ product }) {
  const { addToCart } = useCart()
  const { isInWishlist, toggleWishlist } = useWishlist()
  const saved = isInWishlist(product.id)

  const renderStars = (rating) => {
    const full = Math.floor(rating)
    const half = rating % 1 >= 0.5
    let stars = '★'.repeat(full)
    if (half) stars += '½'
    stars += '☆'.repeat(5 - full - (half ? 1 : 0))
    return stars
  }

  const handleAddToCart = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    await addToCart(product.id)
  }

  const handleToggleWishlist = (e) => {
    e.preventDefault()
    e.stopPropagation()
    toggleWishlist(product)
  }

  return (
    <Link to={`/products/${product.id}`} className="product-card" id={`product-card-${product.id}`}>
      <div className="product-card-image-wrap">
        <img
          src={product.image_url}
          alt={product.name}
          className="product-card-image"
          loading="lazy"
        />
        <div className="product-card-overlay">
          <div className="product-card-badges-col">
            <span className="product-card-category badge badge-accent">{product.category}</span>
            {product.stock === 0 && (
              <span className="badge" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid rgba(239,68,68,0.2)' }}>
                Out of Stock
              </span>
            )}
          </div>
          <button
            type="button"
            className={`product-card-wishlist-btn ${saved ? 'active' : ''}`}
            title={saved ? 'Remove from wishlist' : 'Save to wishlist'}
            onClick={handleToggleWishlist}
          >
            <Heart size={16} fill={saved ? '#ec4899' : 'none'} color={saved ? '#ec4899' : 'currentColor'} />
          </button>
        </div>
      </div>

      <div className="product-card-body">
        <h3 className="product-card-name">{product.name}</h3>
        <p className="product-card-desc">{product.description}</p>

        <div className="product-card-rating">
          <span className="stars">{renderStars(product.rating)}</span>
          <span className="product-card-review-count">({product.review_count.toLocaleString()})</span>
        </div>

        <div className="product-card-footer">
          <span className="product-card-price">${product.price.toFixed(2)}</span>
          <button
            className="btn btn-primary btn-sm product-card-add-btn"
            id={`add-to-cart-${product.id}`}
            onClick={handleAddToCart}
            disabled={product.stock === 0}
          >
            <ShoppingCart size={14} />
            Add
          </button>
        </div>
      </div>
    </Link>
  )
}
