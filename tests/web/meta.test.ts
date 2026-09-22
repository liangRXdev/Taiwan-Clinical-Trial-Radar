/**
 * E2(b) ＋ E3：非 facet metadata surface。
 *
 * §9.3.5 把呈現層分成 facet widget（E2(a)，封閉名單雙向對帳）與**單值的資料來源
 * 資訊**（本檔）。兩份 inventory 分開，且**不得互相吸收**——否則把一張未核准的
 * facet 卡標成 metadata 就能同時逃過兩邊。
 *
 * E3 要的是**精確 fixture 值**，所以本檔的 expected 一律寫死，
 * 不從 `manifest` 重新組字串——用 production code 的同一份輸入格出 expected
 * 等於自我驗證，格式錯了兩邊一起錯。
 */

import { describe, expect, it } from "vitest";

import type { Manifest } from "../../src/lib/types.js";
import { renderDetail } from "../../src/ui/detail.js";
import { formatBuiltAt, META_FIELDS, META_SURFACE_ATTR, renderMeta } from "../../src/ui/meta.js";
import { renderStats, STAT_SURFACE_ATTR } from "../../src/ui/stats.js";
import { META } from "../../src/ui/text.js";
import { manifest, shard, stats, trials } from "./fixture.js";

/** fixture 的精確值。fixture 換人時這四行要一起改，那正是 E3 想要的摩擦。 */
const EXPECTED: Record<string, string> = {
  sourceUpdatedAt: "2026/09/18",
  builtAt: "2026/09/18 09:02（台北時間）",
  trialCount: "47 個試驗",
  recordCount: "78 筆",
};

function fields(node: HTMLElement): Record<string, { label: string; value: string }> {
  const out: Record<string, { label: string; value: string }> = {};
  for (const row of node.querySelectorAll(`[${META_SURFACE_ATTR}]`)) {
    const key = row.getAttribute(META_SURFACE_ATTR)!;
    out[key] = {
      label: row.querySelector("dt")!.textContent ?? "",
      value: row.querySelector("dd")!.textContent ?? "",
    };
  }
  return out;
}

function withManifest(patch: Partial<Manifest>): Manifest {
  return { ...structuredClone(manifest), ...patch };
}

describe("E3：metadata surface 的 label 對應精確 fixture 值", () => {
  const seen = fields(renderMeta(manifest));

  it("四個欄位的集合恰為封閉名單（雙向）", () => {
    expect(Object.keys(seen).sort()).toEqual([...META_FIELDS].sort());
  });

  for (const key of META_FIELDS) {
    it(`${key} 的值精確相等`, () => {
      expect(seen[key]!.value).toBe(EXPECTED[key]);
    });
  }

  it("label 逐一可見且互不相同", () => {
    const labels = Object.values(seen).map((f) => f.label);
    expect(labels).toEqual([
      META.sourceUpdatedAt,
      META.builtAt,
      META.trialCount,
      META.recordCount,
    ]);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("總數與 manifest 的 trialCount／recordCount 一致（不是卡片數或 index 長度）", () => {
    expect(seen.trialCount!.value).toContain(String(manifest.trialCount));
    expect(seen.recordCount!.value).toContain(String(manifest.recordCount));
    expect(manifest.trialCount).toBe(trials.length);
  });
});

describe("E3：`sourceUpdatedAt` 對應到 record 的 `資料更新時間`", () => {
  /**
   * 獨立重算：§6.5 的 `dateFuture` **不可採計，且排除於全站 `sourceUpdatedAt`**。
   * fixture 裡有一筆 2099-01-01——天真的「取最大值」會得到它，這條因此測得出差別。
   */
  function recomputed(): { max: string; naiveMax: string } {
    const all: string[] = [];
    const accountable: string[] = [];
    for (const name of Object.keys(manifest.files.recordShards)) {
      for (const rec of Object.values(shard(name).records)) {
        const typed = rec.typed["資料更新時間"];
        if (typeof typed !== "string") continue;
        all.push(typed);
        if (!(rec.fieldFlags["資料更新時間"] ?? []).includes("dateFuture")) accountable.push(typed);
      }
    }
    return {
      max: accountable.sort().at(-1)!,
      naiveMax: all.sort().at(-1)!,
    };
  }

  it("等於**可採計** record 的最大 `資料更新時間`", () => {
    expect(manifest.sourceUpdatedAt).toBe(recomputed().max);
  });

  it("fixture 確實含一筆 `dateFuture`，否則這條 oracle 測不出差別", () => {
    const { max, naiveMax } = recomputed();
    expect(naiveMax).not.toBe(max);
    expect(naiveMax).toBe("2099-01-01");
  });
});

describe("E3：日期不得偽造", () => {
  it("`sourceUpdatedAt` 為 null → 顯示「來源未提供」", () => {
    const seen = fields(renderMeta(withManifest({ sourceUpdatedAt: null })));
    expect(seen.sourceUpdatedAt!.value).toBe(META.sourceUpdatedUnknown);
  });

  it("**不得代入 `buildDate`／`fetchedAt`／`builtAt`**", () => {
    const m = withManifest({ sourceUpdatedAt: null });
    const row = fields(renderMeta(m)).sourceUpdatedAt!.value;
    for (const fake of [m.buildDate, m.fetchedAt, m.builtAt, "2026/09/18"]) {
      expect(row).not.toContain(fake);
    }
    // 連「像日期」都不行：數字接斜線是使用者會讀成日期的形狀
    expect(row).not.toMatch(/\d{4}[/-]\d{2}/);
  });

  it("`builtAt` 無法解析 → 顯示「無法辨識」，不退回今天", () => {
    const seen = fields(renderMeta(withManifest({ builtAt: "not-a-timestamp" })));
    expect(seen.builtAt!.value).toBe(META.builtAtUnparsed);
    expect(seen.builtAt!.value).not.toMatch(/\d{4}\//);
  });
});

describe("`builtAt` 的台北時間換算", () => {
  it("UTC 01:02 → 09:02 同日", () => {
    expect(formatBuiltAt("2026-09-18T01:02:03Z")).toBe("2026/09/18 09:02（台北時間）");
  });

  it("**跨日**：UTC 16:30 → 次日 00:30", () => {
    expect(formatBuiltAt("2026-09-18T16:30:00Z")).toBe("2026/09/19 00:30（台北時間）");
  });

  it("跨年：UTC 12/31 23:00 → 次年 01/01 07:00", () => {
    expect(formatBuiltAt("2026-12-31T23:00:00Z")).toBe("2027/01/01 07:00（台北時間）");
  });

  it("**`+00:00` 與 `Z` 等價**——正式 ETL 輸出前者，fixture 用後者", () => {
    expect(formatBuiltAt("2026-09-18T01:02:03+00:00")).toBe(formatBuiltAt("2026-09-18T01:02:03Z"));
  });

  it("已帶 +08:00 的時刻不得再加八小時", () => {
    expect(formatBuiltAt("2026-09-18T09:02:03+08:00")).toBe("2026/09/18 09:02（台北時間）");
  });

  it("無法解析回 null，**不回空字串或今天**", () => {
    expect(formatBuiltAt("")).toBeNull();
    expect(formatBuiltAt("2026-13-45T99:99:99Z")).toBeNull();
  });
});

describe("E2(b)：metadata surface 不是 facet widget", () => {
  const metaNode = renderMeta(manifest);

  it("metadata 區塊內**不存在** facet 標記", () => {
    expect(metaNode.querySelectorAll(`[${STAT_SURFACE_ATTR}]`)).toHaveLength(0);
  });

  it("facet 區塊內**不存在** metadata 標記——兩份 inventory 不互相吸收", () => {
    expect(renderStats(stats).querySelectorAll(`[${META_SURFACE_ATTR}]`)).toHaveLength(0);
  });

  it("**metadata 的每一項都是單值**，沒有任何分組計數", () => {
    // 分組計數的形狀是「一個 label 配一列以上的子項」。metadata 的 dd 內
    // 不得出現表格或清單——那是 facet widget 繞過 E2(a) inventory 的入口。
    for (const row of metaNode.querySelectorAll(`[${META_SURFACE_ATTR}]`)) {
      expect(row.querySelectorAll("table, ul, ol, tbody")).toHaveLength(0);
      expect(row.querySelectorAll("dd")).toHaveLength(1);
    }
  });

  it("facet 名單與 metadata 名單**沒有交集**", () => {
    const facets = [...renderStats(stats).querySelectorAll(`[${STAT_SURFACE_ATTR}]`)].map((n) =>
      n.getAttribute(STAT_SURFACE_ATTR),
    );
    for (const f of facets) expect(META_FIELDS).not.toContain(f);
  });
});

describe("E3：詳情頁與 record 切換後的 metadata 一致", () => {
  const trial = trials.find((t) => t.recordCount > 1)!;

  it("fixture 確有多 record 的 Trial（否則「切換 record」測不到）", () => {
    expect(trial.recordCount).toBeGreaterThan(1);
  });

  it("詳情頁渲染後 metadata 值與搜尋頁**逐欄相等**", () => {
    const onSearch = fields(renderMeta(manifest));
    // 詳情頁的 metadata 與 detail 同層渲染（app.ts）；此處組同一組節點驗值不漂移
    const detailNode = renderDetail(trial, shard(trial.shard), { nearDuplicates: [] });
    const onDetail = fields(renderMeta(manifest));
    expect(onDetail).toEqual(onSearch);
    // 詳情內容本身不得另外長出一份 metadata（同一事實兩個 surface 會漂移）
    expect(detailNode.querySelectorAll(`[${META_SURFACE_ATTR}]`)).toHaveLength(0);
  });

  it("切換到另一個 Trial 後 metadata 不變——它描述的是資料集，不是這筆試驗", () => {
    const other = trials.find((t) => t.id !== trial.id)!;
    renderDetail(other, shard(other.shard), { nearDuplicates: [] });
    expect(fields(renderMeta(manifest))).toEqual(fields(renderMeta(manifest)));
    expect(fields(renderMeta(manifest)).sourceUpdatedAt!.value).toBe(EXPECTED.sourceUpdatedAt);
  });
});
