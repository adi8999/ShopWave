import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import client from '../api/client'

const CATEGORIES = ['Electronics', 'Clothing', 'Books', 'Home']

const EMPTY = {
  name: '',
  description: '',
  price: '',
  category: 'Electronics',
  image_url: '',
  stock: '',
  rating: '4.5',
  review_count: '0',
}

export default function ProductForm({ product, onSuccess, onCancel }) {
  const isEditing = Boolean(product)
  const [form, setForm] = useState(
    isEditing
      ? {
          name: product.name,
          description: product.description || '',
          price: product.price,
          category: product.category,
          image_url: product.image_url || '',
          stock: product.stock,
          rating: product.rating,
          review_count: product.review_count,
        }
      : EMPTY
  )
  const [loading, setLoading] = useState(false)

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    const payload = {
      ...form,
      price: parseFloat(form.price),
      stock: parseInt(form.stock, 10),
      rating: parseFloat(form.rating),
      review_count: parseInt(form.review_count, 10),
    }

    try {
      if (isEditing) {
        await client.put(`/admin/products/${product.id}`, payload)
        toast.success('Product updated!')
      } else {
        await client.post('/admin/products', payload)
        toast.success('Product created!')
        setForm(EMPTY)
      }
      onSuccess?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="admin-form">
      <div className="form-grid-2">
        <div className="form-group">
          <label>Product Name *</label>
          <input name="name" value={form.name} onChange={handleChange} required placeholder="e.g. Sony WH-1000XM5" />
        </div>
        <div className="form-group">
          <label>Category *</label>
          <select name="category" value={form.category} onChange={handleChange}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <textarea
          name="description"
          value={form.description}
          onChange={handleChange}
          rows={3}
          placeholder="Brief product description..."
        />
      </div>

      <div className="form-group">
        <label>Image URL</label>
        <input name="image_url" value={form.image_url} onChange={handleChange} placeholder="https://..." />
      </div>

      <div className="form-grid-3">
        <div className="form-group">
          <label>Price ($) *</label>
          <input name="price" type="number" step="0.01" min="0" value={form.price} onChange={handleChange} required placeholder="0.00" />
        </div>
        <div className="form-group">
          <label>Stock *</label>
          <input name="stock" type="number" min="0" value={form.stock} onChange={handleChange} required placeholder="0" />
        </div>
        <div className="form-group">
          <label>Rating (0–5)</label>
          <input name="rating" type="number" step="0.1" min="0" max="5" value={form.rating} onChange={handleChange} placeholder="4.5" />
        </div>
      </div>

      <div className="admin-form-actions">
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Saving…' : isEditing ? 'Update Product' : 'Add Product'}
        </button>
      </div>
    </form>
  )
}
