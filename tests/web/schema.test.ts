/**
 * schemaVersion 2 的稀疏 `displayFields` 還原（§9.3.3）。
 *
 * **這個檔案守的是一行 `??` 就會造成的誤導**：`typed` 為 `null` 是有意義的狀態
 * （未提供／無法解析／超出可表示範圍／衝突），若還原時寫成 `v.typed ?? v.raw`，
 * §6.6 的整套 sentinel 語意會在那一行全部消失——而畫面上看不出來，
 * 使用者會把「來源填了無法解析的東西」讀成「來源就是這個值」。
 */

import { describe, expect, it } from "vitest";

import {
  densifyField,
  densifyIndex,
  SUPPORTED_SCHEMA_VERSION,
  type SparseFieldValue,
} from "../../src/lib/schema.js";
import type { TrialsIndex } from "../../src/lib/types.js";
import { index, manifest, trials } from "./fixture.js";

describe("§9.3.3 稀疏值物件的還原", () => {
  it("`typed` 鍵不存在 → 代入 `raw`", () => {
    expect(densifyField({ raw: "台大醫院" })).toEqual({
      raw: "台大醫院",
      typed: "台大醫院",
      flags: [],
    });
  });

  it("`typed` 存在且不同 → 照原值（前導零那類）", () => {
    expect(densifyField({ raw: "026", typed: 26 })).toEqual({ raw: "026", typed: 26, flags: [] });
  });

  it("**`typed` 明寫 `null` → 保持 `null`，不得代入 `raw`**", () => {
    // 這是 `??` 會寫錯的那一格。raw 是來源填的無法解析文字，typed 是 null
    // 代表「本站讀不出數字」——代入 raw 會讓下游把它當成一個有效值。
    const v: SparseFieldValue = { raw: "約400", typed: null, flags: ["numericUnparsed"] };
    const dense = densifyField(v);
    expect(dense.typed).toBeNull();
    expect(dense.typed).not.toBe("約400");
    expect(dense.flags).toEqual(["numericUnparsed"]);
  });

  it("**反向哨兵**：`??` 的寫法在上一格會給出錯誤結果", () => {
    const v: SparseFieldValue = { raw: "約400", typed: null };
    // 證明兩種寫法不等價——沒有這條，換成 `??` 不會有任何測試轉紅
    expect(v.typed ?? v.raw).toBe("約400");
    expect(densifyField(v).typed).toBeNull();
  });

  it("`flags` 不存在 → 空陣列（而非 undefined）", () => {
    const dense = densifyField({ raw: "x" });
    expect(dense.flags).toEqual([]);
    expect(Array.isArray(dense.flags)).toBe(true);
  });

  it("`typed` 為 `0` 不得被當成缺席（`sourceZero` 是有意義的值）", () => {
    expect(densifyField({ raw: "0", typed: 0, flags: ["sourceZero"] }).typed).toBe(0);
  });

  it("`typed` 為空字串也照原值，不退回 raw", () => {
    expect(densifyField({ raw: " ", typed: "" }).typed).toBe("");
  });
});

describe("§9.3.1 schema 版本 fail-closed", () => {
  it("版本不符即拋，不嘗試讀下去", () => {
    expect(() => densifyIndex({ trials: [] } as unknown as TrialsIndex, 1)).toThrow(/schema 版本/);
    expect(() => densifyIndex({ trials: [] } as unknown as TrialsIndex, 99)).toThrow(/schema 版本/);
  });

  it("fixture 的 manifest 就是本前端支援的版本", () => {
    expect(manifest.schemaVersion).toBe(SUPPORTED_SCHEMA_VERSION);
  });
});

describe("實際 artifact 的還原結果", () => {
  it("每個卡片欄位還原後都有三個鍵，且 `flags` 一律是陣列", () => {
    for (const t of trials) {
      for (const [field, v] of Object.entries(t.displayFields)) {
        expect(Object.keys(v).sort(), `${t.id}/${field}`).toEqual(["flags", "raw", "typed"]);
        expect(Array.isArray(v.flags)).toBe(true);
      }
    }
  });

  it("**`typed` 為 null 的欄位確實存在**，否則上面的規則測不出差別", () => {
    const nulls = trials.flatMap((t) =>
      Object.entries(t.displayFields).filter(([, v]) => v.typed === null),
    );
    expect(nulls.length).toBeGreaterThan(0);
  });

  it("`typed === raw` 的欄位也確實存在（那些在檔案裡是省略的）", () => {
    const same = trials.flatMap((t) =>
      Object.entries(t.displayFields).filter(([, v]) => v.typed === v.raw),
    );
    expect(same.length).toBeGreaterThan(0);
  });

  it("還原是冪等的（對已稠密的資料再跑一次不變）", () => {
    const again = densifyIndex(index, manifest.schemaVersion);
    expect(again.trials[0]!.displayFields).toEqual(index.trials[0]!.displayFields);
  });
});
