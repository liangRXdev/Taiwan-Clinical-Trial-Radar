/**
 * §9.3.5 各檔 schema 的 TypeScript 對應。
 *
 * 這裡只描述**前端實際讀取的欄位**。把整份 schema 抄成型別會產生第二份規格，
 * 而兩份規格必然漂移——真正的契約在 `.ai-review/plan.md` §9.3.5 與
 * `tests/fixtures/web_artifact/`（後者由現行 ETL 產生，漂移會使 Python 測試轉紅）。
 */

/** §9.3.3 的 typed 值。數值欄位可能是區間（§6.6.3 的 `numericRange`）。 */
export type Typed = string | number | NumericRange | null;

export interface NumericRange {
  min: number;
  max: number;
}

export function isNumericRange(v: Typed): v is NumericRange {
  return typeof v === "object" && v !== null && "min" in v && "max" in v;
}

/** §6.4.5 的 `{raw, typed, flags}` 三元組。 */
export interface FieldValue {
  raw: string;
  typed: Typed;
  flags: string[];
}

/** §9.3.4：每一筆 latest-cohort record 的獨立 recordId 與五欄陣列。 */
export interface SearchEntry {
  /** recordId */
  r: string;
  /** 已 `searchNormalize` 的欄位文字，順序固定為 SHORT_SEARCH_FIELDS */
  f: string[];
}

/** §6.4.4 的 Trial（在 `trials-index.json` 內）。 */
export interface Trial {
  id: string;
  protocolRaw: string[];
  protocolNonIdentifier: boolean;
  suspectedTestRow: boolean;
  nearDuplicateGroup: string | null;
  latestSourceDate: string | null;
  dateUnknown: boolean;
  latestCohortCount: number;
  recordCount: number;
  latestAmbiguous: boolean;
  /** 衝突的呈現欄位名。**全部 13 個**呈現欄位皆可入列，含四個長文字欄位。 */
  conflictFields: string[];
  /**
   * §6.4.5：**只含 9 個卡片欄位**，且實際鍵集合 = 允許集合 − `conflictFields` 中
   * 屬於這 9 欄者。四個長文字欄位不在此（F3），詳情頁逐 record 從 shard 取原文。
   */
  displayFields: Record<string, FieldValue>;
  searchShortLatest: SearchEntry[];
  shard: string;
}

export interface TrialsIndex {
  datasetVersion: string;
  trials: Trial[];
}

/** §9.3.5 的按需搜尋檔（`search-short-all` 等）。 */
export interface SearchFile {
  datasetVersion: string;
  fields: string[];
  records: Array<{
    r: string;
    t: string;
    /** 可採計日期；`null` 表示該 record 無可採計日期（§7.2 的「資料日期不明」） */
    d: string | null;
    f: string[];
  }>;
}

export interface FacetBucket {
  value: string;
  count: number;
}

export interface Facet {
  denominatorKind: string;
  buckets: FacetBucket[];
  unprovided: number;
  conflicted: number;
}

export interface Stats {
  datasetVersion: string;
  denominators: { trials: number; records: number };
  facets: Record<string, Facet>;
}

export interface FileMeta {
  path: string;
  bytes: number;
  gzipBytes: number;
  /**
   * §9.3.5：**建置期 quality 11 的估算值，不是實際傳輸大小。**
   * 只有五個具名 top-level 條目有此欄位；`recordShards` 沒有。
   */
  brotliBytes?: number;
}

export interface Manifest {
  schemaVersion: number;
  datasetVersion: string;
  artifactDigest: string;
  sourceDatasetId: number;
  sourceUpdatedAt: string | null;
  fetchedAt: string;
  builtAt: string;
  buildDate: string;
  sourceSha256: string;
  trialCount: number;
  recordCount: number;
  bootstrap: boolean;
  files: {
    trialsIndex: FileMeta;
    stats: FileMeta;
    searchShortAll: FileMeta;
    searchLongLatest: FileMeta;
    searchLongAll: FileMeta;
    recordShards: Record<string, FileMeta>;
  };
}

/** §9.3.5 的 shard。詳情頁的唯一資料來源。 */
export interface Shard {
  datasetVersion: string;
  trials: Record<string, { latestCohort: string[]; recordIds: string[] }>;
  records: Record<string, ShardRecord>;
}

export interface ShardRecord {
  /** 16 欄的原始值 */
  raw: Record<string, string>;
  typed: Record<string, Typed>;
  /** 只含**有旗標**的欄位 */
  fieldFlags: Record<string, string[]>;
  recordFlags: string[];
}
