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
import { lookupProtocol } from "./lib/protocol.js";
import { filesFor, filesToLoad, scopeKey, type Scope, type SearchFileKey } from "./lib/scope.js";
import type { Manifest, SearchFile, Shard, Stats, TrialsIndex } from "./lib/types.js";
import { buildUrl, isBrowsing, parseUrl, type AppState } from "./lib/urlState.js";
import { renderCard } from "./ui/card.js";
import { renderDetail } from "./ui/detail.js";
import { renderDisclaimer } from "./ui/disclaimer.js";
import { el, mount } from "./ui/dom.js";
import { renderFilters } from "./ui/filters.js";
import { renderMeta } from "./ui/meta.js";
import { renderScopeBar, renderZeroResultHint } from "./ui/scopeBar.js";
import { renderStats } from "./ui/stats.js";
import { LABEL } from "./ui/text.js";

const DATA_BASE = "data";

/**
 * 一次渲染的結果卡數上限。
 *
 * 2026-09-21 F4 實測：渲染時間隨**卡片數**線性成長（約 0.15 ms／張），與 scope 或
 * 資料量無關——「臨床」在 all+all 命中 2,616 個試驗、407 ms，超過 300 ms 門檻。
 * 搜尋本身不是瓶頸（乳癌 273 張只要 127 ms）。
 *
 * **總數照實顯示**，分批只影響一次畫多少張。把總數也截成 50 會讓使用者以為
 * 只有 50 個試驗符合——那是誤導，比慢更嚴重。
 *
 * 不進 URL state：§7.4 的參數表是經五輪覆審定案的契約，為一個純顯示層的
 * 批次大小去動它不划算；重新整理回到第一批是可接受的代價。
 */
const PAGE_SIZE = 50;
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
  private shown = PAGE_SIZE;
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

  /**
   * §8.5：載入失敗時**真的退回**上一個 scope——state、URL、結果集三者一起。
   *
   * 舊版丟棄 `ensureScopeFiles` 的回傳值，於是 `state.scope` 停在新 scope、
   * URL 停在新 scope，而畫面上那句「已退回原本的搜尋範圍」是寫死的字串。
   * 使用者看到的是一個宣稱已退回、實際沒退回、且可能以部分索引產生的結果集。
   */
  private async onNavigate(prev: Scope | null = null): Promise<void> {
    const ok = await this.ensureScopeFiles(this.state.scope);
    if (!ok && prev !== null && scopeKey(prev) !== scopeKey(this.state.scope)) {
      this.state = { ...this.state, scope: prev };
      // `replaceState` 而非 `pushState`：退回不是一次新的導覽，
      // 否則上一頁會把使用者送回那個載不起來的 scope。
      history.replaceState(null, "", buildUrl(this.state) || location.pathname);
    }
    this.render();
  }

  /**
   * §8.5：載入失敗則**退回上一個 scope 並說明**，不得靜默維持舊結果集。
   *
   * **成功載入且通過版本驗證的檔案留在 cache**（使用者定案 2026-09-22）：
   * 下次再切到需要它的 scope 就不必重載。留著是安全的——`results()` 只讀
   * `filesFor(目前 scope)`，cache 裡多出來的檔案不會參與搜尋，
   * 因此不影響畫面、scope、URL 或結果集。
   */
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
    // 條件一變就回到第一批：沿用舊的 shown 會讓新結果一次畫出上百張
    this.shown = PAGE_SIZE;
    const prev = this.state.scope;
    this.state = next;
    history.pushState(null, "", buildUrl(next) || location.pathname);
    void this.onNavigate(prev);
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
        // **只讀目前 scope 所需的檔案**，不疊代整個 cache。
        // 疊代 cache 會讓「曾經載入過但已不屬於目前 scope」的檔案繼續參與搜尋——
        // 退回 scope 之後結果集卻沒退回，那是最難察覺的一種漏報／多報。
        for (const key of filesFor(this.state.scope)) {
          const file = this.searchFiles.get(key);
          // 缺檔代表 scope 與 cache 不一致（正常流程下不會發生）。**不靜默略過**：
          // 少一個檔就是少一批 record，使用者看到的是「查無資料」。
          if (file === undefined) throw new Error(`scope 需要 ${key} 但未載入`);
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

  /**
   * §7.4／E8：`?protocol=` 以 identity 正規化後比對並**導向 canonical**。
   *
   * 舊版只有 parse／build——URL 收下這個參數、原樣保留，然後**什麼都不做**。
   * 那比完全不支援更糟：使用者以為查了，實際看到的是未篩選的瀏覽頁。
   *
   * 命中 → `replaceState` 換成 `?trial=<id>`（canonical 形式，不留 `protocol`）。
   * 不接受或查無 → 顯示對應訊息，**兩者分開**，並保留原參數不改寫，
   * 使用者才看得出剛才那個網址發生了什麼事。
   */
  private resolveProtocol(): void {
    const raw = this.state.protocol;
    if (raw === null) return;

    const result = lookupProtocol(this.index.trials, raw);
    if (result.kind === "match") {
      this.state = { ...this.state, protocol: null, trial: result.trialId };
      history.replaceState(null, "", buildUrl(this.state) || location.pathname);
      return;
    }
    this.errors.set(
      "protocol",
      result.kind === "rejected" ? LABEL.protocolRejected(raw) : LABEL.protocolNotFound(raw),
    );
    // 值不被接受時**不得沿用它去搜尋**，把它清掉但保留 URL 原樣
    this.state = { ...this.state, protocol: null };
  }

  private render(): void {
    this.validateRanges();
    this.resolveProtocol();
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

    const visible = hits.slice(0, this.shown);
    const list = el(
      "div",
      { class: "results", id: "results" },
      visible.map((h) =>
        renderCard(h, { detailHref: (id) => buildUrl({ ...this.state, trial: id, q: this.state.q }) }),
      ),
    );

    let more: HTMLElement | null = null;
    if (hits.length > visible.length) {
      const remaining = hits.length - visible.length;
      const button = el("button", {
        type: "button",
        class: "more-btn",
        text: `載入更多（再 ${Math.min(PAGE_SIZE, remaining)} 筆，尚有 ${remaining} 筆）`,
      });
      button.addEventListener("click", () => {
        this.shown += PAGE_SIZE;
        this.renderSearchPage();
        // 焦點不得因為重畫而遺失（G3）
        document.querySelector<HTMLElement>(".more-btn")?.focus();
      });
      more = el("div", { class: "more" }, [
        el("p", {
          class: "more__status",
          // **總數照實說**，並明示目前只畫了幾張
          text: `目前顯示 ${visible.length} 筆，共 ${hits.length} 筆符合`,
        }),
        button,
      ]);
    }

    mount(
      this.root,
      el("div", { class: "wrap" }, [
        el("a", { class: "skip-link", href: "#results", text: "跳至搜尋結果" }),
        el("header", { class: "site-header" }, [
          el("h1", { text: "台灣藥品臨床試驗檢索" }),
          // 總數只由 `renderMeta` 呈現（E3）。這裡再寫一次等於同一個事實有兩個
          // 不受同一個 oracle 約束的 surface，兩者漂移時使用者看得到、測試看不到。
          el("p", { class: "lede", text: "資料來源：TFDA 開放資料 205（藥品臨床試驗審查紀錄）。" }),
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
            more,
            renderStats(this.stats),
            renderMeta(this.manifest),
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
        el("main", { id: "detail" }, [
          renderDetail(trial, shard, { nearDuplicates: near }),
          renderMeta(this.manifest),
        ]),
        renderDisclaimer(),
      ]),
    );
  }
}

export { DIMENSIONS };
