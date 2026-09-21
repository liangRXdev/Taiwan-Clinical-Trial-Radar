/**
 * 搜尋 scope 控制項（§8.5 的 UI 硬性要求、D7）。
 *
 * 五條硬性要求，每一條都是為了「**避免把預設縮小變成靜默漏報**」：
 *
 * 1. 擴大 scope 的兩個控制項必須在**搜尋結果區可見**，不得藏在設定或選單深處。
 * 2. 切換前顯示需下載的大小，依集合差逐檔取 `brotliBytes`，**不得前端寫死**。
 * 3. 結果區**持續顯示**目前 scope。
 * 4. 零結果時提示可擴大的 scope 與其大小。
 * 5. 載入失敗則**退回上一個 scope 並說明**，不得靜默維持舊結果集。
 */

import {
  estimatedBytes,
  filesToLoad,
  formatSize,
  widerScopes,
  type Scope,
  type SearchFileKey,
} from "../lib/scope.js";
import type { Manifest } from "../lib/types.js";
import { chip, el } from "./dom.js";
import { SCOPE } from "./text.js";

const FIELDS_LABEL: Record<Scope["fields"], string> = {
  short: SCOPE.fieldsShort,
  all: SCOPE.fieldsAll,
};
const HISTORY_LABEL: Record<Scope["history"], string> = {
  latest: SCOPE.historyLatest,
  all: SCOPE.historyAll,
};

export interface ScopeBarOptions {
  manifest: Manifest;
  scope: Scope;
  loaded: ReadonlySet<SearchFileKey>;
  /** 上一次載入失敗的說明；非 null 時顯示並表示已退回 */
  loadError: string | null;
  onChange: (next: Scope) => void;
}

/** 切換某一維度後的 scope 與其下載成本描述。 */
function costOf(opts: ScopeBarOptions, next: Scope): string {
  const need = filesToLoad(next, opts.loaded);
  if (need.length === 0) return "不需額外下載";
  return SCOPE.willDownload(formatSize(estimatedBytes(opts.manifest, need)));
}

function toggle(
  opts: ScopeBarOptions,
  dim: "fields" | "history",
  value: string,
  label: string,
): HTMLElement {
  const next = { ...opts.scope, [dim]: value } as Scope;
  const current = opts.scope[dim] === value;
  const id = `scope-${dim}-${value}`;

  const input = el("input", {
    type: "radio",
    name: `scope-${dim}`,
    id,
    value,
    checked: current,
  });
  input.addEventListener("change", () => {
    if (input.checked) opts.onChange(next);
  });

  return el("div", { class: "scope__option" }, [
    input,
    el("label", { for: id }, [
      el("span", { text: label }),
      // **切換前**就顯示成本，不是按下去才知道
      current ? null : el("span", { class: "scope__cost", text: `　${costOf(opts, next)}` }),
    ]),
  ]);
}

export function renderScopeBar(opts: ScopeBarOptions): HTMLElement {
  return el(
    "section",
    // **在結果區內**，不是設定選單。class 名字刻意帶 results，讓「搬走」這件事在 diff 上顯眼
    { class: "scope scope--in-results", "aria-label": "搜尋範圍" },
    [
      // 3. 持續顯示目前 scope
      el("p", {
        class: "scope__current",
        text: SCOPE.current(FIELDS_LABEL[opts.scope.fields], HISTORY_LABEL[opts.scope.history]),
      }),
      // 5. 載入失敗 → 說明並已退回
      opts.loadError === null
        ? null
        : el("p", { class: "alert alert--error", text: `⚠ ${SCOPE.loadFailed}（${opts.loadError}）` }),
      el("fieldset", { class: "scope__group" }, [
        el("legend", { text: SCOPE.fieldsLabel }),
        toggle(opts, "fields", "short", SCOPE.fieldsShort),
        toggle(opts, "fields", "all", SCOPE.fieldsAll),
      ]),
      el("fieldset", { class: "scope__group" }, [
        el("legend", { text: SCOPE.historyLabel }),
        toggle(opts, "history", "latest", SCOPE.historyLatest),
        toggle(opts, "history", "all", SCOPE.historyAll),
      ]),
    ],
  );
}

/** 4. 零結果時的擴大提示。**列出每個方向與其大小**，不是只說「試試看別的」。 */
export function renderZeroResultHint(opts: ScopeBarOptions): HTMLElement | null {
  const wider = widerScopes(opts.scope);
  if (wider.length === 0) return null;

  return el("div", { class: "zero-hint" }, [
    chip("info", SCOPE.zeroHint),
    el(
      "ul",
      {},
      wider.map((next) => {
        const label =
          next.fields !== opts.scope.fields ? FIELDS_LABEL[next.fields] : HISTORY_LABEL[next.history];
        const button = el("button", { type: "button", class: "link-btn" }, [
          el("span", { text: label }),
          el("span", { class: "scope__cost", text: `　${costOf(opts, next)}` }),
        ]);
        button.addEventListener("click", () => opts.onChange(next));
        return el("li", {}, [button]);
      }),
    ),
  ]);
}
