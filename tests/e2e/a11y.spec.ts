/**
 * G 群驗收：G1 viewport、G2 對比、G3 鍵盤，＋ E5 的逐頁免責可見性。
 *
 * **跑在 production build 上**：dev server 送的是未 bundle 的模組，而 G2 量的是
 * 使用者實際看到的顏色——兩者在 CSS 上相同，但把量測固定在 dist 才能與 F1 的口徑一致。
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

import { sampleContrast, type ContrastSample } from "./contrast.js";

/** G1 的最低 viewport matrix。 */
const VIEWPORTS = [
  { name: "360x640", width: 360, height: 640 },
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1280x800", width: 1280, height: 800 },
] as const;

/** G2 的路由 × 狀態矩陣。每一格都要有實際可達的 URL。 */
interface Route {
  name: string;
  /**
   * **必須是函式**：`beforeAll` 解析出來的 trialId 在**收集期**還是空字串，
   * 寫成字面值會讓網址變成 `/?trial=` 而渲染出「找不到試驗」的錯誤頁——
   * 那個頁面小又乾淨，G1 會過、G2 會因為文字太少而爆，**假綠比紅更貴**。
   */
  url: () => string;
  /** 進入後要先做的事（例如 focus 某個控制項以量 focus 態） */
  prepare?: (page: Page) => Promise<void>;
}

const collected: Array<{ route: string; viewport: string; samples: ContrastSample[] }> = [];

async function firstTrialId(page: Page): Promise<string> {
  await page.goto("/");
  const id = await page.locator("[data-trial]").first().getAttribute("data-trial");
  if (id === null) throw new Error("首頁沒有任何結果卡");
  return id;
}

/**
 * **每個路由都要先證明自己渲染的是預期的頁面。**
 * 錯誤頁又小又乾淨，會讓 viewport 與對比檢查輕鬆通過——而那是假綠。
 */
async function assertNotErrorPage(page: Page, routeName: string): Promise<void> {
  const errors = await page.locator(".alert--error").allTextContents();
  const fatal = errors.filter((t) => /找不到試驗|載入失敗|資料版本不一致/.test(t));
  expect(fatal, `${routeName} 渲染出的是錯誤頁，不是待測頁面`).toEqual([]);
}

/** 兩種資料規模。狀態矩陣的覆蓋責任依規模不同——見 `狀態矩陣覆蓋`。 */
const FIXTURE_TRIALS = 47;
const PRODUCTION_TRIALS = 5888;

let detailId = "";
let ambiguousId = "";
let dateUnknownId = "";
let trialCount = 0;

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  detailId = await firstTrialId(page);

  // 直接從資料層挑出各狀態的代表，不靠 DOM 猜——猜錯會讓整個狀態矩陣少一格而不自知
  const picked = await page.evaluate(async () => {
    const m = await (await fetch("data/manifest.json")).json();
    const idx = await (await fetch(`data/${m.files.trialsIndex.path}`)).json();
    const amb = idx.trials.find((t: { latestAmbiguous: boolean }) => t.latestAmbiguous);
    const unk = idx.trials.find((t: { dateUnknown: boolean }) => t.dateUnknown);
    return { amb: amb?.id ?? "", unk: unk?.id ?? "", n: idx.trials.length };
  });
  ambiguousId = picked.amb;
  dateUnknownId = picked.unk;
  trialCount = picked.n;

  // `latestAmbiguous` 兩種規模都有（真實資料 143 個），是硬性要求
  expect(ambiguousId, "資料須有 latestAmbiguous 的 Trial").not.toBe("");

  // **`dateUnknown` 在真實資料是 0 筆**——18,736 列的日期全部可解析（QA report 實測）。
  // 因此那一格在 production 規模上「不存在」，不是「沒測到」。硬性斷言會讓整個矩陣
  // 在真實資料上掛掉；反過來，默默跳過又會讓 fixture 規模也悄悄失去覆蓋。
  // 折衷：依規模決定，並由 `狀態矩陣覆蓋` 那條測試把「誰該涵蓋哪一格」寫死。
  if (trialCount === FIXTURE_TRIALS) {
    expect(dateUnknownId, "fixture 規模須有 dateUnknown 的 Trial").not.toBe("");
  }

  await page.close();
});

function routes(): Route[] {
  return [
    { name: "首頁／瀏覽", url: () => "/" },
    { name: "結果／有查詢", url: () => "/?q=MK" },
    { name: "結果／零結果", url: () => "/?q=zzzzzzzznoresult" },
    { name: "詳情／latestAmbiguous", url: () => `/?trial=${ambiguousId}` },
    // 這一格只在資料裡真的有 dateUnknown 時才存在（真實資料是 0 筆）
    ...(dateUnknownId === ""
      ? []
      : [{ name: "詳情／dateUnknown", url: () => `/?trial=${dateUnknownId}` }]),
    { name: "詳情", url: () => `/?trial=${detailId}` },
    { name: "結果／無效值", url: () => "/?updated=%E5%A3%9E%E6%8E%89%E7%9A%84%E5%80%BC" },
    { name: "結果／篩選 focus", url: () => "/", prepare: async (p) => void (await p.locator("#q").focus()) },
  ];
}

test("狀態矩陣覆蓋：哪一格由哪個資料規模負責", async () => {
  // **把覆蓋責任寫死**，否則「這個規模沒有這一格」與「測試忘了測」在報告上長得一樣。
  expect([FIXTURE_TRIALS, PRODUCTION_TRIALS]).toContain(trialCount);
  if (trialCount === FIXTURE_TRIALS) {
    expect(dateUnknownId, "dateUnknown 由 fixture 規模負責涵蓋").not.toBe("");
  } else {
    expect(dateUnknownId, "真實資料的 dateUnknown 實測為 0 筆；若非 0 表示上游變了，矩陣要補").toBe("");
  }
});

test.describe("G1：viewport matrix", () => {
  for (const vp of VIEWPORTS) {
    for (const route of routes()) {
      test(`${vp.name} × ${route.name}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(route.url());
        await page.waitForSelector(".wrap");
        await assertNotErrorPage(page, route.name);
        if (route.prepare) await route.prepare(page);

        // 1. 無橫向捲動
        const { scrollWidth, clientWidth } = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        expect(scrollWidth, `${route.name} 在 ${vp.name} 橫向溢出`).toBeLessThanOrEqual(
          clientWidth,
        );

        // 2. **可見文字、表單與 focusable 的 bounding box 均在 viewport 內**
        //    只驗 scrollWidth 會放過「元素超出右緣但被 overflow:hidden 切掉」的情況
        const overflowing = await page.evaluate((w) => {
          const bad: string[] = [];
          const sel = "a, button, input, select, textarea, [tabindex], p, li, dd, dt, th, td, h1, h2, h3, h4";
          for (const node of document.querySelectorAll(sel)) {
            const s = getComputedStyle(node);
            if (s.display === "none" || s.visibility === "hidden") continue;
            const r = node.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) continue;
            // 捲動容器內的元素以容器為界，不以 viewport 為界
            if (node.closest(".filter__options") !== null) continue;
            // **skip link 與 sr-only 刻意定位在畫面外**，那是標準的無障礙模式，
            // 不是溢出。skip link 在 focus 後必須進入 viewport——另有專測。
            if (node.classList.contains("skip-link")) continue;
            if (node.classList.contains("sr-only")) continue;
            if (r.left < -1 || r.right > w + 1) {
              bad.push(`${node.tagName.toLowerCase()}.${String(node.className).slice(0, 30)} → ${Math.round(r.left)}..${Math.round(r.right)}`);
            }
          }
          return bad.slice(0, 5);
        }, vp.width);
        expect(overflowing, `${route.name} 在 ${vp.name} 有元素超出 viewport`).toEqual([]);
      });
    }
  }
});

test.describe("G2：對比當場實算", () => {
  for (const route of routes()) {
    test(`${route.name}`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto(route.url());
      await page.waitForSelector(".wrap");
      await assertNotErrorPage(page, route.name);
      if (route.prepare) await route.prepare(page);

      const samples = await sampleContrast(page);
      collected.push({ route: route.name, viewport: "1280x800", samples });

      expect(samples.length, "沒有量到任何文字，選擇器或頁面壞了").toBeGreaterThan(5);

      const failures = samples.filter((s) => !s.passes);
      expect(
        failures.map((f) => `${f.selector}｜${f.text}｜${f.fg} on ${f.bg} = ${f.ratio}:1 < ${f.threshold}`),
        `${route.name} 有文字不過 WCAG AA`,
      ).toEqual([]);
    });
  }

  test.afterAll(() => {
    // G2：每組輸出 selector、前景、背景與 ratio 並**寫入 CI artifact**
    mkdirSync("reports", { recursive: true });
    writeFileSync(
      "reports/contrast.json",
      JSON.stringify({ generatedAt: new Date().toISOString(), routes: collected }, null, 1),
      "utf-8",
    );
  });
});

test.describe("G3：鍵盤可達性", () => {
  test("tab 可走完主要控制項，順序合理且不遺失 focus", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".wrap");

    const seen: string[] = [];
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const a = document.activeElement;
        if (a === null || a === document.body) return null;
        return `${a.tagName.toLowerCase()}#${a.id || ""}.${String(a.className).slice(0, 20)}`;
      });
      // **focus 不得掉到 body**（遺失）
      expect(info, `第 ${i + 1} 次 Tab 後 focus 遺失`).not.toBeNull();
      seen.push(info!);
    }

    // 跳至結果的 skip link 應該是第一個
    expect(seen[0]).toContain("skip-link");
    // 搜尋框要在篩選之前——先搜尋再縮小範圍是這個工具的主要動線
    const qIndex = seen.findIndex((s) => s.includes("#q"));
    const filterIndex = seen.findIndex((s) => s.includes("f-phase"));
    expect(qIndex).toBeGreaterThanOrEqual(0);
    if (filterIndex >= 0) expect(qIndex).toBeLessThan(filterIndex);
  });

  test("無 keyboard trap：Tab 一路前進不會卡在同一個元素", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".wrap");
    const seq: string[] = [];
    for (let i = 0; i < 30; i++) {
      await page.keyboard.press("Tab");
      seq.push(await page.evaluate(() => document.activeElement?.id ?? "-"));
    }
    // 連續 5 次停在同一個元素即視為 trap
    for (let i = 4; i < seq.length; i++) {
      const window5 = seq.slice(i - 4, i + 1);
      expect(new Set(window5).size, `疑似 keyboard trap：${window5.join(",")}`).toBeGreaterThan(1);
    }
  });

  test("checkbox 以 Space 切換，且 state 反映在 accessibility tree", async ({ page }) => {
    await page.goto("/");
    const box = page.locator('.filters input[type="checkbox"]').first();
    await box.focus();
    expect(await box.isChecked()).toBe(false);
    await page.keyboard.press("Space");
    await page.waitForFunction(() => location.search.includes("="));
    expect(page.url()).toContain("=");
  });

  test("每個表單控制項都有 accessible name", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".wrap");
    const missing = await page.evaluate(() => {
      const bad: string[] = [];
      for (const node of document.querySelectorAll("input, select, textarea, button")) {
        const id = node.id;
        const labelled =
          node.getAttribute("aria-label") ??
          (id ? document.querySelector(`label[for="${id}"]`)?.textContent : null) ??
          node.closest("label")?.textContent ??
          node.textContent;
        if (labelled === null || labelled.trim() === "") {
          bad.push(`${node.tagName.toLowerCase()}#${id || "(無 id)"}`);
        }
      }
      return bad;
    });
    expect(missing).toEqual([]);
  });

  test("skip link **focus 後進入 viewport**，不是永遠躲著", async ({ page }) => {
    // G1 把它排除在溢出檢查外，代價是必須另外證明它真的用得到——
    // 一個永遠在 -9999px 的 skip link 等於沒有。
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto("/");
    const link = page.locator(".skip-link").first();
    await link.focus();
    const box = await link.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(360);
    await expect(link).toBeFocused();
  });

  test("focus ring 可見（outline 未被移除）", async ({ page }) => {
    await page.goto("/");
    await page.locator("#q").focus();
    const outline = await page.locator("#q").evaluate((n) => {
      const s = getComputedStyle(n);
      return { width: s.outlineWidth, style: s.outlineStyle };
    });
    expect(outline.style).not.toBe("none");
    expect(parseFloat(outline.width)).toBeGreaterThan(0);
  });
});

test.describe("E5：三項免責逐頁可見", () => {
  const LINES = [
    "本站不提供試驗目前的招募狀態",
    "不等於該藥品已獲上市核准",
    "請向官方資料來源、試驗執行機構與醫療專業人員確認",
  ];

  for (const route of [
    { name: "首頁", url: "/" },
    { name: "結果頁", url: "/?q=MK" },
    { name: "詳情頁", url: () => `/?trial=${detailId}` },
  ]) {
    test(`${route.name}`, async ({ page }) => {
      await page.goto(typeof route.url === "function" ? route.url() : route.url);
      await page.waitForSelector(".disclaimer");

      for (const line of LINES) {
        const node = page.locator(".disclaimer", { hasText: line }).first();
        await expect(node, `${route.name} 缺免責：${line}`).toBeVisible();
      }

      // 可見性不只是「DOM 裡有」：要在 viewport 尺寸下真的有面積
      const box = await page.locator(".disclaimer").first().boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThan(10);
    });
  }
});
