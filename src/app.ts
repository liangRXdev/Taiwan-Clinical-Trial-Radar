/**
 * 應用組裝：資料載入、路由、渲染。
 *
 * **fail-closed 延續到前端**（§9.2.2）：每個非 manifest 檔案的 `datasetVersion` 須等於
 * manifest 的值，不符即停止並顯示「資料版本不一致，請重新載入」——**不得混用**。
 * 瀏覽器或 CDN 跨版本混用固定 URL 的檔案是真實情境，而混用的後果是顯示一個
 * 由兩個版本拼出來的答案，那正是本專案最怕的誤導。
 */

import { applyFilters, DIMENSIONS, parseDateRange, type Dimension } from "./lib/filter.js";
import {
  browseAll,
  mergeHits,
  parseQuery,
  searchEntries,
  searchLatestShort,
  type TrialHit,
} from "./lib/search.js";
import { filesToLoad, type Scope, type SearchFileKey } from "./lib/scope.js";
import type { Manifest, SearchFile, Shard, Stats, TrialsIndex } from "./lib/types.js";
import { buildUrl, isBrowsing, parseUrl, type AppState } from "./lib/urlState.js";
import { renderCard } from "./ui/card.js";
import { renderDetail } from "./ui/detail.js";
import { renderDisclaimer } from "./ui/disclaimer.js";
import { el, mount } from "./ui/dom.js";
import { renderFilters } from "./ui/filters.js";
import { renderScopeBar, renderZeroResultHint } from "./ui/scopeBar.js";
import { renderStats } from "./ui/stats.js";
import { LABEL } from "./ui/text.js";

const DATA_BASE = "data";
const VERSION_MISMATCH = "資料版本不一致，請重新載入";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}/${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`載入失敗：${path}（HTTP ${res.status}）`);
  return (await res.json()) as T;
}

/** §9.2.2：**一次資料載入只能解析同一個 manifest 版本。** */
function assertVersion(obj: { datasetVersion: string }, manifest: Manifest, path: string): void {
  if (obj.datasetVersion !== manifest.datasetVersion) {
    throw new Error(`${VERSION_MISMATCH}（${path}）`);
  }
}

export class App {
  private manifest!: Manifest;
  private index!: TrialsIndex;
  private stats!: Stats;
  private state: AppState = parseUrl(location.search).state;
  private errors = new Map<string, string>();
  private readonly searchFiles = new Map<SearchFileKey, SearchFile>();
  private readonly shards = new Map<string, Shard>();
  private scopeError: string | null = null;

  constructor(private readonly root: HTMLElement) {}

  async start(): Promise<void> {
    try {
      this.manifest = await fetchJson<Manifest>("manifest.json");
      this.index = await fetchJson<TrialsIndex>(this.manifest.files.trialsIndex.path);
      this.stats = await fetchJson<Stats>(this.manifest.files.stats.path);
      assertVersion(this.index, this.manifest, "trials-index");
      assertVersion(this.stats, this.manifest, "stats");
    } catch (e) {
      this.fatal(e);
      return;
    }
    // 先載入目前 scope 需要的檔，否則分享進來的 ?history=all 連結會先渲染一次窄結果
    await this.ensureScopeFiles(this.state.scope);
    this.render();
    addEventListener("popstate", () => {
      this.state = parseUrl(location.search).state;
      void this.onNavigate();
    });
  }

  private fatal(e: unknown): void {
    const msg = e instanceof Error ? e.message : String(e);
    mount(
      this.root,
      el("div", { class: "wrap" }, [
        el("p", { class: "alert alert--error", text: `⚠ ${msg}` }),
        renderDisclaimer(),
      ]),
    );
  }

  private async onNavigate(): Promise<void> {
    await this.ensureScopeFiles(this.state.scope);
    this.render();
  }

  /** §8.5：載入失敗則**退回上一個 scope 並說明**，不得靜默維持舊結果集。 */
  private async ensureScopeFiles(scope: Scope): Promise<boolean> {
    const need = filesToLoad(scope, new Set(this.searchFiles.keys()));
    for (const key of need) {
      try {
        const file = await fetchJson<SearchFile>(this.manifest.files[key].path);
        assertVersion(file, this.manifest, key);
        this.searchFiles.set(key, file);
      } catch (e) {
        this.scopeError = e instanceof Error ? e.message : String(e);
        return false;
      }
    }
    this.scopeError = null;
    return true;
  }

  private async shardOf(name: string): Promise<Shard> {
    const cached = this.shards.get(name);
    if (cached) return cached;
    const meta = this.manifest.files.recordShards[name];
    if (meta === undefined) throw new Error(`manifest 無此 shard：${name}`);
    const s = await fetchJson<Shard>(meta.path);
    assertVersion(s, this.manifest, `shard ${name}`);
    this.shards.set(name, s);
    return s;
  }

  private navigate(next: AppState): void {
    this.state = next;
    history.pushState(null, "", buildUrl(next) || location.pathname);
    void this.onNavigate();
  }

  private results(): TrialHit[] {
    const terms = parseQuery(this.state.q);
    const trials = this.index.trials;

    // §8.2：**空查詢不執行搜尋**，顯示瀏覽狀態——不是「命中全部」
    let hits: TrialHit[];
    if (terms.length === 0) {
      hits = browseAll(trials);
    } else {
      const groups: TrialHit[][] = [];
      const { fields, history } = this.state.scope;
      if (fields === "short" && history === "latest") {
        groups.push(searchLatestShort(trials, terms));
      } else {
        for (const [, file] of this.searchFiles) {
          groups.push(searchEntries(trials, file.records, terms));
        }
        if (history === "latest" && fields === "all") {
          groups.push(searchLatestShort(trials, terms));
        }
      }
      hits = mergeHits(groups);
    }
    return applyFilters(hits, this.state.filters);
  }

  private validateRanges(): void {
    this.errors.clear();
    for (const dim of ["period", "updated"] as const) {
      const v = this.state.filters[dim];
      if (v !== null && parseDateRange(v) === null) {
        this.errors.set(dim, `${dim} 須為 YYYY-MM-DD..YYYY-MM-DD 且起不晚於迄`);
      }
    }
  }

  private render(): void {
    this.validateRanges();
    if (this.state.trial !== null) {
      void this.renderDetailPage(this.state.trial);
      return;
    }
    this.renderSearchPage();
  }

  private scopeBarOptions() {
    return {
      manifest: this.manifest,
      scope: this.state.scope,
      loaded: new Set(this.searchFiles.keys()),
      loadError: this.scopeError,
      onChange: (next: Scope) => this.navigate({ ...this.state, scope: next }),
    };
  }

  private renderSearchPage(): void {
    const hits = this.results();
    const browsing = isBrowsing(this.state);

    const input = el("input", {
      type: "search",
      id: "q",
      value: this.state.q,
      placeholder: "輸入計畫書編號、試驗名稱、申請者或適應症",
      "aria-label": "搜尋",
    });
    input.addEventListener("change", () => this.navigate({ ...this.state, q: input.value }));

    const list = el(
      "div",
      { class: "results", id: "results" },
      hits.map((h) =>
        renderCard(h, { detailHref: (id) => buildUrl({ ...this.state, trial: id, q: this.state.q }) }),
      ),
    );

    mount(
      this.root,
      el("div", { class: "wrap" }, [
        el("a", { class: "skip-link", href: "#results", text: "跳至搜尋結果" }),
        el("header", { class: "site-header" }, [
          el("h1", { text: "台灣藥品臨床試驗檢索" }),
          el("p", {
            class: "lede",
            text: `資料來源：TFDA 開放資料 205。共 ${this.manifest.trialCount} 個試驗、${this.manifest.recordCount} 筆審查紀錄。`,
          }),
        ]),
        renderDisclaimer(),
        el("div", { class: "searchbar" }, [input]),
        el("div", { class: "layout" }, [
          el("aside", {}, [
            renderFilters({
              stats: this.stats,
              state: this.state.filters,
              errors: this.errors,
              callbacks: {
                onToggle: (dim: Dimension, value: string, checked: boolean) => {
                  // `period`／`updated` 是單值區間，不走 checkbox；收窄型別而不是用 cast，
                  // 讓「哪些維度是多值」這件事由型別系統守住而不是註解。
                  if (dim === "period" || dim === "updated") return;
                  const filters = structuredClone(this.state.filters);
                  const arr = filters[dim];
                  filters[dim] = checked ? [...arr, value] : arr.filter((v) => v !== value);
                  this.navigate({ ...this.state, filters });
                },
                onRange: (dim, value) => {
                  const filters = structuredClone(this.state.filters);
                  filters[dim] = value === "" ? null : value;
                  this.navigate({ ...this.state, filters });
                },
              },
            }),
          ]),
          el("main", {}, [
            renderScopeBar(this.scopeBarOptions()),
            ...[...this.errors.values()].map((m) => el("p", { class: "alert alert--error", text: `⚠ ${m}` })),
            el("p", {
              class: "result-count",
              text: browsing
                ? `瀏覽全部 ${hits.length} 個試驗（依資料更新時間排序）`
                : `符合條件：${hits.length} 個試驗`,
            }),
            hits.length === 0 ? renderZeroResultHint(this.scopeBarOptions()) : null,
            list,
            renderStats(this.stats),
          ]),
        ]),
        renderDisclaimer(),
      ]),
    );
  }

  private async renderDetailPage(trialId: string): Promise<void> {
    const trial = this.index.trials.find((t) => t.id === trialId);
    if (trial === undefined) {
      this.fatal(new Error(`找不到試驗：${trialId}`));
      return;
    }
    let shard: Shard;
    try {
      shard = await this.shardOf(trial.shard);
    } catch (e) {
      this.fatal(e);
      return;
    }

    const near = this.index.trials
      .filter((t) => t.nearDuplicateGroup !== null && t.nearDuplicateGroup === trial.nearDuplicateGroup && t.id !== trial.id)
      .map((t) => ({
        id: t.id,
        label: t.protocolRaw.join("、") || LABEL.noProtocol,
        href: buildUrl({ ...this.state, trial: t.id }),
      }));

    const back = el("a", { href: buildUrl({ ...this.state, trial: null }), text: "← 回搜尋結果" });

    mount(
      this.root,
      el("div", { class: "wrap" }, [
        el("a", { class: "skip-link", href: "#detail", text: "跳至試驗內容" }),
        back,
        renderDisclaimer(),
        el("main", { id: "detail" }, [renderDetail(trial, shard, { nearDuplicates: near })]),
        renderDisclaimer(),
      ]),
    );
  }
}

export { DIMENSIONS };
