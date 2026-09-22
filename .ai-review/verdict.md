# 覆核判定（M4 規格符合度稽核）

- 日期：2026-09-22
- Codex 原始輸出：`.ai-review/codex-review.md`（第一輪，未完成）
- 覆核方式：**每一項都回去讀該檔案該行驗證**，不憑 Codex 描述判斷

> **本檔尚未完整。** 第一輪 Codex 未輸出正式報告，只在過程中點名兩項實作問題，
> 兩項都經獨立覆核確認屬實，列於下表。它同時列出的驗收缺口清單
> （B1/B5/B7、C1–C3、D1/D7/D8、F1–F4、G1–G3、H1–H3）**尚未覆核，不得直接採信**——
> 第二輪（`.ai-review/codex-prompt-r2.md`）正在跑，結果到齊後補完本表。

---

## 判定總表

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| 1 | §7.2 命中日期標錯：非最新紀錄命中時顯示的是 Trial 的最新日期 | **High** | **接受** | `src/ui/card.ts:82` 在 `fromOlder === true` 的分支裡取 `trial.latestSourceDate` 格式化後填進 `LABEL.hitFromOlder`，而該常數的文字是「命中來自 ${date} 的審查紀錄」。`fromOlder` 的定義（`card.ts:75`）正是「命中不在最新 cohort 內」——所以這個分支**保證**顯示的日期不是命中那筆紀錄的日期。 |
| 2 | §8.5 scope 載入失敗沒有真的退回，且可能以部分索引產生結果 | **High** | **接受** | `src/app.ts:107-110` 的 `onNavigate` 呼叫 `await this.ensureScopeFiles(...)` 但**丟棄回傳值**。`ensureScopeFiles`（`app.ts:113-127`）失敗時只設 `scopeError` 並 `return false`，`this.state.scope` 仍是新的、`this.searchFiles` 保留失敗前已載入的檔案。接著 `render()` 走 `results()`，非預設 scope 會 `for (const [, file] of this.searchFiles)` 疊代**部分載入**的集合。 |
| 3 | 上述第 2 項的 e2e 測試是恆真斷言 | **Medium** | **接受** | `tests/e2e/scope-perf.spec.ts:111-125` 只斷言 `.scope .alert--error` 的文字含「已退回原本的搜尋範圍」，而那是 `src/ui/text.ts` 的 `SCOPE.loadFailed` **寫死字串**，只要錯誤分支有渲染就必然成立。測試從未檢查 `state.scope`、URL、或結果集是否真的退回。 |

統計：**接受 3／部分接受 0／拒絕 0**（第一輪範圍內）。

---

## 細節與建議修法

### 1. §7.2 命中日期（`src/ui/card.ts:81-87`）

```ts
if (fromOlder) {
  const date = formatDate(trial.latestSourceDate);   // ← Trial 的最新日期
  parts.push(chip("info", date === null ? LABEL.hitDateUnknown : LABEL.hitFromOlder(date)));
}
```

**為什麼是誤導而不只是 bug**：這個標籤存在的目的，就是告訴使用者「你搜到的字出現在一筆
**較舊**的紀錄裡」。它現在顯示的卻是該 Trial **最新**紀錄的日期——使用者會以為那句話
描述的是命中紀錄，而事實上那是另一筆紀錄的日期。比不顯示日期更糟。

同一段的註解寫著「**無可採計日期時不得偽造**」——防住了「塞一個假的 null 日期」，
卻沒防住「塞一個真實但屬於別筆紀錄的日期」。

**資料是有的**：§9.3.5 的搜尋索引 record 形狀是 `{r, t, d, f}`，`d` 就是該筆紀錄的
可採計日期。而 `fromOlder` 只可能在 `searchEntries`（讀那些檔）產生的命中上為真——
`searchShortLatest` 的命中依定義都在最新 cohort 內。**需要的日期恰好在需要它的路徑上。**

建議修法：

1. `Hit`（`src/lib/search.ts:43-48`）增加 `date: string | null`
2. `matchRecord`（同檔 `:51`）從 `entry.d` 填入；`trials-index` 內嵌的 `SearchEntry`
   沒有 `d`，那條路徑填 `null`（它永遠不會走到 `fromOlder`）
3. `card.ts` 改用**命中的日期**；一個 Trial 有多筆較舊命中且日期不同時，
   §7.2 的文字是單數——**這是規格沒有涵蓋的情形，要先決定**：列出全部日期、
   取最新的一筆較舊命中、或改成「命中來自較舊的審查紀錄（N 筆）」。
   **不要默默取一個**，那會重蹈同一個錯。
4. 測試要能抓到這個：造一個 Trial，其最新日期與較舊命中紀錄的日期**不同**，
   斷言卡片上出現的是後者。現行 D1／§7.2 的測試沒有這個案例
   （`tests/web/render.test.ts` 的「命中來自非最新 cohort → 標示來源日期」
   只驗了標籤有出現）。

### 2. §8.5 scope 退回（`src/app.ts:107-110`）

```ts
private async onNavigate(): Promise<void> {
  await this.ensureScopeFiles(this.state.scope);   // ← 回傳值被丟棄
  this.render();
}
```

三個後果，由輕到重：

1. **UI 說謊**：畫面顯示「已退回原本的搜尋範圍」，但 `state.scope` 是新的，
   `.scope__current` 與 scope 控制項都還指著新範圍。
2. **URL 與 state 不一致**：`navigate()`（`app.ts:140-146`）在載入**之前**就
   `history.pushState`，失敗後 URL 停在新 scope。重新整理會再試一次同一個失敗。
3. **可能以部分索引產生結果**（最嚴重）：`all`+`all` 需要三個檔，若第二個 404，
   第一個已進 `this.searchFiles`。`results()`（`app.ts:162-164`）疊代整個 map，
   於是使用者拿到「比預設多、比目標少」的結果集，而畫面上沒有任何訊號說明這件事。
   這是**漏報**——規格 §8.5 明寫「不得靜默維持舊結果集」，現況比那還糟。

建議修法：在 `onNavigate` 檢查回傳值，失敗時把 `state.scope` 還原為前一個值並
`history.replaceState` 同步 URL，再 render。前一個 scope 要在 `navigate()` 進入時
先存下來。**另需決定**：失敗時已載入的那半個檔案要不要留在 cache——留著下次可省一次
下載，但要確保 `results()` 只讀「目前 scope 所需」的檔案集合，而不是整個 map。
後者才是根因：`results()` 疊代 `this.searchFiles` 而非 `filesToLoad(scope)` 的結果。

### 3. 對應測試是恆真的（`tests/e2e/scope-perf.spec.ts:111-125`）

修正上述兩項時，測試要一併改成：

- 斷言 `location.search` 退回前一個 scope
- 斷言 scope 控制項的 checked 狀態退回
- 斷言結果集**與失敗前完全相同**（目前完全沒有驗這個，而它才是「不得靜默維持舊結果集」
  真正要守的東西）
- 反向哨兵：把退回邏輯拿掉後，上述斷言必須轉紅

---

## 待補

第二輪 Codex（`.ai-review/codex-prompt-r2.md`）跑完後，把 A1–H5 的逐條判定表併入本檔，
並對「完全沒有測試對應」的驗收編號逐一覆核。
