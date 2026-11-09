import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:3011",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command: "uv run uvicorn aerolm.api:app --host 127.0.0.1 --port 8011",
      env: { AEROLM_BACKEND: "rules", AEROLM_API_KEY: "", AEROLM_EVIDENCE_POLICY: "warn" },
      cwd: "..",
      url: "http://127.0.0.1:8011/healthz",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev",
      env: { PORT: "3011", AEROLM_API_URL: "http://127.0.0.1:8011" },
      url: "http://127.0.0.1:3011",
      reuseExistingServer: false,
    },
  ],
});
