import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/discovery',
  fullyParallel: true,
  workers: 2,
  retries: 0,
  timeout: 30000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5180',
    timezoneId: 'Asia/Seoul',
    trace: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {},
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [1, 0].map((enabled) => ({
    command: `npm run dev -- --host 127.0.0.1 --port ${enabled ? 5180 : 5181} --strictPort`,
    url: `http://127.0.0.1:${enabled ? 5180 : 5181}`,
    reuseExistingServer: false,
    env: { VITE_DISCOVERY_ENABLED: String(enabled), VITE_API_URL: '' },
    timeout: 60000,
  })),
});
