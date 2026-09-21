/**
 * 詳情頁（§7.3、E6、E8）。
 *
 * **不做方向性 diff**：依日期分組列出完整來源紀錄，日期之間只標示「哪些欄位存在不同值」，
 * **不產生方向箭頭**。理由是日期平手時沒有可靠順序——實測 21 組人數衝突正是同日平手，
 * `20 → 30` 的箭頭可能寫反。
 *
 * 這一頁是四個長文字欄位的**唯一使用者入口**（它們不在 `trials-index` 內，見 F3），
 * 所以 E6 要求四欄各自斷言全文精確相等。
 */

import type { Shard, ShardRecord, Trial } from "../lib/types.js";
import { chip, el } from "./dom.js";
import { FIELD_NOTE, formatDate, LABEL } from "./text.js";

/** 16 欄的 canonical 順序，詳情頁逐 record 全部列出。 */
const ALL_FIELDS = [
  "臨床試驗申請者",
  "臨床試驗計畫書編號",
  "臨床試驗計畫中文名稱",
  "臨床試驗期別",
  "本臨床試驗規模",
  "試驗目的",
  "試驗預計執行期間起",
  "試驗預計執行期間迄",
  "全球預計受試者人數",
  "台灣預計受試者人數",
  "適應症中文",
  "主要評估指標",
  "納入條件",
  "排除條件",
  "TFDA收文號",
  "資料更新時間",
] as const;

/** 長文字欄位：保留原文換行、不截斷（§7.3）。 */
const LONG_TEXT = new Set(["試驗目的", "主要評估指標", "納入條件", "排除條件"]);

function recordDate(rec: ShardRecord): string | null {
  const flags = rec.fieldFlags["資料更新時間"] ?? [];
  // **有 typed 日期 ≠ 可採計**：`dateFuture` 的 typed 是合法 ISO 日期卻必須置末。
  // 只看 typed 的實作會把未來日期當成最新，那正是 §6.5 要擋的。
  if (flags.some((f) => f === "dateMissing" || f === "dateUnparsed" || f === "dateFuture")) {
    return null;
  }
  const typed = rec.typed["資料更新時間"];
  return typeof typed === "string" ? typed : null;
}

function fieldRow(rec: ShardRecord, field: string): HTMLElement {
  const raw = rec.raw[field] ?? "";
  const notes = (rec.fieldFlags[field] ?? [])
    .map((f) => FIELD_NOTE[f])
    .filter((x): x is string => x !== undefined);

  const valueNode = LONG_TEXT.has(field)
    ? // **原文換行不截斷**（§7.3）。`white-space: pre-wrap` 交給 CSS，
      // 這裡用 textContent 放整段原文——切斷或折疊都會讓 E6 的全文比對失敗，
      // 而那條比對存在的理由正是「臨床人員要讀到完整的納入排除條件」。
      el("div", { class: "detail__long", text: raw })
    : el("span", { class: "mono", text: raw.trim() === "" ? "—" : raw });

  return el("div", { class: "detail__row", "data-field": field }, [
    el("dt", { text: field }),
    el("dd", {}, [valueNode, ...notes.map((n) => chip("muted", n))]),
  ]);
}

function recordBlock(rid: string, rec: ShardRecord): HTMLElement {
  const flags = rec.recordFlags
    .map((f) => FIELD_NOTE[f])
    .filter((x): x is string => x !== undefined);

  return el("section", { class: "detail__record", "data-record": rid }, [
    el("h4", { class: "detail__rid mono", text: rid }),
    flags.length > 0 ? el("div", { class: "detail__flags" }, flags.map((f) => chip("warn", f))) : null,
    el("dl", { class: "detail__fields" }, ALL_FIELDS.map((f) => fieldRow(rec, f))),
  ]);
}

/**
 * 找出同一組內「哪些欄位存在不同值」。**只列欄位名，不做方向性比較。**
 */
export function differingFields(records: readonly ShardRecord[]): string[] {
  if (records.length < 2) return [];
  return ALL_FIELDS.filter((f) => new Set(records.map((r) => r.raw[f] ?? "")).size > 1);
}

export interface DetailOptions {
  /** 近似編號群內的其他 Trial（E8 要求顯示提示與連結） */
  nearDuplicates: Array<{ id: string; label: string; href: string }>;
}

export function renderDetail(trial: Trial, shard: Shard, opts: DetailOptions): HTMLElement {
  const entry = shard.trials[trial.id];
  if (entry === undefined) {
    // §9.3.6 I3 的違規。前端不自行修補——靜默顯示空白頁比報錯更難追。
    throw new Error(`shard 缺少 trialId：${trial.id}`);
  }

  const records = entry.recordIds.map((rid) => {
    const rec = shard.records[rid];
    if (rec === undefined) throw new Error(`shard 缺少 recordId：${rid}`);
    return { rid, rec };
  });

  // 依可採計日期分組；**無可採計日期者置末**（§7.3），不塞進日期序列。
  const byDate = new Map<string, Array<{ rid: string; rec: ShardRecord }>>();
  const undated: Array<{ rid: string; rec: ShardRecord }> = [];
  for (const item of records) {
    const d = recordDate(item.rec);
    if (d === null) undated.push(item);
    else {
      const list = byDate.get(d);
      if (list) list.push(item);
      else byDate.set(d, [item]);
    }
  }

  const dateGroups = [...byDate.entries()].sort((a, b) => b[0].localeCompare(a[0]));

  const groupNodes = dateGroups.map(([date, items]) =>
    el("section", { class: "detail__group", "data-date": date }, [
      el("h3", { class: "detail__date mono", text: formatDate(date)! }),
      // **同日多筆明示「順序未知」**（§7.3）：不編號、不說「第一筆」
      items.length > 1 ? chip("warn", LABEL.sameDayUnordered) : null,
      items.length > 1
        ? el("p", {
            class: "detail__diff",
            text: `本日各筆之間有不同值的欄位：${
              differingFields(items.map((i) => i.rec)).join("、") || "（無）"
            }`,
          })
        : null,
      ...items.map((i) => recordBlock(i.rid, i.rec)),
    ]),
  );

  const undatedNode =
    undated.length > 0
      ? el("section", { class: "detail__group detail__group--undated" }, [
          el("h3", { class: "detail__date", text: LABEL.undatedRecords }),
          chip("warn", LABEL.dateUnknown),
          ...undated.map((i) => recordBlock(i.rid, i.rec)),
        ])
      : null;

  const variants =
    trial.protocolRaw.length > 1
      ? el("p", { class: "detail__variants" }, [
          el("span", { text: `${LABEL.mergedVariants}：` }),
          el("span", { class: "mono", text: trial.protocolRaw.join("、") }),
        ])
      : null;

  const near =
    opts.nearDuplicates.length > 0
      ? el("section", { class: "detail__near" }, [
          el("h3", { text: LABEL.nearDuplicate }),
          el(
            "ul",
            {},
            opts.nearDuplicates.map((n) =>
              el("li", {}, [el("a", { href: n.href, class: "mono", text: n.label })]),
            ),
          ),
        ])
      : null;

  return el("div", { class: "detail", "data-trial": trial.id }, [
    el("h2", {
      class: "detail__title",
      text: trial.displayFields["臨床試驗計畫中文名稱"]?.raw.trim() || "（來源未提供名稱）",
    }),
    el("p", { class: "detail__protocol mono" }, [
      trial.protocolNonIdentifier
        ? chip("info", LABEL.noProtocol)
        : el("span", { text: trial.protocolRaw.join("、") }),
    ]),
    variants,
    trial.latestAmbiguous ? chip("warn", LABEL.ambiguous) : null,
    near,
    el("p", { class: "detail__count", text: `共 ${records.length} 筆審查紀錄` }),
    ...groupNodes,
    undatedNode,
  ]);
}
