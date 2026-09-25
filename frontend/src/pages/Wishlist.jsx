import { Link } from 'react-router-dom'
import { Heart, ShoppingCart, Trash2, ArrowLeft, Package, Sparkles } from 'lucide-react'
import { useWishlist } from '../context/WishlistContext'
import { useCart } from '../context/CartContext'
import toast from 'react-hot-toast'
import './Wishlist.css'

export default function Wishlist() {
  const { items, loading, removeFromWishlist } = useWishlist()
  const { addToCart } = useCart()

  const handleMoveToCart = async (product) => {
    const success = await addToCart(product.id, 1)
    if (success) {
      await removeFromWishlist(product.id)
      toast.success(`Moved '${product.name}' to cart!`)
    }
  }

  if (loading) {
    return (
      <div className="loading-spinner page">
        <div className="spinner" />
      </div>
    )
  }

  return (
    <div className="wishlist-page page page-fade">
      <div className="container">
        {/* Header */}
        <div className="wishlist-header">
          <div className="wishlist-title-wrap">
            <h1 className="page-title">
              <Heart size={28} className="wishlist-heart-icon" fill="currentColor" /> My Wishlist
            </h1>
            <p className="page-subtitle">
              {items.length} {items.length === 1 ? 'saved item' : 'saved items'} ready for your cart
            </p>
          </div>
          <Link to="/products" className="btn btn-outline btn-sm">
            <ArrowLeft size={16} /> Continue Shopping
          </Link>
        </div>

        {items.length === 0 ? (
          <div className="wishlist-empty-card">
            <div className="wishlist-empty-icon-wrap">
              <Heart size={48} className="empty-heart-icon" />
            </div>
            <h2>Your wishlist is empty</h2>
            <p>Save items you like while shopping so you can easily find and purchase them later.</p>
            <Link to="/products" className="btn btn-primary btn-lg">
              <Sparkles size={18} /> Explore Products
            </Link>
          </div>
        ) : (
          <div className="wishlist-grid">
            {items.map((product) => {
              const isOutOfStock = product.stock === 0
              return (
                <div key={product.id} className="wishlist-card">
                  <div className="wishlist-card-image-wrap">
                    <img
                      src={product.image_url}
                      alt={product.name}
                      className="wishlist-card-image"
                      loading="lazy"
                    />
                    <span className="badge badge-accent wishlist-badge">
                      {product.category}
                    </span>
                    <button
                      className="wishlist-remove-btn"
                      title="Remove from wishlist"
                      onClick={() => removeFromWishlist(product.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>

                  <div className="wishlist-card-content">
                    <Link to={`/products/${product.id}`} className="wishlist-card-name">
                      {product.name}
                    </Link>
                    <p className="wishlist-card-desc">{product.description}</p>

                    <div className="wishlist-card-stock">
                      <Package size={14} />
                      {isOutOfStock ? (
                        <span style={{ color: 'var(--danger)' }}>Out of stock</span>
                      ) : (
                        <span style={{ color: 'var(--success)' }}>In stock ({product.stock} left)</span>
                      )}
                    </div>

                    <div className="wishlist-card-footer">
                      <span className="wishlist-card-price">${product.price.toFixed(2)}</span>
                      <button
                        className="btn btn-primary btn-sm btn-move-cart"
                        onClick={() => handleMoveToCart(product)}
                        disabled={isOutOfStock}
                      >
                        <ShoppingCart size={15} /> Move to Cart
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
