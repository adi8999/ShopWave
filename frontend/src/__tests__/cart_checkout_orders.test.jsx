import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import toast from 'react-hot-toast'
import client from '../api/client'
import { AuthProvider } from '../context/AuthContext'
import { CartProvider } from '../context/CartContext'
import Cart from '../pages/Cart'
import Checkout from '../pages/Checkout'
import Orders from '../pages/Orders'

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('../hooks/useOrderTracking', () => ({
  useOrderTracking: () => ({
    status: null,
    paymentStatus: null,
    connected: false,
    lastUpdate: null,
  }),
}))

vi.mock('@stripe/stripe-js', () => ({
  loadStripe: vi.fn(() => Promise.resolve(null)),
}))

vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }) => <div>{children}</div>,
  CardElement: () => <div data-testid="card-element" />,
  useStripe: () => null,
  useElements: () => null,
}))

const SAMPLE_CART = [
  {
    id: 10,
    product_id: 1,
    quantity: 2,
    product: {
      id: 1,
      name: 'Wireless Headphones',
      category: 'Electronics',
      price: '30.00', // Decimal string serialized from backend
      image_url: 'https://example.com/hp.jpg',
    },
  },
]

describe('Cart, Checkout, and Orders Flows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('sw_token', 'test-jwt')
    localStorage.setItem('sw_user', JSON.stringify({ id: 1, name: 'Alice', email: 'alice@test.com' }))
  })

  it('renders Cart totals from Decimal prices and supports quantity update', async () => {
    client.get.mockResolvedValue({ data: SAMPLE_CART })
    client.put.mockResolvedValue({ data: { ...SAMPLE_CART[0], quantity: 3 } })

    render(
      <MemoryRouter initialEntries={['/cart']}>
        <AuthProvider>
          <CartProvider>
            <Cart />
          </CartProvider>
        </AuthProvider>
      </MemoryRouter>
    )

    // Wait for cart items to load: 2 * $30.00 = $60.00 (free shipping >= $50, 8% tax = $4.80, total = $64.80)
    await waitFor(() => {
      expect(screen.getByText('Wireless Headphones')).toBeInTheDocument()
      expect(screen.getByText('FREE')).toBeInTheDocument()
      expect(screen.getByText('$4.80')).toBeInTheDocument()
      expect(screen.getByText('$64.80')).toBeInTheDocument()
    })

    fireEvent.click(document.getElementById('increase-qty-10'))
    await waitFor(() => {
      expect(client.put).toHaveBeenCalledWith('/cart/10', { quantity: 3 })
    })
  })

  it('surfaces backend checkout errors (e.g. 409 stock conflict)', async () => {
    client.get.mockResolvedValue({ data: SAMPLE_CART })
    client.post.mockRejectedValueOnce({
      response: { data: { detail: 'Insufficient stock for Wireless Headphones' } },
    })

    render(
      <MemoryRouter initialEntries={['/checkout']}>
        <AuthProvider>
          <CartProvider>
            <Checkout />
          </CartProvider>
        </AuthProvider>
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Shipping Information')).toBeInTheDocument())

    fireEvent.change(document.getElementById('shipping-name'), { target: { value: 'Alice' } })
    fireEvent.change(document.getElementById('shipping-address'), { target: { value: '123 Main St' } })
    fireEvent.change(document.getElementById('shipping-city'), { target: { value: 'NYC' } })
    fireEvent.change(document.getElementById('shipping-zip'), { target: { value: '10001' } })
    fireEvent.click(document.getElementById('place-order-btn'))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Insufficient stock for Wireless Headphones')
    })
  })

  it('renders Orders list with Decimal amounts and status badges', async () => {
    client.get.mockResolvedValueOnce({
      data: [
        {
          id: 42,
          status: 'awaiting_payment',
          payment_status: 'pending',
          total_amount: '64.80',
          created_at: '2026-11-26T10:00:00Z',
          shipping_name: 'Alice',
          shipping_address: '123 Main St',
          shipping_city: 'NYC',
          shipping_zip: '10001',
          items: [
            {
              id: 1,
              product_id: 1,
              quantity: 2,
              unit_price: '32.40',
              product: { name: 'Wireless Headphones', image_url: 'https://example.com/hp.jpg' },
            },
          ],
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/orders?success=42']}>
        <AuthProvider>
          <Orders />
        </AuthProvider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Order #42 placed successfully!')).toBeInTheDocument()
      expect(screen.getByText('Awaiting Payment')).toBeInTheDocument()
      expect(screen.getAllByText('$64.80').length).toBeGreaterThan(0)
      expect(screen.getByText(/Alice — 123 Main St/)).toBeInTheDocument()
    })
  })
})
