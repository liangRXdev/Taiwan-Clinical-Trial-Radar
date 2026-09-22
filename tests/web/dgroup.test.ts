/**
 * D1／D2／D3／D6／D8：搜尋欄位歸屬、比對語意、多詞語意、衝突分組、區間重疊。
 *
 * **D4（canonical URL 與 reload）與 D5 的 DOM 控制項在 e2e**：那兩條驗的是
 * 真實 URL 與重新整理後的控制項狀態，happy-dom 的假 `location` 證明不了。
 *
 * 本檔的 canary 由 `scripts/build_web_fixture.py` 的 `CANARY_TOKENS` 產生：
 * 每一欄一個全域唯一的 ASCII token。用 a_core 的自然值當 canary 測到的是巧合
 * ——它的「唯一值」多半同時出現在別欄。
 */

import { describe, expect, it } from "vitest";

import { applyFilters, CONFLICTED, DIMENSIONS, UNPROVIDED } from "../../src/lib/filter.js";
import {
  browseAll,
  mergeHits,
  parseQuery,
  searchEntries,
  searchLatestShort,
  searchNormalize,
  type TrialHit,
} from "../../src/lib/search.js";
import { filesToLoad, type Scope } from "../../src/lib/scope.js";
import { emptyState } from "../../src/lib/urlState.js";
import { renderCard, SHORT_FIELD_NAMES } from "../../src/ui/card.js";
import { index, searchFile, trials } from "./fixture.js";

/** 與 `scripts/build_web_fixture.py` 的 `CANARY_TOKENS` 一一對應。 */
const SHORT_CANARY: Record<string, string> = {
  臨床試驗計畫書編號: "CANARYPROTOCOLZZ",
  臨床試驗計畫中文名稱: "CANARYTITLEZZ",
  臨床試驗申請者: "CANARYAPPLICANTZZ",
  適應症中文: "CANARYINDICATIONZZ",
  TFDA收文號: "CANARYRECEIPTZZ",
};

const LONG_CANARY: Record<string, string> = {
  試驗目的: "CANARYPURPOSEZZ",
  主要評估指標: "CANARYENDPOINTZZ",
};

/** §8.5 的 9 個不可搜尋欄位。**任何 scope 都不得搜到**。 */
const UNSEARCHABLE_CANARY: Record<string, string> = {
  臨床試驗期別: "CANARYPHASEZZ",
  本臨床試驗規模: "CANARYSCALEZZ",
  試驗預計執行期間起: "CANARYSTARTZZ",
  試驗預計執行期間迄: "CANARYENDZZ",
  全球預計受試者人數: "CANARYGLOBALZZ",
  台灣預計受試者人數: "CANARYLOCALZZ",
  納入條件: "CANARYINCLUSIONZZ",
  排除條件: "CANARYEXCLUSIONZZ",
  資料更新時間: "CANARYUPDATEDZZ",
};

const SCOPES: Scope[] = [
  { fields: "short", history: "latest" },
  { fields: "short", history: "all" },
  { fields: "all", history: "latest" },
  { fields: "all", history: "all" },
];

const DEFAULT_SCOPE = SCOPES[0]!;

/** 與 `app.ts` 的 `results()` 同一套組裝。搬一份是為了不把 App 的 fetch 拖進來。 */
function searchInScope(scope: Scope, q: string): TrialHit[] {
  const terms = parseQuery(q);
  if (terms.length === 0) return browseAll(trials);

  const groups: TrialHit[][] = [];
  if (scope.fields === "short" && scope.history === "latest") {
    groups.push(searchLatestShort(trials, terms));
  } else {
    for (const key of filesToLoad(scope, new Set())) {
      groups.push(searchEntries(trials, searchFile(key).records, terms));
    }
    if (scope.history === "latest" && scope.fields === "all") {
      groups.push(searchLatestShort(trials, terms));
    }
  }
  return mergeHits(groups);
}

const ids = (hits: TrialHit[]): string[] => hits.map((h) => h.trial.id).sort();

/** canary 列所屬的 Trial。fixture 換人時直接爆。 */
const canaryTrial = trials.find((t) => t.protocolRaw.includes("CANARYPROTOCOLZZ"))!;

describe("D1：每一個可搜尋欄位各有唯一 canary", () => {
  it("canary trial 存在且只有一筆 record（否則命中歸屬會混進別列）", () => {
    expect(canaryTrial).toBeDefined();
    expect(canaryTrial.recordCount).toBe(1);
  });

  for (const [field, token] of Object.entries(SHORT_CANARY)) {
    it(`短欄 ${field}：預設 scope 即命中，且**精確為** canary trial`, () => {
      expect(ids(searchInScope(DEFAULT_SCOPE, token))).toEqual([canaryTrial.id]);
    });
  }

  for (const [field, token] of Object.entries(LONG_CANARY)) {
    it(`長欄 ${field}：預設 scope **搜不到**，擴大欄位後精確命中`, () => {
      expect(ids(searchInScope(DEFAULT_SCOPE, token))).toEqual([]);
      expect(ids(searchInScope({ fields: "all", history: "latest" }, token))).toEqual([
        canaryTrial.id,
      ]);
      expect(ids(searchInScope({ fields: "all", history: "all" }, token))).toEqual([
        canaryTrial.id,
      ]);
    });
  }

  for (const [field, token] of Object.entries(UNSEARCHABLE_CANARY)) {
    it(`不可搜尋欄位 ${field}：**四種 scope 全部搜不到**`, () => {
      for (const scope of SCOPES) {
        expect(ids(searchInScope(scope, token)), `${field} 在 ${JSON.stringify(scope)}`).toEqual([]);
      }
    });
  }

  it("不可搜尋的 canary 恰為 9 個，且與可搜尋的 7 個**沒有交集**", () => {
    expect(Object.keys(UNSEARCHABLE_CANARY)).toHaveLength(9);
    const searchable = new Set([...Object.values(SHORT_CANARY), ...Object.values(LONG_CANARY)]);
    for (const token of Object.values(UNSEARCHABLE_CANARY)) expect(searchable.has(token)).toBe(false);
    expect(searchable.size).toBe(7);
  });

  it("**多欄同時命中時命中標籤集合完全相等**", () => {
    const q = `${SHORT_CANARY.臨床試驗計畫中文名稱} ${SHORT_CANARY.適應症中文}`;
    const hits = searchInScope(DEFAULT_SCOPE, q);
    expect(ids(hits)).toEqual([canaryTrial.id]);

    const card = renderCard(hits[0]!, { detailHref: (id) => `?trial=${id}` });
    const label = card.querySelector(".hit__fields")!.textContent ?? "";
    const shown = label.replace("命中欄位：", "").split("、").sort();
    expect(shown).toEqual(["臨床試驗計畫中文名稱", "適應症中文"].sort());
  });

  it("單欄命中時標籤**只有那一欄**，不多報", () => {
    const hits = searchInScope(DEFAULT_SCOPE, SHORT_CANARY.TFDA收文號!);
    const card = renderCard(hits[0]!, { detailHref: (id) => `?trial=${id}` });
    const label = card.querySelector(".hit__fields")!.textContent ?? "";
    expect(label).toBe("命中欄位：TFDA收文號");
  });

  it("短欄名單的順序即 §9.3.4 的欄位順序（標籤靠索引對應，錯位即誤標）", () => {
    expect([...SHORT_FIELD_NAMES]).toEqual(Object.keys(SHORT_CANARY));
  });

  /**
   * **同日 cohort 的每一筆 record 都要被搜尋到**，不只第一筆。
   *
   * 2026-09-22 的哨兵實測：把 `searchLatestShort` 改成只讀 `searchShortLatest[0]`，
   * 當時全部 206 條前端測試**無一轉紅**——同日兩筆中只出現在後一筆的值會靜默搜不到，
   * 而使用者看到的是「查無資料」。那是漏報，風險排序上最嚴重的一類。
   */
  it("**cohort 內每一筆 record 的值都搜得到**（不得只讀第一筆）", () => {
    const multi = trials.filter((t) => t.searchShortLatest.length > 1);
    expect(multi.length, "fixture 缺多 record cohort").toBeGreaterThan(0);

    let checkedLaterRecord = 0;
    for (const t of multi) {
      for (const [i, entry] of t.searchShortLatest.entries()) {
        // 只挑「該筆獨有」的值，否則第一筆也有、測不出差別
        const own = entry.f.find(
          (v) =>
            v.trim() !== ""
            && t.searchShortLatest.every((other, j) => j === i || !other.f.includes(v)),
        );
        if (own === undefined) continue;
        if (i > 0) checkedLaterRecord += 1;
        expect(ids(searchInScope(DEFAULT_SCOPE, own)), `${t.id} 第 ${i} 筆的 ${own}`).toContain(t.id);
      }
    }
    // 沒有檢到任何「第一筆以外」的值時，這條等於沒測
    expect(checkedLaterRecord, "沒有檢到第一筆以外的 record").toBeGreaterThan(0);
  });
});

describe("D2：逐欄的 §8.1 policy 與 §8.2 operator", () => {
  /** `shouldMatch`／`mustNotMatch` 成對表達，避免只寫正例。 */
  const CASES: { name: string; q: string; match: boolean }[] = [
    { name: "完整 token", q: "CANARYTITLEZZ", match: true },
    { name: "substring（中段）", q: "NARYTITLE", match: true },
    { name: "prefix", q: "CANARYTI", match: true },
    { name: "suffix", q: "TITLEZZ", match: true },
    { name: "casefold：全小寫", q: "canarytitlezz", match: true },
    { name: "casefold：混合大小寫", q: "CaNaRyTiTlEzZ", match: true },
    { name: "NFKC：全形英數", q: "ＣＡＮＡＲＹＴＩＴＬＥＺＺ", match: true },
    { name: "前後空白不影響", q: "  CANARYTITLEZZ  ", match: true },
    { name: "少一個字元的鄰近字串不得模糊命中", q: "CANARYTITLEZX", match: false },
    { name: "**不做標點移除**：插入連字號後不得命中", q: "CANARY-TITLEZZ", match: false },
    { name: "不同欄位的 canary 不得互相命中", q: "CANARYENDPOINTZZ", match: false },
  ];

  for (const c of CASES) {
    it(`${c.name} → ${c.match ? "命中" : "不命中"}`, () => {
      const got = ids(searchInScope(DEFAULT_SCOPE, c.q));
      if (c.match) expect(got).toEqual([canaryTrial.id]);
      else expect(got).not.toContain(canaryTrial.id);
    });
  }

  it("空查詢與純空白查詢**不執行搜尋**（回瀏覽狀態，不是命中全部）", () => {
    expect(parseQuery("")).toEqual([]);
    expect(parseQuery("   　 ")).toEqual([]);
    expect(searchInScope(DEFAULT_SCOPE, "").length).toBe(trials.length);
  });

  it("**identity 與 search 正規化分開**：identity 不合併，但 search 命中兩者", () => {
    // fixture 的 `MK-3475-158` 與 `MK3475-158` 是**兩個** Trial（identity 不折疊連字號）
    const withHyphen = trials.filter((t) => t.protocolRaw.includes("MK-3475-158"));
    const without = trials.filter((t) => t.protocolRaw.includes("MK3475-158"));
    expect(withHyphen).toHaveLength(1);
    expect(without).toHaveLength(1);
    expect(withHyphen[0]!.id).not.toBe(without[0]!.id);

    // 而 search 以 substring 比對：`3475-158` 同時命中兩者
    const hit = ids(searchInScope(DEFAULT_SCOPE, "3475-158"));
    expect(hit).toContain(withHyphen[0]!.id);
    expect(hit).toContain(without[0]!.id);
  });

  it("`searchNormalize` 本身不移除標點（policy 的單元證明）", () => {
    expect(searchNormalize("MK-3475")).toBe("mk-3475");
    expect(searchNormalize("ＭＫ－３４７５")).toBe("mk-3475");
    expect(searchNormalize("  a   b  ")).toBe("a b");
  });

  it("中文無空白字串以 substring 命中（不依賴斷詞）", () => {
    const target = trials.find((t) =>
      t.searchShortLatest.some((e) => e.f.some((v) => v.includes("非小細胞肺癌"))),
    )!;
    expect(ids(searchInScope(DEFAULT_SCOPE, "細胞肺"))).toContain(target.id);
  });
});

describe("D3：多詞語意的完整結果集合", () => {
  it("兩詞同欄（同一 record 的同一欄）→ 命中", () => {
    expect(ids(searchInScope(DEFAULT_SCOPE, "CANARY TITLEZZ"))).toContain(canaryTrial.id);
  });

  it("兩詞跨欄（同一 record 的不同欄）→ 命中，且結果集**精確相等**", () => {
    const q = `${SHORT_CANARY.臨床試驗申請者} ${SHORT_CANARY.TFDA收文號}`;
    expect(ids(searchInScope(DEFAULT_SCOPE, q))).toEqual([canaryTrial.id]);
  });

  it("只命中其中一詞 → **必排除**", () => {
    const q = `${SHORT_CANARY.臨床試驗計畫中文名稱} CANARYNOTPRESENTZZ`;
    expect(ids(searchInScope(DEFAULT_SCOPE, q))).toEqual([]);
  });

  it("**兩詞分別命中同一 Trial 的不同 SourceRecord → 必排除**（record 層 AND）", () => {
    // 掃全部多 record 的 Trial，找出「兩筆各自獨有一個短欄值」的那一個。
    // 只看第一個多 record 的 Trial 會落在長文字衝突的案例上——它的短欄逐字相同，
    // 挑不出兩個詞，這條就會退化成「沒有資料所以沒測」。
    let target: { trial: (typeof trials)[number]; a: string; b: string } | null = null;
    for (const t of trials) {
      const entries = t.searchShortLatest;
      if (entries.length < 2) continue;
      const a = entries[0]!.f.find((v) => v.trim() !== "" && !entries[1]!.f.includes(v));
      const b = entries[1]!.f.find((v) => v.trim() !== "" && !entries[0]!.f.includes(v));
      if (a !== undefined && b !== undefined) {
        target = { trial: t, a, b };
        break;
      }
    }

    // fixture 沒有這種組合時明確失敗，不靜默跳過——跳過等於這條沒測
    expect(target, "fixture 缺「同 Trial 不同 record 各含一詞」的案例").not.toBeNull();
    const got = ids(searchInScope(DEFAULT_SCOPE, `${target!.a} ${target!.b}`));
    expect(got).not.toContain(target!.trial.id);
  });

  it("跨 record 的 AND 在 `history=all` 同樣不成立", () => {
    const q = `${SHORT_CANARY.臨床試驗計畫中文名稱} CANARYINCLUSIONZZ`;
    for (const scope of SCOPES) expect(ids(searchInScope(scope, q))).toEqual([]);
  });
});

describe("D6：每一個可能衝突的欄位各有 latestAmbiguous oracle", () => {
  /** `scripts/build_web_fixture.py` 的 `CONFLICT_PAIRS` ＋ a_core 既有的衝突欄位。 */
  const EXPECT_CONFLICT: Record<string, string> = {
    本臨床試驗規模: "CONFLICT-01",
    臨床試驗申請者: "CONFLICT-02",
    試驗預計執行期間起: "CONFLICT-03",
    試驗預計執行期間迄: "CONFLICT-04",
    排除條件: "CONFLICT-05",
    試驗目的: "CONFLICT-06",
    主要評估指標: "CONFLICT-07",
  };

  const byProtocolRaw = (p: string) => trials.find((t) => t.protocolRaw.includes(p))!;

  for (const [field, protocol] of Object.entries(EXPECT_CONFLICT)) {
    it(`${field} 衝突 → latestAmbiguous 且 conflictFields **精確為** [${field}]`, () => {
      const t = byProtocolRaw(protocol);
      expect(t.latestAmbiguous).toBe(true);
      expect(t.conflictFields).toEqual([field]);
      expect(t.latestCohortCount).toBe(2);
    });
  }

  it("**可篩選的衝突欄位歸入「不一致」，且不出現在任一具體值的結果中**", () => {
    const cases: { dim: (typeof DIMENSIONS)[number]; protocol: string }[] = [
      { dim: "scale", protocol: "CONFLICT-01" },
      { dim: "applicant", protocol: "CONFLICT-02" },
      { dim: "period", protocol: "CONFLICT-03" },
    ];
    for (const c of cases) {
      const t = byProtocolRaw(c.protocol);
      if (c.dim === "period") continue; // period 是區間輸入，不走 bucket 選單
      const filters = { ...emptyState().filters, [c.dim]: [CONFLICTED] };
      const inConflicted = ids(applyFilters(browseAll(trials), filters));
      expect(inConflicted, `${c.dim} 的不一致分組`).toContain(t.id);

      // 任何具體值的篩選都不得撈到它
      const values = index.trials
        .flatMap((x) => Object.values(x.displayFields).map((v) => v.raw))
        .filter((v) => v !== "" && v !== UNPROVIDED && v !== CONFLICTED);
      for (const v of new Set(values)) {
        const got = ids(applyFilters(browseAll(trials), { ...emptyState().filters, [c.dim]: [v] }));
        expect(got, `${c.dim}=${v} 撈到了衝突 trial`).not.toContain(t.id);
      }
    }
  });

  it("**長文字欄位不可篩選，但照樣使 `latestAmbiguous` 成立**", () => {
    const longFields = ["納入條件", "排除條件", "試驗目的", "主要評估指標"];
    for (const field of longFields) {
      const t = trials.find((x) => x.conflictFields.includes(field));
      expect(t, `fixture 缺 ${field} 的衝突案例`).toBeDefined();
      expect(t!.latestAmbiguous, `${field} 衝突卻不 ambiguous＝漏報`).toBe(true);
      // 長文字不在 displayFields（F3），所以「候選值不出現在卡片」是恆真的——
      // 真正守得住的是上面那條 latestAmbiguous
      expect(Object.keys(t!.displayFields)).not.toContain(field);
    }
  });

  it("**`資料更新時間` 結構上不可能衝突**：cohort 的定義就是同一個可採計日期", () => {
    for (const t of trials) expect(t.conflictFields).not.toContain("資料更新時間");
  });
});

describe("D8：`enroll` 的區間重疊", () => {
  const rangeTrial = trials.find(
    (t) => t.displayFields.台灣預計受試者人數?.raw === "20-40",
  )!;

  it("fixture 確有一筆 `20-40`", () => {
    expect(rangeTrial).toBeDefined();
    expect(rangeTrial.displayFields.台灣預計受試者人數!.flags).toContain("numericRange");
  });

  it("**同時**出現在 `11-30` 與 `31-100` 兩個 bucket", () => {
    for (const bucket of ["11-30", "31-100"]) {
      const got = ids(applyFilters(browseAll(trials), { ...emptyState().filters, enroll: [bucket] }));
      expect(got, `bucket ${bucket}`).toContain(rangeTrial.id);
    }
  });

  it("卡片顯示 **raw `20-40`**，不折成單一數字", () => {
    const card = renderCard({ trial: rangeTrial, hits: [] }, { detailHref: (id) => `?trial=${id}` });
    const text = card.textContent ?? "";
    expect(text).toContain("20-40");
    // 折成端點之一的實作會在卡上留下一個孤零零的數字
    expect(text).not.toMatch(/台灣預計受試者人數[^0-9]*20(?!-)/);
  });

  it("`numericUnparsed`／`numericImplausible` 歸「未提供」，**不進任何數值 bucket**", () => {
    const buckets = ["0", "1-10", "11-30", "31-100", "101-500", "501-"];
    for (const t of trials) {
      const fv = t.displayFields.台灣預計受試者人數;
      if (fv === undefined) continue;
      const flags = fv.flags;
      if (!flags.includes("numericUnparsed") && !flags.includes("numericImplausible")) continue;

      for (const b of buckets) {
        const got = ids(applyFilters(browseAll(trials), { ...emptyState().filters, enroll: [b] }));
        expect(got, `${t.id}（${fv.raw}）不該進 bucket ${b}`).not.toContain(t.id);
      }
      const unprovided = ids(
        applyFilters(browseAll(trials), { ...emptyState().filters, enroll: [UNPROVIDED] }),
      );
      expect(unprovided).toContain(t.id);
    }
  });
});
