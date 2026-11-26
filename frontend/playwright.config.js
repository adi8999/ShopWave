import { defineConfig } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:4173'

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL,
    headless: true,
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'npm run preview -- --host 127.0.0.1 --port 4173',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 60000,
      },
})
