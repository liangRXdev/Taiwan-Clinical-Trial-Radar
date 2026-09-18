# Taiwan Clinical Trial Radar — 規格 v0.4（consolidated）

> **這是唯一具規範效力的規格。** `Taiwan-Clinical-Trial-Radar-spec.md` v0.1、本檔 v0.2 與 v0.3 均降為歷史文件，**不再具 normative 效力**。
> 依據：2026-09-18 dataset 205 實測 + Codex 第一輪（`plan-review-r1.md`／`plan-verdict-r1.md`）+ 第二輪（`plan-review-r2.md`／`plan-verdict-r2.md`）。
> 狀態：**待第三輪限縮覆審**（只審 §6.3／§6.4／§6.5／§9.2／§9.3 與搜尋分層）。尚未寫任何程式碼。

---

## 1. 目標

台灣藥品臨床試驗檢索站。把 TFDA dataset 205 轉成可搜尋、可篩選、可追溯資料日期的靜態網頁，回答：

1. 台灣有哪些經衛福部審查的藥品臨床試驗？
2. 某疾病、試驗名稱、protocol number 或申請者涉及哪些試驗？
3. 試驗期別、規模、期間、預計收案數、主要評估指標與納入／排除條件為何？
4. 公開資料更新到何時、該去哪裡確認最新狀態？

使用者：臨床藥師、醫師、CRC／研究護理師、研究者。單次查詢情境。

## 2. 非目標

- **dataset 206–209 的任何 join**（v0.1 §3.1／§5.1／§8／§9／§14／§18 中所有 206–209、`linkageStatus`、`linkage-report`、`verify_linkage.py`、寄信詢問 TFDA 的要求**一併作廢**）。
- 受試者適格性判定；病歷、病況自由文字或任何病患資料輸入。
- 招募狀態顯示或推論。**不保留 feature flag。**
- AI 生成試驗摘要、療效比較、試驗品質評分、risk of bias、證據等級。
- 試驗優先排序或「最適合」推薦。
- 有方向性的版本 diff（`A → B` 箭頭）。
- **自動合併近似的 protocol 寫法**（見 §6.2.1）。
- 醫院 geocoding 與「附近正在招募」。
- 搜尋字串、IP 或任何 analytics 蒐集。
- PI 姓名的人物績效排行。
- Service worker／PWA。

## 3. 資料來源與平台限制

實測（2026-09-18）：

| 項目 | 值 |
|---|---|
| 端點 | `https://data.fda.gov.tw/data/opendata/export/205/csv` → `200`、`application/zip` |
| 內含檔 | `205_2.csv`，UTF-8 with BOM |
| ZIP／解壓後 | 42 MB／166,450,190 bytes |
| 列數／欄數 | 18,736／16 |
| 不同 protocol | 5,882（另 6 列 protocol 為空）→ 5,888 個 Trial |
| 最新 cohort 紀錄數 | 6,921 |
| `資料更新時間` | 全部合法 `YYYY/MM/DD`，零空值、零未來日期，範圍 2024/12/20 – 2026/08/17 |
| `試驗預計執行期間` | 格式全合法，但 **7 列 end < start** |
| 控制字元 | **無 U+001F**；58,140 個欄位含換行、10,725 個含 TAB |
| 單列最長文字 | `納入條件`／`排除條件` 22,490；`試驗目的` 5,512；`主要評估指標` 5,166 |

16 欄（來源順序，此順序為 canonical 欄位順序）：`臨床試驗申請者`、`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`、`TFDA收文號`、`資料更新時間`。

平台限制：純靜態，無後端／DB／認證／runtime API；前端不得解析 166 MB CSV；`data.fda.gov.tw` 從 GitHub Actions 直抓可行不需 proxy（對 Google IP 回 500 只適用 Apps Script，與 `consumer.fda.gov.tw` 的境外 IP TLS 切斷亦不同）；GitHub Actions 月排程 + `workflow_dispatch`；部署 Cloudflare Pages。

## 4. 來源沒有執行狀態

官方資料集頁面列有 `執行狀態`，實際 16 欄沒有。不提供招募／執行狀態的篩選、標章或排序維度，**不保留旗標**。來源若日後新增此欄，走 §9.5 的 schema 變更與規格修訂流程。

**TFDA 審查通過 ≠ 目前正在招募；試驗使用 ≠ 藥品已獲 TFDA 上市核准。** 這兩句是 §10 免責的必要內容。

## 5. 架構決策

**5.1 只做 dataset 205。** 206–209 無可驗證 trial identifier，筆數不一致（512,140／27,774／28,800）。代價是永久放棄藥品、機構、ICD-9 關聯，接受。

**5.2 部署 Cloudflare Pages。** 不選 GH Pages：`liangrxdev.github.io` 多工具共用 origin，Cache Storage 不依 SW scope 隔離，既有專案已踩過跨 repo 互刪快取。

**5.3 選型。** Python 3.12+（標準 `csv` + dataclass／Pydantic 驗證）；TypeScript（Vite）；pytest + Vitest + Playwright；純邏輯抽為可 import 函式供無網路 mock 測試。

## 6. 資料模型

### 6.1 命名

來源列稱 **SourceRecord（審查紀錄）**。18,736 列對應 5,882 protocol，2,821 個 protocol 有多列（最多 23 列），其中只有 61 組 16 欄全同。

「一列 = 某一版試驗計畫書」是推論不是事實；資料只證明同 protocol 有多筆審查紀錄。規格與 UI 一律用「審查紀錄」，**不稱「第 N 版」**。

### 6.2 Identity normalization（與搜尋正規化分離）

**identity normalization**（只用於主鍵）：`strip` → `NFKC` → `upper`。**不做**標點移除、不做內部空白壓縮、不做前後綴剝離。

實測：對 5,882 個 protocol 產生 **0 個碰撞**。

兩個不同 raw protocol 正規化後相同 → 硬失敗 `IDENTITY_COLLISION` 並產出 collision report（內容契約見 §9.8），**不得合併**。（fail-closed 而非保留為不同 Trial：合併會誤配，保留兩個同鍵 Trial 會讓 URL 不唯一，硬失敗使月更新維持 last-known-good。）

**search normalization** 另定於 §8.1，兩者**各自獨立驗證**，不得共用實作。

#### 6.2.1 近似 protocol 不自動合併，但必須揭露

§6.2 不剝標點、不壓空白，代價是**同一個試驗的不同寫法會成為兩個 Trial**。實測 **18 組**：

| 差異類型 | 實例 |
|---|---|
| 多一個空格 | `9785-CL- 0123` / `9785-CL-0123`；`219288 (B-Well 2)` / `219288(B-Well 2)` |
| 全形括號＋空格 | `LOXO-RET-17001 (J2G-OX-JZJA)` / `LOXO-RET-17001（J2G-OX-JZJA）` |
| 括號未閉合 | `ROR-PH-301(APD811-301` / `ROR-PH-301(APD811-301)`；`ROR-PH-303` 同型 |
| 連字號有無 | `MK-3475-158` / `MK3475-158`；`CA209-9DW` / `CA2099DW`；`CA224-1093` / `CA2241093`；`CA239-0004` / `CA2390004`；`CA204-219` / `CA204219`；`SNR-04` / `SNR04`；`NHRI-FV-001` / `NHRIFV001`；`GS-US-563-5925` / `GS-US-5635925`；`ALXN2220-ATTR-CM-301` / `ALXN2220-ATTRCM-301` |
| 上游刪除標記前綴 | `BGB-16673-303` / `刪_BGB-16673-303` |

**維持不自動合併**（自動合併會誤配，違反寧可漏報不可誤報），但必須：

1. **偵測**：以 `剝除所有非英數字元後 upper` 為 **loose key**（僅用於偵測，**絕不用於收斂**），將 loose key 相同但 identity key 不同的 Trial 歸為一個 `nearDuplicateGroup`。
2. **QA report** 列出每個 group 的全部 raw protocol 與 trialId。
3. **UI**：詳情頁顯示「其他寫法近似的計畫書編號」與連結，讓使用者自行判斷。**不自動合併、也不無聲漏掉。**
4. loose key 為空字串（protocol 完全不含英數字）者**不納入** nearDuplicateGroup（見 §6.2.2），否則會把所有非編號值錯歸成一群。

#### 6.2.2 protocol 非識別碼值

實測 protocol 欄位含 **7 個不同值、共 9 列**完全不含英數字元：`系統測試`、`計畫書編號系統測試`、`臨床試驗計畫初版編號`、`未列編號`、`無`、`科技部研究計畫(申請中)`、`聯亞生技開發股份有限公司`（申請者名稱填錯欄位）。另有含英數字但顯非編號者，如 `計畫書編號123`、`計畫書編號A`（申請者 `CDE`、標題 `計畫書標題（名稱)test 收案到哪一個欄位中A`）、`未列編號。第二版，97/10/3`、`IRB編號：KMUHIRB-F(I)-20200122`。

規則：

- protocol 值**不含任何英數字元**時，Trial 標記 `protocolNonIdentifier: true`。
- **不刪除任何資料**（刪資料就是改寫上游）。UI 顯示「來源未提供計畫書編號」，統計歸入「未提供編號」類別，**不得作為 `?protocol=` 別名**。
- 疑似上游測試列（`臨床試驗申請者` 與 `臨床試驗計畫中文名稱` 皆空，或標題含 `test`）**單獨計數警示**，同樣不自動刪除。
- QA report 完整列出上述兩類的 raw 值與 trialId。

### 6.3 Canonical serialization 與 ID

**canonical serialization 必須對 16 欄 tuple 一對一。** 作法：對 16 欄的 **raw 值**（已去 BOM、未經任何正規化），依 §3 的 canonical 欄位順序，逐欄輸出 `<UTF-8 位元組長度>` + `U+001F` + `<欄位位元組>`，欄位之間再以 `U+001F` 分隔。長度前綴使得任何欄位內容（含分隔符本身）都不會造成歧義。

**額外硬性檢查**：任一欄位含 `U+001F` 時硬失敗 `SOURCE_CONTROL_CHAR`。實測本快照**無 U+001F**（控制字元只有 CR/LF/TAB），故此檢查目前恆不觸發，但不得省略——不可假設未來匯出也沒有。

**identity key**：

- protocol 非空 → `"P:" + identityNormalize(protocol)`
- protocol 為空 → `"H:" + sha256(canonicalSerialization)`；多列 content hash 相同時附出現序號 `"#k"`，`k` 由 canonical serialization 排序後配置，**不依輸入列序**（這些列逐位元相同，序號分配在內容上不可區分，輸出仍確定）

**trialId** = `"t" + sha256(identityKey)[:16]`；**recordId** = `trialId + "r" + sha256(canonicalSerialization)[:16]`，完全相同的重複列附 `"#k"`（規則同上）。

**三層碰撞偵測，全部 fail-closed**：

| 層級 | 條件 | error code |
|---|---|---|
| identity key | 不同 raw protocol → 相同 identity key | `IDENTITY_COLLISION` |
| trialId | 不同 identity key → 相同 trialId（16-hex 截短碰撞） | `ID_TRUNCATION_COLLISION` |
| recordId | 不同 canonical serialization → 相同 recordId | `ID_TRUNCATION_COLLISION` |

實測：16,328 個不同紀錄的 16-hex 截短 **0 碰撞**。仍須偵測。

**shard key** = `trialId` 的**第 2–3 個字元**（即 sha256 的前 2 hex；`trialId` 第 1 字元固定為字面 `t`，不是 hex）。shard 檔名為 `records/<shardKey>.<hash>.json`，`shardKey` ∈ `00`–`ff`。

**ID 穩定性界限（須寫進 README）**：只保證**對相同來源快照穩定**。上游重排、增刪或修改欄位時 ID 可能變動；不得宣稱 ID 跨快照代表同一實體。空 protocol 的 hash-based ID 尤其如此。

### 6.4 Trial 結構、呈現欄位與同日衝突

**呈現欄位（封閉集合，13 欄）**：16 欄扣除 `臨床試驗計畫書編號`（已是主鍵）、`TFDA收文號`（非呈現用途、且 2,788 個重複鍵）、`資料更新時間`（cohort 的判定依據本身）：

`臨床試驗申請者`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`。

**衝突比較模式**：以 `NFKC` + 全部空白移除後的值判定是否衝突；**顯示一律用 raw 值**。

實測影響：raw 比較得 **157 組** ambiguous，NFKC+空白正規化比較得 **143 組**，差 **14 組**。那 14 組只差空白或全半形，標成「不一致」是假警報，會訓練使用者忽略警示。

```
Trial
  id                     trialId
  protocolRaw[]          raw protocol 值（identity 正規化後相同者），昇序
  protocolNonIdentifier  bool（§6.2.2）
  nearDuplicateGroup     loose key 或 null（§6.2.1）
  latestSourceDate       可採計日期的最大值（§6.5）；無可採計日期時為 null
  dateUnknown            bool；latestSourceDate 為 null 時為 true
  latestCohort[]         latestSourceDate 當日的 recordId，昇序；dateUnknown 時為「全部 recordId」
  latestAmbiguous        latestCohort 長度 >1 且呈現欄位（正規化後）有衝突時為 true
  conflictFields[]       衝突的呈現欄位名，依 canonical 欄位順序
  displayFields          latestCohort 內無衝突呈現欄位的共同 raw 值
  recordIds[]            全部 recordId，依（可採計日期降序、不可採計者置末、recordId 昇序）
  shard                  shardKey
```

**`dateUnknown` 與 `latestAmbiguous` 是兩個獨立旗標**，語意不同，不得互相取代：

| 情形 | `dateUnknown` | `latestAmbiguous` | 卡片 |
|---|---|---|---|
| 單筆最新、日期正常 | false | false | 正常顯示 |
| 同日多筆、正規化後全同 | false | false | 顯示共同值 |
| 同日多筆、有衝突 | false | **true** | 只顯示無衝突欄位 |
| 無任何可採計日期 | **true** | 依全部 record 判定 | 顯示「資料日期無法辨識，請查官方來源」；仍顯示無衝突欄位 |

實測 846 個平手組的分布：**689 組（81%）16 欄全同**（`latestAmbiguous=false`，顯示共同值，`recordIds` 保留 multiplicity）；**157 組 raw 有差異，其中 143 組正規化後仍衝突**（`latestAmbiguous=true`）。

衝突組欄位分布（raw 比較）：`納入條件` 74（另 12 組僅空白／全形差異）、`試驗預計執行期間迄` 48、`試驗目的` 40、`主要評估指標` 34、`全球預計受試者人數` 22、`台灣預計受試者人數` 21（如 `19` vs `31`、`0` vs `4`）、`臨床試驗計畫中文名稱` 20、`臨床試驗期別` 3（如 `Phase Ⅱ` vs `Phase Ⅰ,Phase Ⅱ`）。

`latestAmbiguous=true` 時：卡片**只顯示無衝突的共同欄位**，衝突欄位顯示「同日多筆資料不一致，請展開確認」，**不得任取一值**；詳情頁並列該日全部紀錄並明示**順序未知**；**hash 只用於 cohort 內穩定排序，不宣稱時間先後**，不得以完整度或 hash 推定業務新舊。

（曾考慮的「取非空欄位數最多者」實測幾乎無效：846 組中只唯一決出 5 組。已棄。）

### 6.5 日期規則

**可採計日期**：格式為 `YYYY/MM/DD`、可解析為實際日曆日、且**不晚於 build 當日**。實測 `資料更新時間` 18,736 筆全部符合。

| 情形 | 處置 |
|---|---|
| 格式不符或不可解析 | 不可採計。record 保留、標記 `dateUnparsed`、原值照顯示、記入 QA report |
| 空值 | 不可採計。標記 `dateMissing` |
| **晚於 build 當日** | **不可採計**。標記 `dateFuture`、warning、原值照顯示，且**排除於 `latestSourceDate` 選擇與全站 `sourceUpdatedAt`** |
| 某 Trial 無任何可採計日期 | `latestSourceDate=null`、`dateUnknown=true`、`latestCohort` = 全部 recordId |

**未來日期不得支配卡片。** 這是在 Codex 給的兩個選項中明確選定：單筆打錯的 `2099/01/01` 若參與 latest 選擇，會永久遮蔽該試驗所有正常紀錄並讓卡片以它的值代表 Trial——那是最高風險（誤導）。改為排除於選擇、但該紀錄仍出現在歷史並標記「日期超出合理範圍」。實測目前 0 筆。

全站 `sourceUpdatedAt` 只由可採計日期計算；被排除的原值記入 QA report。

`試驗預計執行期間` end < start（實測 **7 列**）→ warning，兩值都原樣顯示並標記「期間起迄順序異常」，**不自動交換、不隱藏**。

### 6.6 sentinel 與數值解析

| 型別 | 實測 sentinel | 資料層 | UI |
|---|---|---|---|
| 分類（`臨床試驗期別`、`本臨床試驗規模`） | `"0"` 各 156／266 筆 | typed value = `null`，**raw 值保留於 SourceRecord** | 顯示「未提供」；**不進篩選選單、不進 facet** |
| 數值（`全球預計受試者人數`、`台灣預計受試者人數`） | `"0"` 1,080 筆 | 見下表 | 見下表 |
| 文字（`納入條件`、`排除條件`、`主要評估指標` 等） | `N/A` 469／`NA` 67／`NA` 42／`NA` 61 | 保留原文，`N/A`／`NA`／`""` **互相可區分** | 原文照顯示；QA report 分別計數 |

**數值欄位的完整解析規則**（v0.3 未定義，導致驗收條件反過來創造規則）：

| 原值 | typed value | 旗標 | UI | 分級 |
|---|---|---|---|---|
| 純十進位整數（含 `0`） | 該整數 | `sourceZero: true`（僅當為 0） | 數字；為 0 時顯示「0（來源填 0）」，**不得**呈現為「確定沒有受試者」 | 正常 |
| 空字串 | `null` | `numericMissing` | 「未提供」 | 正常 |
| 非空但無法解析為整數（含千分位、範圍、文字） | `null` | `numericUnparsed`，raw 保留 | 顯示 raw 原值 + 「數值格式未辨識」 | **warning** |
| 負數 | `null` | `numericImplausible`，raw 保留 | 顯示 raw 原值 + 「數值超出合理範圍」 | **warning** |

三類 sentinel 均保留 raw 值可稽核。

## 7. 呈現層

### 7.1 各功能使用哪一層

| 功能 | 資料層 |
|---|---|
| 結果卡欄位 | `displayFields` ＋ `latestAmbiguous`／`dateUnknown`／`protocolNonIdentifier` 標記 |
| 篩選 | `displayFields`。衝突欄位的 trial 在該維度歸入「同日多筆不一致」分組，**不任取一值** |
| 統計卡 | 以 **Trial** 為分母並明寫「試驗」；衝突、sentinel、`protocolNonIdentifier` 各歸入明確的「未提供／不一致／未提供編號」類別。另可提供以「審查紀錄」為分母的次要統計，須明確標示分母 |
| 搜尋 | 依使用者選定的 **scope**（§8.5），預設為「最新 cohort × 短欄」 |
| 詳情頁 | 全部 `recordIds` |

### 7.2 命中標示

搜尋結果必須標示命中的**欄位名**與**來源紀錄**：

- 命中紀錄有可採計日期 → 標示該日期；命中來自非最新 cohort 時，卡片標示「命中來自 YYYY/MM/DD 的審查紀錄」。
- 命中紀錄**無可採計日期** → 標示「資料日期不明」，**不得偽造成合法日期**、不得省略標示。
- **不得**把非最新紀錄的命中值歸到最新紀錄上顯示。
- 多欄同時命中時須列出**全部**命中欄位，不得只列第一個。

### 7.3 版本歷史：不做方向性 diff

依日期分組列出完整來源紀錄，使用者點選查看原文；日期之間可標示「哪些欄位存在不同值」，**不產生方向箭頭**；同日多筆明示「順序未知」；無可採計日期者置末並標示「資料日期不明」。

理由：日期平手時沒有可靠順序，`20 → 30` 的箭頭可能寫反（實測 21 組人數衝突正是同日平手）。

### 7.4 URL state schema

canonical query string 的參數、順序與編碼如下。**canonical 形式 = 只輸出非預設值的參數，依本表順序排列，值以 `encodeURIComponent` 編碼。**

| 參數 | 值域 | 預設 | 備註 |
|---|---|---|---|
| `q` | 字串 | 無 | 搜尋字串（raw，不預先正規化） |
| `trial` | trialId | 無 | 詳情頁 canonical 入口 |
| `protocol` | raw protocol | 無 | 別名；以 **identity normalization 後**比對，命中後 **client-side 導向 canonical `?trial=`**；`protocolNonIdentifier` 的值不接受 |
| `phase` | 多值 | 無 | 同維度多選 |
| `scale` | 多值 | 無 | 同維度多選 |
| `applicant` | 多值 | 無 | 值為 raw 申請者字串 |
| `enroll` | bucket id 多值 | 無 | 見 §8.4 |
| `period` | `YYYY-MM-DD..YYYY-MM-DD` | 無 | 試驗預計執行期間 |
| `updated` | `YYYY-MM-DD..YYYY-MM-DD` | 無 | 資料更新時間 |
| `fields` | `short` \| `all` | `short` | 搜尋欄位 scope（§8.5） |
| `history` | `latest` \| `all` | `latest` | 搜尋歷史 scope（§8.5） |

規則：

- **重複參數**：同維度多值以重複參數表達（`phase=X&phase=Y`），值依字典序排列後輸出。
- **未知參數**：忽略但保留於 URL 不改寫（避免與未來版本打架）。
- **無效值**（不在值域內的 phase、格式錯誤的日期區間、未知 trialId／protocol）→ 顯示明確訊息與回搜尋入口，**不得空白頁、不得靜默回首頁、不得靜默丟棄該條件**。
- **scope 必須編碼進 URL**，否則分享的連結重現不出同一結果集。

## 8. 搜尋規格

### 8.1 search normalization（與 §6.2 獨立）

依序：`strip` → `NFKC` → `casefold` → 內部連續空白壓為單一空格。**不做**標點移除、不做連字號正規化。

（註：NFKC 會把全形數字折成半形，這是**等價**而非誤命中；v0.2 把它列為誤命中反例是錯的。）

### 8.2 matching operator

- query 以**空白切分**為 terms（切分前先套 §8.1）。
- 每個 term 對正規化後的欄位文字做 **substring 比對**（中文無空白，token 化不可行）。
- **空查詢或純空白查詢 → 不執行搜尋**，顯示瀏覽狀態（全部 Trial 依 `latestSourceDate` 降序），不視為「命中全部」。
- 不做 prefix-only、不做模糊比對、不做同義詞擴展。

### 8.3 多詞語意

每個 term 只要命中**任一**在 scope 內的可搜尋欄位即該 term 成立；**同一個 SourceRecord 內全部 term 成立**才算該 record 命中（**record 層 AND，欄位層 OR**）。

**兩個 term 分別命中同一 Trial 的不同 SourceRecord 時不算命中**——那是 Trial 層 AND，會大幅多報。

### 8.4 篩選維度、值域與組合語意

| 維度 | typed value | null／衝突歸類 |
|---|---|---|
| `phase` | `臨床試驗期別` 的 7 個合法值（`Phase Ⅰ`／`Ⅱ`／`Ⅲ`／`Ⅳ`／`Phase Ⅰ,Phase Ⅱ`／`Phase Ⅱ,Phase Ⅲ`／`其他`） | `"0"` → 未提供；衝突 → 不一致 |
| `scale` | `多國多中心`／`台灣單中心`／`台灣多中心` | 同上 |
| `applicant` | raw 申請者字串 | 空 → 未提供；衝突 → 不一致 |
| `enroll` | `台灣預計受試者人數` bucket：`0`（等於 0）、`1-10`、`11-30`、`31-100`、`101-`；區間為**閉區間** | `null` → 未提供；衝突 → 不一致 |
| `period` | `試驗預計執行期間起` ≤ 區間末 且 `迄` ≥ 區間首（**重疊**語意，非包含） | 任一端不可解析 → 未提供 |
| `updated` | `latestSourceDate` 落於閉區間內 | `dateUnknown` → 未提供 |

**組合語意**：**同維度多選 = OR，跨維度 = AND。** 「未提供」與「不一致」是每個維度的可選值，選中時只回傳該類 trial。

篩選**不存在**招募／執行狀態維度——filter schema、DOM 控制項、URL parser、輸出 state 四處皆不得有。

### 8.5 搜尋 scope 分層（實測驅動）

v0.3 同時要求「搜尋涵蓋全部歷史紀錄」「7 個可搜尋欄位」「初始 payload ≤1.5 MB gzip」——實測三者**不可能同時成立**：

| 索引範圍 | gzip |
|---|---:|
| 最新 cohort × 5 短欄 | **601 KiB** |
| 全部紀錄 × 5 短欄 | 1,649 KiB |
| 最新 cohort × 2 長欄 | 2,044 KiB |
| 最新 cohort × 7 欄 | 2,607 KiB |
| 全部紀錄 × 2 長欄 | 5,389 KiB |
| 全部紀錄 × 7 欄 | 6,958 KiB |

因此搜尋分為兩個獨立的 scope 維度，**預設為最小者**：

- **短欄（`fields=short`，預設）**：`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗申請者`、`適應症中文`、`TFDA收文號`
- **全欄（`fields=all`）**：另加 `試驗目的`、`主要評估指標`
- **最新（`history=latest`，預設）**：只搜 `latestCohort` 內的 record
- **全部（`history=all`）**：搜全部 record

索引載入：

| scope | 額外載入 | 實測 gzip |
|---|---|---:|
| `short` + `latest` | 無（併入 `trials-index`） | 0 |
| `all` + `latest` | 長欄索引（最新 cohort） | 2,044 KiB |
| `short` + `all` | 短欄索引（全部紀錄） | 1,649 KiB |
| `all` + `all` | 上述兩者 + 長欄索引（全部紀錄） | 1,649 + 5,389 KiB |

**UI 硬性要求**（避免把預設縮小變成靜默漏報）：

- 擴大 scope 的兩個控制項必須**在搜尋結果區可見**，不得藏在設定或選單深處。
- 切換前**顯示需下載的大小**（由 manifest 提供實際位元組數，非寫死）。
- 結果區必須持續顯示目前 scope，例如「目前搜尋範圍：試驗名稱等 5 欄、僅最新審查紀錄」。
- 零結果時，必須提示可擴大的 scope 與其大小。
- 載入失敗 → 退回上一個 scope 並說明，**不得靜默維持舊結果集**。

## 9. ETL、發布與輸出契約

### 9.1 管線

```
下載至 temp（正式 artifact 不動）
→ HTTP 驗證 → ZIP 完整性 → UTF-8-BOM 解碼 → 16 欄欄名與順序、列寬驗證
→ 控制字元檢查 → 正規化（保留 raw）→ identity 收斂為 Trial + SourceRecord
→ 三層碰撞偵測 → 產生全部 artifact 至 staging
→ 整體 digest 與 referential integrity 驗證
→ promotion（§9.2）
```

### 9.2 發布契約

v0.3 聲稱「git commit 是原子發布邊界」，這**只對了一半**。commit 對 repository tree 確實是原子快照，但不能保證：(a) 中途崩潰時 working tree 完整；(b) 瀏覽器或 CDN 不跨版本混用固定 URL 的檔案。以下分開處理。

#### 9.2.1 保證下在正確的邊界

CI runner 的 working tree 是**用後即棄、無任何讀者**。因此保證改為：

> **被 commit 並 push 出去的 tree 永遠是完整一致的；不存在部分發布的 commit。**

**不再聲稱** working tree 在中途失敗後「整體等於舊版」——逐檔替換做不到這件事，而 commit 的原子性不回復 working tree。

作法：全部 artifact 先寫進 staging 目錄並通過整體驗證；替換 `public/data/`、`git add -A`、`git commit` 收攏為管線**最後三個步驟**；任一步失敗即非零 exit，runner 隨即丟棄。

#### 9.2.2 跨檔版本綁定（解決瀏覽器／CDN 混用）

所有 artifact 採**內容雜湊檔名**，由單一版本化入口解析：

- `manifest.json` 是**唯一固定 URL**，`Cache-Control: no-cache`（每次驗證）。
- 其餘全部檔案帶內容雜湊（`trials-index.<hash>.json`、`records/ab.<hash>.json`…），`Cache-Control: public, max-age=31536000, immutable`。
- manifest 內含 `datasetVersion` 與所有檔案的雜湊路徑；**一次前端資料載入只能解析同一個 manifest 版本**。
- 每個非 manifest 檔案的 top-level 都含 `datasetVersion`；前端載入後**斷言等於 manifest 的值**，不符即 fail-closed，顯示「資料版本不一致，請重新載入」，**不得混用**。
- 舊雜湊檔案留在使用者快取中但已無人引用，不需清理。

#### 9.2.3 部署鏈

- Cloudflare Pages 以 `main` 的 commit SHA 建置；**該 commit 即 build 輸入的唯一來源**。
- 部署啟用（activation）成功後該版本才是 authoritative；啟用失敗時**前一個成功部署仍為 authoritative**，資料不回退、不混合。
- 部署失敗須產生通知；下一次月更新的 baseline 仍以「最後一個成功發布快照」為準（§9.7）。

### 9.3 輸出契約

```
public/data/
  manifest.json                        固定 URL
  trials-index.<hash>.json
  stats.<hash>.json
  search-short-all.<hash>.json         全部紀錄 × 5 短欄（按需）
  search-long-latest.<hash>.json       最新 cohort × 2 長欄（按需）
  search-long-all.<hash>.json          全部紀錄 × 2 長欄（按需）
  records/<00..ff>.<hash>.json
qa/
  schema-report.json
  quality-report.json
  collision-report.json                僅在碰撞時產生
```

**`manifest.json`**（全部欄位 required，`null` 僅在標注處允許）：

```json
{
  "schemaVersion": 1,
  "datasetVersion": "<16 hex>",
  "sourceDatasetId": 205,
  "sourceUpdatedAt": "YYYY-MM-DD | null",
  "fetchedAt": "<ISO-8601>",
  "builtAt": "<ISO-8601>",
  "sourceSha256": "<64 hex>",
  "trialCount": 5888,
  "recordCount": 18736,
  "bootstrap": false,
  "files": {
    "trialsIndex":      { "path": "trials-index.<hash>.json", "bytes": 0, "gzipBytes": 0 },
    "stats":            { "path": "stats.<hash>.json", "bytes": 0, "gzipBytes": 0 },
    "searchShortAll":   { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "searchLongLatest": { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "searchLongAll":    { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "recordShards":     { "00": { "path": "records/00.<hash>.json", "bytes": 0, "gzipBytes": 0 } }
  }
}
```

`files[*].gzipBytes` 是 §8.5 的 UI 顯示下載大小的來源，**不得在前端寫死**。

**`trials-index.<hash>.json`**：

```json
{
  "datasetVersion": "<16 hex>",
  "trials": [ /* Trial，依 trialId 昇序 */ ]
}
```

`Trial` 為 §6.4 的結構，另含 `searchShortLatest`（該 Trial 最新 cohort 各 record 的 5 短欄正規化文字），使 `short`+`latest` scope 不需額外檔案。

**`stats.<hash>.json`**：

```json
{
  "datasetVersion": "<16 hex>",
  "denominators": { "trials": 5888, "records": 18736 },
  "facets": {
    "phase": {
      "denominatorKind": "trials",
      "buckets": [ { "value": "Phase Ⅲ", "count": 0 } ],
      "unprovided": 0,
      "conflicted": 0
    }
  }
}
```

每個 facet 的 `buckets` 計數 + `unprovided` + `conflicted` **必須等於** `denominators.trials`。

**搜尋索引檔**：

```json
{
  "datasetVersion": "<16 hex>",
  "fields": ["purpose", "primaryEndpoint"],
  "records": [ { "r": "<recordId>", "t": "<trialId>", "d": "YYYY-MM-DD | null", "f": ["<正規化文字>"] } ]
}
```

`f` 的順序對應 `fields`。`d` 為 `null` 表示該 record 無可採計日期（供 §7.2 標示「資料日期不明」）。

**`records/<shard>.<hash>.json`**：

```json
{
  "datasetVersion": "<16 hex>",
  "records": { "<recordId>": { "raw": { "<16 欄欄名>": "<raw 值>" }, "typed": { }, "flags": [ ] } }
}
```

**不變量**：

- 排序 total order：`trials` 依 `trialId` 昇序；`recordIds` 依（可採計日期降序、不可採計置末、`recordId` 昇序）。
- referential integrity：每個被引用的 `recordId` 存在於 `trial.shard` 指定的 shard；每個 record 被**恰好一個** Trial 引用；`manifest.files` 列出的檔案集合**等於** `public/data/` 的實際檔案集合。
- **整體 digest** = 對 `manifest.files` 全部路徑（依路徑字典序）的 `sha256(檔案位元組)` 串接後再取 sha256，**不含** `manifest.json` 自身。
- `datasetVersion` = 整體 digest 的前 16 hex。
- schemaVersion 升級：欄位移除、改名、型別或語意變更須 bump；純新增可選欄位不 bump。判準是「舊版前端讀到新資料會做什麼」。

### 9.4 `builtAt` 與「無變動不發布」

`builtAt` = **目前已發布 artifact 的建置時間**，不是本次 workflow 執行時間。

**no-change 比較的排除清單**：`builtAt`、`fetchedAt`、**`sourceSha256`**。

排除 `sourceSha256` 的理由：上游若以相同資料重新打包，ZIP metadata 或列序變動會改變 source SHA 而正規化資料不變；把它算進比較會每月產生噪音 commit。`sourceSha256` 是 provenance 不是資料，每次抓取的值記入 QA report 以保留追溯。

若排除上述三欄後其餘輸出的**整體 digest 相同** → 不發布、不 commit，`builtAt` 與 manifest 均不變。

UI 標籤須與此語意一致：顯示「資料建置時間」，**不得**顯示為「最後檢查時間」。

### 9.5 失敗分類

只接受最終 HTTP 狀態 `200`。content-type 以 `;` 前的 MIME 比對等於 `application/zip`（允許參數，如 `application/zip;charset=utf-8`）。

| error code | 層 | 觸發 |
|---|---|---|
| `HTTP_STATUS` | transport | 任何非 200 的最終狀態（含 4xx／5xx／429） |
| `HTTP_TIMEOUT` | transport | 連線或讀取逾時 |
| `HTTP_TRUNCATED` | transport | 實收位元組與 `Content-Length` 不符，或下載中斷 |
| `UPSTREAM_ERROR_PAGE` | transport | 200 但 MIME 非 zip |
| `ZIP_CORRUPT` | archive | ZIP 結構或 CRC 失敗 |
| `ZIP_NO_CSV` | archive | ZIP 內無 `.csv` |
| `CSV_DECODE` | decode | UTF-8 解碼失敗 |
| `SOURCE_CONTROL_CHAR` | decode | 欄位含 `U+001F`（§6.3） |
| `SCHEMA_MISMATCH` | schema | 欄名集合或順序與 16 欄不符；**detail 須載明 missing／extra／order 三類差異** |
| `ROW_WIDTH` | schema | 列寬不符超過門檻 |
| `ZERO_ROWS` | content | schema 通過但 0 資料列 |
| `ROWCOUNT_DROP` | content | 驟降超過門檻（§9.6） |
| `IDENTITY_COLLISION` | content | §6.2 的正規化碰撞 |
| `ID_TRUNCATION_COLLISION` | content | §6.3 的 trialId／recordId 截短碰撞 |
| `INTEGRITY_DIGEST` | publish | 整體 digest 或 referential integrity 失敗 |
| `PROMOTION_FAILED` | publish | 替換、`git add`、commit 或 push 失敗 |

**移除了 `SCHEMA_COLUMN_RENAMED`／`MISSING`／`EXTRA` 三個分立 code**：欄位 rename 同時滿足 missing 與 extra，無客觀判定方式，把它列為獨立必然 code 會讓真實異常拿到不穩定的 code。改為單一 `SCHEMA_MISMATCH` 攜帶 detail。

**多重失敗的 precedence**（由外而內，先觸發者勝）：`transport` → `archive` → `decode` → `schema` → `content` → `publish`。

每個 code 對應**相異的 exit code**。stderr 訊息只作輔助，**不得以「訊息含某字串」作為測試判定**。

失敗絕不回空陣列。抓取失敗與「官方回覆空集」必須分辨：目前 205 無 sentinel 列，0 資料列一律走 `ZERO_ROWS` 硬失敗。

### 9.6 驟降門檻與 warning 的落點

分母 = 上一個**成功發布快照**的來源資料列數 `prev`；`drop = (prev - cur) / prev`，以有理數比較，**不四捨五入**。

| 條件 | 結果 |
|---|---|
| `drop > 0.20` | 硬失敗 `ROWCOUNT_DROP`，不發布 |
| `0.10 < drop ≤ 0.20` | warning，發布 |
| `drop ≤ 0.10` | 正常發布 |

恰好 `20.0%` 屬 warning（邊界為**嚴格大於**）。首次無 baseline → bootstrap 模式：不做驟降比較，要求列數 ≥1 且 schema 通過，manifest 記 `bootstrap: true`，**不假裝完成比較**。

**所有 warning 必須出現在 `qa/quality-report.json` 的結構化欄位中**（含 code、計數、範例 recordId），不得只印在 log——否則「只在 log 印一行」就能通過驗收，且前端與後續 build 無法消費。

### 9.7 併發、baseline 與重入

- `schedule` 與 `workflow_dispatch` **共用同一 concurrency group**，`cancel-in-progress: false`（排隊而非取消）。
- **不得取消已進入 promotion 階段的 run。**
- **baseline 取樣時點為取得發布權之後**：GitHub 的 `concurrency` 讓後到的 run 排隊，但 `actions/checkout` 預設取**觸發時的 SHA**，不是排隊結束時的分支 tip。因此取得發布權後必須**顯式 fetch 並 checkout 預設分支最新 tip**，再據此決定 baseline。
- **promotion 前須再次驗證**正式版本自 baseline 取樣以來未變；不符即 fail-closed（不覆蓋前一個 run 的結果）。

## 10. 風險權重與免責

風險排序：**誤導 > 資料正確性 > XSS**（無登入、無 session、無使用者資料，XSS 竊取不到憑證）。寧可漏報不可誤報。

免責須在首頁、結果頁、詳情頁**可見**（可見性定義綁定 §11 G1／G2 的 viewport、尺寸與對比 oracle，不只是 DOM visibility），且必須表達三項核心性質：

1. 本站**不提供目前招募狀態**；
2. TFDA 審查／試驗使用**不等於藥品已獲上市核准**；
3. 試驗狀態與收案資格**須向官方資料來源、試驗執行機構與醫療專業人員確認**。

## 11. 驗收條件

全部 fixture 為**凍結**資料，不從活資料抽樣；凍結時母體不可縮成剛好等於子集。每條驗收都須能回答「什麼弱化實作會通過這條但功能其實是壞的」。

### A. 資料模型與收斂

- **A1** 寫死**每個來源列 fingerprint → trialId 的 group membership**（不只總數）。「不應合併」的反例須採用 §6.2 **明確不折疊**的差異——連字號有無（`MK-3475-158` / `MK3475-158`）、空格有無（`9785-CL- 0123` / `9785-CL-0123`）、括號閉合（`ROR-PH-301(APD811-301` / `...301)`）；**不得**使用大小寫或全半形差異，那些依 §6.2 會折疊、依 A7 應為 `IDENTITY_COLLISION`。另須有「應合併」案例（同一 raw protocol 多列）。
- **A2** fixture 每個案例附明確 oracle（所屬 group、record 數、`latestAmbiguous`、`dateUnknown`、`conflictFields`、`displayFields`、raw 保存、預期 error／warning）。**必含**：≥1 個 10 列以上 protocol、≥1 組 16 欄全同純重複、≥2 筆完全相同的空 protocol 列、≥3 組同日衝突、≥1 組同日但正規化後全同、≥1 組同日僅空白／全半形差異（須判為**不衝突**）、≥1 筆 `TFDA收文號="移案BPA"`、≥1 筆收文號重複、≥1 個 `nearDuplicateGroup`、≥1 筆 `protocolNonIdentifier`。**四類日期異常各 ≥1**：不可解析、空值、未來日期、`試驗預計執行期間` end<start；每類附完整 Trial 與 UI oracle。
- **A3** 對 reverse 與 ≥3 個固定 seed 的排列，外加涵蓋「重複列 × 平手 × 空 protocol」交叉組合的 property invariant：先斷言輸出**檔案 inventory 完全相同**，再逐檔 SHA-256 相同，再斷言每個 tie case 的語意結果相同。
- **A4 反向哨兵** 把同日處置改為「任取 cohort 第一筆為 latest」時，須斷言失敗發生在**指定 tie group 的 `latestAmbiguous` 由 true 變 false**，且 mutation oracle 須涵蓋 `displayFields`、篩選分組與統計輸出——只保留 ambiguity 旗標但把第一筆值偷偷放進 `displayFields` 或 stats 的實作必須被殺死。
- **A5** 比對來源 canonical fingerprint 的**完整 multiset 含 multiplicity**。oracle 的 row identity 必須**獨立於 §6.3 的 canonical serialization**（否則兩邊共用同一個非一對一實作會一致地漏列而自我驗證），並含分隔符／長度前綴的邊界 fixture。
- **A6** 兩筆完全相同的空 protocol 列須各自取得唯一 ID、multiset 完整保留、多排列輸出一致。
- **A7** 注入兩個不同 raw protocol 但 identity 正規化後相同的列（如僅大小寫或全半形不同）→ 必須以 `IDENTITY_COLLISION` 硬失敗，且 `collision-report.json` 須**唯一定位**每個 collision group、全部相關 raw protocol、identity-normalized 值與來源 fingerprint。**空 report 或只含 code 的 report 必須使測試失敗。**
- **A8** 注入不同 identity key 但 trialId 前 16 hex 相同的 fixture → 必須以 `ID_TRUNCATION_COLLISION` 硬失敗；recordId 同理。
- **A9** `nearDuplicateGroup` 偵測：斷言 18 組實測案例全部被偵測、`protocolNonIdentifier` 的值**不被**歸入任何 group、且偵測用的 loose key **不影響**任何 Trial 的收斂結果（以 A1 的 group membership 再驗一次）。

### B. ETL 與發布可靠性

- **B1** §9.5 **每一個** error code 各有測試，斷言：(a) 非零且相異的 exit code；(b) 已發布狀態未變（完整檔名集合、每檔 SHA-256、`manifest.files` 指向、整體 digest 均不變）；(c) **無新增正式檔**。content-type 須測 `application/zip;charset=utf-8`（通過）與 `text/html`（失敗）。
- **B2** 每個案例寫死 structured error code 與 layer；**不得**以 stderr 字串判定。另須有**多重異常** fixture（如同時 transport 中斷與 schema 不符）驗證 §9.5 的 precedence。
- **B3** 斷言 CSV schema **已通過後**才因零列失敗，明確回傳 `ZERO_ROWS`，且已發布 digest 不變。
- **B4** 門檻案例須含 `drop` = 0.0／0.10／0.1001／**0.20**／0.2001／整數列數邊界／首次無 baseline（bootstrap）。逐案例斷言 warning／success／hard-failure 與**是否發布**，且 warning 須出現在 `qa/quality-report.json` 的結構化欄位（只印 log 必須失敗）。
- **B5** 失敗注入點須涵蓋**每一個正式狀態變更之後**：替換第一個／部分／最後一個 artifact 後、刪除 orphan artifact 途中、`git add` 只含部分變更、commit 失敗、commit 成功但 push 失敗、push 成功但部署啟用失敗，以及**非例外式終止**（SIGTERM／取消）。每個點斷言：**不存在部分發布的 commit**；已 push 的 tree 整體等於舊版或整體等於新版，不允許第三種 digest。
- **B6** referential integrity 反例各自獨立：record 被兩個 Trial 引用、同一 Trial 重複引用同一 record、record 放錯 shard、`manifest.files` 與實際檔案集合不符、Trial 引用不存在的 recordId → 全部須 `INTEGRITY_DIGEST` 硬失敗。
- **B7** 跨版本綁定：注入「manifest 為新版但某 shard 為舊 `datasetVersion`」的情境 → 前端須 fail-closed 顯示「資料版本不一致，請重新載入」，**不得**混用渲染。另斷言除 `manifest.json` 外所有檔名都帶內容雜湊、且 manifest 為唯一固定 URL。

### C. Sentinel 與數值解析

- **C1** **兩個**分類欄位（`臨床試驗期別`、`本臨床試驗規模`）**各自**通過五處斷言：typed value 為 `null`、raw 值仍等於 `"0"`、`stats.json` 的 facet 不含 `"0"`、實際 filter DOM 不含該選項、卡片／詳情顯示「未提供」。
- **C2** 依 §6.6 的數值解析表，對 `0`／正整數／空字串／無法解析（含千分位與文字）／負數**逐筆**斷言 typed value、旗標真值、warning 分級與 UI 文字。`sourceZero` 只在值為 0 時為 true（對所有數字都設 true 的實作必須失敗）。
- **C3** 寫死 `N/A`／`NA`／`""` 三類的**精確計數與對應 recordId**，並斷言詳情切換到該 record 後的**可見文字精確相等**。
- **C4 反向哨兵**（三個**獨立**且**確為違規**的 mutation；**不得**使用「分類 typed value 轉 null」，那是 §6.6 規定的正確行為）：
  1. 分類 sentinel 的 **raw 值遺失** → C1 的 raw 斷言須失敗
  2. `stats.json` 的 facet **保留 `"0"`** → C1 的 facet 與 filter DOM 斷言須失敗
  3. 文字 sentinel `N/A`／`NA`／`""` **塌成同一值** → C3 須失敗

### D. 搜尋與篩選

- **D1** §8.5 短欄的 5 個欄位與全欄的 2 個欄位**各有唯一 canary** 與精確 expected trialId 清單；**另有 9 個不可搜尋欄位的負面 canary**（誤把它們納入索引必須失敗）。多欄同時命中時命中標籤集合須**完全相等**。
- **D2** 逐欄寫死 §8.1 policy 與 §8.2 operator，fixture 以 `shouldMatch`／`mustNotMatch` pair 表達，**不依賴人工裁決**。須含 substring／prefix／完整詞的邊界正反例（證明是 substring 而非 prefix-only）、中文無空白字串、空查詢與純空白查詢（須**不執行搜尋**）。identity 與 search normalization **分開驗證**，須有「identity 不合併但 search 命中」的案例證明兩者未共用實作。
- **D3** 對同一查詢寫死完整結果集合，須含：兩詞同欄正例、兩詞跨欄正例、只命中其中一詞的必排除負例，以及**兩詞分別命中同一 Trial 的不同 SourceRecord 的必排除案例**（Trial 層 AND 冒充 record 層 AND 必須被抓到）。
- **D4** 每個正式 filter 維度至少一組，**另加**同維度多選（OR）、跨維度組合（AND）、每個 bucket 的閉區間端點、`period` 的重疊語意邊界、重複 query param、未知 param、無效值。斷言結果 trialId 清單逐一相同且順序相同、**canonical URL 字串精確相等**、reload 後控制項狀態精確相等。
- **D5** 以**封閉的 filter schema 與 DOM selector invariant** 為主 oracle：斷言 filter schema、DOM 控制項、URL parser、輸出 state 四處均不存在 trial-status 維度。列舉中文同義詞（「收案情形」「招募」「可報名」）只作 mutation guard，**不作為主要判定**（同義詞不是封閉集合，無法形成可證偽測試）。
- **D6** **每一個可篩選且可能衝突的欄位**（phase、scale、applicant、enroll、period）各有一組 `latestAmbiguous` oracle，斷言該 trial 歸入「不一致」分組且**不出現**在任一具體值的篩選結果中。
- **D7** scope 切換：斷言四種 scope 組合各自的結果集、URL 的 `fields`／`history` 參數可重現、切換前顯示的大小取自 `manifest.files[*].gzipBytes`（**非前端寫死**）、scope 指示文字持續可見、零結果時提示可擴大的 scope、索引載入失敗時退回上一個 scope 並顯示說明（**不得靜默維持舊結果集**）。

### E. 呈現與誤導防範

- **E1** 以「**允許呈現的狀態概念封閉清單** + §10 三項免責文句的正向精確斷言」為主 oracle；禁字（「招募中」「開放收案」「可報名」）只作 mutation guard。**不對來源原文設無條件禁字**（`納入條件` 裡合理出現 `active`）。
- **E2** 由**實際 DOM／card schema 反向比對** oracle inventory：任何存在於 DOM 但不在 oracle 清單中的統計卡**必須使測試失敗**。每張卡寫死精確值、單位、分母類型；各 facet 的 `buckets + unprovided + conflicted` 須等於 `denominators.trials`。
- **E3** 斷言各 label 對應**精確 fixture 值**（來源 `資料更新時間` 對應 record、`builtAt` 對應 manifest），且覆蓋首頁、結果頁、詳情頁與 record 切換後——只斷言「兩者不相等」會讓互換值的實作通過。
- **E4** 建立**來源資料可到達的輸出 surface 封閉 inventory**（卡片、詳情、record 切換、filter option、搜尋命中標籤、統計 label、accessible name、URL 顯示），逐一測 XSS fixture（`<script>`、`"><img onerror=...>`、含引號與角括號）：斷言以可見 text 呈現、未生成由來源控制的元素或 event handler、執行觀察值（注入 counter）不變。
- **E5** 逐頁斷言 §10 三項核心性質的**可見文字**，可見性綁定 G1／G2 的 viewport、最小字級與對比 oracle（極小字、遮蓋、低對比必須失敗）。
- **E6** inclusion 與 exclusion **各**有長 fixture（含 22,490 字元案例）：展開後換行正規化後**全文精確相等**、首尾 canary 存在、切換 record 後亦相符。
- **E7** `latestAmbiguous=true` 的卡片須顯示「同日多筆資料不一致」；對**全部衝突候選值**做等價檢查——斷言候選值不出現在卡片的可見文字、accessible name、attribute 或 data-state 中（含**截斷與正規化後**的形式）。詳情頁須顯示「順序未知」。
- **E8** `dateUnknown=true` 的卡片顯示「資料日期無法辨識，請查官方來源」；`protocolNonIdentifier=true` 顯示「來源未提供計畫書編號」且 `?protocol=` 不接受該值；`nearDuplicateGroup` 非空時詳情頁顯示近似編號提示與連結。

### F. 效能（分層預算）

- **F1** **Tier 0（預設 scope 的冷啟動）≤1.0 MB gzip**。定義為「冷啟動到**可搜尋 readiness**」的全部 network responses：readiness 以**功能性 probe** 判定——執行一個固定查詢並取得正確結果集，才算就緒（避免過早宣告就緒把索引移到量測窗外）。以 production build 與固定 gzip 設定量測，列出納入檔案清單與總和寫入 CI artifact。實測基線：`trials-index` 715 KiB + 短欄索引 601 KiB（高度重疊，合併後約 715–900 KiB）。
- **F2** 各按需 tier 的實測 gzip 上限記錄於規格與 CI artifact（`all`+`latest` 2,044 KiB；`short`+`all` 1,649 KiB；`all`+`all` 另加 5,389 KiB），**不計入 F1**，但超出記錄值 20% 須在 CI 告警。
- **F3** 長文字隔離：在 `納入條件`／`排除條件`／`試驗目的`／`主要評估指標` 放**多筆分散的唯一 canary**（≥5 筆，跨不同 shard），斷言 Tier 0 的全部 response 與 bundle 均不含其**內容**，且**初始 payload 的 schema 不含這些欄位鍵**；只有開啟對應 record shard 或載入對應搜尋 tier 後才出現。（單一 canary 可被特判移除，其餘長文字仍塞進初始 bundle。）
- **F4** 以 production-scale fixture（5,888 Trial／18,736 SourceRecord）與固定查詢 corpus（零結果、極多結果、中文、英文、多詞、protocol）量測；計時自**輸入事件到結果 DOM 完成**；基準環境為 **GitHub Actions runner 類別 + 固定 CPU throttle 倍率**，固定樣本數，判定門檻為 **p95 ≤300 ms**。規格明寫「跨時間比較僅在同 runner 類別內有效」——不假裝取得實驗室級可比性。達不到須寫**瓶頸歸因**，不調鬆數字。

### G. 無障礙

- **G1** 最低 viewport matrix：360×640、390×844、768×1024、1280×800（各含縱向）。除 `scrollWidth ≤ clientWidth` 外，斷言可見文字、表單與 focusable elements 的 **bounding box 均在 viewport 內**——`overflow-x:hidden` 造成裁切必須失敗。
- **G2** 規格列出**最低必測的路由 × 狀態矩陣**（首頁／結果／詳情 × default／hover／focus／disabled／warning／`latestAmbiguous`／`dateUnknown`／`protocolNonIdentifier`／零結果／載入失敗），並與實際元件狀態 inventory **雙向對帳**（實際存在但未列入矩陣者須使測試失敗）。每組輸出 selector、前景、背景與 ratio，依 normal/large text 門檻判定並寫入 CI artifact。**當場計算，不憑目視。**
- **G3** 每一類互動元件（搜尋框、各 filter、scope 切換、折疊、record 切換、複製按鈕、近似編號連結）逐項斷言 tab 可達、順序、Enter/Space 行為、focus 不遺失、無 keyboard trap，**並同時斷言 accessible name、role、state 與錯誤訊息關聯**（鍵盤可用但 screen reader 不可用必須失敗）。期別與警示須有可讀文字或 accessible name，不以顏色為唯一線索。
- **G4 條件式** 首版以數字卡與清單為**必須**，圖表為**可選**（M2 依 payload 與 a11y 成本決定）。**若**提供圖表：替代 table/list 須在 **accessibility tree 可達**（`hidden`／`inert` 必須失敗）、具標題與欄名，且 key/value 集合與圖表**實際呈現的資料**精確相等。

### H. CI 與自動化

- **H1** 規格列出**最低 gate 集合**（lint、type-check、pytest、vitest、Playwright、a11y、payload 量測）並與 workflow jobs **雙向對帳**。對每個 gate 注入一個已知失敗，斷言 workflow／job 為 failure；檢查實際執行的命令、觸發分支與 path filter，斷言無 `continue-on-error`。
- **H2** 以同一凍結來源連跑兩次：第二次 git tree、整體 digest 與 HEAD 均不變。**另須測真正的重疊情境**：兩個 run 同時排隊、前一個 run 發布後第二個 run 須**重新 checkout 分支 tip 並重取 baseline**（斷言它沒有沿用觸發時的舊 SHA），以及 promotion 前的版本再驗證會在版本已變時 fail-closed。diff 摘要以獨立 oracle 驗證精確的 additions／removals／modifications。
- **H3** 上線當天手動 dispatch 一次、再跑第二次驗冪等。明定第二次是**重新下載並驗證 source SHA 相同**（不是快取第一次的下載結果），並列出第二次必經的 stage 清單；斷言兩次都完整跑完 pipeline，第二次明確回報 no normalized change 且不產生 commit。
- **H4** 斷言所有**直接與間接** `uses`（含 reusable workflow、container digest）均為不可變 SHA／digest；workflow 預設 `permissions` 為最小／read，只有唯一的資料更新 job 明示 `contents: write`，其他 job 明示無 write。

## 12. 里程碑

- **M0** 本規格通過第三輪限縮覆審（進行中）
- **M1** repo 鷹架與 ETL（A／B／C 驗收）。**M1 前須先封存**：identity 規則（§6.2）、canonical serialization 與 ID 契約（§6.3）、呈現欄位集合與衝突比較模式（§6.4）、日期規則（§6.5）、數值解析（§6.6）、發布契約（§9.2）、輸出契約（§9.3）
- **M2** 前端 MVP（D／E／F／G 驗收）
- **M3** CI 與月更新（H 驗收）＋ Cloudflare Pages 首次部署
- **M4** 收尾：README（含 §6.3 的 ID 穩定性界限）、收進 `pharmacy-portal`、跑 `/codex-review` 以 A1–H4 做規格符合度稽核

## 13. 後續版本（不進本次範圍）

- 上游停更偵測。**不可**以「距今天數」為唯一判準（`資料更新時間` 最新值 2026/08/17 已距今約一個月，稀疏更新是常態）；應以「連續 N 次 build 的 `sourceUpdatedAt` 未前進」為判準。
- 每月變更監測。`no longer present` **不得**自動稱為 terminated。
- 有方向性的版本 diff（需來源提供版號或可靠時間戳）。
- 近似 protocol 的**人工裁決合併表**（由藥師逐組確認後才合併，不自動化）。
- ClinicalTrials.gov cross-link（以 NCT ID／protocol number 精確比對，保留 unmatched／ambiguous）。
- Service worker／離線。若做，快取前綴須限定自家，即使在獨立 origin 上也照規矩寫。
- Email 訂閱（需另評估個資、誤報與營運責任）。

## 14. 修訂紀錄

- **v0.4（2026-09-18）** 依 `plan-verdict-r2.md`（接受 53／部分接受 1／拒絕 0，Blocker 0）改寫。**三項第一輪的偏離被第二輪否決並已改正**：
  - §9.2 重寫。原「git commit 即原子發布邊界」只對一半：新增 §9.2.1 把保證下在「已 commit／push 的 tree」而非 working tree；新增 §9.2.2 **內容雜湊檔名 + `datasetVersion` 綁定 + 快取策略**以解決瀏覽器／CDN 跨版本混用（原修訂完全漏掉）；新增 §9.2.3 部署鏈
  - B5 失敗注入點自 4 個擴為涵蓋每個正式狀態變更、push／部署失敗與非例外式終止
  - 日期規則回復 **High**：新增獨立旗標 `dateUnknown`（解除 §6.4／§6.5 的模型矛盾）、未來日期**排除於 latest 選擇**（原規則會讓單筆 2099 永久支配卡片）、A2 強制含四類日期異常
  - 其餘：§6.3 canonical serialization 改長度前綴確保一對一＋三層碰撞偵測＋`SOURCE_CONTROL_CHAR`＋shard key 更正為第 2–3 字元；§6.4 新增**封閉的 13 欄呈現欄位集合**與衝突比較模式（實測 raw 157 組 vs 正規化 143 組）；§6.6 補數值解析完整規則（原本驗收條件反過來創造規則）；§8.2 補 matching operator；§8.4 補值域與組合語意；§7.4 補完整 URL state schema；§9.3 補逐檔 schema 與整體 digest 定義；§9.4 no-change 比較排除 `sourceSha256`；§9.5 移除無法客觀判定的 `SCHEMA_COLUMN_RENAMED` 並定義 precedence；§9.6 warning 須落在結構化 artifact；§9.7 baseline 取樣時點改為取得發布權之後；C4 三個 mutation 全部改為真正違規的行為（原第一個 mutation 是合規行為）
  - **我方實測新增**：§6.2.1 近似 protocol 的偵測與揭露（18 組，不自動合併）、§6.2.2 protocol 非識別碼值（9 列測試資料與非編號值）、§8.5 **搜尋 scope 分層**——實測 v0.3 的「搜尋涵蓋全部歷史 × 7 欄」為 6,958 KiB gzip，是 F1 預算的 4.6 倍，三項要求不可能同時成立；改為預設短欄＋最新 cohort（約 715–900 KiB）並提供可見的擴大控制項
  - 驗收條件新增 A8、A9、B7、D7、E8、F2；F1 改功能性 probe 判定 readiness；F4 基準環境改 runner 類別 + p95
