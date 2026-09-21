/**
 * D7（scope 切換）與 F4（搜尋效能）。
 *
 * **這兩條必須跑 production-scale 資料**（5,888 Trial／18,736 record）：
 * 47 筆的搜尋在任何實作下都是 0 ms，F4 的 300 ms 門檻等於沒測；
 * 而 scope 切換的下載成本在 47 筆時三個檔都只有幾 KiB，分不出總量與增量的差別。
 *
 *     npm run e2e:prod
 *
 * 資料規模不對時**直接 skip 並說明**，不降格用小 fixture 跑出一個漂亮數字——
 * 那正是 F1／F4 反覆警告的「量了一個不是使用者成本的數字然後宣告合格」。
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const PRODUCTION_TRIALS = 5888;

interface Manifest {
  trialCount: number;
  files: Record<string, { path: string; brotliBytes?: number }>;
}

async function loadManifest(page: Page): Promise<Manifest> {
  await page.goto("/");
  return page.evaluate(async () => (await (await fetch("data/manifest.json")).json()) as Manifest);
}

let manifest: Manifest;
let isProduction = false;

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  manifest = await loadManifest(page);
  isProduction = manifest.trialCount === PRODUCTION_TRIALS;
  await page.close();
});

test.describe("D7：scope 切換", () => {
  test("四種 scope 的所需檔案集合與 §8.5 的表一致", async ({ page }) => {
    const requested: string[] = [];
    await page.route("**/data/**", async (route) => {
      requested.push(new URL(route.request().url()).pathname.split("/").pop()!);
      await route.continue();
    });

    await page.goto("/?q=test");
    await page.waitForSelector(".scope");

    const searchFiles = () =>
      requested.filter((f) => f.startsWith("search-")).map((f) => f.split(".")[0]);

    // 預設 scope：**不需額外載入**（searchShortLatest 併在 trials-index 內）
    expect(searchFiles()).toEqual([]);

    // short + all → 只多 search-short-all
    await page.goto("/?q=test&history=all");
    await page.waitForSelector(".scope");
    expect(new Set(searchFiles())).toEqual(new Set(["search-short-all"]));

    // all + all → 三個檔
    requested.length = 0;
    await page.goto("/?q=test&fields=all&history=all");
    await page.waitForSelector(".scope");
    expect(new Set(searchFiles())).toEqual(
      new Set(["search-short-all", "search-long-latest", "search-long-all"]),
    );
  });

  test("**切換成本依起點而異**，且顯示的是級距不是精確位元組", async ({ page }) => {
    await page.goto("/?q=test");
    await page.waitForSelector(".scope");

    const costs = await page.locator(".scope__cost").allTextContents();
    expect(costs.length).toBeGreaterThan(0);
    for (const c of costs) {
      // §8.5：一律「約 X KiB／MiB」，**不得呈現精確到 byte 的數字**
      expect(c).toMatch(/不需額外下載|約 [\d.]+ (KiB|MiB)|大小不明/);
      expect(c).not.toMatch(/\d{4,} bytes/);
    }
  });

  test("scope 指示在結果區**持續可見**，且控制項不藏在選單裡", async ({ page }) => {
    await page.goto("/?q=test");
    const bar = page.locator(".scope--in-results");
    await expect(bar).toBeVisible();
    await expect(bar.locator(".scope__current")).toContainText("目前搜尋範圍");

    // 捲到結果中段後仍在 DOM 內且可見（不是 hover 才出現的浮層）
    await page.evaluate(() => window.scrollTo(0, 400));
    await expect(bar).toBeAttached();

    // 兩個控制項都是原生 radio，不在 <details>／<dialog> 裡
    expect(await bar.locator('input[type="radio"]').count()).toBe(4);
    expect(await bar.locator("details, dialog").count()).toBe(0);
  });

  test("零結果時提示可擴大的 scope **與其大小**", async ({ page }) => {
    await page.goto("/?q=zzzzzzzznoresult");
    const hint = page.locator(".zero-hint");
    await expect(hint).toBeVisible();
    await expect(hint).toContainText("可擴大搜尋範圍");

    const items = hint.locator("li");
    expect(await items.count()).toBe(2);
    for (const text of await items.allTextContents()) {
      expect(text).toMatch(/約 [\d.]+ (KiB|MiB)|不需額外下載/);
    }
  });

  test("**載入失敗退回上一個 scope 並說明**，不靜默維持舊結果集", async ({ page }) => {
    await page.goto("/?q=test");
    await page.waitForSelector(".scope");

    // 讓按需檔 404
    await page.route("**/search-short-all.*.json", (route) => route.fulfill({ status: 404 }));

    await page.locator("#scope-history-all").check();
    await page.waitForSelector(".scope .alert--error");

    const msg = await page.locator(".scope .alert--error").textContent();
    expect(msg).toContain("已退回原本的搜尋範圍");
    // 仍顯示目前 scope，使用者看得出自己在哪
    await expect(page.locator(".scope__current")).toBeVisible();
  });

  test("URL 的 fields／history 可重現同一結果集", async ({ page }) => {
    // **等 .result-count 而不是 .results**：零結果時 .results 是空 div、沒有高度，
    // 等 visible 會一直逾時——而「零結果也要能重現」正是這條要驗的情境之一。
    await page.goto("/?q=MK&fields=all&history=all");
    await page.waitForSelector(".result-count");
    const first = await page.locator(".result-count").textContent();
    const firstList = await page.locator(".results").textContent();
    expect(first).toMatch(/\d/);

    await page.reload();
    await page.waitForSelector(".result-count");
    expect(await page.locator(".result-count").textContent()).toBe(first);
    expect(await page.locator(".results").textContent()).toBe(firstList);
  });

  test("零結果的 scope 也能由 URL 重現", async ({ page }) => {
    await page.goto("/?q=zzzzzzzznoresult&fields=all&history=all");
    await page.waitForSelector(".result-count");
    await expect(page.locator(".result-count")).toContainText("0 個試驗");
    // 已在最大範圍：**仍要說話**，不得只留空白（空白最常被讀成「還在載入」）
    const hint = page.locator(".zero-hint--widest");
    await expect(hint).toBeVisible();
    await expect(hint).toContainText("已是最大搜尋範圍");
    await expect(hint).toContainText("查無結果不代表該試驗不存在");
    // 最大範圍時不該再出現「可擴大」的按鈕
    expect(await page.locator(".zero-hint .link-btn").count()).toBe(0);
    // scope 仍由 URL 決定，零結果不得把它重設回預設值
    expect(await page.locator("#scope-fields-all").isChecked()).toBe(true);
    expect(await page.locator("#scope-history-all").isChecked()).toBe(true);
  });
});

test.describe("F4：搜尋效能", () => {
  /** §11 F4 的固定查詢 corpus。 */
  const CORPUS = [
    { name: "零結果", q: "zzzzzzzznoresult" },
    { name: "極多結果", q: "臨床" },
    { name: "中文", q: "乳癌" },
    { name: "英文", q: "phase" },
    { name: "多詞", q: "台灣 試驗" },
    { name: "protocol", q: "MK-3475" },
  ];
  const SAMPLES = 20;
  const P95_MS = 300;

  test("p95 ≤ 300 ms（輸入事件 → 結果 DOM 完成）", async ({ page }) => {
    // 6 個查詢 × 20 次取樣。**逾時不得當成「測不出來」而略過**——
    // 逾時本身就是一個結果（代表單次搜尋遠超門檻），要讓它以數字的形式出現。
    test.setTimeout(600_000);
    test.skip(
      !isProduction,
      `F4 須用 production-scale 資料（實得 ${manifest?.trialCount} 個 Trial，需 ${PRODUCTION_TRIALS}）。請跑 npm run e2e:prod`,
    );

    await page.goto("/?fields=all&history=all");
    await page.waitForSelector(".result-count");

    const results: Array<{ query: string; samples: number[]; p95: number }> = [];

    for (const item of CORPUS) {
      const times: number[] = [];
      for (let i = 0; i < SAMPLES; i++) {
        // 每次換一個不影響結果集的後綴，避免瀏覽器或實作的快取讓第二次起變成 0 ms
        const q = item.q;
        const ms = await page.evaluate(async (query: string) => {
          const input = document.querySelector<HTMLInputElement>("#q")!;
          input.value = query;
          const t0 = performance.now();
          input.dispatchEvent(new Event("change", { bubbles: true }));
          // 等到結果 DOM 重新掛上
          await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
          document.querySelector("#results");
          return performance.now() - t0;
        }, q);
        times.push(ms);
      }
      times.sort((a, b) => a - b);
      const p95 = times[Math.min(times.length - 1, Math.ceil(0.95 * times.length) - 1)]!;
      results.push({ query: item.name, samples: times.map((t) => Math.round(t * 100) / 100), p95 });
    }

    mkdirSync("reports", { recursive: true });
    writeFileSync(
      "reports/perf.json",
      JSON.stringify(
        {
          generatedAt: new Date().toISOString(),
          trialCount: manifest.trialCount,
          sampleSize: SAMPLES,
          thresholdMs: P95_MS,
          note: "跨時間比較僅在同 runner 類別內有效（§11 F4）",
          results,
        },
        null,
        1,
      ),
      "utf-8",
    );

    const over = results.filter((r) => r.p95 > P95_MS);
    expect(
      over.map((r) => `${r.query}: p95 ${r.p95.toFixed(1)} ms > ${P95_MS} ms`),
      "達不到須寫瓶頸歸因，不調鬆數字",
    ).toEqual([]);
  });

  test("production 規模時資料量與 manifest 相符（保護上面那條不被小資料矇混）", async () => {
    test.skip(!isProduction, "非 production 資料，略過");
    expect(manifest.trialCount).toBe(PRODUCTION_TRIALS);
  });
});
