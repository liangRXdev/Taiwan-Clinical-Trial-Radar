# 覆核判定（M4 規格符合度稽核）

- 日期：2026-09-22
- Codex 原始輸出：`.ai-review/codex-review.md`（第二輪，A1–H5 八群全部完成）
- 覆核方式：**回去讀該檔案該行驗證**，不憑 Codex 描述判斷

---

## Codex 的統計（未經覆核的原始判定）

| 群 | 符合 | 弱化 | 缺測 | 未實作 |
|---|---:|---:|---:|---:|
| A（A1–A10） | 2 | 8 | 0 | 0 |
| B（B1–B9） | 2 | 7 | 0 | 0 |
| C（C1–C6） | 0 | 6 | 0 | 0 |
| D（D1–D8） | 3 | 5 | 0 | 0 |
| E（E1–E8） | 0 | 8 | 0 | 0 |
| F（F1–F4） | 0 | 3 | 0 | **1** |
| G（G1–G4） | 1 | 3 | 0 | 0 |
| H（H1–H5） | 2 | 2 | **1** | 0 |
| **合計** | **10** | **42** | **1** | **1** |

**「弱化」佔 78%，這個比例本身不是壞消息**——它多半意味「測試存在且方向正確，但 oracle
比規格寬」。真正要處理的是下面覆核過、會造成使用者可見錯誤的那幾項。

---

## 已逐行覆核的項目

| # | 項目 | 嚴重度 | 判定 | 理由（已驗證） |
|---|------|--------|------|------|
| 1 | **§7.2 命中日期標錯**：非最新紀錄命中時顯示 Trial 的最新日期 | **High** | **接受** | `src/ui/card.ts:82` 在 `fromOlder === true` 的分支取 `trial.latestSourceDate`，而 `fromOlder`（`:75`）的定義正是「命中不在最新 cohort 內」——這個分支**保證**顯示一個不屬於該紀錄的日期。 |
| 2 | **測試把上述誤導行為寫成 expected** | **High** | **接受** | `tests/web/render.test.ts:156` 斷言 `toContain(LABEL.hitFromOlder(t.latestSourceDate!...))`。不是沒抓到 bug，是**鎖住**了它——修正實作會讓這條測試轉紅。 |
| 3 | **§8.5 scope 載入失敗沒有真的退回** | **High** | **接受** | `src/app.ts:107-110` 的 `onNavigate` 丟棄 `ensureScopeFiles` 回傳值。失敗時 `state.scope` 仍是新的、URL 已 pushState、`searchFiles` 保留半套；`results()`（`:162-164`）疊代整個 map → **以部分索引產生結果**。 |
| 4 | **上述的 e2e 是恆真斷言** | Medium | **接受** | `tests/e2e/scope-perf.spec.ts:111-125` 只斷言錯誤區塊含「已退回原本的搜尋範圍」，而那是 `SCOPE.loadFailed` 寫死字串，錯誤分支一渲染就必然成立。從未檢查 state／URL／結果集。 |
| 5 | **`?protocol=` 半套實作**（§7.4／E8） | **High** | **接受**（證據需更正） | Codex 說「repo 沒有 `?protocol=` 對應程式碼」**不精確**：`src/lib/urlState.ts:16,74-75,137-138` 有 parse 與 build，URL 會原樣保留該參數。但 `src/app.ts` **從不讀 `state.protocol`**（全 repo 只有 urlState 內部三處用到）。所以 §7.4 的「以 identity 正規化後比對並導向 canonical」與 E8 的「不接受 `protocolNonIdentifier` 的值」**兩者都不存在**。**有 parse 而無行為比完全沒有更糟**——URL 收下了然後靜默忽略。 |
| 6 | **F2 完全未實作** | **High** | **接受** | §11 F2 要求「各按需檔案的壓縮基線記錄於規格與 CI artifact，超出記錄值 20% 須在 CI 告警」。`scripts/measure_payload.py` 只量 Tier 0 的三個檔，三個按需 search 檔完全沒納入；全 repo 找不到任何基線比較或 20% 門檻。 |
| 7 | **`measure-f1-live.mjs` 沒有被任何 workflow 呼叫** | **High** | **接受** | `grep -rn "measure-f1-live" .github/ package.json` 為空。F1 的四條量測邊界在 CI／部署 gate 層級**一條都沒有被強制**；目前綠燈只代表建置期估算（`measure_payload.py`）通過，而那支腳本自己寫明「通過不代表 F1 通過」。 |
| 8 | **E7 只掃候選值的原形** | Medium | **接受** | `tests/web/render.test.ts:58-81` 收集 candidates 時只取 `raw.trim()`。§11 E7 明文要求「含**截斷與正規化後**的形式」——卡片若顯示截斷版或 NFKC 正規化版，這條測不到。 |
| 9 | **C5 的十五列窮盡測試只驗「回傳非空 tuple」** | Medium | **接受** | `tests/test_c_sentinels.py:201-203` 是 `assert isinstance(key, tuple) and key`。§11 C5 要求「表中每一列各有正例」，而回傳**錯誤但非空**的比較鍵會通過全部 15 列。 |
| 10 | **E2 的 facet inventory 以 `data-` 屬性為主 oracle** | Medium | **部分接受** | 屬實：`tests/web/render.test.ts:244-249` 以 `STAT_SURFACE_ATTR`（`data-stat-facet`）雙向對帳，而 §11 E2 明文「不得只依 CSS class 或 card selector」。**但嚴重度沒有 Codex 暗示的高**：該屬性是元件自己掛的語意標記，繞過它需要有人新寫一個統計元件且刻意不掛——不是既有程式碼的缺陷，是 oracle 的強度上限。正確修法是改以「可見文字中出現分組計數的區塊」辨識，而非移除現有屬性。 |
| 11 | **A1 的 fingerprint membership 用 `<=` 而非精確相等** | Low | **部分接受** | 觀察屬實（`tests/test_a_whitespace_merge.py:279`），上一行註解還寫「逐列寫死而非只比總數」。**但 Codex 建議的精確相等會弄壞測試**：`_donor()` 挑到 `BIG-001`，而 a_core 裡**有 11 列**共用該 identity，合併後的 Trial 本來就會多出另外 10 列的 fingerprint。正確修法是把 expected 算成「a_core 中所有該 identity 的列 ＋ 注入的變體」再比相等。 |

統計（已覆核部分）：**接受 8／部分接受 2／拒絕 0**（另第 5 項證據需更正但結論成立）。

---

## 尚未逐行覆核

Codex 的 54 條判定中，上表覆核了 11 條。**其餘 43 條（多為「弱化」）尚未驗證，不得直接採信。**
它們的共同形態是「測試存在且方向正確，但 oracle 比規格寬」，風險低於上表各項，
但其中可能還有同類的恆真斷言。建議在處理完必修項後分批覆核。

**H3 判定為「缺測」是合理的但要講清楚**：H3 要求的是「上線當天 dispatch 兩次驗冪等」，
那是**執行時**驗收，本來就不會有對應的單元測試。2026-09-22 確實跑了兩次
（run 35674776960 發布、35675079518 回報 no normalized change、HEAD 不變），
證據在 `PROGRESS.md`。Codex 說「進度文字不是測試」——對，但也不該期待它是。
**要補的是把那兩個 run 的 ID、兩次 source SHA、HEAD 寫進可稽核的紀錄**，
而不是寫一個假裝在驗它的測試。

---

## 處置結果（2026-09-22，commit `9d10779`）

**五項必修全部修畢**，使用者定案：命中日期**列出全部**、`?protocol=` **補完**、
scope 失敗時成功且驗證過的檔案可留 cache 但不得影響畫面／scope／URL／結果集。

| # | 處置 | 驗證 |
|---|---|---|
| 1、2 | `Hit` 加 `date`，由搜尋索引的 `d` 帶出；多筆日期去重昇序**全部列出**；有／無日期並存時兩種標示都出現 | 測試改為「命中日期 ≠ Trial 最新日期」，並加反向斷言「最新日期不得出現在命中標籤裡」 |
| 3、4 | `results()` 改讀 `filesFor(目前 scope)`；失敗還原 `state.scope` ＋ `replaceState` | e2e 改驗 URL／控制項／結果集三者退回，另加「部分載入不得以半套索引產生結果」；**停用退回邏輯實測兩條都轉紅** |
| 5 | 新 `src/lib/protocol.ts`：identity 比對 ＋ canonical 導向；`rejected` 與 `notFound` **分開** | 13 條 unit ＋ 4 條 e2e |
| 6 | `payload-baseline.json` ＋ `check_on_demand()`，超 20% **告警不失敗** | 反向哨兵：基線減半後三個檔都告警 |
| 7 | `measure-f1-live.mjs` 接進 `deploy.yml` 部署後步驟並產 artifact；去重改為記次數計入 | `test_f1_的真實量測有進部署_gate` |
| 8–11 | **未處理**（Medium／Low），見下 | — |

未處理的四項：E7 候選值只掃原形、C5 十五列只驗非空 tuple、E2 的 selector oracle、
A1 的 `<=`。都不影響使用者可見行為，建議與其餘 43 條未覆核項一起分批處理。

---

## 必修清單（Critical/High，判定為接受或部分接受）

依建議處理順序：

1. **§7.2 命中日期**（第 1、2 項）——使用者可見的誤導，且測試鎖住了錯誤行為。
   修實作時**必須同時改測試**，否則修不動。
   **待決定**：一個 Trial 有多筆較舊命中且日期不同時要怎麼標（§7.2 的文字是單數，規格沒涵蓋）。
2. **§8.5 scope rollback**（第 3、4 項）——會讓使用者拿到以部分索引產生的結果集，屬漏報。
   根因是 `results()` 疊代 `this.searchFiles` 而非 `filesToLoad(scope)` 的結果。
   **待決定**：失敗時已載入的半個檔案要不要留在 cache。
3. **`?protocol=` 半套實作**（第 5 項）——要嘛補完（identity 比對 ＋ canonical 導向 ＋
   拒收 non-identifier），要嘛從 `PARAM_ORDER` 移除並修規格。**現況是最糟的第三種**。
4. **F1 的真實量測沒有進 gate**（第 7 項）——把 `measure-f1-live.mjs` 接進 `deploy.yml`
   的部署後驗證步驟（那裡已經在 curl 線上 manifest，是天然的掛載點），並產出 CI artifact。
   順帶修它的兩個量測邊界偏差：`new Set(requested)` 去重違反「全部 network responses」；
   「第二次重抓」是冷啟動 response 的代理而非本體，至少要記錄這個限制。
5. **F2 未實作**（第 6 項）——三個按需檔的基線與 20% 告警。

Medium 以下（第 8、9、10、11 項）建議一併處理，但不阻擋上線。

---

## 邊界

- 全程唯讀，**未修改任何 source code**。只寫 `.ai-review/` 下的報告檔。
- 修不修、怎麼修由使用者決定。
