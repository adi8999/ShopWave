import { useState, useEffect, useCallback, useRef } from 'react'
import { Search, SlidersHorizontal, X, ChevronLeft, ChevronRight, Star } from 'lucide-react'
import client from '../api/client'
import ProductCard from '../components/ProductCard'
import './Products.css'

const SORT_OPTIONS = [
  { value: 'newest',     label: 'Newest First' },
  { value: 'price_asc',  label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating_desc',label: 'Top Rated' },
]

const PRICE_RANGES = [
  { label: 'All Prices', min: null, max: null },
  { label: 'Under $25',  min: null, max: 25 },
  { label: '$25–$100',   min: 25,   max: 100 },
  { label: '$100–$300',  min: 100,  max: 300 },
  { label: 'Over $300',  min: 300,  max: null },
]

export default function Products() {
  // State
  const [query, setQuery]           = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [categories, setCategories] = useState([])
  const [selectedCat, setSelectedCat]     = useState('')
  const [priceRange, setPriceRange]       = useState(PRICE_RANGES[0])
  const [sortBy, setSortBy]               = useState('newest')
  const [page, setPage]                   = useState(1)

  const [products, setProducts]   = useState([])
  const [total, setTotal]         = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading]     = useState(true)
  const [filtersOpen, setFiltersOpen] = useState(false)

  const LIMIT = 12
  const debounceTimer = useRef(null)

  // Debounce search input 300ms
  useEffect(() => {
    clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedQ(query)
      setPage(1) // reset to page 1 on new search
    }, 300)
    return () => clearTimeout(debounceTimer.current)
  }, [query])

  // Fetch categories once
  useEffect(() => {
    client.get('/products/categories').then((res) => setCategories(res.data))
  }, [])

  // Fetch products whenever filters change
  const fetchProducts = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        page,
        limit: LIMIT,
        sort_by: sortBy,
      }
      if (debouncedQ)         params.q = debouncedQ
      if (selectedCat)        params.category = selectedCat
      if (priceRange.min != null) params.min_price = priceRange.min
      if (priceRange.max != null) params.max_price = priceRange.max

      const res = await client.get('/products', { params })
      setProducts(res.data.items)
      setTotal(res.data.total)
      setTotalPages(res.data.pages)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [debouncedQ, selectedCat, priceRange, sortBy, page])

  useEffect(() => { fetchProducts() }, [fetchProducts])

  // Reset to page 1 when filters change
  const handleCategoryChange = (cat) => {
    setSelectedCat(cat === selectedCat ? '' : cat)
    setPage(1)
  }
  const handlePriceRange = (range) => { setPriceRange(range); setPage(1) }
  const handleSort = (val) => { setSortBy(val); setPage(1) }

  const clearFilters = () => {
    setQuery(''); setDebouncedQ(''); setSelectedCat(''); setPriceRange(PRICE_RANGES[0])
    setSortBy('newest'); setPage(1)
  }

  const hasFilters = query || selectedCat || priceRange.min || priceRange.max || sortBy !== 'newest'

  return (
    <div className="products-page">
      {/* ── Top toolbar ── */}
      <div className="products-toolbar">
        <div className="search-wrapper">
          <Search size={16} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search products…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button className="search-clear" onClick={() => setQuery('')}><X size={14} /></button>
          )}
        </div>

        <div className="toolbar-right">
          {/* Sort */}
          <select
            className="sort-select"
            value={sortBy}
            onChange={(e) => handleSort(e.target.value)}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* Mobile filter toggle */}
          <button className="filter-toggle-btn" onClick={() => setFiltersOpen(!filtersOpen)}>
            <SlidersHorizontal size={16} /> Filters
          </button>

          {hasFilters && (
            <button className="clear-filters-btn" onClick={clearFilters}>
              <X size={14} /> Clear
            </button>
          )}
        </div>
      </div>

      <div className="products-layout">
        {/* ── Sidebar ── */}
        <aside className={`filter-sidebar ${filtersOpen ? 'open' : ''}`}>
          <div className="sidebar-section">
            <h3 className="sidebar-title">Category</h3>
            <button
              className={`cat-pill ${!selectedCat ? 'active' : ''}`}
              onClick={() => handleCategoryChange('')}
            >All</button>
            {categories.map((cat) => (
              <button
                key={cat}
                className={`cat-pill ${selectedCat === cat ? 'active' : ''}`}
                onClick={() => handleCategoryChange(cat)}
              >{cat}</button>
            ))}
          </div>

          <div className="sidebar-section">
            <h3 className="sidebar-title">Price Range</h3>
            {PRICE_RANGES.map((r) => (
              <button
                key={r.label}
                className={`cat-pill ${priceRange.label === r.label ? 'active' : ''}`}
                onClick={() => handlePriceRange(r)}
              >{r.label}</button>
            ))}
          </div>
        </aside>

        {/* ── Products grid ── */}
        <div className="products-main">
          <div className="products-meta">
            {loading ? 'Loading…' : `${total} product${total !== 1 ? 's' : ''} found`}
          </div>

          {loading ? (
            <div className="products-grid">
              {Array.from({ length: LIMIT }).map((_, i) => (
                <div key={i} className="product-skeleton" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="products-empty">
              <Search size={48} style={{ opacity: 0.3 }} />
              <p>No products match your filters.</p>
              <button className="btn-primary" onClick={clearFilters}>Clear Filters</button>
            </div>
          ) : (
            <div className="products-grid">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}

          {/* ── Pagination ── */}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="page-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft size={16} />
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => Math.abs(p - page) <= 2 || p === 1 || p === totalPages)
                .reduce((acc, p, idx, arr) => {
                  if (idx > 0 && p - arr[idx - 1] > 1) acc.push('…')
                  acc.push(p)
                  return acc
                }, [])
                .map((item, i) =>
                  item === '…' ? (
                    <span key={`ellipsis-${i}`} className="page-ellipsis">…</span>
                  ) : (
                    <button
                      key={item}
                      className={`page-btn ${page === item ? 'active' : ''}`}
                      onClick={() => setPage(item)}
                    >{item}</button>
                  )
                )
              }

              <button
                className="page-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight size={16} />
              </button>

              <span className="page-info">Page {page} of {totalPages}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
