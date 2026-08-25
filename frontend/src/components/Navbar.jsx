import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ShoppingCart, User, LogOut, Menu, X, Package, Zap, Shield } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import './Navbar.css'

export default function Navbar() {
  const { user, logout, isLoggedIn } = useAuth()
  const { totalItems } = useCart()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
    setUserMenuOpen(false)
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav className="navbar">
      <div className="container navbar-inner">
        {/* Logo */}
        <Link to="/" className="navbar-logo">
          <div className="navbar-logo-icon">
            <Zap size={18} fill="currentColor" />
          </div>
          <span>ShopWave</span>
        </Link>

        {/* Center nav links */}
        <div className={`navbar-links ${mobileOpen ? 'open' : ''}`}>
          <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>Home</Link>
          <Link to="/products" className={`nav-link ${isActive('/products') ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>Products</Link>
          {isLoggedIn && (
            <Link to="/orders" className={`nav-link ${isActive('/orders') ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>My Orders</Link>
          )}
          {user?.is_admin && (
            <Link to="/admin" className={`nav-link admin-nav-link ${isActive('/admin') ? 'active' : ''}`} onClick={() => setMobileOpen(false)}>
              <Shield size={14} /> Admin
            </Link>
          )}
        </div>

        {/* Right actions */}
        <div className="navbar-actions">
          {/* Cart */}
          <Link to="/cart" className="navbar-cart-btn" id="navbar-cart-btn">
            <ShoppingCart size={20} />
            {totalItems > 0 && (
              <span className="cart-badge">{totalItems}</span>
            )}
          </Link>

          {/* User menu */}
          {isLoggedIn ? (
            <div className="user-menu-wrapper">
              <button
                className="user-avatar-btn"
                id="user-menu-btn"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
              >
                <div className="user-avatar">
                  {user?.name?.charAt(0).toUpperCase()}
                </div>
              </button>
              {userMenuOpen && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <p className="user-dropdown-name">{user?.name}</p>
                    <p className="user-dropdown-email">{user?.email}</p>
                  </div>
                  <div className="user-dropdown-divider" />
                  <Link to="/orders" className="user-dropdown-item" onClick={() => setUserMenuOpen(false)}>
                    <Package size={15} /> My Orders
                  </Link>
                  {user?.is_admin && (
                    <Link to="/admin" className="user-dropdown-item admin-dropdown-item" onClick={() => setUserMenuOpen(false)}>
                      <Shield size={15} /> Admin Panel
                    </Link>
                  )}
                  <button className="user-dropdown-item danger" id="logout-btn" onClick={handleLogout}>
                    <LogOut size={15} /> Log Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="auth-buttons">
              <Link to="/login" className="btn btn-ghost btn-sm">Log In</Link>
              <Link to="/register" className="btn btn-primary btn-sm" id="signup-btn">Sign Up</Link>
            </div>
          )}

          {/* Mobile hamburger */}
          <button className="hamburger" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>
    </nav>
  )
}
