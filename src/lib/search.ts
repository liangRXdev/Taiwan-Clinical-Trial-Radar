/**
 * §8.1 search normalization、§8.2 matching operator、§8.3 多詞語意。
 *
 * **`searchNormalize` 與 `identityNormalize` 各自獨立驗證，不得共用實作**（§6.2）。
 * 這裡天然滿足——identity 那一側在 Python，本檔在 TypeScript——但仍要記住兩者用途相反：
 * identity 保守（不折疊標點與空白，寧可拆成兩個 Trial），search 寬鬆（折疊大小寫與空白，
 * 寧可多命中）。**不要因為看起來相近就把其中一邊改成呼叫另一邊。**
 */

import type { SearchEntry, Trial } from "./types.js";

/** §6.0：`nfkc(strip(s))` → casefold → 內部連續空白壓為單一空格。 */
export function searchNormalize(s: string | null | undefined): string {
  // JS 沒有 Python 的 casefold；`toLowerCase()` 對本資料集（中英數）等價。
  // **不做**標點移除、不做連字號正規化（§8.1）。
  return (s ?? "").normalize("NFKC").trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * §8.2：query 先 `searchNormalize`，再以**空白切分**為 terms。
 *
 * 空查詢或純空白查詢回傳空陣列 → 呼叫端**不執行搜尋**，顯示瀏覽狀態。
 * **不得視為「命中全部」**：那會讓「沒有查詢」與「查詢命中全部」在 UI 上無法區分。
 */
export function parseQuery(q: string): string[] {
  const n = searchNormalize(q);
  return n === "" ? [] : n.split(" ");
}

/**
 * §8.3：**record 層 AND、欄位層 OR**。
 *
 * 每個 term 只要命中該 record 的**任一**可搜尋欄位即成立；
 * **同一個 record 內全部 term 成立**才算該 record 命中。
 *
 * **兩個 term 分別命中同一 Trial 的不同 record 時不算命中**——那是 Trial 層 AND，
 * 會大幅多報，而多報在本專案的風險排序裡屬於「誤導」。
 */
export function recordMatches(fields: readonly string[], terms: readonly string[]): boolean {
  return terms.every((term) => fields.some((f) => f.includes(term)));
}

export interface Hit {
  /** 命中的 recordId */
  recordId: string;
  /** 命中的欄位索引（對應該檔的 `fields` 順序）。**列出全部**，§7.2 要求 */
  fieldIndexes: number[];
  /**
   * **命中那一筆紀錄**的可採計日期（`YYYY-MM-DD`），無可採計日期為 `null`。
   *
   * §7.2 的「命中來自 YYYY/MM/DD」指的是**這個**日期，不是 Trial 的
   * `latestSourceDate`。兩者在「命中來自較舊紀錄」的情形下**必然不同**，
   * 而那正是要標示的情形——用後者等於顯示一個不屬於該紀錄的日期。
   *
   * `trials-index` 內嵌的 `searchShortLatest` 沒有 `d` 欄（它全是最新 cohort，
   * 不會觸發該標示），那條路徑填 `null`。
   */
  date: string | null;
}

/** 對單一 record 求出命中欄位；未命中回傳 `null`。 */
export function matchRecord(
  entry: { r: string; f: string[]; d?: string | null },
  terms: readonly string[],
): Hit | null {
  if (!recordMatches(entry.f, terms)) return null;

  // §7.2：多欄同時命中時須列出**全部**命中欄位。只回傳第一個命中欄位的實作
  // 會讓卡片少標一個來源，而使用者無從得知他搜的詞其實出現在別的欄位。
  const fieldIndexes: number[] = [];
  entry.f.forEach((value, i) => {
    if (terms.some((t) => value.includes(t))) fieldIndexes.push(i);
  });
  return { recordId: entry.r, fieldIndexes, date: entry.d ?? null };
}

export interface TrialHit {
  trial: Trial;
  hits: Hit[];
}

/**
 * 預設 scope（`short`+`latest`）的搜尋：資料全在 `trials-index` 的 `searchShortLatest`。
 *
 * 回傳順序為 `latestSourceDate` 降序、`dateUnknown` 置末、`trialId` 昇序——
 * 與瀏覽狀態同一套排序，使「有查詢」與「無查詢」的結果列表在視覺上可比。
 */
export function searchLatestShort(trials: readonly Trial[], terms: readonly string[]): TrialHit[] {
  const out: TrialHit[] = [];
  for (const trial of trials) {
    const hits: Hit[] = [];
    for (const entry of trial.searchShortLatest) {
      const hit = matchRecord(entry, terms);
      if (hit) hits.push(hit);
    }
    if (hits.length > 0) out.push({ trial, hits });
  }
  return out.sort((a, b) => compareTrials(a.trial, b.trial));
}

/**
 * §8.2 的瀏覽狀態：**空查詢不執行搜尋**，列出全部 Trial。
 *
 * 分開一個函式而不是用「空 terms 命中全部」，是為了讓呼叫端無法把兩者混為一談。
 */
export function browseAll(trials: readonly Trial[]): TrialHit[] {
  return [...trials].sort(compareTrials).map((trial) => ({ trial, hits: [] }));
}

/**
 * 排序：可採計日期降序 → `dateUnknown` 置末 → `trialId` 昇序。
 *
 * **`dateUnknown` 置末不是「當成很舊」**：它沒有日期，放進日期序列的任何位置都是偽造。
 * 末端是唯一不宣稱時序的位置（與 §9.3.6 I5 的 `recordIds` 排序同一原則）。
 */
export function compareTrials(a: Trial, b: Trial): number {
  if (a.dateUnknown !== b.dateUnknown) return a.dateUnknown ? 1 : -1;
  if (!a.dateUnknown && a.latestSourceDate !== b.latestSourceDate) {
    return (b.latestSourceDate ?? "").localeCompare(a.latestSourceDate ?? "");
  }
  return a.id.localeCompare(b.id);
}

/**
 * 按需 scope 的搜尋：資料在獨立的 search 檔內，record 以 `t` 指回 Trial。
 *
 * `entries` 已是該 scope 所需的**全部** record（呼叫端負責依 §8.5 合併多個檔）。
 */
export function searchEntries(
  trials: readonly Trial[],
  entries: ReadonlyArray<{ r: string; t: string; f: string[] }>,
  terms: readonly string[],
): TrialHit[] {
  const byId = new Map(trials.map((t) => [t.id, t]));
  const grouped = new Map<string, Hit[]>();

  for (const entry of entries) {
    const hit = matchRecord(entry, terms);
    if (!hit) continue;
    const list = grouped.get(entry.t);
    if (list) list.push(hit);
    else grouped.set(entry.t, [hit]);
  }

  const out: TrialHit[] = [];
  for (const [trialId, hits] of grouped) {
    const trial = byId.get(trialId);
    // 指到不存在的 Trial 是 §9.3.6 I3 的違規，前端不自行修補——
    // 靜默跳過會讓資料缺陷變成「查不到」，那比報錯更難追。
    if (!trial) throw new Error(`search 檔引用了不存在的 trialId：${trialId}`);
    out.push({ trial, hits });
  }
  return out.sort((a, b) => compareTrials(a.trial, b.trial));
}

/** 合併同一 Trial 在多個 scope 檔內的命中（`all`+`all` 會同時載入三個檔）。 */
export function mergeHits(groups: readonly TrialHit[][]): TrialHit[] {
  const byId = new Map<string, TrialHit>();
  for (const group of groups) {
    for (const { trial, hits } of group) {
      const existing = byId.get(trial.id);
      if (existing) existing.hits.push(...hits);
      else byId.set(trial.id, { trial, hits: [...hits] });
    }
  }
  return [...byId.values()].sort((a, b) => compareTrials(a.trial, b.trial));
}

export type { SearchEntry };
