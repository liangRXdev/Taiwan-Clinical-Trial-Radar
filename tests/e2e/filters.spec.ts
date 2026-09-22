/**
 * D4（篩選 × canonical URL × reload）與 D5（呈現層不存在 trial-status 維度）。
 *
 * **這兩條非 e2e 不可**：D4 要斷言「canonical URL 字串精確相等」與「reload 後
 * 控制項狀態精確相等」，happy-dom 的假 `location` 與不會真的重新載入的頁面
 * 兩樣都證明不了。邏輯層的對應斷言在 `tests/web/filter.test.ts`／`urlState.test.ts`。
 *
 * 跑 fixture 規模：D4 驗的是語意與 URL 契約，不是效能。
 */

import { expect, test, type Page } from "@playwright/test";

const FIXTURE_TRIALS = 55;

/** §8.4 的六個維度。**沒有招募／執行狀態**，D5 以此為封閉 oracle。 */
const DIMENSIONS = ["phase", "scale", "applicant", "enroll", "period", "updated"] as const;

/** D5 的 mutation guard：這些字眼不得出現在任何控制項或 URL 參數名。 */
const STATUS_WORDS = ["status", "recruit", "招募", "收案", "執行中", "已結案"];

async function trialIds(page: Page): Promise<string[]> {
  return page.locator("article.card--result").evaluateAll((nodes) =>
    nodes.map((n) => n.getAttribute("data-trial") ?? ""),
  );
}

/** 位址列目前的 query string（含 `?`；無參數時為空字串）。 */
async function query(page: Page): Promise<string> {
  return page.evaluate(() => location.search);
}

/** 勾選中的篩選值，依維度收攏。reload 前後比對用。 */
async function checkedState(page: Page): Promise<Record<string, string[]>> {
  return page.evaluate(() => {
    const out: Record<string, string[]> = {};
    for (const group of document.querySelectorAll<HTMLElement>("[data-dim]")) {
      const dim = group.getAttribute("data-dim")!;
      const range = group.querySelector<HTMLInputElement>("input.filter__range");
      if (range) {
        out[dim] = range.value === "" ? [] : [range.value];
        continue;
      }
      out[dim] = [...group.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')]
        .filter((i) => i.checked)
        .map((i) => i.value)
        .sort();
    }
    return out;
  });
}

async function toggle(page: Page, dim: string, value: string): Promise<void> {
  await page
    .locator(`[data-dim="${dim}"] .filter__option[data-value="${value}"] input`)
    .check();
  await page.waitForFunction(
    (d) => location.search.includes(`${d}=`),
    dim,
  );
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("article.card--result").first()).toBeVisible();
});

test.describe("D4：每個維度各一組，含 canonical URL 與 reload", () => {
  test("fixture 規模正確（小資料會讓多數斷言變成空集合比空集合）", async ({ page }) => {
    const text = await page.locator(".result-count").textContent();
    expect(text).toContain(String(FIXTURE_TRIALS));
  });

  for (const dim of ["phase", "scale", "applicant", "enroll"] as const) {
    test(`${dim}：勾選 → URL、結果、reload 後控制項三者一致`, async ({ page }) => {
      const value = await page
        .locator(`[data-dim="${dim}"] .filter__option`)
        .first()
        .getAttribute("data-value");
      expect(value, `${dim} 沒有任何選項`).not.toBeNull();

      await toggle(page, dim, value!);

      const url = await query(page);
      const ids = await trialIds(page);
      const state = await checkedState(page);

      // canonical URL 精確相等：只有這一個參數，且值經 encodeURIComponent
      expect(url).toBe(`?${dim}=${encodeURIComponent(value!)}`);
      expect(ids.length).toBeGreaterThan(0);
      expect(ids.length).toBeLessThan(FIXTURE_TRIALS);

      // reload 後：URL 不變、結果**順序逐一相同**、控制項狀態精確相等
      await page.reload();
      await expect(page.locator("article.card--result").first()).toBeVisible();
      expect(await query(page)).toBe(url);
      expect(await trialIds(page)).toEqual(ids);
      expect(await checkedState(page)).toEqual(state);
    });
  }

  for (const dim of ["period", "updated"] as const) {
    test(`${dim}：區間輸入 → URL、結果、reload 後控制項三者一致`, async ({ page }) => {
      const range = "2025-01-01..2026-12-31";
      await page.locator(`#f-${dim}`).fill(range);
      await page.locator(`#f-${dim}`).press("Enter");
      await page.waitForFunction((d) => location.search.includes(`${d}=`), dim);

      const url = await query(page);
      expect(url).toBe(`?${dim}=${encodeURIComponent(range)}`);

      const ids = await trialIds(page);
      const state = await checkedState(page);
      expect(state[dim]).toEqual([range]);

      await page.reload();
      expect(await query(page)).toBe(url);
      expect(await trialIds(page)).toEqual(ids);
      expect(await checkedState(page)).toEqual(state);
    });
  }

  test("同維度多選 = **OR**（結果為各自的聯集且無重複）", async ({ page }) => {
    const values = await page
      .locator('[data-dim="phase"] .filter__option')
      .evaluateAll((n) => n.map((x) => x.getAttribute("data-value")!).slice(0, 2));
    expect(values).toHaveLength(2);

    await toggle(page, "phase", values[0]!);
    const a = await trialIds(page);
    await page.goto("/");
    await toggle(page, "phase", values[1]!);
    const b = await trialIds(page);

    await page.goto("/");
    await toggle(page, "phase", values[0]!);
    await toggle(page, "phase", values[1]!);
    const both = await trialIds(page);

    expect(new Set(both)).toEqual(new Set([...a, ...b]));
    expect(both.length).toBe(new Set(both).size);
    // 值依字典序進 URL（§7.4），不是點選順序
    expect(await query(page)).toBe(
      [...values].sort().map((v) => `phase=${encodeURIComponent(v)}`).join("&").replace(/^/, "?"),
    );
  });

  test("跨維度 = **AND**（結果為兩者的交集子集）", async ({ page }) => {
    const phase = await page
      .locator('[data-dim="phase"] .filter__option')
      .first()
      .getAttribute("data-value");
    const scale = await page
      .locator('[data-dim="scale"] .filter__option')
      .first()
      .getAttribute("data-value");

    await toggle(page, "phase", phase!);
    const onlyPhase = await trialIds(page);
    await toggle(page, "scale", scale!);
    const both = await trialIds(page);

    for (const id of both) expect(onlyPhase).toContain(id);
    expect(both.length).toBeLessThanOrEqual(onlyPhase.length);
  });

  test("**重複 query param** 視為同維度多選，並正規化為 canonical 順序", async ({ page }) => {
    const values = await page
      .locator('[data-dim="phase"] .filter__option')
      .evaluateAll((n) => n.map((x) => x.getAttribute("data-value")!).slice(0, 2));
    const reversed = [...values].sort().reverse();

    await page.goto(`/?${reversed.map((v) => `phase=${encodeURIComponent(v)}`).join("&")}`);
    await expect(page.locator(".filters")).toBeVisible();

    const state = await checkedState(page);
    expect(state.phase).toEqual([...values].sort());
  });

  test("**未知參數保留於 URL 且不改寫**——含之後的 canonical 改寫", async ({ page }) => {
    await page.goto("/?utm_source=line&foo=bar");
    await expect(page.locator("article.card--result").first()).toBeVisible();
    expect(await query(page)).toBe("?utm_source=line&foo=bar");
    expect(await trialIds(page)).toHaveLength(Math.min(FIXTURE_TRIALS, 50));

    // **載入時不改寫 URL 是理所當然的，證明不了保留**：要等一次真的改寫。
    // 勾一個篩選使 app 重組 canonical URL，未知參數必須還在。
    const value = await page
      .locator('[data-dim="phase"] .filter__option')
      .first()
      .getAttribute("data-value");
    await toggle(page, "phase", value!);

    const after = await query(page);
    expect(after).toContain("utm_source=line");
    expect(after).toContain("foo=bar");
    expect(after).toContain(`phase=${encodeURIComponent(value!)}`);
  });

  test("**無效值有明確訊息，且不靜默丟棄該條件**", async ({ page }) => {
    await page.goto("/?updated=2026-12-31..2026-01-01");
    const alert = page.locator(".filter__group[data-dim='updated'] .alert--error");
    await expect(alert).toBeVisible();
    // 條件被保留（控制項仍帶原值），不是被吃掉
    expect((await checkedState(page)).updated).toEqual(["2026-12-31..2026-01-01"]);
    // 結果為空而非全部——靜默丟棄會顯示全部 55 筆
    expect(await trialIds(page)).toHaveLength(0);
  });

  test("`enroll` 的 bucket 端點：`20-40` 同時落在兩個相鄰 bucket（D8 的 DOM 對應）", async ({
    page,
  }) => {
    for (const bucket of ["11-30", "31-100"]) {
      await page.goto("/");
      await toggle(page, "enroll", bucket);
      const cards = page.locator("article.card--result");
      const raws = await cards.evaluateAll((nodes) =>
        nodes.map((n) => n.textContent ?? "").filter((t) => t.includes("20-40")),
      );
      expect(raws.length, `bucket ${bucket} 應含 raw 20-40 的卡片`).toBeGreaterThan(0);
    }
  });
});

test.describe("D5：呈現層不存在 trial-status 維度", () => {
  test("**DOM 控制項**恰為六個維度，沒有第七個", async ({ page }) => {
    const dims = await page
      .locator("[data-dim]")
      .evaluateAll((n) => n.map((x) => x.getAttribute("data-dim")!));
    expect(dims.sort()).toEqual([...DIMENSIONS].sort());
  });

  test("**URL parser** 不接受任何 trial-status 參數：給了也不出現在控制項狀態", async ({
    page,
  }) => {
    await page.goto("/?status=recruiting&trialStatus=open&招募=是");
    await expect(page.locator(".filters")).toBeVisible();
    const state = await checkedState(page);
    expect(Object.keys(state).sort()).toEqual([...DIMENSIONS].sort());
    for (const values of Object.values(state)) expect(values).toEqual([]);
  });

  test("**mutation guard**：控制項與 label 不出現狀態字眼", async ({ page }) => {
    const text = (await page.locator(".filters").textContent()) ?? "";
    for (const word of STATUS_WORDS) expect(text).not.toContain(word);

    const attrs = await page.locator(".filters [data-dim], .filters input").evaluateAll((nodes) =>
      nodes.flatMap((n) => [...n.attributes].map((a) => `${a.name}=${a.value}`)),
    );
    for (const a of attrs) {
      for (const word of STATUS_WORDS) expect(a).not.toContain(word);
    }
  });

  test("免責第一項在篩選頁仍可見——「沒有這個維度」要講出來，不是留白", async ({ page }) => {
    await expect(page.locator(".disclaimer").first()).toContainText("不提供試驗目前的招募狀態");
  });
});
