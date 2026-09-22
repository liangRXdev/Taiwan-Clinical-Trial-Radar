/**
 * 所有使用者可見文句的**單一來源**。
 *
 * 散落在各 render 模組的字串會漂移成兩種寫法，而 E1／E5／E8 驗的是**精確文句**——
 * 「同日多筆資料不一致」與「同日多筆不一致」對使用者沒差，對測試是兩個字串。
 *
 * §10 的三項免責在此定義，E5 逐頁斷言它們的可見文字。
 */

/** §10：免責的三項核心性質。**三項都要可見，不可只寫一句「僅供參考」。** */
export const DISCLAIMER = [
  "本站不提供試驗目前的招募狀態，也無法判斷是否仍在收案。",
  "列入 TFDA 審查或試驗使用，不等於該藥品已獲上市核准。",
  "試驗狀態與收案資格請向官方資料來源、試驗執行機構與醫療專業人員確認。",
] as const;

export const DISCLAIMER_TITLE = "使用前請注意";

/** §7.2／E7／E8 的標記文句。 */
export const LABEL = {
  /** E7：`latestAmbiguous=true` 的卡片。**不得顯示任何候選值。** */
  ambiguous: "同日多筆資料不一致，請展開確認",
  /** E8：`dateUnknown=true` */
  dateUnknown: "資料日期無法辨識，請查官方來源",
  /** E8：`protocolNonIdentifier=true` */
  noProtocol: "來源未提供計畫書編號",
  /** §7.3：同日多筆 */
  sameDayUnordered: "同日多筆，順序未知",
  /** §7.2：命中來自非最新 cohort */
  hitFromOlder: (date: string) => `命中來自 ${date} 的審查紀錄`,
  /** §7.2：命中紀錄無可採計日期。**不得偽造成合法日期。** */
  hitDateUnknown: "命中紀錄的資料日期不明",
  /** E8：近似編號 */
  nearDuplicate: "其他寫法近似的計畫書編號",
  /** §6.2：合併後的多個寫法 */
  mergedVariants: "來源另有下列寫法（僅前後空白不同，已合併）",
  /** §7.3：無可採計日期的紀錄置末 */
  undatedRecords: "資料日期不明的紀錄",
} as const;

/** 篩選的兩個特殊值。**與 facet bucket 並列，不是被藏起來的雜訊。** */
export const FILTER_SPECIAL = {
  unprovided: "未提供",
  conflicted: "同日多筆不一致",
} as const;

/** §8.5 的 scope 控制項文案。 */
export const SCOPE = {
  fieldsLabel: "搜尋欄位",
  fieldsShort: "主要欄位（編號、名稱、申請者、適應症、收文號）",
  fieldsAll: "加上試驗目的與主要評估指標",
  historyLabel: "搜尋範圍",
  historyLatest: "僅最新審查紀錄",
  historyAll: "全部歷史審查紀錄",
  current: (fields: string, history: string) => `目前搜尋範圍：${fields}、${history}`,
  willDownload: (size: string) => `切換需下載 ${size}`,
  loadFailed: "資料載入失敗，已退回原本的搜尋範圍",
  zeroHint: "找不到結果。可擴大搜尋範圍再試一次：",
  /** 已在最大範圍時的零結果。**不得什麼都不顯示**——那會讓使用者以為畫面還沒載完。 */
  zeroAtWidest:
    "已是最大搜尋範圍，仍找不到結果。本站只收錄 TFDA dataset 205 的審查紀錄，"
    + "查無結果不代表該試驗不存在；請改向官方資料來源查詢。",
} as const;

/**
 * §9.3.5 的**非 facet metadata surface**（E2(b)／E3）。
 *
 * 全部是**單值**：沒有任何一項是分組計數，那些歸 facet widget（E2(a)）。
 * `sourceUpdatedAt` 為 null 時用 `sourceUpdatedUnknown`，**不得代入建置日或今天**。
 */
export const META = {
  title: "資料版本",
  sourceUpdatedAt: "來源資料更新日",
  sourceUpdatedUnknown: "來源未提供",
  builtAt: "本站資料建置時間",
  builtAtUnparsed: "建置時間無法辨識",
  taipeiSuffix: "（台北時間）",
  trialCount: "收錄試驗數",
  recordCount: "收錄審查紀錄",
  trialUnit: (n: number) => `${n} 個試驗`,
  recordUnit: (n: number) => `${n} 筆`,
  note: "本站為靜態快照，資料更新日之後的異動不會反映在此。",
} as const;

/** §7.1 統計卡。**以 Trial 為分母並明寫「試驗」。** */
export const STATS = {
  unit: "試驗",
  denominatorNote: (n: number) => `分母為 ${n} 個試驗（非審查紀錄筆數）`,
  recordNote: (n: number) => `資料含 ${n} 筆審查紀錄`,
} as const;

/** §6.6 的欄位級提示。`numericRange` 顯示 raw 原文（E8）。 */
export const FIELD_NOTE: Record<string, string> = {
  categoricalUnprovided: "來源未提供",
  categoricalUnknown: "來源值不在已知清單內",
  numericMissing: "來源未提供",
  sourceZero: "來源填 0",
  numericRange: "來源為範圍值",
  numericRangeInvalid: "來源範圍的起迄顛倒",
  numericImplausible: "數值超出合理範圍",
  numericUnparsed: "數值無法解析",
  numericOutOfRange: "數值超出可表示範圍",
  dateMissing: "來源未提供日期",
  dateUnparsed: "日期無法解析",
  dateFuture: "日期晚於資料建置日",
  periodStartMissing: "期間起未提供",
  periodStartUnparsed: "期間起無法解析",
  periodEndMissing: "期間迄未提供",
  periodEndUnparsed: "期間迄無法解析",
  rawVariants: "同日多筆的原文寫法不同（值相同）",
  periodEndBeforeStart: "期間迄早於期間起",
  suspectedTestRow: "疑似上游測試資料",
};

/** `YYYY-MM-DD` → `YYYY/MM/DD`。**null 一律回 null，不得代入今天或空字串**。 */
export function formatDate(iso: string | null): string | null {
  return iso === null ? null : iso.replaceAll("-", "/");
}
