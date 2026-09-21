/**
 * G／D7／F4 的 e2e 設定。
 *
 * **對 `dist/` 的 production build 量測**，不是 dev server：F1／F4 的數字要對應
 * 使用者實際拿到的位元組，而 dev server 送的是未壓縮、未 bundle 的模組。
 *
 * 資料規模由 `E2E_DATA` 決定（見 scripts/prepare-e2e-data.mjs）：
 * G 群用 fixture，D7／F4 用 production——47 筆量不出效能門檻。
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

export default defineConfig({
  testDir: "tests/e2e",
  // 效能量測要固定樣本，平行會互相干擾
  workers: 1,
  fullyParallel: false,
  reporter: [["list"], ["json", { outputFile: "reports/e2e-results.json" }]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    // G2 的對比量測須關閉任何動畫，否則抓到的是過渡中的顏色
    reducedMotion: "reduce",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx vite preview --port ${PORT} --strictPort`,
    port: PORT,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
