import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:5173", viewport: { width: 1280, height: 860 }, trace: "off", screenshot: "only-on-failure", launchOptions: { args: ["--lang=en"] } },
});
