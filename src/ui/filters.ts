/**
 * 篩選面板（§8.4、D5、G3）。
 *
 * **`applicant` 實資料有 371 個 bucket**，不能全列成 checkbox（規格未涵蓋此規模）。
 * 採「可搜尋的計數清單」：依 count 降序、捲動容器、上方 type-ahead 過濾。
 * 三個 facet 共用同一元件——為單一維度做特例會讓 D5 的「四處對帳」多一個例外分支，
 * 而例外分支正是弱化實作藏身的地方。
 *
 * **type-ahead 只過濾「顯示哪些選項」，不改變已選中的值**：捲動看不到的已選項目
 * 仍然生效，否則使用者會以為自己取消了篩選。
 */

import {
  CONFLICTED,
  DIMENSIONS,
  ENROLL_BUCKETS,
  UNPROVIDED,
  type Dimension,
  type FilterState,
} from "../lib/filter.js";
import type { Facet, Stats } from "../lib/types.js";
import { el } from "./dom.js";
import { FILTER_SPECIAL } from "./text.js";

/** 超過這個數量才顯示 type-ahead 過濾框。phase(7)／scale(3) 用不到。 */
export const TYPEAHEAD_THRESHOLD = 12;

export const DIMENSION_TITLES: Record<Dimension, string> = {
  phase: "試驗期別",
  scale: "試驗規模",
  applicant: "試驗申請者",
  enroll: "台灣預計受試者人數",
  period: "試驗預計執行期間",
  updated: "資料更新時間",
};

export interface FilterOption {
  value: string;
  label: string;
  count: number | null;
}

/** facet → 選項清單。**「未提供」與「不一致」恆置頂**，它們不是雜訊。 */
export function facetOptions(facet: Facet): FilterOption[] {
  const specials: FilterOption[] = [
    { value: UNPROVIDED, label: FILTER_SPECIAL.unprovided, count: facet.unprovided },
    { value: CONFLICTED, label: FILTER_SPECIAL.conflicted, count: facet.conflicted },
  ];
  const buckets = [...facet.buckets]
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
    .map((b) => ({ value: b.value, label: b.value, count: b.count }));
  return [...specials, ...buckets];
}

export function enrollOptions(): FilterOption[] {
  return [
    { value: UNPROVIDED, label: FILTER_SPECIAL.unprovided, count: null },
    { value: CONFLICTED, label: FILTER_SPECIAL.conflicted, count: null },
    ...ENROLL_BUCKETS.map((b) => ({
      value: b.id,
      label: b.max === null ? `${b.min} 人以上` : b.min === b.max ? `${b.min} 人` : `${b.min}–${b.max} 人`,
      count: null,
    })),
  ];
}

export interface FilterCallbacks {
  onToggle: (dim: Dimension, value: string, checked: boolean) => void;
  onRange: (dim: "period" | "updated", value: string) => void;
}

function optionList(
  dim: Dimension,
  options: readonly FilterOption[],
  selected: readonly string[],
  cb: FilterCallbacks,
): HTMLElement {
  const list = el("div", { class: "filter__options", role: "group", "aria-label": DIMENSION_TITLES[dim] });

  for (const opt of options) {
    const id = `f-${dim}-${encodeURIComponent(opt.value)}`;
    const input = el("input", {
      type: "checkbox",
      id,
      value: opt.value,
      checked: selected.includes(opt.value),
    });
    input.addEventListener("change", () => cb.onToggle(dim, opt.value, input.checked));

    const countText = opt.count === null ? "" : ` (${opt.count})`;
    list.append(
      el("div", { class: "filter__option", "data-value": opt.value }, [
        input,
        el("label", { for: id }, [
          el("span", { text: opt.label }),
          opt.count === null ? null : el("span", { class: "mono filter__count", text: countText }),
        ]),
      ]),
    );
  }
  return list;
}

function typeahead(list: HTMLElement, dim: Dimension): HTMLElement {
  const id = `f-${dim}-search`;
  const input = el("input", {
    type: "search",
    id,
    class: "filter__search",
    placeholder: "輸入關鍵字過濾選項",
    "aria-controls": list.id || `f-${dim}-options`,
  });

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    for (const node of list.querySelectorAll<HTMLElement>(".filter__option")) {
      const label = node.textContent?.toLowerCase() ?? "";
      const checked = node.querySelector<HTMLInputElement>("input")?.checked ?? false;
      // **已選中的選項永遠顯示**：藏起來會讓使用者以為篩選被取消了
      node.hidden = q !== "" && !checked && !label.includes(q);
    }
  });

  return el("div", { class: "filter__searchbox" }, [
    el("label", { for: id, class: "sr-only", text: `過濾${DIMENSION_TITLES[dim]}選項` }),
    input,
  ]);
}

function rangeField(
  dim: "period" | "updated",
  value: string | null,
  error: string | null,
  cb: FilterCallbacks,
): HTMLElement {
  const id = `f-${dim}`;
  const errId = `${id}-err`;
  const input = el("input", {
    type: "text",
    id,
    class: "filter__range mono",
    value: value ?? "",
    placeholder: "YYYY-MM-DD..YYYY-MM-DD",
    // G3：錯誤訊息須與控制項有 **程式可讀的關聯**，不是只放在旁邊
    "aria-invalid": error !== null ? "true" : null,
    "aria-describedby": error !== null ? errId : null,
  });
  input.addEventListener("change", () => cb.onRange(dim, input.value.trim()));

  return el("div", { class: "filter__group", "data-dim": dim }, [
    el("label", { for: id, class: "filter__title", text: DIMENSION_TITLES[dim] }),
    input,
    error === null ? null : el("p", { id: errId, class: "alert alert--error", text: `⚠ ${error}` }),
  ]);
}

export interface FilterPanelOptions {
  stats: Stats;
  state: FilterState;
  errors: Map<string, string>;
  callbacks: FilterCallbacks;
}

export function renderFilters(opts: FilterPanelOptions): HTMLElement {
  const { stats, state, errors, callbacks } = opts;

  const groups: HTMLElement[] = [];

  for (const dim of DIMENSIONS) {
    if (dim === "period" || dim === "updated") {
      groups.push(rangeField(dim, state[dim], errors.get(dim) ?? null, callbacks));
      continue;
    }

    const options =
      dim === "enroll" ? enrollOptions() : facetOptions(stats.facets[dim]!);
    const list = optionList(dim, options, state[dim], callbacks);
    list.id = `f-${dim}-options`;

    groups.push(
      el("fieldset", { class: "filter__group", "data-dim": dim }, [
        el("legend", { class: "filter__title", text: DIMENSION_TITLES[dim] }),
        options.length > TYPEAHEAD_THRESHOLD ? typeahead(list, dim) : null,
        list,
      ]),
    );
  }

  return el("form", { class: "filters", "aria-label": "篩選條件" }, groups);
}
