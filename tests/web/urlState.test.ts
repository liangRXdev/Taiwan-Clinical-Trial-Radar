/**
 * D 群驗收：§7.4 URL state schema、§8.5 scope 檔案集合。
 *
 * D4 要求「**canonical URL 字串精確相等**」。順序、編碼、重複參數、未知參數任一走樣，
 * 分享出去的連結就重現不出同一結果集——而使用者不會知道自己看到的是不同的東西。
 */

import { describe, expect, it } from "vitest";

import { emptyFilter } from "../../src/lib/filter.js";
import {
  DEFAULT_SCOPE,
  estimatedBytes,
  filesFor,
  filesToLoad,
  formatSize,
  SCOPE_FILES,
  scopeKey,
  widerScopes,
} from "../../src/lib/scope.js";
import { buildUrl, emptyState, isBrowsing, parseUrl, PARAM_ORDER } from "../../src/lib/urlState.js";
import { manifest } from "./fixture.js";

describe("§7.4 canonical query string", () => {
  it("**只輸出非預設值**：預設 scope 不出現在 URL", () => {
    const s = emptyState();
    expect(buildUrl(s)).toBe("");
    expect(s.scope).toEqual(DEFAULT_SCOPE);
  });

  it("依 PARAM_ORDER 排列，不是依輸入順序", () => {
    const { state } = parseUrl("?history=all&phase=X&q=abc&fields=all");
    expect(buildUrl(state)).toBe("?q=abc&phase=X&fields=all&history=all");
  });

  it("同維度多值以重複參數表達，**值依字典序排列**", () => {
    const { state } = parseUrl("?phase=Z&phase=A&phase=M");
    expect(buildUrl(state)).toBe("?phase=A&phase=M&phase=Z");
  });

  it("值以 encodeURIComponent 編碼", () => {
    const s = emptyState();
    s.q = "中文 & 符號";
    expect(buildUrl(s)).toBe("?q=%E4%B8%AD%E6%96%87%20%26%20%E7%AC%A6%E8%99%9F");
  });

  it("**未知參數忽略但保留於 URL 不改寫**", () => {
    const { state } = parseUrl("?q=abc&utm_source=line&unknown=1");
    expect(state.unknown).toEqual([
      ["utm_source", "line"],
      ["unknown", "1"],
    ]);
    expect(buildUrl(state)).toBe("?q=abc&utm_source=line&unknown=1");
  });

  it("parse → build 為冪等（canonical 形式的不動點）", () => {
    const canonical = "?q=abc&phase=A&phase=B&enroll=11-30&fields=all&history=all";
    const once = buildUrl(parseUrl(canonical).state);
    const twice = buildUrl(parseUrl(once).state);
    expect(once).toBe(canonical);
    expect(twice).toBe(once);
  });

  it("PARAM_ORDER 與 §7.4 的表格順序一致", () => {
    expect([...PARAM_ORDER]).toEqual([
      "q",
      "trial",
      "protocol",
      "phase",
      "scale",
      "applicant",
      "enroll",
      "period",
      "updated",
      "fields",
      "history",
    ]);
  });

  it("D5：URL parser 不接受任何 trial-status 參數", () => {
    const { state } = parseUrl("?status=recruiting&recruiting=1&招募=是");
    // 一律落入 unknown（保留但不解讀），**不得**有對應的 filter 維度
    expect(state.unknown.map(([k]) => k).sort()).toEqual(["recruiting", "status", "招募"]);
    expect(state.filters).toEqual(emptyFilter());
  });
});

describe("§7.4 無效值", () => {
  it("period／updated 格式錯 → 回報錯誤且**保留該條件**", () => {
    const { state, errors } = parseUrl("?updated=2026-13-99");
    expect(errors).toHaveLength(1);
    expect(errors[0]!.param).toBe("updated");
    // 保留：丟掉會讓使用者以為篩選生效了
    expect(state.filters.updated).toBe("2026-13-99");
  });

  it("fields／history 非法值 → 回報錯誤並維持預設", () => {
    const { state, errors } = parseUrl("?fields=everything&history=forever");
    expect(errors.map((e) => e.param).sort()).toEqual(["fields", "history"]);
    expect(state.scope).toEqual(DEFAULT_SCOPE);
  });

  it("**不得靜默回首頁**：錯誤與 state 同時回傳，呼叫端才顯示得出訊息", () => {
    const { state, errors } = parseUrl("?q=abc&updated=壞");
    expect(errors).toHaveLength(1);
    expect(state.q).toBe("abc");
  });
});

describe("isBrowsing", () => {
  it("無查詢、無篩選、無詳情 → 瀏覽狀態", () => {
    expect(isBrowsing(emptyState())).toBe(true);
    expect(isBrowsing(parseUrl("?fields=all").state)).toBe(true);
  });

  it("純空白查詢仍是瀏覽狀態（§8.2）", () => {
    expect(isBrowsing(parseUrl("?q=%20%20").state)).toBe(true);
  });

  it("有任一篩選即非瀏覽狀態", () => {
    expect(isBrowsing(parseUrl("?phase=A").state)).toBe(false);
    expect(isBrowsing(parseUrl("?updated=2026-01-01..2026-12-31").state)).toBe(false);
  });
});

describe("§8.5 scope → 所需檔案集合", () => {
  it("四種組合的集合與規格表一致", () => {
    expect(SCOPE_FILES["short|latest"]).toEqual([]);
    expect(SCOPE_FILES["short|all"]).toEqual(["searchShortAll"]);
    expect(SCOPE_FILES["all|latest"]).toEqual(["searchLongLatest"]);
    expect(SCOPE_FILES["all|all"]).toEqual([
      "searchShortAll",
      "searchLongLatest",
      "searchLongAll",
    ]);
  });

  it("預設 scope 不需額外載入（searchShortLatest 併在 index 內）", () => {
    expect(filesFor(DEFAULT_SCOPE)).toEqual([]);
  });

  it("**已在快取中的檔案不得重複計入**", () => {
    const target = { fields: "all", history: "all" } as const;
    const loaded = new Set(["searchShortAll" as const]);
    expect(filesToLoad(target, loaded)).toEqual(["searchLongLatest", "searchLongAll"]);
  });

  it("切換成本依起點而異——這正是 v0.8 記單一數字的歧義所在", () => {
    const target = { fields: "all", history: "all" } as const;
    const fromDefault = filesToLoad(target, new Set());
    const fromShortAll = filesToLoad(target, new Set(["searchShortAll" as const]));
    expect(fromDefault).toHaveLength(3);
    expect(fromShortAll).toHaveLength(2);

    const a = estimatedBytes(manifest, fromDefault)!;
    const b = estimatedBytes(manifest, fromShortAll)!;
    expect(a).toBeGreaterThan(b);
  });

  it("估算位元組取自 manifest，**不得前端寫死**", () => {
    const bytes = estimatedBytes(manifest, ["searchShortAll"]);
    expect(bytes).toBe(manifest.files.searchShortAll.brotliBytes);
  });

  it("manifest 缺 brotliBytes → **回 null 而非退回 gzipBytes**", () => {
    // gzip 大約 43%，拿它假裝知道比不顯示更誤導
    const broken = {
      ...manifest,
      files: { ...manifest.files, searchShortAll: { path: "x", bytes: 1, gzipBytes: 2 } },
    };
    expect(estimatedBytes(broken as typeof manifest, ["searchShortAll"])).toBeNull();
  });

  it("§8.5：顯示為**四捨五入的級距**，不是精確到 byte", () => {
    expect(formatSize(1024)).toBe("約 1 KiB");
    expect(formatSize(700 * 1024)).toBe("約 700 KiB");
    expect(formatSize(1536 * 1024)).toBe("約 1.5 MiB");
    expect(formatSize(null)).toBe("大小不明");
    // 不得出現精確位元組
    expect(formatSize(712345)).not.toMatch(/712345/);
  });

  it("零結果時可提示的擴大方向", () => {
    expect(widerScopes(DEFAULT_SCOPE)).toEqual([
      { fields: "all", history: "latest" },
      { fields: "short", history: "all" },
    ]);
    expect(widerScopes({ fields: "all", history: "all" })).toEqual([]);
  });

  it("scopeKey 與 SCOPE_FILES 的鍵一一對應（沒有打不到的 scope）", () => {
    const keys = new Set(Object.keys(SCOPE_FILES));
    for (const fields of ["short", "all"] as const) {
      for (const history of ["latest", "all"] as const) {
        expect(keys.has(scopeKey({ fields, history }))).toBe(true);
      }
    }
    expect(keys.size).toBe(4);
  });
});
