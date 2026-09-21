/**
 * 統計卡（§7.1、E2）。
 *
 * **以 Trial 為分母並明寫「試驗」。** 資料是 18,736 列對 5,888 個試驗，
 * 用列數當分母會讓每個數字都偏大，而使用者沒有任何線索看得出來。
 *
 * E2(a) 要求 facet widget 的 inventory 與 §9.3.5 的封閉名單**雙向對帳**：
 * DOM 中有而清單中無者失敗，清單中有而 DOM 中無者亦失敗。本模組因此只從
 * `stats.facets` 產生卡片，**不接受呼叫端另外插入統計區塊**。
 */

import type { Facet, Stats } from "../lib/types.js";
import { el } from "./dom.js";
import { FILTER_SPECIAL, STATS } from "./text.js";

/** §9.3.5 的封閉 facet 名單。E2 的唯一 oracle 來源。 */
export const FACET_TITLES: Record<string, string> = {
  phase: "試驗期別",
  scale: "試驗規模",
  applicant: "試驗申請者",
};

/** 統計區塊的辨識標記。E2 要求辨識不得只依 CSS class——這個屬性是**語意**標記：
 * 凡帶有它的區塊就是「對使用者呈現分組計數」的統計 surface，測試以它雙向對帳。 */
export const STAT_SURFACE_ATTR = "data-stat-facet";

function facetCard(name: string, facet: Facet, denominatorTrials: number): HTMLElement {
  const total =
    facet.buckets.reduce((n, b) => n + b.count, 0) + facet.unprovided + facet.conflicted;

  // §9.3.5：`buckets + unprovided + conflicted` 須等於 `denominators.trials`。
  // 不符時**顯示錯誤而不是顯示數字**——一張加不起來的統計卡比沒有統計卡更誤導。
  if (total !== denominatorTrials) {
    return el("section", { class: "card card--stat card--stat-error", [STAT_SURFACE_ATTR]: name }, [
      el("h3", { text: FACET_TITLES[name] ?? name }),
      el("p", {
        class: "alert alert--error",
        text: `⚠ 統計資料不一致（${total} ≠ ${denominatorTrials}），已停止顯示本卡`,
      }),
    ]);
  }

  const rows = [
    ...facet.buckets.map((b) => ({ label: b.value, count: b.count, special: false })),
    { label: FILTER_SPECIAL.unprovided, count: facet.unprovided, special: true },
    { label: FILTER_SPECIAL.conflicted, count: facet.conflicted, special: true },
  ];

  return el("section", { class: "card card--stat", [STAT_SURFACE_ATTR]: name }, [
    el("h3", { class: "card__title", text: FACET_TITLES[name] ?? name }),
    el("p", { class: "hint", text: STATS.denominatorNote(denominatorTrials) }),
    el(
      "table",
      { class: "stat__table" },
      [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { scope: "col", text: "分組" }),
            el("th", { scope: "col", text: `試驗數` }),
          ]),
        ]),
        el(
          "tbody",
          {},
          rows.map((r) =>
            el("tr", { class: r.special ? "stat__row--special" : null }, [
              el("th", { scope: "row", text: r.label }),
              // 數值一律 mono（house style）
              el("td", { class: "mono", text: `${r.count} ${STATS.unit}` }),
            ]),
          ),
        ),
      ],
    ),
  ]);
}

export function renderStats(stats: Stats): HTMLElement {
  const trialsN = stats.denominators.trials;

  // **只從封閉名單產生**。名單外的 facet 出現在資料裡時要顯眼地報出來，
  // 而不是默默多渲染一張卡——E2 的雙向對帳靠的就是這個集合相等。
  const unexpected = Object.keys(stats.facets).filter((k) => !(k in FACET_TITLES));
  const missing = Object.keys(FACET_TITLES).filter((k) => !(k in stats.facets));

  return el("div", { class: "stats" }, [
    el("h2", { text: "資料概況" }),
    el("p", { class: "hint", text: STATS.recordNote(stats.denominators.records) }),
    ...(unexpected.length > 0 || missing.length > 0
      ? [
          el("p", {
            class: "alert alert--error",
            text: `⚠ facet 名單與資料不符（多出：${unexpected.join("、") || "無"}；缺少：${
              missing.join("、") || "無"
            }）`,
          }),
        ]
      : []),
    ...Object.keys(FACET_TITLES)
      .filter((name) => name in stats.facets)
      .map((name) => facetCard(name, stats.facets[name]!, trialsN)),
  ]);
}
