import { test, expect } from '@playwright/test'

test.describe('ShopWave Customer Journey E2E', () => {
  test('customer logs in, browses products, updates cart, checks out, and views order', async ({ page }) => {
    let cartItems = []
    let orders = []

    // Mock backend API endpoints cleanly with realistic test payloads
    await page.route('**/api/**', async (route) => {
      const req = route.request()
      const url = new URL(req.url())
      const path = url.pathname

      if (path === '/api/auth/login' && req.method() === 'POST') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            access_token: 'e2e-test-jwt',
            token_type: 'bearer',
            user: { id: 1, name: 'E2E User', email: 'e2e@shopwave.test', is_admin: false },
          }),
        })
      }

      if (path === '/api/products/categories') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: '["Electronics"]' })
      }

      if (path === '/api/products' && req.method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 1,
                name: 'Studio Headphones',
                description: 'Crisp studio sound',
                price: '60.00',
                category: 'Electronics',
                image_url: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300',
                stock: 5,
                rating: '4.8',
                review_count: 12,
                created_at: '2026-11-26T00:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            pages: 1,
            limit: 20,
          }),
        })
      }

      if (path === '/api/cart' && req.method() === 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(cartItems) })
      }

      if (path === '/api/cart' && req.method() === 'POST') {
        cartItems = [
          {
            id: 101,
            product_id: 1,
            quantity: 1,
            product: {
              id: 1,
              name: 'Studio Headphones',
              price: '60.00',
              category: 'Electronics',
              image_url: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300',
            },
          },
        ]
        return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(cartItems[0]) })
      }

      if (path === '/api/cart' && req.method() === 'DELETE') {
        cartItems = []
        return route.fulfill({ status: 204, body: '' })
      }

      if (path === '/api/orders/checkout' && req.method() === 'POST') {
        const body = req.postDataJSON()
        const newOrder = {
          id: 501,
          total_amount: '60.00',
          status: 'awaiting_payment',
          payment_status: 'pending',
          shipping_name: body.shipping_name,
          shipping_address: body.shipping_address,
          shipping_city: body.shipping_city,
          shipping_zip: body.shipping_zip,
          created_at: '2026-11-26T10:00:00Z',
          items: [
            {
              id: 1,
              product_id: 1,
              quantity: 1,
              unit_price: '60.00',
              product: { id: 1, name: 'Studio Headphones', image_url: '' },
            },
          ],
        }
        orders = [newOrder]
        cartItems = []
        return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(newOrder) })
      }

      if (path === '/api/orders/me' && req.method() === 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(orders) })
      }

      if (path.endsWith('/ws-ticket')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ticket":"e2e-ws-ticket"}' })
      }

      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    })

    // 1. Login
    await page.goto('/login')
    await page.fill('#login-email', 'e2e@shopwave.test')
    await page.fill('#login-password', 'Password123!')
    await page.click('#login-submit-btn')
    await expect(page).toHaveURL(/\/$/)

    // 2. Browse catalog and add to cart
    await page.goto('/products')
    await expect(page.getByText('Studio Headphones')).toBeVisible()
    await page.click('#add-to-cart-1')

    // 3. View cart and proceed to checkout
    await page.goto('/cart')
    await expect(page.getByText('$60.00').first()).toBeVisible()
    await page.click('#checkout-btn')
    await expect(page).toHaveURL(/\/checkout/)

    // 4. Fill shipping details & place order
    await page.fill('#shipping-name', 'E2E User')
    await page.fill('#shipping-address', '100 Test Blvd')
    await page.fill('#shipping-city', 'Austin')
    await page.fill('#shipping-zip', '78701')
    await page.click('#place-order-btn')

    // 5. Verify order view and route restoration on reload
    await expect(page).toHaveURL(/\/orders\?success=501/)
    await expect(page.getByText('Order #501 placed successfully!')).toBeVisible()
    await page.reload()
    await expect(page).toHaveURL(/\/orders\?success=501/)
    await expect(page.getByText('Awaiting Payment')).toBeVisible()
  })
})
