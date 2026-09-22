/**
 * §7.4／E8 的 `?protocol=` 查詢：以 identity 正規化後比對，並導向 canonical。
 *
 * **這裡刻意重寫一份 `identityNormalize`，不呼叫 `searchNormalize`。**
 * §6.2 明文要求兩者各自獨立驗證：identity 保守（不折疊標點與空白，寧可拆成兩個
 * Trial），search 寬鬆（折疊大小寫與空白，寧可多命中）。共用一份實作時，
 * 任一方的調整都會靜默改變另一方——而其中一方是主鍵。
 *
 * 與 `trial_radar/normalize.py` 的 `identity_normalize` 是同一個定義的兩份實作，
 * `tests/web/protocol.test.ts` 以雙方共同的 fixture 值綁住它們不漂移。
 */

import type { Trial } from "./types.js";

/** §6.0：`nfkc(strip(s))` 後轉大寫。**不做**標點移除、不壓內部空白、不剝前後綴。 */
export function identityNormalize(s: string | null | undefined): string {
  return (s ?? "").trim().normalize("NFKC").toUpperCase();
}

/**
 * §6.0：ASCII 英數字元**僅指** A–Z、a–z、0–9。
 *
 * 必須明定，否則實作會相反——JS 的 `/\w/` 與 Python 的 `isalnum()` 都會把
 * 中文算進去，於是 `系統測試` **不會**被判為 non-identifier，與意圖完全相反。
 */
export function hasAsciiAlnum(s: string | null | undefined): boolean {
  return /[0-9A-Za-z]/.test((s ?? "").normalize("NFKC"));
}

export type ProtocolLookup =
  | { kind: "match"; trialId: string }
  /** 值本身不是編號（§6.2.2）——**不接受**，不是「查無結果」 */
  | { kind: "rejected"; reason: "nonIdentifier" }
  /** 是合法形狀的編號，但本站沒有這一筆 */
  | { kind: "notFound" };

/**
 * 以 identity 正規化後比對 `?protocol=` 的值。
 *
 * 三種結果刻意分開，**不可合併成「有／沒有」**：
 * - `rejected` 是「這個值本站不接受」（E8：`protocolNonIdentifier` 的值不得作為查詢值）
 * - `notFound` 是「本站沒有這筆」——而**查無結果不代表該試驗不存在**（§10）
 *
 * 兩者對使用者的意義完全不同，合併會讓前者被讀成後者。
 */
export function lookupProtocol(trials: readonly Trial[], raw: string): ProtocolLookup {
  const key = identityNormalize(raw);
  if (key === "" || !hasAsciiAlnum(raw)) return { kind: "rejected", reason: "nonIdentifier" };

  for (const t of trials) {
    if (!t.protocolRaw.some((p) => identityNormalize(p) === key)) continue;
    // 命中的 Trial 自己被標為「來源未提供計畫書編號」時同樣不接受——
    // 那些值（`系統測試`、`未列編號`…）不是識別碼，拿它當查詢值會讓
    // 一堆不相干的試驗共用同一個「編號」。
    if (t.protocolNonIdentifier) return { kind: "rejected", reason: "nonIdentifier" };
    return { kind: "match", trialId: t.id };
  }
  return { kind: "notFound" };
}
