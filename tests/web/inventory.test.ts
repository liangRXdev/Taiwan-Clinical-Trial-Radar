/**
 * E1（允許呈現的狀態概念封閉清單）與 E4（來源資料可到達的輸出 surface 封閉 inventory）。
 *
 * 兩條的共同形狀是**封閉性**：不是「抽幾個地方測測看」，而是先把清單寫死，
 * 再雙向對帳。E4 原本散在 `render.test.ts` 裡三個各自獨立的案例——那測得到
 * 「這三處有跳脫」，測不到「沒有第四處」，而第四處正是 XSS 的所在。
 *
 * E1 的紀律：**禁字只作 mutation guard，且不得施加於來源原文**。試驗名稱裡本來
 * 就可能出現「收案」二字，對來源原文設無條件禁字會把合法資料判成違規，
 * 那是漏報與誤報同時發生。
 */

import { describe, expect, it } from "vitest";

import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { CONFLICTED, UNPROVIDED } from "../../src/lib/filter.js";
import type { Trial } from "../../src/lib/types.js";
import { buildUrl, emptyState } from "../../src/lib/urlState.js";
import { renderCard } from "../../src/ui/card.js";
import { renderDetail } from "../../src/ui/detail.js";
import { renderDisclaimer } from "../../src/ui/disclaimer.js";
import { facetOptions, renderFilters } from "../../src/ui/filters.js";
import { renderMeta } from "../../src/ui/meta.js";
import { renderStats } from "../../src/ui/stats.js";
import { DISCLAIMER, FIELD_NOTE, FILTER_SPECIAL, LABEL, META, SCOPE, STATS } from "../../src/ui/text.js";
import { manifest, shard, stats, trials } from "./fixture.js";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "src");

function srcFiles(dir = SRC_DIR): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...srcFiles(p));
    else if (entry.name.endsWith(".ts")) out.push(p);
  }
  return out;
}

// ─────────────────────────────────────────────────────────────── E1

/**
 * **允許呈現的狀態概念封閉清單。**
 *
 * 「狀態概念」＝本站自己對一筆試驗所作的陳述。來源欄位的值不在此列——
 * 那是資料，不是本站的主張。清單以外的狀態陳述一律視為違規，
 * 其中最要緊的是招募／收案狀態：本站沒有那份資料，說什麼都是編的。
 */
const ALLOWED_STATE_CONCEPTS = [
  // §7.2／E7／E8：對「資料本身」的陳述
  "同日多筆資料不一致",
  "資料日期無法辨識",
  "來源未提供計畫書編號",
  "同日多筆順序未知",
  "命中來自較舊的審查紀錄",
  "命中紀錄的資料日期不明",
  "近似的計畫書編號",
  "合併自僅空白不同的寫法",
  "資料日期不明的紀錄",
  // §6.6：欄位級的解析結果
  "來源未提供",
  "來源值不在已知清單內",
  "來源填 0",
  "來源為範圍值",
  "來源範圍起迄顛倒",
  "數值超出合理範圍",
  "數值無法解析",
  "數值超出可表示範圍",
  "日期無法解析",
  "日期晚於資料建置日",
  "期間端未提供或無法解析",
  "期間迄早於期間起",
  "疑似上游測試資料",
  // §9.3.5／E3：資料集層級的事實
  "來源資料更新日",
  "本站資料建置時間",
  "收錄總數",
] as const;

type Concept = (typeof ALLOWED_STATE_CONCEPTS)[number];

/**
 * 會作出狀態陳述的文句表。**`SCOPE` 不在其中**——它講的是搜尋範圍，
 * 不是對試驗或資料的判斷。納進來只會讓對帳變成形式。
 */
function claimTables(): Record<string, string> {
  const out: Record<string, string> = {};
  const add = (prefix: string, table: Record<string, unknown>) => {
    for (const [k, v] of Object.entries(table)) {
      out[`${prefix}.${k}`] =
        typeof v === "function" ? String((v as (x: never) => string)("2026/09/18" as never)) : String(v);
    }
  };
  add("LABEL", LABEL);
  add("FILTER_SPECIAL", FILTER_SPECIAL);
  add("FIELD_NOTE", FIELD_NOTE);
  add("META", META);
  return out;
}

/**
 * 每一句狀態陳述 → 它主張的概念。**雙向對帳的另一半**：
 * 表裡少一個 key（新增了沒登記的陳述）或多一個死概念，都要轉紅。
 *
 * 多對一是正常的——概念是分類，文句是措辭。
 */
const CONCEPT_OF: Record<string, Concept> = {
  "LABEL.ambiguous": "同日多筆資料不一致",
  "LABEL.dateUnknown": "資料日期無法辨識",
  "LABEL.noProtocol": "來源未提供計畫書編號",
  "LABEL.sameDayUnordered": "同日多筆順序未知",
  "LABEL.hitFromOlder": "命中來自較舊的審查紀錄",
  "LABEL.hitDateUnknown": "命中紀錄的資料日期不明",
  "LABEL.nearDuplicate": "近似的計畫書編號",
  "LABEL.mergedVariants": "合併自僅空白不同的寫法",
  "LABEL.undatedRecords": "資料日期不明的紀錄",
  "FILTER_SPECIAL.unprovided": "來源未提供",
  "FILTER_SPECIAL.conflicted": "同日多筆資料不一致",
  "FIELD_NOTE.categoricalUnprovided": "來源未提供",
  "FIELD_NOTE.categoricalUnknown": "來源值不在已知清單內",
  "FIELD_NOTE.numericMissing": "來源未提供",
  "FIELD_NOTE.sourceZero": "來源填 0",
  "FIELD_NOTE.numericRange": "來源為範圍值",
  "FIELD_NOTE.numericRangeInvalid": "來源範圍起迄顛倒",
  "FIELD_NOTE.numericImplausible": "數值超出合理範圍",
  "FIELD_NOTE.numericUnparsed": "數值無法解析",
  "FIELD_NOTE.numericOutOfRange": "數值超出可表示範圍",
  "FIELD_NOTE.dateMissing": "來源未提供",
  "FIELD_NOTE.dateUnparsed": "日期無法解析",
  "FIELD_NOTE.dateFuture": "日期晚於資料建置日",
  "FIELD_NOTE.periodStartMissing": "期間端未提供或無法解析",
  "FIELD_NOTE.periodStartUnparsed": "期間端未提供或無法解析",
  "FIELD_NOTE.periodEndMissing": "期間端未提供或無法解析",
  "FIELD_NOTE.periodEndUnparsed": "期間端未提供或無法解析",
  "FIELD_NOTE.rawVariants": "合併自僅空白不同的寫法",
  "FIELD_NOTE.periodEndBeforeStart": "期間迄早於期間起",
  "FIELD_NOTE.suspectedTestRow": "疑似上游測試資料",
  "META.title": "來源資料更新日",
  "META.sourceUpdatedAt": "來源資料更新日",
  "META.sourceUpdatedUnknown": "來源資料更新日",
  "META.note": "來源資料更新日",
  "META.builtAt": "本站資料建置時間",
  "META.builtAtUnparsed": "本站資料建置時間",
  "META.taipeiSuffix": "本站資料建置時間",
  "META.trialCount": "收錄總數",
  "META.recordCount": "收錄總數",
  "META.trialUnit": "收錄總數",
  "META.recordUnit": "收錄總數",
};

/** mutation guard（**只掃本站自撰文句**，不掃來源原文）。 */
const FORBIDDEN_IN_OWN_COPY = ["招募", "收案", "執行中", "尚在進行", "已結案", "可報名"];

/**
 * 本站自撰的全部使用者可見文句。E1 的掃描對象就是這一集合。
 *
 * 函式型的文句（帶參數）一律代入一個代表值後納入——把它們跳過去，
 * 等於「只要把違規字眼寫進帶參數的句子就掃不到」。
 */
function ownCopy(): string[] {
  const sources: Record<string, unknown>[] = [FILTER_SPECIAL, FIELD_NOTE, META, SCOPE, STATS, LABEL];
  const out: string[] = [...DISCLAIMER];
  for (const table of sources) {
    for (const v of Object.values(table)) {
      if (typeof v === "string") out.push(v);
      else if (typeof v === "function") out.push(String((v as (x: never) => string)("2026/09/18" as never)));
    }
  }
  return out;
}

describe("E1：§10 三項免責的正向精確斷言", () => {
  it("三項逐一可見（**正向**，不是「沒有禁字就算過」）", () => {
    const text = renderDisclaimer().textContent ?? "";
    for (const line of DISCLAIMER) expect(text).toContain(line);
    expect(DISCLAIMER).toHaveLength(3);
  });

  it("第一項明講「不提供招募狀態」——這是本站最重要的一句話", () => {
    expect(DISCLAIMER[0]).toContain("不提供試驗目前的招募狀態");
  });

  it("第二項明講「列入審查不等於已核准」", () => {
    expect(DISCLAIMER[1]).toContain("不等於該藥品已獲上市核准");
  });

  it("第三項把確認責任導向官方來源與醫療專業人員", () => {
    expect(DISCLAIMER[2]).toContain("官方資料來源");
    expect(DISCLAIMER[2]).toContain("醫療專業人員");
  });
});

describe("E1：狀態概念封閉清單", () => {
  it("清單本身無重複（重複會讓雙向對帳失去意義）", () => {
    expect(new Set(ALLOWED_STATE_CONCEPTS).size).toBe(ALLOWED_STATE_CONCEPTS.length);
  });

  it("**每一句狀態陳述都登記了概念**——新增文句而未登記即紅", () => {
    const unregistered = Object.keys(claimTables()).filter((k) => !(k in CONCEPT_OF));
    expect(unregistered).toEqual([]);
  });

  it("**每個概念都有文句用到**——清單裡不得有已無對應的死概念", () => {
    const used = new Set(Object.values(CONCEPT_OF));
    const dead = ALLOWED_STATE_CONCEPTS.filter((c) => !used.has(c));
    expect(dead).toEqual([]);
  });

  it("登記的概念全部落在封閉清單內", () => {
    for (const [key, concept] of Object.entries(CONCEPT_OF)) {
      expect(ALLOWED_STATE_CONCEPTS, `${key} 的概念不在清單內`).toContain(concept);
    }
  });

  it("**反向哨兵**：憑空多一句狀態陳述時，第一條會轉紅", () => {
    const withExtra = { ...claimTables(), "LABEL.recruitingNow": "目前開放報名" };
    const unregistered = Object.keys(withExtra).filter((k) => !(k in CONCEPT_OF));
    expect(unregistered).toEqual(["LABEL.recruitingNow"]);
  });

  it("**mutation guard**：自撰文句不得出現招募／收案狀態字眼", () => {
    for (const line of ownCopy()) {
      for (const word of FORBIDDEN_IN_OWN_COPY) {
        // 免責句本身要能說「不提供招募狀態」，那是唯一允許提及的地方
        if (DISCLAIMER.includes(line as (typeof DISCLAIMER)[number])) continue;
        expect(line, `自撰文句出現「${word}」：${line}`).not.toContain(word);
      }
    }
  });

  it("**禁字不得施加於來源原文**：含「收案」的來源值照樣完整顯示", () => {
    const payload = "本試驗目前收案中（來源原文）";
    const fake = {
      ...trials[0]!,
      conflictFields: [],
      displayFields: { 臨床試驗計畫中文名稱: { raw: payload, typed: payload, flags: [] } },
    } as unknown as Trial;
    const card = renderCard({ trial: fake, hits: [] }, { detailHref: (id) => `?trial=${id}` });
    expect(card.textContent).toContain(payload);
  });

  it("本站不存在任何 trial-status 維度的篩選或統計（D5 的呈現層對應）", () => {
    const panel = renderFilters({
      stats,
      state: { phase: [], scale: [], applicant: [], enroll: [], period: null, updated: null },
      errors: new Map(),
      callbacks: { onToggle: () => {}, onRange: () => {} },
    });
    const text = panel.textContent ?? "";
    for (const word of FORBIDDEN_IN_OWN_COPY) expect(text).not.toContain(word);
  });
});

// ─────────────────────────────────────────────────────────────── E4

const XSS = '<img src=x onerror="alert(1)">';
const XSS_2 = "\"><script>alert(2)</script>";

/** 來源資料可到達的輸出 surface。**封閉清單**——新增 surface 須同時登記並測試。 */
const SOURCE_REACHABLE_SURFACES = [
  "卡片",
  "詳情頁",
  "record 切換",
  "filter option",
  "搜尋命中標籤",
  "統計 label",
  "accessible name",
  "URL 顯示",
] as const;

const covered = new Set<string>();

function surface(name: (typeof SOURCE_REACHABLE_SURFACES)[number], fn: () => void): void {
  it(`${name}：來源資料以文字呈現，不產生元素`, () => {
    covered.add(name);
    fn();
  });
}

/** 注入後的共同斷言：不產生元素、原文完整保留。 */
function expectInert(node: Element, payload: string): void {
  expect(node.querySelector("img")).toBeNull();
  expect(node.querySelector("script")).toBeNull();
  expect(node.textContent ?? "").toContain(payload);
}

describe("E4：來源資料可到達的輸出 surface 封閉 inventory", () => {
  const href = (id: string) => `?trial=${id}`;

  surface("卡片", () => {
    const fake = {
      ...trials[0]!,
      conflictFields: [],
      protocolRaw: [XSS],
      protocolNonIdentifier: false,
      displayFields: { 臨床試驗計畫中文名稱: { raw: XSS, typed: XSS, flags: [] } },
    } as unknown as Trial;
    expectInert(renderCard({ trial: fake, hits: [] }, { detailHref: href }), XSS);
  });

  surface("詳情頁", () => {
    const t = trials.find((x) => x.recordCount > 1 && !x.dateUnknown)!;
    const sh = structuredClone(shard(t.shard));
    const rid = sh.trials[t.id]!.recordIds[0]!;
    sh.records[rid]!.raw["納入條件"] = XSS_2;
    expectInert(renderDetail(t, sh, { nearDuplicates: [] }), XSS_2);
  });

  surface("record 切換", () => {
    // 同一 Trial 的**第二筆** record：只驗第一筆時，一個「只跳脫最新紀錄」的
    // 實作會全綠，而詳情頁是把每一筆都畫出來的。
    const t = trials.find((x) => x.recordCount > 1)!;
    const sh = structuredClone(shard(t.shard));
    const rid = sh.trials[t.id]!.recordIds[1]!;
    sh.records[rid]!.raw["臨床試驗計畫中文名稱"] = XSS;
    expectInert(renderDetail(t, sh, { nearDuplicates: [] }), XSS);
  });

  surface("filter option", () => {
    const poisoned = structuredClone(stats);
    poisoned.facets.applicant!.buckets[0]!.value = XSS;
    const panel = renderFilters({
      stats: poisoned,
      state: { phase: [], scale: [], applicant: [], enroll: [], period: null, updated: null },
      errors: new Map(),
      callbacks: { onToggle: () => {}, onRange: () => {} },
    });
    expectInert(panel, XSS);
    // option 的 value 是要進 URL 的，也不得被當成標記
    expect(facetOptions(poisoned.facets.applicant!).map((o) => o.value)).toContain(XSS);
  });

  surface("搜尋命中標籤", () => {
    const t = trials.find((x) => x.searchShortLatest.length > 0)!;
    const fake = {
      ...t,
      conflictFields: [],
      protocolRaw: [XSS],
      protocolNonIdentifier: false,
    } as unknown as Trial;
    const card = renderCard(
      { trial: fake, hits: [{ recordId: t.searchShortLatest[0]!.r, fieldIndexes: [0] }] },
      { detailHref: href },
    );
    expectInert(card, XSS);
  });

  surface("統計 label", () => {
    const poisoned = structuredClone(stats);
    poisoned.facets.phase!.buckets[0]!.value = XSS;
    expectInert(renderStats(poisoned), XSS);
  });

  surface("accessible name", () => {
    // chip 的 `aria-label` 由本站文句組成，但 filter option 的 accessible name
    // 含**來源值**。螢幕閱讀器讀得到的字串同樣要是純文字。
    const poisoned = structuredClone(stats);
    poisoned.facets.scale!.buckets[0]!.value = XSS;
    const panel = renderFilters({
      stats: poisoned,
      state: { phase: [], scale: [], applicant: [], enroll: [], period: null, updated: null },
      errors: new Map(),
      callbacks: { onToggle: () => {}, onRange: () => {} },
    });
    const names = [...panel.querySelectorAll("[aria-label]")].map((n) => n.getAttribute("aria-label"));
    for (const n of names) expect(n).not.toBeNull();
    // 任何 accessible name 都不得含未經跳脫的標記殘留（它們是 attribute，不是 HTML）
    expect(panel.querySelector("img")).toBeNull();
    expect(panel.textContent ?? "").toContain(XSS);
  });

  surface("URL 顯示", () => {
    const state = { ...emptyState(), q: XSS_2, filters: { ...emptyState().filters, phase: [XSS] } };
    const url = buildUrl(state);
    // 編碼後不得殘留可被解析為標記的裸字元
    expect(url).not.toContain("<");
    expect(url).not.toContain('"');
    // 而且必須是**可逆**的編碼，不是把內容吃掉
    expect(decodeURIComponent(new URLSearchParams(url.replace(/^\?/, "")).get("q")!)).toBe(XSS_2);
  });

  it("inventory **封閉**：清單中的每一個 surface 都有對應測試", () => {
    expect([...covered].sort()).toEqual([...SOURCE_REACHABLE_SURFACES].sort());
  });

  it("**結構性保證**：`src/` 全域不存在 innerHTML 類的寫法", () => {
    const banned = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"];
    // 先去註解：`dom.ts` 的說明段落本來就要寫出「不使用 innerHTML」這句話，
    // 掃原始碼字串會把那段自我說明判成違規。
    const stripComments = (s: string) =>
      s.replaceAll(/\/\*[\s\S]*?\*\//g, "").replaceAll(/\/\/.*/g, "");
    let scanned = 0;
    for (const file of srcFiles()) {
      const body = stripComments(readFileSync(file, "utf-8"));
      scanned += 1;
      for (const token of banned) {
        expect(body, `${file} 出現 ${token}`).not.toContain(token);
      }
    }
    // 去註解不得把整個檔案吃光，否則這條會變成恆真
    expect(scanned).toBeGreaterThanOrEqual(10);
    expect(stripComments(readFileSync(srcFiles()[0]!, "utf-8")).trim().length).toBeGreaterThan(0);
  });

  it("metadata surface 的值同樣不是 HTML（E3 的 surface 也在來源可達路徑上）", () => {
    const poisoned = { ...structuredClone(manifest), sourceUpdatedAt: XSS };
    expectInert(renderMeta(poisoned), XSS);
  });

  it("特殊篩選值常數未被來源資料覆寫（`UNPROVIDED`／`CONFLICTED` 不是來源值）", () => {
    for (const bucket of Object.values(stats.facets).flatMap((f) => f.buckets)) {
      expect(bucket.value).not.toBe(UNPROVIDED);
      expect(bucket.value).not.toBe(CONFLICTED);
    }
  });
});
