import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import toast from 'react-hot-toast'
import client from '../api/client'
import { AuthProvider } from '../context/AuthContext'
import ProtectedRoute from '../components/ProtectedRoute'
import Login from '../pages/Login'
import Register from '../pages/Register'

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

describe('Auth Pages & ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('submits login credentials and stores session on success', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-abc',
        user: { id: 1, name: 'Alice', email: 'alice@test.com', is_admin: false },
      },
    })

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<div>Store Home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
      target: { value: 'alice@test.com' },
    })
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
      target: { value: 'Password123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(client.post).toHaveBeenCalledWith('/auth/login', {
        email: 'alice@test.com',
        password: 'Password123!',
      })
      expect(localStorage.getItem('sw_token')).toBe('jwt-abc')
      expect(screen.getByText('Store Home')).toBeInTheDocument()
    })
  })

  it('shows error toast when login fails', async () => {
    client.post.mockRejectedValueOnce({
      response: { data: { detail: 'Incorrect email or password' } },
    })

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
      target: { value: 'alice@test.com' },
    })
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
      target: { value: 'WrongPass1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Incorrect email or password')
    })
  })

  it('validates register password mismatch and short password before calling API', async () => {
    render(
      <MemoryRouter initialEntries={['/register']}>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.change(screen.getByPlaceholderText('John Doe'), { target: { value: 'Alice' } })
    fireEvent.change(screen.getByPlaceholderText('you@example.com'), { target: { value: 'a@test.com' } })
    fireEvent.change(screen.getByPlaceholderText('At least 8 characters'), { target: { value: 'Password123!' } })
    fireEvent.change(screen.getByPlaceholderText('Repeat your password'), { target: { value: 'Mismatch123!' } })
    fireEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(toast.error).toHaveBeenCalledWith('Passwords do not match')
    expect(client.post).not.toHaveBeenCalled()

    fireEvent.change(screen.getByPlaceholderText('At least 8 characters'), { target: { value: 'short' } })
    fireEvent.change(screen.getByPlaceholderText('Repeat your password'), { target: { value: 'short' } })
    fireEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(toast.error).toHaveBeenCalledWith('Password must be at least 8 characters')
    expect(client.post).not.toHaveBeenCalled()
  })

  it('redirects unauthenticated users from ProtectedRoute and allows authenticated users', () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={['/orders']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route
              path="/orders"
              element={
                <ProtectedRoute>
                  <div>Private Orders</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    unmount()

    localStorage.setItem('sw_user', JSON.stringify({ id: 1, name: 'Alice', email: 'a@test.com' }))
    render(
      <MemoryRouter initialEntries={['/orders']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route
              path="/orders"
              element={
                <ProtectedRoute>
                  <div>Private Orders</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByText('Private Orders')).toBeInTheDocument()
  })
})
