import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { useAuth } from './AuthContext'
import toast from 'react-hot-toast'

const WishlistContext = createContext(null)

export function WishlistProvider({ children }) {
  const { isLoggedIn } = useAuth()
  const [wishlistIds, setWishlistIds] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchWishlist = useCallback(async () => {
    if (!isLoggedIn) {
      setWishlistIds([])
      setItems([])
      return
    }
    try {
      setLoading(true)
      const [idsRes, itemsRes] = await Promise.all([
        client.get('/wishlist/ids'),
        client.get('/wishlist'),
      ])
      setWishlistIds(idsRes.data || [])
      setItems(itemsRes.data || [])
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [isLoggedIn])

  useEffect(() => {
    fetchWishlist()
  }, [fetchWishlist])

  const isInWishlist = useCallback(
    (productId) => wishlistIds.includes(productId),
    [wishlistIds]
  )

  const toggleWishlist = useCallback(
    async (product) => {
      if (!isLoggedIn) {
        toast.error('Please log in to save items to your wishlist')
        return false
      }

      const pid = product.id
      const currentlySaved = wishlistIds.includes(pid)

      // Optimistic update
      setWishlistIds((prev) =>
        currentlySaved ? prev.filter((id) => id !== pid) : [...prev, pid]
      )
      if (currentlySaved) {
        setItems((prev) => prev.filter((it) => it.id !== pid))
      } else {
        setItems((prev) => [product, ...prev])
      }

      try {
        const { data } = await client.post(`/wishlist/${pid}`)
        toast.success(data.message || (data.in_wishlist ? 'Added to wishlist!' : 'Removed from wishlist'))
        return data.in_wishlist
      } catch (err) {
        // Revert optimistic update on error
        setWishlistIds((prev) =>
          currentlySaved ? [...prev, pid] : prev.filter((id) => id !== pid)
        )
        fetchWishlist()
        toast.error(err.response?.data?.detail || 'Failed to update wishlist')
        return currentlySaved
      }
    },
    [isLoggedIn, wishlistIds, fetchWishlist]
  )

  const removeFromWishlist = useCallback(
    async (productId) => {
      setWishlistIds((prev) => prev.filter((id) => id !== productId))
      setItems((prev) => prev.filter((it) => it.id !== productId))
      try {
        await client.delete(`/wishlist/${productId}`)
        toast.success('Removed from wishlist')
      } catch {
        fetchWishlist()
        toast.error('Failed to remove item')
      }
    },
    [fetchWishlist]
  )

  return (
    <WishlistContext.Provider
      value={{
        wishlistIds,
        items,
        loading,
        isInWishlist,
        toggleWishlist,
        removeFromWishlist,
        fetchWishlist,
        totalWishlist: wishlistIds.length,
      }}
    >
      {children}
    </WishlistContext.Provider>
  )
}

export const useWishlist = () => {
  const ctx = useContext(WishlistContext)
  if (!ctx) throw new Error('useWishlist must be used within WishlistProvider')
  return ctx
}
