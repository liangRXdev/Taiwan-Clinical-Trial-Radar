/**
 * D 群驗收：§8.4 篩選維度、值域與組合語意。
 *
 * D5 的主 oracle 是**封閉的 filter schema**：斷言四處（schema／DOM／URL parser／輸出 state）
 * 均不存在 trial-status 維度。這裡守 schema 與 parser 兩處，DOM 那兩處在 UI 測試。
 */

import { describe, expect, it } from "vitest";

import {
  applyFilters,
  categoryOf,
  CONFLICTED,
  DIMENSIONS,
  DIMENSION_FIELD,
  emptyFilter,
  ENROLL_BUCKETS,
  enrollBucketsOf,
  parseDateRange,
  periodCategoryOf,
  UNPROVIDED,
  updatedCategoryOf,
} from "../../src/lib/filter.js";
import { byProtocol, stats, trials } from "./fixture.js";

const wrap = (t: (typeof trials)[number]) => ({ trial: t });
const all = trials.map(wrap);

describe("§8.4 filter schema 是封閉的", () => {
  it("恰為六個維度，**不含招募／執行狀態**", () => {
    expect([...DIMENSIONS]).toEqual([
      "phase",
      "scale",
      "applicant",
      "enroll",
      "period",
      "updated",
    ]);
  });

  it("D5：schema 內不存在任何 trial-status 維度的同義詞", () => {
    const banned = /status|recruit|招募|執行狀態|收案/i;
    for (const d of DIMENSIONS) expect(d).not.toMatch(banned);
    for (const f of Object.values(DIMENSION_FIELD)) expect(f).not.toMatch(banned);
  });

  it("三個 facet 維度與 stats.json 的 facet 名單對齊", () => {
    // §9.3.5：facet 名單是封閉集合，E2 以它為唯一 oracle 來源
    expect(Object.keys(stats.facets).sort()).toEqual(["applicant", "phase", "scale"]);
  });
});

describe("§8.4 分類維度的歸類三者互斥且窮盡", () => {
  it("每個 Trial 在每個分類維度都恰好落入一類", () => {
    for (const t of trials) {
      for (const dim of ["phase", "scale", "applicant"] as const) {
        const c = categoryOf(t, DIMENSION_FIELD[dim]!);
        expect(typeof c).toBe("string");
        expect(c.length).toBeGreaterThan(0);
      }
    }
  });

  it("**衝突欄位歸入「不一致」，不任取一值**", () => {
    const t = trials.find((x) => x.conflictFields.includes("臨床試驗期別"));
    if (t === undefined) throw new Error("fixture 須有 phase 衝突的 Trial");
    expect(categoryOf(t, "臨床試驗期別")).toBe(CONFLICTED);
    // 衝突欄位在 displayFields 中完全省略（§6.4.5），所以連候選值都拿不到
    expect(t.displayFields["臨床試驗期別"]).toBeUndefined();
  });

  it("「不一致」被選中時只回傳該類 trial，不混入具體值", () => {
    const state = { ...emptyFilter(), phase: [CONFLICTED] };
    const res = applyFilters(all, state);
    expect(res.length).toBeGreaterThan(0);
    expect(res.every((x) => x.trial.conflictFields.includes("臨床試驗期別"))).toBe(true);
  });
});

describe("§8.4 enroll 的區間語意", () => {
  it("bucket 是**閉區間**且不重疊、不留縫", () => {
    expect(ENROLL_BUCKETS.map((b) => b.id)).toEqual(["0", "1-10", "11-30", "31-100", "101-"]);
    for (let i = 1; i < ENROLL_BUCKETS.length; i++) {
      const prev = ENROLL_BUCKETS[i - 1]!;
      const cur = ENROLL_BUCKETS[i]!;
      expect(cur.min).toBe((prev.max ?? Infinity) + 1);
    }
  });

  it("D8：一筆 `20-40` **同時**落在 11-30 與 31-100", () => {
    const fake = {
      conflictFields: [],
      displayFields: { 台灣預計受試者人數: { raw: "20-40", typed: { min: 20, max: 40 }, flags: ["numericRange"] } },
    } as unknown as (typeof trials)[number];
    expect(enrollBucketsOf(fake)).toEqual(["11-30", "31-100"]);
  });

  it("其餘數值旗標一律歸「未提供」，**不得猜一個數字進 bucket**", () => {
    for (const typed of [null, "20 人左右"]) {
      const fake = {
        conflictFields: [],
        displayFields: { 台灣預計受試者人數: { raw: "x", typed, flags: [] } },
      } as unknown as (typeof trials)[number];
      expect(enrollBucketsOf(fake)).toEqual([UNPROVIDED]);
    }
  });

  it("0 有自己的 bucket（`sourceZero` 不等於未提供）", () => {
    const fake = {
      conflictFields: [],
      displayFields: { 台灣預計受試者人數: { raw: "0", typed: 0, flags: ["sourceZero"] } },
    } as unknown as (typeof trials)[number];
    expect(enrollBucketsOf(fake)).toEqual(["0"]);
  });
});

describe("§8.4 period 的重疊語意", () => {
  const range: [string, string] = ["2026-01-01", "2026-12-31"];

  const make = (start: string | null, end: string | null) =>
    ({
      conflictFields: [],
      displayFields: {
        試驗預計執行期間起: { raw: "", typed: start, flags: [] },
        試驗預計執行期間迄: { raw: "", typed: end, flags: [] },
      },
    }) as unknown as (typeof trials)[number];

  it("重疊即命中，不是包含", () => {
    expect(periodCategoryOf(make("2025-01-01", "2026-06-01"), range)).toBe(true);
    expect(periodCategoryOf(make("2026-06-01", "2027-06-01"), range)).toBe(true);
    expect(periodCategoryOf(make("2020-01-01", "2030-01-01"), range)).toBe(true);
  });

  it("完全在區間外 → 不命中", () => {
    expect(periodCategoryOf(make("2027-01-01", "2027-12-31"), range)).toBe(false);
    expect(periodCategoryOf(make("2020-01-01", "2020-12-31"), range)).toBe(false);
  });

  it("端點重合仍算重疊（閉區間）", () => {
    expect(periodCategoryOf(make("2026-12-31", "2027-06-01"), range)).toBe(true);
    expect(periodCategoryOf(make("2025-01-01", "2026-01-01"), range)).toBe(true);
  });

  it("**任一端 typed 為 null → 未提供**，不猜另一端", () => {
    expect(periodCategoryOf(make(null, "2026-06-01"), range)).toBe(UNPROVIDED);
    expect(periodCategoryOf(make("2026-06-01", null), range)).toBe(UNPROVIDED);
  });
});

describe("§8.4 updated", () => {
  const range: [string, string] = ["2026-01-01", "2026-12-31"];

  it("latestSourceDate 落於閉區間內", () => {
    const t = { dateUnknown: false, latestSourceDate: "2026-01-01" } as unknown as (typeof trials)[number];
    expect(updatedCategoryOf(t, range)).toBe(true);
  });

  it("**dateUnknown → 未提供**", () => {
    const t = { dateUnknown: true, latestSourceDate: null } as unknown as (typeof trials)[number];
    expect(updatedCategoryOf(t, range)).toBe(UNPROVIDED);
  });
});

describe("§8.4 組合語意：同維度 OR、跨維度 AND", () => {
  it("同維度多選 = OR", () => {
    const values = stats.facets.phase!.buckets.slice(0, 2).map((b) => b.value);
    if (values.length < 2) throw new Error("fixture 的 phase 須有 ≥2 個 bucket");

    const a = applyFilters(all, { ...emptyFilter(), phase: [values[0]!] });
    const b = applyFilters(all, { ...emptyFilter(), phase: [values[1]!] });
    const both = applyFilters(all, { ...emptyFilter(), phase: values });

    expect(both.length).toBe(a.length + b.length);
  });

  it("跨維度 = AND（結果為各自的子集）", () => {
    const phase = stats.facets.phase!.buckets[0]!.value;
    const scale = stats.facets.scale!.buckets[0]!.value;

    const onlyPhase = applyFilters(all, { ...emptyFilter(), phase: [phase] });
    const combined = applyFilters(all, { ...emptyFilter(), phase: [phase], scale: [scale] });

    expect(combined.length).toBeLessThanOrEqual(onlyPhase.length);
    const ids = new Set(onlyPhase.map((x) => x.trial.id));
    expect(combined.every((x) => ids.has(x.trial.id))).toBe(true);
  });

  it("空篩選不排除任何 Trial", () => {
    expect(applyFilters(all, emptyFilter())).toHaveLength(trials.length);
  });
});

describe("§7.4 日期區間的無效值", () => {
  it("格式不符 → null", () => {
    expect(parseDateRange("2026-01-01")).toBeNull();
    expect(parseDateRange("2026/01/01..2026/12/31")).toBeNull();
    expect(parseDateRange("")).toBeNull();
  });

  it("**起晚於迄 → null，不靜默交換**", () => {
    // 使用者寫反時要看到訊息，自動修正會讓他以為自己寫對了
    expect(parseDateRange("2026-12-31..2026-01-01")).toBeNull();
  });

  it("起等於迄 → 合法（單日）", () => {
    expect(parseDateRange("2026-05-05..2026-05-05")).toEqual(["2026-05-05", "2026-05-05"]);
  });

  it("無效值**不得靜默丟棄該條件**——結果為空而非全部", () => {
    const res = applyFilters(all, { ...emptyFilter(), updated: "壞掉的值" });
    expect(res).toHaveLength(0);
    expect(res.length).not.toBe(trials.length);
  });
});

describe("合併後 Trial 的篩選", () => {
  it("多寫法的 Trial 在篩選中只出現一次", () => {
    const merged = trials.filter((t) => t.protocolRaw.length > 1);
    expect(merged.length).toBeGreaterThan(0);
    const res = applyFilters(all, emptyFilter());
    for (const t of merged) {
      expect(res.filter((x) => x.trial.id === t.id)).toHaveLength(1);
    }
  });

  it("fixture 的 SAME-010 確實被合併成一個 Trial", () => {
    const t = byProtocol("SAME-010");
    expect(t.protocolRaw).toContain("SAME-010 ");
    expect(t.protocolRaw.length).toBeGreaterThan(1);
  });
});
