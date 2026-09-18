# M0.5 fixture 與 artifact 樣本反驗出的規格洞

日期：2026-09-18
範圍：A 群 fixture 補 v0.5 新案例（50 → 73 列、29 → 45 Trial）＋ 最小 artifact 樣本（驗收 B8）
規格版本：`.ai-review/plan.md` v0.5

A 群第一輪的經驗是「寫 fixture 比再讀一遍 prose 更能找出問題」——它抓到 7 個洞。
本輪延續同一作法，**改成先把 v0.5 新增的契約做出來**：把 A2 要求但尚未存在的案例補進 fixture，
並照 §9.3.2 的文字真的產出一份合規 artifact。結果又抓到 **3 個洞**（1 High、2 Medium）。

---

## 摘要

| # | 嚴重度 | 章節 | 一句話 | 觸發物 |
|---|---|---|---|---|
| GAP-8 | **High** | §6.4.2 | 比較鍵表漏了三個語意狀態，同日兩列處於這些狀態時衝突與否無法從規格導出 | `CMP-035`／`CMP-036`／`CMP-037` |
| GAP-9 | Medium | §6.6.3 | 「可表示範圍」沒有序位，與「第一個命中者決定結果」字面矛盾 | `nr027-bounds` |
| GAP-10 | Medium | §9.3.5／F1 | `stats.json` 的 facet 名單未封閉，且它在 Tier 0 卻沒計入 F1 的實測基線 | 產出樣本的 `stats.json` 時 |

三個洞的共同形狀與第一輪相同：**規格在「主線」上寫得很細，但邊緣狀態的組合沒有被列舉過。**
GAP-8 尤其明顯——§6.4.2 是 v0.5 才新增的、是三項封存契約之一，表格看起來很完整（10 列），
但對照 §9.3.3 的旗標封閉集合就會發現少了三個。**兩份清單都在同一份規格裡，只是沒有人對過。**

---

## GAP-8（High）：semantic comparison key 的型別表不完備

**在哪裡**：§6.4.2 的比較鍵表列出 10 個型別／語意狀態。

**問題**：§9.3.3 的 field-scoped 旗標封閉集合中，有三個狀態在比較鍵表裡沒有對應項：

| 狀態 | 來自 | 比較鍵 |
|---|---|---|
| `numericRangeInvalid` | §6.6.3 序 4（`min > max`） | **未定義** |
| `numericOutOfRange` | §6.6.3 可表示範圍 | **未定義** |
| `categoricalUnknown` | §6.6.1 非合法分類值 | **未定義** |

**後果**：同日兩列皆處於這三種狀態之一、但 raw 不同時，衝突與否無法從規格導出。
實作只能二選一，而兩種都能自圓其說：

- **比 typed**（皆 `null`）→ 判不衝突，任取一筆 raw 當代表值。
  這正是第三輪否決 GAP-5 建議的理由：會**隱藏異常**。`40-20` 與 `50-30` 都是順序異常，
  但它們是兩筆不同的來源錯誤，任取一筆呈現等於替上游決定哪一筆才算數。
- **比 `conflictText(raw)`** → 判衝突，欄位從卡片省略。

規格必須指定一種。不指定的直接代價：**C5「逐型別驗證」寫不完**（只能寫 4 個型別，另 3 個無 oracle），
**A3 的跨排列一致性也不保證**——兩個排列下若實作任取一筆，取到的可能不同。

**fixture 觸發點**（各一組同日兩列，raw 不同）：

| Trial | 欄位 | 兩個 raw |
|---|---|---|
| `CMP-035` | `台灣預計受試者人數` | `40-20` / `50-30` |
| `CMP-036` | `臨床試驗期別` | `第三期` / `Phase III` |
| `CMP-037` | `全球預計受試者人數` | `9007199254740992` / `9007199254740993` |

`oracle.json` 對這三個 Trial 的 `latestAmbiguous` 與 `conflictFields` 填 `"__SPEC_GAP__"`，
`check_a_core.py` 的 `[8]` 段獨立列出並斷言「未定義狀態集合恰為這三個」。
**規格補上之後，這個斷言會變成紅的**——那是預期的，改 oracle 時一併移除。

**建議**：比照已定案的 `numericUnparsed`／`numericImplausible`，三者皆採 `(旗標名, conflictText(raw))`。
理由一致：這三種狀態的 typed 都是 `null`，唯一帶資訊的是 raw 原文，而 UI 本來就要顯示 raw 加異常提示。
採這個規則，上表三組全部**判為衝突**，與「寧可漏報不可誤報」一致。

---

## GAP-9（Medium）：可表示範圍檢查沒有序位

**在哪裡**：§6.6.3 的解析順序表（序 1–6）＋ 其後的「可表示範圍」段落。

**問題**：表宣告「**依下列順序**比對，第一個命中者決定結果（固定順序使每個值只有一個分類）」。
但 `9007199254740992` 先命中序 2（`^\d+$`）得 typed 值，再被表後的範圍檢查改成 `null`
並加 `numericOutOfRange`。**「第一個命中者決定結果」在字面上不成立。**

**後果**：兩個實務問題無法從規格導出——

1. 超界時序位旗標是否保留？`0` 不可能超界所以 `sourceZero` 無爭議，但 `numericRange` 有。
2. 範圍值只有**單一端點**超界（如 `1-9007199254740992`）時，旗標是 `[numericRange, numericOutOfRange]`
   還是只有 `numericOutOfRange`？typed 是整個 `null`、還是只把超界那端設 `null`？

第 2 點直接影響 `enroll` 篩選：若 typed 保留 `{min:1, max:null}`，D8 的區間重疊判定沒有定義。

**建議**：把可表示範圍檢查寫成解析順序表的**後置步驟**（序 2／3 命中後套用），並明定：
超界時 typed 一律為 `null`、旗標為該序位旗標 ＋ `numericOutOfRange`、分級為 warning、
`enroll` 歸「未提供」。

**現況**：`check_a_core.py` 依此建議實作（range 超界回傳 `["numericRange","numericOutOfRange"]`），
但 **fixture 未含單端超界的範圍值**——那要等規格定案才知道 oracle 該寫什麼，不先猜。

---

## GAP-10（Medium）：`stats.json` 的內容與大小沒有被封存

**在哪裡**：§9.3.5 的 `stats.json` schema ＋ §11 F1。

**問題兩層**：

1. **facet 名單未封閉。** §9.3.5 只寫「`facets` 的每個 facet 的 `buckets + unprovided + conflicted`
   必須等於 `denominators.trials`」，並註明「`enroll` 因區間重疊可跨 bucket，故不列為 facet；
   facet 僅含互斥維度」。但**沒有列出 facet 名單**。§8.4 的六個篩選維度中，
   `phase`／`scale`／`applicant` 是互斥的，`enroll` 已排除，`period` 是重疊語意（不互斥），
   `updated` 取決於 bucket 是否分割時間軸——後兩者要不要成為 facet，規格沒說。

   產樣本時我只能自己挑（`phase`／`scale`／`applicant`）。**E2 要求「任何存在於 DOM 但不在 oracle
   清單中的統計卡必須使測試失敗」——那個清單現在沒有來源。**

2. **`stats.json` 在 Tier 0 卻沒計入 F1 基線。** F1 定義 Tier 0 為「冷啟動到可搜尋 readiness 的
   **全部** network responses」，實測基線卻只寫 `trials-index` 1,236 KiB。首頁要顯示統計卡（E2）、
   篩選控制項要有值域（§8.4 的 `applicant` 值為 raw 申請者字串），兩者都來自 `stats.json`，
   因此它在 Tier 0 內。1,236 KiB 對 1.5 MB 只剩約 300 KiB 餘裕，而 **`applicant` 的 distinct 值數
   從未量測**——PROGRESS.md 第 50 行那張表是「差異欄位分布（按組數）」，不是 cardinality，
   `臨床試驗申請者 165` 指的是 165 個多列 protocol 組在該欄位有差異，**不是 165 個申請者**。

**建議**：
- 封閉 facet 名單（含 `period`／`updated` 的取捨與理由），寫進 §9.3.5，並讓 E2 引用它。
- F1 的「納入檔案清單」明列 `manifest.json` ＋ `trials-index` ＋ `stats.json`，
  重新量測含 `stats.json` 的 Tier 0 總和。**量測前不要調整門檻**。

**這個洞不是 fixture 抓到的，是產樣本時抓到的**——寫 `stats.json` 那幾行時發現沒有依據可寫。
記在這裡是因為它與另外兩個同源：規格把主線寫細了，但沒有把「輸出到底有哪些、多大」對過一遍。

---

## 本輪同時完成的事（非缺口）

### A 群 fixture 補齊 v0.5 的 A2 必含案例

50 → **73 列**、29 → **45 Trial**。新增：

| 案例 | rowKey | 為什麼非有不可 |
|---|---|---|
| 空白-only protocol（ASCII 空白 ×3、U+3000） | `wsonly-ascii`／`wsonly-ideo` | §6.3.1 的判定依據是 `identityNormalize` 後是否為空。以 `raw == ""` 實作者會把這兩列誤走 `P:` 分支並產生 identity key `"P:"` 的碰撞 |
| `buildDate` 當日／+1 日 | `bd024-today`／`bd024-tomorrow` | 兩列的台灣人數刻意不同（12／99），把 +1 日算進 latest 的實作會讓卡片顯示 99 |
| 嚴格範圍（`至` 與 `-` 各一） | `nr025-strict` | 兼 D8：`20-40` 須同時落入 `11-30` 與 `31-100` |
| `min > max` | `nr026-invalid` | 不得自動交換為 `20-40` |
| 超界（2^53）＋ 前導零 | `nr027-bounds` | 直接輸出 `9007199254740992` 會失真；`026` 的 raw 不得顯示為 `26` |
| 約略值 | `nr028-approx` | **反向哨兵**：任何「抽出字串中的數字」的實作都會把 typed 填成 400／480 |
| `TEST` 值型 | `test029` | protocol 合法、申請者與標題非空 → §6.2.2 的 (a)(c) 都不成立，只靠 (b) 觸發 |
| 期間端不可解析／缺值 | `pd030-unparsed`／`pd031-missing` | 兩者是不同旗標；且**不得**判為 `periodEndBeforeStart`（§6.5.3 只在兩端皆可解析時比較） |
| C5 的四個比較鍵型別 | `cmp032`～`cmp034` | `20`/`２０` 與 `20-40`/`20～40` 須不衝突；`20-40`/`20-41` 須衝突 |

`check_a_core.py` 同步改為 v0.5 規則：`[2]` 的同日分類改用 semantic comparison key、
`[4]` 改用 §6.6.3 的完整 lexical grammar。**73 列全部重新計數**（見下）。

### 計數再一次應驗「要數全部列」

`periodFieldAnomalies` 的 `periodEndMissing` 是 **`["nonid-test", "pd031-missing"]`**，不是只有後者——
`nonid-test`（上游測試列）的期間兩端本來就都是空的。這與第一輪 `排除條件="N/A"` 寫 1 實際 3 是同一種錯，
差別只在這次先想到要數全部。`numericStateCounts` 因此改為八類互斥且加總必須等於
73 × 2 = **146** 的形式，讓漏數會直接失敗而不是悄悄少一筆。

### 最小 artifact 樣本：§9.3.2 可實作、無循環

`tests/fixtures/artifact_sample/` 產出 7 個非 manifest 檔案 ＋ `manifest.json`，
`check_b8.py` 的 B8 四條全綠。關鍵那條是 **B8-1b**：

> 從**已寫入 `datasetVersion` 的最終檔案**移除 top-level `datasetVersion` 後重算，
> 得到同一個 `datasetVersion`。

這就是循環被解開的操作型證據——v0.4 的寫法連一份合規 artifact 都產不出來，v0.5 產得出來且自我一致。

B8-3（兩個檔案內容互換）另加一條反向哨兵：斷言互換前後的 payload hash **多重集合相同**。
沒有這條的話，「互換後 digest 改變」也可能只是因為內容本來就不同，證不到「邏輯檔名已納入」。

順帶證明可檢查的：§9.3.6 的排序／referential integrity／計數一致／inventory 四類不變量、
B7 的「除 `manifest.json` 外全部檔名帶內容雜湊」、§6.4.5 的「衝突欄位完全省略」、
§6.4.3 的「`rawVariants` 在欄位層級」。

**樣本不是 ETL。** `build_sample.py` 沒有 identity 收斂、cohort 判定或 sentinel 分型，
兩個 Trial 的模型內容是手寫的；只有 canonical serialization、ID 與兩個 digest 是照規格算的，
因為那正是 B8 要證明可實作的部分。M1 不得沿用它當實作——規格要能被兩份獨立的程式碼各自寫出來才算寫清楚。

### 觀察到但不是問題

`search-long-latest` 與 `search-long-all` 在本樣本中 payload 完全相同（樣本的 4 筆 record 都在
latest cohort 內），故 `<h>` 也相同（`7f8e217cf937682e`）。兩者的發布路徑仍相異（stem 不同），
`datasetVersion` 也因為串接納入邏輯檔名而不受影響。記下來是因為第一眼會以為是 bug。

---

## 下一步

1. **GAP-8／GAP-9／GAP-10 進 v0.6**，跑一輪限縮的 `/codex-checkplan`（只審這三項與其修訂）。
   GAP-8 的修訂會使 `check_a_core.py` 的 `[8]` 段轉紅，那是預期行為。
2. B 群 fixture：§9.5 每個 error code 的注入、§9.3.6 每條不變量的反例、promotion 各失敗點。
3. C4 的三個獨立 mutation。
