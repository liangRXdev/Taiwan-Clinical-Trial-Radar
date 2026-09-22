/**
 * 非 facet metadata surface（§9.3.5、E2(b)、E3）。
 *
 * §9.3.5 把呈現層分成兩類，**各由不同契約約束**：facet widget（`phase`／`scale`／
 * `applicant`，走 E2(a) 的封閉名單雙向對帳）與本模組的**單值資料來源資訊**
 * （`sourceUpdatedAt`／`builtAt`／兩個總數，走 E3 的精確值斷言）。
 *
 * **本模組不得出現任何分組計數。** 一旦這裡長出「依某維度分組的計數」，它就是一個
 * 繞過 E2(a) inventory 的 facet widget——而 E2 明寫統計 surface 的辨識不得只依
 * CSS class 或 card selector，正是為了堵這條路。`renderMeta` 只輸出四個具名單值。
 *
 * **日期一律照實**：`sourceUpdatedAt` 為 null 時顯示「來源未提供」，不得代入
 * `builtAt`、`fetchedAt` 或今天——偽造一個資料更新日是本專案風險排序最高的誤導。
 */

import type { Manifest } from "../lib/types.js";
import { el } from "./dom.js";
import { formatDate, META } from "./text.js";

/**
 * metadata 欄位的語意標記。
 *
 * 與 `STAT_SURFACE_ATTR` 分開是刻意的：E2 的 facet inventory 掃的是那個屬性，
 * 本屬性掃的是 E3 的 metadata 清單，兩份 inventory **不得互相吸收**，否則
 * 「把一張未核准的 facet 卡標成 metadata」就能同時逃過兩邊。
 */
export const META_SURFACE_ATTR = "data-meta-field";

/** E3 的封閉 metadata 名單。新增 surface 須同時改本表與 E3 的 oracle。 */
export const META_FIELDS = ["sourceUpdatedAt", "builtAt", "trialCount", "recordCount"] as const;

export type MetaField = (typeof META_FIELDS)[number];

/**
 * `builtAt`（UTC 瞬間）→ 台北時間的可讀字串。
 *
 * 不用 `toLocaleString` 的 timeZone 選項：那依賴執行環境的 ICU 資料，同一份
 * 位元組在 CI 與瀏覽器可能格出兩種字串，而 E3 驗的是**精確文字**。
 * 位移固定 +08:00（台灣無日光節約），手算比引進不可控的相依安全。
 *
 * **無法解析時回 null**，呼叫端顯示「無法辨識」——不得退回今天或空字串。
 */
export function formatBuiltAt(iso: string): string | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const d = new Date(t + 8 * 60 * 60 * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}/${p(d.getUTCMonth() + 1)}/${p(d.getUTCDate())}`
    + ` ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}${META.taipeiSuffix}`
  );
}

function row(field: MetaField, label: string, value: string): HTMLElement {
  return el("div", { class: "meta__row", [META_SURFACE_ATTR]: field }, [
    el("dt", { class: "meta__label", text: label }),
    el("dd", { class: "meta__value mono", text: value }),
  ]);
}

/**
 * 每個頁面都要呼叫一次（E3 覆蓋首頁、結果頁、詳情頁）。
 * 回傳新節點，不共用——一個 DOM 節點只能掛一處。
 */
export function renderMeta(manifest: Manifest): HTMLElement {
  const sourceUpdated = formatDate(manifest.sourceUpdatedAt);
  const built = formatBuiltAt(manifest.builtAt);

  return el("section", { class: "meta", "aria-label": META.title }, [
    el("h2", { class: "meta__title", text: META.title }),
    el("dl", { class: "meta__list" }, [
      row("sourceUpdatedAt", META.sourceUpdatedAt, sourceUpdated ?? META.sourceUpdatedUnknown),
      row("builtAt", META.builtAt, built ?? META.builtAtUnparsed),
      row("trialCount", META.trialCount, META.trialUnit(manifest.trialCount)),
      row("recordCount", META.recordCount, META.recordUnit(manifest.recordCount)),
    ]),
    el("p", { class: "hint", text: META.note }),
  ]);
}
