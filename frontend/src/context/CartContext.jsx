import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { useAuth } from './AuthContext'
import toast from 'react-hot-toast'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  const { isLoggedIn } = useAuth()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchCart = useCallback(async () => {
    if (!isLoggedIn) { setItems([]); return }
    try {
      setLoading(true)
      const { data } = await client.get('/cart')
      setItems(data)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [isLoggedIn])

  useEffect(() => { fetchCart() }, [fetchCart])

  const addToCart = useCallback(async (productId, quantity = 1) => {
    if (!isLoggedIn) {
      toast.error('Please log in to add items to cart')
      return false
    }
    try {
      await client.post('/cart', { product_id: productId, quantity })
      await fetchCart()
      toast.success('Added to cart!')
      return true
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not add to cart')
      return false
    }
  }, [isLoggedIn, fetchCart])

  const updateQuantity = useCallback(async (itemId, quantity) => {
    try {
      if (quantity <= 0) {
        await client.delete(`/cart/${itemId}`)
      } else {
        await client.put(`/cart/${itemId}`, { quantity })
      }
      await fetchCart()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update cart')
    }
  }, [fetchCart])

  const removeItem = useCallback(async (itemId) => {
    try {
      await client.delete(`/cart/${itemId}`)
      await fetchCart()
      toast.success('Item removed')
    } catch {
      toast.error('Failed to remove item')
    }
  }, [fetchCart])

  const clearCart = useCallback(async () => {
    try {
      await client.delete('/cart')
      setItems([])
    } catch {}
  }, [])

  const totalItems = items.reduce((sum, i) => sum + i.quantity, 0)
  const totalPrice = items.reduce((sum, i) => sum + i.product.price * i.quantity, 0)

  return (
    <CartContext.Provider value={{
      items, loading, fetchCart,
      addToCart, updateQuantity, removeItem, clearCart,
      totalItems, totalPrice
    }}>
      {children}
    </CartContext.Provider>
  )
}

export const useCart = () => {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}
