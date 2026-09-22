/**
 * §9.3.1 的 schema 版本檢查，與 schemaVersion 2 起 `displayFields` 的**稀疏還原**。
 *
 * 序列化端（`trial_radar/artifacts.py` 的 `_field_json`）在 `typed` 恰等於 `raw`
 * 時省略 `typed`、在 `flags` 為空時省略 `flags`。實測省 8.1%，而 `trials-index`
 * 佔 Tier 0 的 98%——這是在不改變任何使用者可見行為的前提下唯一能拿到的餘裕。
 *
 * **全部 UI 程式碼看到的仍是稠密的 `FieldValue`**：還原集中在這裡一處，
 * 讓「某個 renderer 忘了處理缺席的 typed」在結構上不可能發生。
 */

import type { FieldValue, Trial, TrialsIndex, Typed } from "./types.js";

/** 本前端支援的 schema 版本。artifact 不是這個版本時 fail-closed。 */
export const SUPPORTED_SCHEMA_VERSION = 2;

/** 序列化在檔案裡的稀疏形狀。`typed`／`flags` 可能不存在。 */
export interface SparseFieldValue {
  raw: string;
  typed?: Typed;
  flags?: string[];
}

/**
 * 稀疏 → 稠密。
 *
 * **只有「鍵不存在」才代入 `raw`。**
 *
 * 不可寫成 `v.typed ?? v.raw`：`typed` 為 `null` 是**有意義的狀態**
 * （未提供／無法解析／超出可表示範圍／衝突），`??` 會把它換成 raw，
 * 於是 §6.6 的整套 sentinel 語意在這一行全部消失——而畫面上看不出來，
 * 使用者會把「來源填了無法解析的東西」讀成「來源就是這個值」。
 */
export function densifyField(v: SparseFieldValue): FieldValue {
  return {
    raw: v.raw,
    typed: "typed" in v ? (v.typed as Typed) : v.raw,
    flags: v.flags ?? [],
  };
}

export function densifyTrial(t: Trial): Trial {
  const displayFields: Record<string, FieldValue> = {};
  for (const [k, v] of Object.entries(t.displayFields as Record<string, SparseFieldValue>)) {
    displayFields[k] = densifyField(v);
  }
  return { ...t, displayFields };
}

/**
 * 檢查 schema 版本並還原全部 Trial。
 *
 * **版本不符即拋**（fail-closed）：一個讀 v1 的前端拿到 v2 會把缺席的 `typed`
 * 當成 `undefined`，篩選與統計會靜默偏掉。這正是 §9.3 要求移除欄位須 bump 的理由。
 */
export function densifyIndex(index: TrialsIndex, schemaVersion: number): TrialsIndex {
  if (schemaVersion !== SUPPORTED_SCHEMA_VERSION) {
    throw new Error(
      `資料 schema 版本不支援（artifact ${schemaVersion}，本站支援 ${SUPPORTED_SCHEMA_VERSION}），請重新載入`,
    );
  }
  return { ...index, trials: index.trials.map(densifyTrial) };
}
