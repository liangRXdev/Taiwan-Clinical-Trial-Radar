/**
 * §8.5 搜尋 scope 分層與「scope → 所需檔案集合」模型。
 *
 * **檔案集合是唯一事實，切換成本一律由集合差導出**（v0.9）。以 scope 名稱記單一數字
 * 必然產生「總量還是增量」的歧義：由預設進入 `all`+`all` 要下載三個檔，
 * 由 `short`+`all` 進入只要兩個，差距達數百 KiB。UI 低報或高報都違反改用實際編碼的初衷。
 */

import type { Manifest } from "./types.js";

export type FieldsScope = "short" | "all";
export type HistoryScope = "latest" | "all";

export interface Scope {
  fields: FieldsScope;
  history: HistoryScope;
}

export const DEFAULT_SCOPE: Scope = { fields: "short", history: "latest" };

/** `manifest.files` 中五個具名 top-level 條目裡，本模組會用到的三個。 */
export type SearchFileKey = "searchShortAll" | "searchLongLatest" | "searchLongAll";

/**
 * §8.5 的封閉表。**Tier 0 三檔（manifest／trials-index／stats）恆含，不列於此。**
 *
 * `short`+`latest` 為空集合：`searchShortLatest` 併在 `trials-index` 內（§9.3.4），
 * 不需額外載入——實測拆成獨立檔**反而更大**（失去跨欄位的壓縮共享）。
 */
export const SCOPE_FILES: Record<string, readonly SearchFileKey[]> = {
  "short|latest": [],
  "short|all": ["searchShortAll"],
  "all|latest": ["searchLongLatest"],
  "all|all": ["searchShortAll", "searchLongLatest", "searchLongAll"],
};

export function scopeKey(scope: Scope): string {
  return `${scope.fields}|${scope.history}`;
}

export function filesFor(scope: Scope): readonly SearchFileKey[] {
  const files = SCOPE_FILES[scopeKey(scope)];
  if (files === undefined) throw new Error(`未知的 scope：${scopeKey(scope)}`);
  return files;
}

/**
 * 切換成本 = `目標集合 − 已載入集合`。**已在快取中的檔案不得重複計入。**
 *
 * 回傳的是**需要新下載的檔案**，位元組由呼叫端向 manifest 取——
 * 本模組不碰數字，避免「集合對了但數字來源錯了」這種只在 UI 上看得出來的缺陷。
 */
export function filesToLoad(target: Scope, loaded: ReadonlySet<SearchFileKey>): SearchFileKey[] {
  return filesFor(target).filter((f) => !loaded.has(f));
}

/**
 * 切換成本的估算位元組。**取自 manifest，不得前端寫死**（§8.5）。
 *
 * 回傳 `null` 表示 manifest 缺少該檔的 `brotliBytes`——此時 UI 須顯示「大小不明」，
 * **不得退回 `gzipBytes` 假裝知道**：那個數字大約 43%，比不顯示更誤導。
 */
export function estimatedBytes(
  manifest: Manifest,
  keys: readonly SearchFileKey[],
): number | null {
  let total = 0;
  for (const key of keys) {
    const meta = manifest.files[key];
    if (meta === undefined || meta.brotliBytes === undefined) return null;
    total += meta.brotliBytes;
  }
  return total;
}

/**
 * §8.5：UI **一律顯示四捨五入的「約 X KiB」級距**，不得呈現精確到 byte 的數字。
 *
 * 因為 `brotliBytes` 是建置期 quality 11 的估算值，而 Cloudflare 的動態壓縮品質
 * 不由 artifact 契約控制（實務約 q4–q5，**比 q11 大**）。給一個精確數字等於宣稱
 * 一件我們控制不了的事。
 */
export function formatSize(bytes: number | null): string {
  if (bytes === null) return "大小不明";
  const kib = bytes / 1024;
  if (kib < 1024) return `約 ${Math.round(kib)} KiB`;
  return `約 ${(kib / 1024).toFixed(1)} MiB`;
}

/** 零結果時可提示的擴大方向：比目前更大、且只差一個維度的 scope。 */
export function widerScopes(current: Scope): Scope[] {
  const out: Scope[] = [];
  if (current.fields === "short") out.push({ fields: "all", history: current.history });
  if (current.history === "latest") out.push({ fields: current.fields, history: "all" });
  return out;
}
