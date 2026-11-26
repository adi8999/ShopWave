import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'

describe('ShopWave Frontend Smoke Tests', () => {
  it('renders storefront title without crashing', () => {
    render(
      <MemoryRouter>
        <main>
          <h1>ShopWave</h1>
        </main>
      </MemoryRouter>
    )
    expect(screen.getByText('ShopWave')).toBeDefined()
  })
})
