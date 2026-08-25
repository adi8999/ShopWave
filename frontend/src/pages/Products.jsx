import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import client from '../api/client'
import ProductCard from '../components/ProductCard'
import './Products.css'

const CATEGORIES = ['Electronics', 'Clothing', 'Books', 'Home']

export default function Products() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get('category') || '')
  const [priceRange, setPriceRange] = useState({ min: '', max: '' })

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (selectedCategory) params.set('category', selectedCategory)
      if (search) params.set('search', search)
      if (priceRange.min) params.set('min_price', priceRange.min)
      if (priceRange.max) params.set('max_price', priceRange.max)
      const { data } = await client.get(`/products?${params}`)
      setProducts(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(fetchProducts, 300)
    return () => clearTimeout(timer)
  }, [search, selectedCategory, priceRange])

  // Sync URL params
  useEffect(() => {
    const params = {}
    if (search) params.search = search
    if (selectedCategory) params.category = selectedCategory
    setSearchParams(params, { replace: true })
  }, [search, selectedCategory])

  const clearFilters = () => {
    setSearch('')
    setSelectedCategory('')
    setPriceRange({ min: '', max: '' })
  }

  const hasFilters = search || selectedCategory || priceRange.min || priceRange.max

  return (
    <div className="products-page page page-fade">
      <div className="container">
        <div className="products-header">
          <div>
            <h1 className="section-title">All Products</h1>
            <p className="section-subtitle">{loading ? '...' : `${products.length} results`}</p>
          </div>
        </div>

        <div className="products-layout">
          {/* Sidebar filters */}
          <aside className="filters-sidebar">
            <div className="filters-header">
              <span><SlidersHorizontal size={16} /> Filters</span>
              {hasFilters && (
                <button className="btn btn-ghost btn-sm" onClick={clearFilters} id="clear-filters-btn">
                  <X size={14} /> Clear
                </button>
              )}
            </div>

            {/* Search */}
            <div className="filter-section">
              <label className="form-label">Search</label>
              <div className="search-wrap">
                <Search size={16} className="search-icon" />
                <input
                  className="form-input search-input"
                  id="product-search-input"
                  type="text"
                  placeholder="Search products..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>

            {/* Category */}
            <div className="filter-section">
              <label className="form-label">Category</label>
              <div className="category-filters">
                <button
                  className={`filter-chip ${selectedCategory === '' ? 'active' : ''}`}
                  onClick={() => setSelectedCategory('')}
                  id="filter-all"
                >
                  All
                </button>
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    className={`filter-chip ${selectedCategory === cat ? 'active' : ''}`}
                    onClick={() => setSelectedCategory(cat === selectedCategory ? '' : cat)}
                    id={`filter-${cat.toLowerCase()}`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            {/* Price range */}
            <div className="filter-section">
              <label className="form-label">Price Range</label>
              <div className="price-inputs">
                <input
                  className="form-input"
                  type="number"
                  placeholder="Min $"
                  value={priceRange.min}
                  onChange={(e) => setPriceRange((p) => ({ ...p, min: e.target.value }))}
                />
                <span className="price-separator">—</span>
                <input
                  className="form-input"
                  type="number"
                  placeholder="Max $"
                  value={priceRange.max}
                  onChange={(e) => setPriceRange((p) => ({ ...p, max: e.target.value }))}
                />
              </div>
            </div>
          </aside>

          {/* Products grid */}
          <div className="products-main">
            {loading ? (
              <div className="loading-spinner"><div className="spinner" /></div>
            ) : products.length === 0 ? (
              <div className="empty-state">
                <h3>No products found</h3>
                <p>Try adjusting your filters</p>
                <button className="btn btn-secondary" onClick={clearFilters} style={{ marginTop: 16 }}>
                  Clear Filters
                </button>
              </div>
            ) : (
              <div className="product-grid">
                {products.map((p) => <ProductCard key={p.id} product={p} />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
