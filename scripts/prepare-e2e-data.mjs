/**
 * 把指定的 artifact 複製到 `public/data/`，供 e2e 使用。
 *
 * 兩種規模，**各自測不同的東西**：
 *
 * - `fixture`（預設，47 Trial）：G1／G2／G3／E5。小而快，且與 vitest 吃同一份資料，
 *   兩邊對不起來時可以直接比對。
 * - `production`（5,888 Trial，取自 `.cache/staging`）：D7 與 F4。
 *   **效能與 scope 切換成本不能用 47 筆量**——F4 明文要求 production-scale fixture，
 *   而 47 筆的搜尋在任何實作下都會是 0 ms，那條門檻等於沒測。
 *
 * **目標是 `dist/data/`，不是 `public/data/`。**
 *
 * `public/data/` 是**已發布的資料**，進版控（§9.2.3：Cloudflare Pages 以 `main` 的
 * commit 為 build 的唯一輸入）。而 promotion 的第二步就是 `git add -A`——測試資料
 * 只要落在那個目錄，一次 e2e 之後跑更新管線就會把 47／55 筆的 fixture 當成正式
 * 資料集 commit 出去，而且它長得跟正常 commit 一模一樣。
 *
 * `dist/` 是 build 產物且已 gitignore，vite preview 直接服務它，因此改寫這裡沒有
 * 任何東西會被誤存。代價是**必須在 `npm run build` 之後才複製**（build 會清空 dist）。
 *
 * 用法：
 *     npm run build && node scripts/prepare-e2e-data.mjs             # fixture
 *     npm run build && node scripts/prepare-e2e-data.mjs production
 */

import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TARGET = join(ROOT, "dist", "data");

const SOURCES = {
  fixture: join(ROOT, "tests", "fixtures", "web_artifact"),
  production: join(ROOT, ".cache", "staging"),
};

const which = process.argv[2] ?? "fixture";
const src = SOURCES[which];

if (src === undefined) {
  console.error(`未知的資料規模：${which}（可用：${Object.keys(SOURCES).join("、")}）`);
  process.exit(2);
}
if (!existsSync(join(ROOT, "dist", "index.html"))) {
  // build 會清空 dist；先複製再 build 等於什麼都沒複製，而 e2e 會拿到 404 頁面
  // 跑完並全綠（G1 曾經就是這樣假綠的）。
  console.error("找不到 dist/index.html：請先 npm run build，再複製 e2e 資料");
  process.exit(1);
}
if (!existsSync(src)) {
  // **不靜默退回 fixture**：那會讓 F4 拿 47 筆量出一個漂亮但無意義的數字
  console.error(
    `找不到 ${which} 資料：${src}\n` +
      (which === "production"
        ? "請先跑：uv run python scripts/build_data.py --source .cache/205.csv --dry-run --staging .cache/staging --qa .cache/qa"
        : "請先跑：uv run python scripts/build_web_fixture.py"),
  );
  process.exit(1);
}

rmSync(TARGET, { recursive: true, force: true });
mkdirSync(TARGET, { recursive: true });
cpSync(src, TARGET, { recursive: true });

console.log(`${which} → dist/data/`);
