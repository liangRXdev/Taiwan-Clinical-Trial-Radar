/**
 * §8.4 篩選維度、值域與組合語意。
 *
 * 三條貫穿全檔的規則：
 *
 * 1. **同維度多選 = OR，跨維度 = AND。**
 * 2. **「未提供」與「不一致」是每個維度的可選值**，選中時只回傳該類 trial——
 *    它們不是「被排除的雜訊」，把它們藏起來等於讓使用者以為資料比實際完整。
 * 3. **衝突欄位不任取一值。** 該 trial 在該維度歸入「不一致」，不出現在任一具體值的
 *    結果中（§7.1）。任取一值會顯示一個看似正確、實際來自其中一筆衝突紀錄的答案，
 *    那是本專案最怕的誤導。
 *
 * **篩選不存在招募／執行狀態維度**——filter schema、DOM 控制項、URL parser、輸出 state
 * 四處皆不得有（§8.4）。本檔的 `DIMENSIONS` 即 filter schema 的唯一來源。
 */

import { isNumericRange, type Trial, type Typed } from "./types.js";

/** 每個維度的兩個特殊值。**不是** facet bucket，而是與 bucket 並列的可選值。 */
export const UNPROVIDED = "__unprovided__";
export const CONFLICTED = "__conflicted__";

export const DIMENSIONS = [
  "phase",
  "scale",
  "applicant",
  "enroll",
  "period",
  "updated",
] as const;

export type Dimension = (typeof DIMENSIONS)[number];

/** 維度 → 來源欄位（`period`／`updated` 不走 `displayFields`，見下）。 */
export const DIMENSION_FIELD: Partial<Record<Dimension, string>> = {
  phase: "臨床試驗期別",
  scale: "本臨床試驗規模",
  applicant: "臨床試驗申請者",
  enroll: "台灣預計受試者人數",
};

export const PERIOD_START = "試驗預計執行期間起";
export const PERIOD_END = "試驗預計執行期間迄";

/** §8.4 的 `enroll` bucket，**閉區間**。`max` 為 `null` 表示無上界。 */
export const ENROLL_BUCKETS: ReadonlyArray<{ id: string; min: number; max: number | null }> = [
  { id: "0", min: 0, max: 0 },
  { id: "1-10", min: 1, max: 10 },
  { id: "11-30", min: 11, max: 30 },
  { id: "31-100", min: 31, max: 100 },
  { id: "101-", min: 101, max: null },
];

export interface FilterState {
  phase: string[];
  scale: string[];
  applicant: string[];
  enroll: string[];
  /** `YYYY-MM-DD..YYYY-MM-DD`，最多一個 */
  period: string | null;
  updated: string | null;
}

export function emptyFilter(): FilterState {
  return { phase: [], scale: [], applicant: [], enroll: [], period: null, updated: null };
}

/** 該維度是否有任何條件。空維度不參與 AND。 */
export function isActive(state: FilterState, dim: Dimension): boolean {
  const v = state[dim];
  return Array.isArray(v) ? v.length > 0 : v !== null;
}

/**
 * 分類／申請者維度：trial 在該維度的歸類。
 *
 * 回傳具體值、`UNPROVIDED` 或 `CONFLICTED`——**三者互斥且窮盡**，
 * 沒有「不屬於任何一類」的 trial，否則某些 trial 會從所有篩選結果中消失。
 */
export function categoryOf(trial: Trial, field: string): string {
  if (trial.conflictFields.includes(field)) return CONFLICTED;
  const value = trial.displayFields[field];
  if (value === undefined || value.typed === null || value.typed === "") return UNPROVIDED;
  return String(value.typed);
}

/**
 * §8.4 的 `enroll`：typed 為區間時，只要與 bucket 區間**有交集**即命中。
 *
 * 一筆 `20-40` 因此會同時出現在 `11-30` 與 `31-100`——那不是 bug，是區間值的正確語意。
 * 卡片顯示 raw 原文（`20-40`），使用者看得出它是區間而非單值。
 */
export function enrollBucketsOf(trial: Trial): string[] {
  const field = DIMENSION_FIELD.enroll!;
  if (trial.conflictFields.includes(field)) return [CONFLICTED];

  const value = trial.displayFields[field];
  if (value === undefined) return [UNPROVIDED];

  const typed: Typed = value.typed;
  let lo: number;
  let hi: number;
  if (typeof typed === "number") {
    lo = hi = typed;
  } else if (isNumericRange(typed)) {
    lo = typed.min;
    hi = typed.max;
  } else {
    // numericMissing／numericUnparsed／numericImplausible／numericRangeInvalid／
    // numericOutOfRange 一律歸「未提供」，**不得猜一個數字進 bucket**
    return [UNPROVIDED];
  }

  const hits = ENROLL_BUCKETS.filter((b) => lo <= (b.max ?? Infinity) && hi >= b.min).map(
    (b) => b.id,
  );
  return hits.length > 0 ? hits : [UNPROVIDED];
}

/** `YYYY-MM-DD..YYYY-MM-DD` → `[起, 迄]`；格式不符回傳 `null`。 */
export function parseDateRange(v: string): [string, string] | null {
  const m = /^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$/.exec(v);
  if (!m) return null;
  const [, a, b] = m as unknown as [string, string, string];
  // 顛倒的區間是無效值，不靜默交換——使用者寫反時要看到訊息（§7.4）
  return a <= b ? [a, b] : null;
}

/**
 * §8.4 的 `period`：`起 ≤ 區間末` 且 `迄 ≥ 區間首`（**重疊**語意，不是包含）。
 *
 * 任一端 typed 為 `null` → 「未提供」。兩端都要有值才判定得了重疊，
 * 只有一端時猜另一端等於替上游補資料。
 */
export function periodCategoryOf(trial: Trial, range: [string, string]): string | boolean {
  if (
    trial.conflictFields.includes(PERIOD_START) ||
    trial.conflictFields.includes(PERIOD_END)
  ) {
    return CONFLICTED;
  }
  const start = trial.displayFields[PERIOD_START]?.typed;
  const end = trial.displayFields[PERIOD_END]?.typed;
  if (typeof start !== "string" || typeof end !== "string") return UNPROVIDED;
  return start <= range[1] && end >= range[0];
}

/**
 * §8.4 的 `updated`：`latestSourceDate` 落於**閉區間**內；`dateUnknown` → 「未提供」。
 */
export function updatedCategoryOf(trial: Trial, range: [string, string]): string | boolean {
  if (trial.dateUnknown || trial.latestSourceDate === null) return UNPROVIDED;
  return trial.latestSourceDate >= range[0] && trial.latestSourceDate <= range[1];
}

/** 單一維度的判定。維度未啟用時一律通過（不參與 AND）。 */
function passesDimension(trial: Trial, dim: Dimension, state: FilterState): boolean {
  if (!isActive(state, dim)) return true;

  switch (dim) {
    case "phase":
    case "scale":
    case "applicant": {
      // 同維度多選 = OR
      return state[dim].includes(categoryOf(trial, DIMENSION_FIELD[dim]!));
    }
    case "enroll": {
      const buckets = enrollBucketsOf(trial);
      return state.enroll.some((selected) => buckets.includes(selected));
    }
    case "period":
    case "updated": {
      const raw = state[dim]!;
      // 特殊值與日期區間互斥：選了「未提供」就是要那一類，不是要一個區間
      if (raw === UNPROVIDED || raw === CONFLICTED) {
        const probe = dim === "period" ? periodCategoryOf : updatedCategoryOf;
        return probe(trial, ["0000-01-01", "9999-12-31"]) === raw;
      }
      const range = parseDateRange(raw);
      // **無效值不得靜默丟棄該條件**（§7.4）。呼叫端須先驗證並顯示訊息；
      // 走到這裡仍無效時回 false（不回傳全部），避免把錯誤展示成「沒有篩選」。
      if (range === null) return false;
      const verdict = dim === "period" ? periodCategoryOf(trial, range) : updatedCategoryOf(trial, range);
      return verdict === true;
    }
  }
}

/** 跨維度 AND。 */
export function applyFilters<T extends { trial: Trial }>(
  items: readonly T[],
  state: FilterState,
): T[] {
  return items.filter((item) => DIMENSIONS.every((d) => passesDimension(item.trial, d, state)));
}
