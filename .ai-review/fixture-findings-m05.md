# M0.5 fixture 與 artifact 樣本反驗出的規格洞

日期：2026-09-18
範圍：M0.5 全部四項——A 群 fixture 補 v0.5 新案例（50 → 73 列、29 → 45 Trial）、最小 artifact 樣本（B8）、
B 群失敗注入 fixture（B1／B2／B3／B4／B5）、§9.3.6 不變量反例（B6）與 C4 的三個 mutation
規格版本：`.ai-review/plan.md` v0.5

A 群第一輪的經驗是「寫 fixture 比再讀一遍 prose 更能找出問題」——它抓到 7 個洞。
本輪延續同一作法，**改成先把 v0.5 新增的契約做出來**：把 A2 要求但尚未存在的案例補進 fixture、
照 §9.3.2 的文字真的產出一份合規 artifact、再對它注入 §9.3.6 與 C4 的反例。
結果又抓到 **5 個洞**（1 High、3 Medium、1 Low）。

---

## 摘要

| # | 嚴重度 | 章節 | 一句話 | 觸發物 |
|---|---|---|---|---|
| GAP-8 | **High** | §6.4.2 | 比較鍵表漏了三個語意狀態，同日兩列處於這些狀態時衝突與否無法從規格導出 | `CMP-035`／`CMP-036`／`CMP-037` |
| GAP-9 | Medium | §6.6.3 | 「可表示範圍」沒有序位，與「第一個命中者決定結果」字面矛盾 | `nr027-bounds` |
| GAP-10 | Medium | §9.3.5／F1 | `stats.json` 的 facet 名單未封閉，且它在 Tier 0 卻沒計入 F1 的實測基線 | 產出樣本的 `stats.json` 時 |
| GAP-11 | Medium | §9.3.6 | 不變量之間有依賴，但規格沒寫評估順序，使 B6 的「各自獨立反例」寫不出來 | B6 的「record 放錯 shard」反例 |
| GAP-12 | Low | §9.6 | 「以有理數比較」在本資料集規模下**不可驗證**；可驗證的是「不四捨五入」 | B4 的門檻案例 |

前三個洞的共同形狀與第一輪相同：**規格在「主線」上寫得很細，但邊緣狀態的組合沒有被列舉過。**
GAP-11／GAP-12 是另一種：**驗收條件本身不成立**——一條要求「獨立反例」但結構上做不到，
一條要求了一件在本專案規模下測不出違反的事。這兩種只有在真的去寫那個反例時才會現形。
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

## GAP-11（Medium）：§9.3.6 的不變量之間有依賴，但沒有評估順序

**在哪裡**：§9.3.6 是一串平鋪的 bullet：排序 total order、referential integrity、計數一致、
inventory、`datasetVersion`／`artifactDigest`、`schemaVersion` 升級。**沒有寫評估順序。**

**問題**：`recordIds` 的排序鍵是「可採計日期降序、不可採計者置末、`recordId` 昇序」，
而那個日期在 **shard 的 record 裡**。當 record 放錯 shard（referential integrity 違規）時，
排序鍵**取不到**——驗證器只能把它當成「沒有日期 → 置末」，於是同時誤報排序違規。

**怎麼發現的**：寫 B6 的「record 放錯 shard」反例時，實際跑出來的違規集合是
`['I2', 'I4']` 而不是預期的 `['I4']`。

**為什麼這不只是實作細節**：B6 明文要求「每一條不變量各有**獨立**反例」。
若某個缺陷必然連帶觸發另一條，那麼**只實作其中一條檢查的驗證器也會通過測試**——
這條驗收就變成假的。要讓反例真的獨立，驗證器必須先評估 referential integrity，
再對通過的 Trial 才評估排序。**那是規格該指定的事，不是實作可以各自決定的。**

**建議**：§9.3.6 明寫評估順序與「無法評估」的處置：

1. inventory ＋ 跨檔版本綁定（沒有檔案就什麼都驗不了）
2. referential integrity（shard 歸屬、唯一 owner、`latestCohort ⊆ recordIds`）
3. 計數一致
4. 排序 total order（**只對通過第 2 步的 Trial 評估**）
5. `datasetVersion`／`artifactDigest`

並規定：上游步驟失敗時，下游那條回報「無法評估」而非「違規」，
error code 一律仍為 `INTEGRITY_DIGEST`（對外行為不變，變的是 report 的歸因）。

**現況**：`check_b6.py` 已依此建議實作並在程式碼裡標注理由；11 條不變量的反例現在
**違規集合 exactly equals 預期**，反向哨兵（未變造樣本零違規）亦成立。

---

## GAP-12（Low）：§9.6 的「以有理數比較」不可驗證

**在哪裡**：§9.6「`drop = (prev - cur) / prev`，以有理數比較，**不四捨五入**」。

**實測**：掃過 `prev ∈ [3, 20000]`（本資料集 18,736 列）在兩個門檻鄰域的全部 `cur`，
**float 與有理數的判定沒有任何一組相異**。原因是 IEEE-754 的除法取最近可表示值，
而 `0.10`／`0.20` 的字面量本身就是各自最近的 double——在這個定義域內兩者恆等。

**後果**：B4 寫不出一個能區分「有理數實作」與「float 實作」的案例。
規格要求了一件在本專案規模下**無法被測試發現違反**的事。

**真正該守的是「不四捨五入」，而那守得住**：

| prev | cur | 精確 drop | 正確判定 | 四捨五入到 2 位 |
|---:|---:|---:|---|---|
| 10000 | 8999 | 0.1001 | publish + **warning** | 0.10 → 無 warning ❌ |
| 10000 | 7999 | 0.2001 | **hard-fail** | 0.20 → **照樣發布** ❌ |

第二列是本組最重要的一例：四捨五入的實作會在上游掉了 20.01% 的資料時**正常發布**。

**建議**：把 §9.6 的文字從「以有理數比較」改為「**不得先四捨五入或截斷到固定小數位再比較**」，
並註記「在 `prev ≤ 20,000` 的定義域內 float 與有理數等價；若未來資料規模改變須重新評估」。
仍可保留有理數實作（它便宜且不需要重評），但**不要在規格裡放一條測不到的要求**——
測不到的要求會讓驗收清單看起來比實際強。

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

`tests/fixtures/artifact_sample/` 以 8 個 Trial 產出 12 個非 manifest 檔案 ＋ `manifest.json`，
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

### B 群失敗注入 fixture（B1／B2／B3／B4／B5）

`tests/fixtures/b_failures/` 造出 12 個有缺陷的輸入，每個都附「什麼弱化實作會通過這條」：

| 缺陷 | 殺掉的弱化實作 |
|---|---|
| 200 但 MIME 為 text/html | 只看 HTTP status |
| ZIP central directory 完好但 CRC 壞 | 只檢查「開得起來」 |
| ZIP 內只有 readme.txt | 直接取第一個成員 |
| 非法 UTF-8 位元組 | `errors='replace'`——會靜默產出 U+FFFD，資料變了但沒有訊號 |
| 欄名集合相同、**順序**不同 | 以 set 比對欄名（而 §6.3 的 canonical serialization 依順序輸出，順序錯 ID 全錯） |
| 某列只有 10 欄 | `csv.DictReader`（缺欄補 None 不報錯） |
| 欄名完全正確但 0 資料列 | 在 schema 之前就用「空檔」短路（B3 明文要求 schema 先過） |
| 三層同時異常 | 沒有 precedence，回傳「先被程式碼碰到的那一個」 |

`check_b_failures.py` 驗證這些輸入**真的有**宣稱的缺陷（corrupt ZIP 真的校驗失敗、
`zero_rows` 的 16 欄真的完全正確），並查核 oracle 自身：16 個 error code 全部有 fixture 或注入點、
每個 case 的 layer 都在 precedence 清單內、B4 的算術與判定相符。

### §9.3.6 不變量反例與 C4 mutation

`check_b6.py` 對 artifact 樣本注入 11 種缺陷，每個都斷言**違規集合 exactly equals 預期**。
兩個設計決定值得記：

1. **注入點在計算 digest 之前。** 真實威脅是「有 bug 的 ETL 產出內部自洽但違反不變量的 artifact」——
   它會把自己算出來的 digest 一併寫進去。改完最終位元組就放著不重算，測到的只是 digest 本身，
   referential integrity 那幾條永遠不會被執行到。每個反例另斷言 `I10`／`I11` **未**觸發，證明這件事。
2. **「record 被兩個 Trial 引用」必須挑同 shard 的一對。** 跨 shard 會連帶違反 shard 歸屬而無法隔離。
   `IND-005` 與 `NR-028` 的 `trialId` 恰好都落在 shard `c4`，樣本為此把它們收了進來。

孤兒檔那條另加一句證明：**孤兒檔不會改變 `artifactDigest`**（§9.3.2 只走 `manifest.files` 的路徑），
所以 inventory 不變量無可取代——沒有它，`public/data/` 裡多一個沒人引用的檔案是完全靜默的。

`check_c4.py` 的三個 mutation 各自斷言「只有目標那組斷言轉紅、其餘仍綠」，並加一條反向查核：
分類 sentinel 的 typed **本來就是 null**，把它「轉成 null」當 mutation 會是測試在要求實作違反 §6.6.1
（v0.3 的 C4 第一個 mutation 就是這個錯，第一輪覆審抓到）。

**C1 的第 4／5 處斷言目前只驗到資料層**（選項清單的唯一來源是 facet buckets、
`displayFields` 帶 `categoricalUnprovided` 供前端直接取用）。DOM 與卡片文字待 M2，`check_c4.py`
的 docstring 明寫這個範圍限制——不假裝驗過。

---

## 下一步

1. **GAP-8～GAP-12 進 v0.6**，跑一輪限縮的 `/codex-checkplan`（只審這五項與其修訂）。
   GAP-8 的修訂會使 `check_a_core.py` 的 `[8]` 段轉紅，那是預期行為。
2. M1 鷹架與 ETL。M0.5 的四項待辦已全部完成（A 群補案例、artifact 樣本、B 群 fixture、C4 mutation）。
