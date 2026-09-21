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
    environment: "node",
    include: ["tests/web/**/*.test.ts"],
  },
});
