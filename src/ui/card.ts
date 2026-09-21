/**
 * 結果卡（§7.1／§7.2、E7／E8）。
 *
 * **最重要的一條：`latestAmbiguous` 的卡片不得出現任何衝突候選值。**
 * 衝突欄位在 `displayFields` 中完全省略（§6.4.5），所以只要老實照 `displayFields`
 * 渲染就不會洩漏——但「從別處撈一個值補上」是很自然的修補衝動，E7 就是在擋那個。
 */

import { CONFLICTED, DIMENSION_FIELD, UNPROVIDED } from "../lib/filter.js";
import type { Hit, TrialHit } from "../lib/search.js";
import type { Trial } from "../lib/types.js";
import { chip, el } from "./dom.js";
import { FIELD_NOTE, formatDate, LABEL } from "./text.js";

/** §9.3.4 固定的五欄順序，供 §7.2 標示命中欄位名。 */
export const SHORT_FIELD_NAMES = [
  "臨床試驗計畫書編號",
  "臨床試驗計畫中文名稱",
  "臨床試驗申請者",
  "適應症中文",
  "TFDA收文號",
] as const;

/** 卡片上顯示的欄位與順序。**長文字四欄不在這裡**（F3，它們不在 index 內）。 */
const CARD_ROWS = [
  "臨床試驗計畫中文名稱",
  "臨床試驗申請者",
  "臨床試驗期別",
  "本臨床試驗規模",
  "適應症中文",
  "試驗預計執行期間起",
  "試驗預計執行期間迄",
  "全球預計受試者人數",
  "台灣預計受試者人數",
] as const;

function fieldValueNode(trial: Trial, field: string): HTMLElement {
  // **衝突欄位完全省略**（§6.4.5）：不顯示任何候選值，只說明狀態。
  if (trial.conflictFields.includes(field)) {
    return el("span", { class: "fv fv--conflict" }, [chip("warn", LABEL.ambiguous)]);
  }

  const value = trial.displayFields[field];
  if (value === undefined) {
    return el("span", { class: "fv fv--none", text: "—" });
  }

  const notes = value.flags.map((f) => FIELD_NOTE[f]).filter((x): x is string => x !== undefined);

  // E8：`numericRange` 顯示 **raw 原文**（`20-40`），不折成單一數字——
  // 折成單一數字會讓使用者以為那是一個確定的人數。
  const shown = value.raw.trim() === "" ? "—" : value.raw;

  return el("span", { class: "fv" }, [
    el("span", { class: "fv__raw", text: shown }),
    ...notes.map((n) => chip("muted", n)),
  ]);
}

/** §7.2 的命中標示。 */
function hitNodes(trial: Trial, hits: readonly Hit[]): HTMLElement | null {
  if (hits.length === 0) return null;

  const names = new Set<string>();
  for (const hit of hits) {
    for (const i of hit.fieldIndexes) {
      const name = SHORT_FIELD_NAMES[i];
      // 長欄 scope 的命中索引超出短欄清單，此時只標「其他欄位」而不猜名稱
      names.add(name ?? "其他可搜尋欄位");
    }
  }

  // 命中是否全部來自最新 cohort。非最新時須標示來源日期（§7.2）。
  const latestIds = new Set(trial.searchShortLatest.map((e) => e.r));
  const fromOlder = hits.some((h) => !latestIds.has(h.recordId));

  const parts: HTMLElement[] = [
    el("span", { class: "hit__fields", text: `命中欄位：${[...names].join("、")}` }),
  ];

  if (fromOlder) {
    const date = formatDate(trial.latestSourceDate);
    // **無可採計日期時不得偽造**（§7.2）——標「資料日期不明」而不是塞一個日期
    parts.push(
      chip("info", date === null ? LABEL.hitDateUnknown : LABEL.hitFromOlder(date)),
    );
  }

  return el("div", { class: "hit" }, parts);
}

export interface CardOptions {
  /** 點詳情頁的 href（由呼叫端組，含 canonical URL state） */
  detailHref: (trialId: string) => string;
}

export function renderCard({ trial, hits }: TrialHit, opts: CardOptions): HTMLElement {
  const title = trial.displayFields["臨床試驗計畫中文名稱"]?.raw.trim();

  const protocolText = trial.protocolNonIdentifier
    ? LABEL.noProtocol
    : trial.protocolRaw.join("、");

  const flags: HTMLElement[] = [];
  if (trial.latestAmbiguous) flags.push(chip("warn", LABEL.ambiguous));
  if (trial.dateUnknown) flags.push(chip("warn", LABEL.dateUnknown));
  if (trial.protocolNonIdentifier) flags.push(chip("info", LABEL.noProtocol));
  if (trial.nearDuplicateGroup !== null) flags.push(chip("info", LABEL.nearDuplicate));

  const date = formatDate(trial.latestSourceDate);

  return el("article", { class: "card card--result", "data-trial": trial.id }, [
    el("h3", { class: "card__title" }, [
      el("a", { href: opts.detailHref(trial.id), text: title || "（來源未提供名稱）" }),
    ]),
    el("p", { class: "card__protocol mono", text: protocolText }),
    flags.length > 0 ? el("div", { class: "card__flags" }, flags) : null,
    el(
      "dl",
      { class: "card__fields" },
      CARD_ROWS.flatMap((field) => [
        el("dt", { text: field }),
        el("dd", {}, [fieldValueNode(trial, field)]),
      ]),
    ),
    el("p", { class: "card__meta" }, [
      // **資料日期不明時不顯示任何日期**，而不是顯示空白讓人以為是今天
      date === null
        ? chip("warn", LABEL.dateUnknown)
        : el("span", { class: "mono", text: `資料更新：${date}` }),
      el("span", { text: `　${trial.recordCount} 筆審查紀錄` }),
      trial.latestCohortCount > 1
        ? el("span", { text: `（最新同日 ${trial.latestCohortCount} 筆）` })
        : null,
    ]),
    hitNodes(trial, hits),
  ]);
}

/**
 * 篩選面板顯示用：把 `UNPROVIDED`／`CONFLICTED` 轉成人看的字。
 * 具體值原樣回傳（**不做任何美化**，那會讓篩選值與卡片上的值對不起來）。
 */
export function facetValueLabel(value: string, special: Record<string, string>): string {
  if (value === UNPROVIDED) return special.unprovided!;
  if (value === CONFLICTED) return special.conflicted!;
  return value;
}

export { DIMENSION_FIELD };
