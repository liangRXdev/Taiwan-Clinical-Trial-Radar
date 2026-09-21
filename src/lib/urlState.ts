/**
 * §7.4 URL state schema。
 *
 * canonical query string：**只輸出非預設值的參數，依本表順序排列。**
 * 順序、編碼、重複參數與未知參數的處置都是契約的一部分——
 * D4 要求「canonical URL 字串精確相等」，任何一條走樣都會讓分享出去的連結重現不出結果。
 */

import { DIMENSIONS, emptyFilter, parseDateRange, type FilterState } from "./filter.js";
import { DEFAULT_SCOPE, type FieldsScope, type HistoryScope, type Scope } from "./scope.js";

/** §7.4 的參數順序。**canonical 輸出依此排列，不是依使用者輸入順序。** */
export const PARAM_ORDER = [
  "q",
  "trial",
  "protocol",
  "phase",
  "scale",
  "applicant",
  "enroll",
  "period",
  "updated",
  "fields",
  "history",
] as const;

export interface AppState {
  q: string;
  trial: string | null;
  protocol: string | null;
  filters: FilterState;
  scope: Scope;
  /** 未知參數：**忽略但保留於 URL 不改寫**（§7.4） */
  unknown: Array<[string, string]>;
}

export interface ParseResult {
  state: AppState;
  /** 無效值。**不得空白頁、不得靜默回首頁、不得靜默丟棄該條件**（§7.4） */
  errors: Array<{ param: string; value: string; message: string }>;
}

export function emptyState(): AppState {
  return {
    q: "",
    trial: null,
    protocol: null,
    filters: emptyFilter(),
    scope: { ...DEFAULT_SCOPE },
    unknown: [],
  };
}

const MULTI = new Set(["phase", "scale", "applicant", "enroll"]);
const KNOWN = new Set<string>(PARAM_ORDER);

export function parseUrl(search: string): ParseResult {
  const params = new URLSearchParams(search);
  const state = emptyState();
  const errors: ParseResult["errors"] = [];

  for (const [key, value] of params) {
    if (!KNOWN.has(key)) {
      state.unknown.push([key, value]);
      continue;
    }
    switch (key) {
      case "q":
        state.q = value;
        break;
      case "trial":
        state.trial = value;
        break;
      case "protocol":
        state.protocol = value;
        break;
      case "phase":
      case "scale":
      case "applicant":
      case "enroll":
        state.filters[key].push(value);
        break;
      case "period":
      case "updated": {
        if (parseDateRange(value) === null) {
          errors.push({
            param: key,
            value,
            message: `${key} 須為 YYYY-MM-DD..YYYY-MM-DD 且起不晚於迄`,
          });
          // **保留該條件**而不是丟掉：丟掉會讓使用者以為篩選生效了
          state.filters[key] = value;
        } else {
          state.filters[key] = value;
        }
        break;
      }
      case "fields":
        if (value === "short" || value === "all") state.scope.fields = value as FieldsScope;
        else errors.push({ param: key, value, message: "fields 只能是 short 或 all" });
        break;
      case "history":
        if (value === "latest" || value === "all") state.scope.history = value as HistoryScope;
        else errors.push({ param: key, value, message: "history 只能是 latest 或 all" });
        break;
    }
  }

  // 同維度多值依字典序排列後輸出（§7.4）。這裡先排好，使 parse → build 為冪等。
  for (const dim of MULTI) {
    const arr = state.filters[dim as "phase"];
    arr.sort((a, b) => a.localeCompare(b));
  }

  return { state, errors };
}

/**
 * 產生 canonical query string。**只輸出非預設值**，依 `PARAM_ORDER` 排列。
 *
 * 未知參數附在最後並保留原值——§7.4 要求「忽略但保留於 URL 不改寫」。
 * 把它們丟掉會讓使用者貼進來的追蹤參數或未來版本的參數在重整後消失。
 */
export function buildUrl(state: AppState): string {
  const parts: string[] = [];
  const push = (k: string, v: string) =>
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(v)}`);

  for (const key of PARAM_ORDER) {
    switch (key) {
      case "q":
        if (state.q !== "") push("q", state.q);
        break;
      case "trial":
        if (state.trial !== null) push("trial", state.trial);
        break;
      case "protocol":
        if (state.protocol !== null) push("protocol", state.protocol);
        break;
      case "phase":
      case "scale":
      case "applicant":
      case "enroll":
        for (const v of [...state.filters[key]].sort((a, b) => a.localeCompare(b))) {
          push(key, v);
        }
        break;
      case "period":
      case "updated":
        if (state.filters[key] !== null) push(key, state.filters[key]!);
        break;
      case "fields":
        if (state.scope.fields !== DEFAULT_SCOPE.fields) push("fields", state.scope.fields);
        break;
      case "history":
        if (state.scope.history !== DEFAULT_SCOPE.history) push("history", state.scope.history);
        break;
    }
  }

  for (const [k, v] of state.unknown) push(k, v);

  return parts.length === 0 ? "" : `?${parts.join("&")}`;
}

/** 本次載入是否只是瀏覽（無查詢、無篩選、無詳情）。 */
export function isBrowsing(state: AppState): boolean {
  return (
    state.q.trim() === "" &&
    state.trial === null &&
    state.protocol === null &&
    DIMENSIONS.every((d) => {
      const v = state.filters[d];
      return Array.isArray(v) ? v.length === 0 : v === null;
    })
  );
}
