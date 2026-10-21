import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "edge-desktop",
      use: {
        ...devices["Desktop Edge"],
        channel: "msedge",
        launchOptions: {
          args: ["--no-sandbox"],
        },
      },
    },
    {
      name: "edge-mobile",
      use: {
        viewport: { width: 390, height: 844 },
        channel: "msedge",
        launchOptions: {
          args: ["--no-sandbox"],
        },
      },
    },
  ],
  webServer: {
    command: "pnpm --dir ../.. dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
