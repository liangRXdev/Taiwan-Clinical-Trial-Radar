/**
 * 免責（§10、E5、G1／G2）。
 *
 * **三項核心性質必須在首頁、結果頁、詳情頁都可見。** 不是「頁尾有一行小字」——
 * E5 逐頁斷言可見文字，而可見性綁定 G1／G2 的 viewport 與對比 oracle。
 *
 * 樣式上刻意**不使用 `--text-muted`**：免責區塊在米色裸底上，而 `#6B7280` 對
 * `#F5F0E8` 只有 4.26:1，不過 AA。用 `--text-primary`（house style 的硬性限制）。
 */

import { el } from "./dom.js";
import { DISCLAIMER, DISCLAIMER_TITLE } from "./text.js";

/** 每個頁面都要呼叫一次。回傳新節點，不共用同一個 DOM 節點（一個節點只能掛一處）。 */
export function renderDisclaimer(): HTMLElement {
  return el("aside", { class: "disclaimer", "aria-label": DISCLAIMER_TITLE }, [
    el("h2", { class: "disclaimer__title", text: DISCLAIMER_TITLE }),
    el(
      "ul",
      { class: "disclaimer__list" },
      DISCLAIMER.map((line) => el("li", { text: line })),
    ),
  ]);
}
