import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ShieldCheck, Truck, RefreshCw, Star } from 'lucide-react'
import client from '../api/client'
import ProductCard from '../components/ProductCard'
import './Home.css'

const CATEGORIES = [
  { name: 'Electronics', emoji: '⚡', desc: 'Gadgets & tech' },
  { name: 'Clothing', emoji: '👕', desc: 'Style & fashion' },
  { name: 'Books', emoji: '📚', desc: 'Learn & explore' },
  { name: 'Home', emoji: '🏡', desc: 'Your sanctuary' },
]

const FEATURES = [
  { icon: <ShieldCheck size={24} />, title: 'Secure Payments', desc: 'End-to-end encrypted checkout' },
  { icon: <Truck size={24} />, title: 'Fast Delivery', desc: 'Free shipping on orders $50+' },
  { icon: <RefreshCw size={24} />, title: 'Easy Returns', desc: '30-day hassle-free returns' },
  { icon: <Star size={24} />, title: 'Top Rated', desc: 'Curated products, verified reviews' },
]

export default function Home() {
  const [featured, setFeatured] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/products?limit=8').then(({ data }) => {
      setFeatured(data.slice(0, 8))
    }).finally(() => setLoading(false))
  }, [])

  return (
    <div className="home page-fade">
      {/* Hero */}
      <section className="hero">
        <div className="hero-bg-glow" />
        <div className="container hero-content">
          <div className="hero-badge badge badge-accent">
            ✨ New arrivals every week
          </div>
          <h1 className="hero-title">
            Shop smarter.<br />
            <span className="hero-title-accent">Live better.</span>
          </h1>
          <p className="hero-subtitle">
            Discover a curated collection of electronics, clothing, books, and home goods —
            all in one beautifully designed store.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-primary btn-lg" id="hero-shop-btn">
              Start Shopping <ArrowRight size={18} />
            </Link>
            <Link to="/register" className="btn btn-secondary btn-lg">
              Create Account
            </Link>
          </div>
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat-value">20+</span>
              <span className="hero-stat-label">Products</span>
            </div>
            <div className="hero-stat-divider" />
            <div className="hero-stat">
              <span className="hero-stat-value">4</span>
              <span className="hero-stat-label">Categories</span>
            </div>
            <div className="hero-stat-divider" />
            <div className="hero-stat">
              <span className="hero-stat-value">4.8★</span>
              <span className="hero-stat-label">Avg Rating</span>
            </div>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="section container">
        <div className="section-header">
          <div>
            <h2 className="section-title">Browse Categories</h2>
            <p className="section-subtitle">Find what you're looking for</p>
          </div>
        </div>
        <div className="categories-grid">
          {CATEGORIES.map((cat) => (
            <Link
              key={cat.name}
              to={`/products?category=${cat.name}`}
              className="category-card"
              id={`category-${cat.name.toLowerCase()}`}
            >
              <div className="category-emoji">{cat.emoji}</div>
              <div>
                <div className="category-name">{cat.name}</div>
                <div className="category-desc">{cat.desc}</div>
              </div>
              <ArrowRight size={16} className="category-arrow" />
            </Link>
          ))}
        </div>
      </section>

      {/* Featured Products */}
      <section className="section container">
        <div className="section-header">
          <div>
            <h2 className="section-title">Featured Products</h2>
            <p className="section-subtitle">Handpicked for you</p>
          </div>
          <Link to="/products" className="btn btn-ghost">
            View all <ArrowRight size={16} />
          </Link>
        </div>

        {loading ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : (
          <div className="product-grid">
            {featured.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        )}
      </section>

      {/* Features */}
      <section className="section">
        <div className="container">
          <div className="features-grid">
            {FEATURES.map((f) => (
              <div className="feature-card" key={f.title}>
                <div className="feature-icon">{f.icon}</div>
                <div>
                  <div className="feature-title">{f.title}</div>
                  <div className="feature-desc">{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
