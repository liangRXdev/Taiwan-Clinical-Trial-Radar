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
 * 用法：
 *     node scripts/prepare-e2e-data.mjs             # fixture
 *     node scripts/prepare-e2e-data.mjs production
 */

import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TARGET = join(ROOT, "public", "data");

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

console.log(`${which} → public/data/`);
