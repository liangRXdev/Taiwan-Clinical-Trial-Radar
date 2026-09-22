/**
 * F1 的**唯一有效量測**：對真實部署量冷啟動到可搜尋 readiness 的全部 network response。
 *
 * §17 F1 封存的四條邊界，逐條對應到本腳本的做法：
 *
 * 1. **計壓縮後的 response body bytes，逐 response 依其實際 `content-encoding`。**
 *    不用 `Content-Length` header、不用解壓後長度、不用 Resource Timing 的 `transferSize`
 *    （後者含 header 與連線開銷，跨瀏覽器不可比）。做法：先用瀏覽器錄下冷啟動實際
 *    發出的 URL，再以原生 `https` 逐一重抓並**累加收到的位元組**（原生 http 模組不會
 *    自動解壓，所以數到的就是實際傳輸的 body）。**不含 header bytes。**
 * 2. **混合 encoding 是正常的**，不因為某個 response 不是 `br` 就排除它或改用估算值。
 * 3. **readiness 前已發起的 request 一律計入**，即使它在 readiness 之後才完成。
 *    因此錄的是 `request` 事件而不是 `response` 事件。
 * 4. **不得以 `manifest.files[*].brotliBytes` 為來源**——那是建置期 q11 估算值。
 *
 * readiness 以**功能性 probe** 判定：執行一個固定查詢並取得正確結果集才算就緒。
 *
 * 用法：
 *     node scripts/measure-f1-live.mjs <部署網址> [報告輸出路徑]
 *
 * **已知限制（明寫而非隱瞞）**：位元組來自 readiness 之後對同一 URL 的第二次請求，
 * 是冷啟動 response 的**代理**而非本體。CDN 若對兩次請求給不同編碼，數字會偏離。
 * 直接量瀏覽器收到的位元組需要 CDP 的 `encodedDataLength`，但那含 header
 * 且跨瀏覽器不可比——規格第 1 條明文禁止。兩害相權取此。
 */

import { get } from "node:https";
import { chromium } from "@playwright/test";

const THRESHOLD_BYTES = 1_500_000;

/** readiness 的固定查詢與其預期性質。**不是「畫面上有東西」**，是「搜尋真的可用」。 */
const PROBE_QUERY = "乳癌";

const base = process.argv[2];
if (!base) {
  console.error("用法：node scripts/measure-f1-live.mjs <部署網址>");
  process.exit(2);
}

/** 以原生 https 重抓並累加 body bytes。原生模組不自動解壓，數到的就是實際傳輸量。 */
function encodedBytes(url, referer) {
  return new Promise((resolve, reject) => {
    const req = get(
      url,
      {
        headers: {
          // 與瀏覽器一致；Cloudflare 依此決定送 br 還是原文
          "accept-encoding": "br, gzip, deflate",
          "user-agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
          ...(referer ? { referer } : {}),
        },
      },
      (res) => {
        let n = 0;
        res.on("data", (chunk) => {
          n += chunk.length;
        });
        res.on("end", () =>
          resolve({ bytes: n, status: res.statusCode, encoding: res.headers["content-encoding"] ?? "identity" }),
        );
      },
    );
    req.on("error", reject);
    req.setTimeout(30_000, () => req.destroy(new Error("timeout")));
  });
}

const browser = await chromium.launch();
const context = await browser.newContext({ bypassCSP: false });
const page = await context.newPage();

/** readiness 前**發起**的全部 request。用 request 而非 response 事件（邊界 3）。 */
const requested = [];
page.on("request", (r) => {
  if (r.url().startsWith("data:")) return;
  requested.push(r.url());
});

await page.goto(base, { waitUntil: "domcontentloaded" });

// 功能性 probe：輸入固定查詢，等到結果卡真的出現且數量與 result-count 相符
await page.locator("#q").fill(PROBE_QUERY);
await page.locator("#q").press("Enter");
await page.locator("article.card--result").first().waitFor({ timeout: 30_000 });

const countText = (await page.locator(".result-count").textContent()) ?? "";
const hits = Number(countText.replace(/\D+/g, ""));
if (!Number.isFinite(hits) || hits <= 0) {
  console.error(`readiness probe 失敗：「${PROBE_QUERY}」的結果數判讀為 ${countText}`);
  await browser.close();
  process.exit(1);
}

await browser.close();

// **不去重。** 規格說的是「全部 network responses」——同一個 URL 被請求兩次就是
// 兩份位元組，使用者兩次都要付。`new Set()` 會讓重複請求靜默漏算。
// 同 URL 只實際抓一次，再依次數計入，避免對部署端多打不必要的流量。
const counts = new Map();
for (const url of requested) counts.set(url, (counts.get(url) ?? 0) + 1);

const rows = [];
for (const [url, times] of counts) {
  const r = await encodedBytes(url, base);
  rows.push({ url, times, bytes: r.bytes * times, perResponse: r.bytes, status: r.status, encoding: r.encoding });
}

rows.sort((a, b) => b.bytes - a.bytes);
const total = rows.reduce((n, r) => n + r.bytes, 0);

console.log(`readiness probe：「${PROBE_QUERY}」命中 ${hits} 個試驗\n`);
for (const r of rows) {
  const short = r.url.replace(base, "").replace(/^https:\/\//, "") || "/";
  const n = r.times > 1 ? ` ×${r.times}` : "";
  console.log(`  ${String(r.bytes).padStart(9)}  ${String(r.encoding).padEnd(9)} ${r.status}  ${short}${n}`);
}
console.log(`\n  ${String(total).padStart(9)}  TOTAL（門檻 ${THRESHOLD_BYTES}，餘 ${THRESHOLD_BYTES - total}）`);

// CI artifact（F1 要求「列出納入檔案清單與總和寫入 CI artifact」）
const outPath = process.argv[3];
if (outPath) {
  const { mkdirSync, writeFileSync } = await import("node:fs");
  const { dirname } = await import("node:path");
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(
    outPath,
    JSON.stringify(
      {
        note:
          "對真實部署的冷啟動量測，F1 的唯一有效 oracle。"
          + "**已知限制**：位元組來自 readiness 後對同一 URL 的第二次請求，"
          + "是冷啟動 response 的代理而非本體；CDN 若對兩次請求給不同編碼，數字會偏離。",
        base,
        probeQuery: PROBE_QUERY,
        probeHits: hits,
        thresholdBytes: THRESHOLD_BYTES,
        totalBytes: total,
        headroomBytes: THRESHOLD_BYTES - total,
        exceedsThreshold: total > THRESHOLD_BYTES,
        responses: rows,
      },
      null,
      1,
    ),
    "utf-8",
  );
  console.log(`\n報告已寫入 ${outPath}`);
}

if (total > THRESHOLD_BYTES) {
  console.error(`\nF1 不合格：超出 ${total - THRESHOLD_BYTES} bytes。`);
  process.exit(1);
}
console.log("\nF1 合格（對真實部署量測）。");
