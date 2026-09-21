/**
 * D 群驗收：§8.1 normalization、§8.2 matching operator、§8.3 多詞語意。
 *
 * **最關鍵的是 §8.3 的「record 層 AND」**：Trial 層 AND 的實作會大幅多報，
 * 而多報在本專案的風險排序裡屬於「誤導」——使用者會以為某個試驗同時符合兩個條件。
 */

import { describe, expect, it } from "vitest";

import {
  browseAll,
  compareTrials,
  matchRecord,
  mergeHits,
  parseQuery,
  recordMatches,
  searchEntries,
  searchLatestShort,
  searchNormalize,
} from "../../src/lib/search.js";
import { searchFile, trials } from "./fixture.js";

describe("§8.1 searchNormalize", () => {
  it("NFKC 折疊全形數字與英文（等價，不是誤命中）", () => {
    expect(searchNormalize("ＡＢＣ１２３")).toBe("abc123");
  });

  it("casefold 大小寫", () => {
    expect(searchNormalize("MK-3475")).toBe("mk-3475");
  });

  it("去前後空白、內部連續空白壓為單一空格", () => {
    expect(searchNormalize("  a   b  ")).toBe("a b");
    expect(searchNormalize("a　　b")).toBe("a b");
  });

  it("**不做**標點移除、不做連字號正規化（§8.1）", () => {
    // 這兩條是刻意的：搜尋要寬鬆但不能寬鬆到把不同的編號視為同一個
    expect(searchNormalize("MK-3475-158")).toBe("mk-3475-158");
    expect(searchNormalize("MK3475158")).toBe("mk3475158");
    expect(searchNormalize("MK-3475-158")).not.toBe(searchNormalize("MK3475158"));
  });

  it("null／undefined 視為空字串", () => {
    expect(searchNormalize(null)).toBe("");
    expect(searchNormalize(undefined)).toBe("");
  });
});

describe("§8.2 matching operator", () => {
  it("空查詢與純空白查詢**不執行搜尋**", () => {
    expect(parseQuery("")).toEqual([]);
    expect(parseQuery("   ")).toEqual([]);
    expect(parseQuery("　")).toEqual([]);
  });

  it("依空白切分為 terms", () => {
    expect(parseQuery("MK 3475")).toEqual(["mk", "3475"]);
  });

  it("substring 比對，不是 prefix-only", () => {
    expect(recordMatches(["abcdef"], ["cde"])).toBe(true);
  });

  it("不做模糊比對、不做同義詞擴展", () => {
    expect(recordMatches(["abcdef"], ["acd"])).toBe(false);
  });
});

describe("§8.3 多詞語意：record 層 AND、欄位層 OR", () => {
  it("同一 record 內兩個 term 分別命中不同欄位 → 命中", () => {
    expect(recordMatches(["alpha", "beta"], ["alpha", "beta"])).toBe(true);
  });

  it("單一 record 缺其中一個 term → 不命中", () => {
    expect(recordMatches(["alpha", "gamma"], ["alpha", "beta"])).toBe(false);
  });

  it("**兩個 term 分別命中同一 Trial 的不同 record → 不算命中**", () => {
    // 這是 Trial 層 AND 的弱化實作會放行的案例，也是 §8.3 明文禁止的那一種多報
    const entries = [
      { r: "r1", t: "t1", f: ["alpha", ""] },
      { r: "r2", t: "t1", f: ["beta", ""] },
    ];
    const hits = searchEntries(trials.slice(0, 0), entries, ["alpha", "beta"]);
    expect(hits).toHaveLength(0);
  });

  it("§7.2：多欄同時命中時列出**全部**命中欄位", () => {
    const hit = matchRecord({ r: "r1", f: ["xx-1", "yy", "xx-2"] }, ["xx"]);
    expect(hit).not.toBeNull();
    expect(hit!.fieldIndexes).toEqual([0, 2]);
  });
});

describe("對真實 artifact 的搜尋", () => {
  it("protocol 可被搜到，且命中欄位索引 0（SHORT_SEARCH_FIELDS 的第一欄）", () => {
    const res = searchLatestShort(trials, parseQuery("MK-3475-158"));
    expect(res).toHaveLength(1);
    expect(res[0]!.trial.protocolRaw).toContain("MK-3475-158");
    expect(res[0]!.hits[0]!.fieldIndexes).toContain(0);
  });

  it("瀏覽狀態列出全部 Trial，且與搜尋結果同一套排序", () => {
    const all = browseAll(trials);
    expect(all).toHaveLength(trials.length);
    const sorted = [...all].sort((a, b) => compareTrials(a.trial, b.trial));
    expect(all.map((x) => x.trial.id)).toEqual(sorted.map((x) => x.trial.id));
  });

  it("**`dateUnknown` 置末**——它沒有日期，放進日期序列任何位置都是偽造", () => {
    const ids = browseAll(trials).map((x) => x.trial);
    const firstUnknown = ids.findIndex((t) => t.dateUnknown);
    if (firstUnknown === -1) throw new Error("fixture 須含 dateUnknown 的 Trial");
    expect(ids.slice(firstUnknown).every((t) => t.dateUnknown)).toBe(true);
  });

  it("history=all 比 latest 搜得到更多 record（scope 切換有可觀察差異）", () => {
    const shortAll = searchFile("searchShortAll");
    const terms = parseQuery("SAME-010");

    const latest = searchLatestShort(trials, terms);
    const all = searchEntries(trials, shortAll.records, terms);

    const latestRecords = latest.reduce((n, h) => n + h.hits.length, 0);
    const allRecords = all.reduce((n, h) => n + h.hits.length, 0);
    expect(allRecords).toBeGreaterThan(latestRecords);
  });

  it("search 檔引用不存在的 trialId → **拋錯而非靜默跳過**", () => {
    // 那是 §9.3.6 I3 的違規。靜默跳過會讓資料缺陷變成「查不到」，比報錯更難追。
    expect(() =>
      searchEntries(trials, [{ r: "r1", t: "不存在", f: ["x"] }], ["x"]),
    ).toThrow(/不存在/);
  });

  it("mergeHits 合併同一 Trial 在多個 scope 檔內的命中，不重複列出 Trial", () => {
    const terms = parseQuery("SAME-010");
    const a = searchLatestShort(trials, terms);
    const b = searchEntries(trials, searchFile("searchShortAll").records, terms);
    const merged = mergeHits([a, b]);

    const ids = merged.map((x) => x.trial.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(merged[0]!.hits.length).toBe(a[0]!.hits.length + b[0]!.hits.length);
  });
});
