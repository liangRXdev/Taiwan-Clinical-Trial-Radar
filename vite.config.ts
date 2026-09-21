/// <reference types="vitest/config" />
import { defineConfig } from "vite";

export default defineConfig({
  // `public/data/` 由 ETL 產生，Vite 原樣複製到 dist（§9.2 的發布目錄即建置輸入）
  publicDir: "public",
  build: {
    target: "es2022",
    // F1 的預算是「全部 network responses」。把 CSS 併進 JS 會讓量測少一個 response
    // 卻不會讓總量變小，反而使歸因變難——保持分離。
    cssCodeSplit: false,
    // **不出 sourcemap 到 production**：它不在 Tier 0 的載入路徑上，但會佔部署體積
    sourcemap: false,
  },
  test: {
    // 純邏輯測試不需要 DOM，但 UI render 模組要。happy-dom 比 jsdom 快一個數量級，
    // 而 G1／G2 的 viewport 與對比量測本來就不能靠模擬 DOM——那是 Playwright 的工作。
    environment: "happy-dom",
    include: ["tests/web/**/*.test.ts"],
  },
});
