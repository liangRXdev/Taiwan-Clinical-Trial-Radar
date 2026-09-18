# Taiwan Clinical Trial Radar — 規格 v0.3（consolidated）

> **這是唯一具規範效力的規格。** `Taiwan-Clinical-Trial-Radar-spec.md` v0.1（2026-09-12）與本檔 v0.2（2026-09-18）均降為歷史文件，**不再具 normative 效力**，不得作為實作或驗收依據。
> 依據：2026-09-18 dataset 205 實測 + Codex 覆審（`plan-review.md`）+ 判定（`plan-verdict.md`）。
> 狀態：**待第二輪覆審**（只審 v0.2 → v0.3 的變更）。尚未寫任何程式碼。

---

## 1. 目標

台灣藥品臨床試驗檢索站。把 TFDA dataset 205 轉成可搜尋、可篩選、可追溯資料日期的靜態網頁，回答：

1. 台灣有哪些經衛福部審查的藥品臨床試驗？
2. 某疾病、試驗名稱、protocol number 或申請者涉及哪些試驗？
3. 試驗期別、規模、期間、預計收案數、主要評估指標與納入／排除條件為何？
4. 公開資料更新到何時、該去哪裡確認最新狀態？

使用者：臨床藥師、醫師、CRC／研究護理師、研究者。單次查詢情境。

## 2. 非目標

- **dataset 206–209 的任何 join**（含以列序、名稱相似度、筆數分組推測關聯）。v0.1 §3.1／§5.1／§8／§9／§14／§18 中所有 206–209、`linkageStatus`、`linkage-report`、`verify_linkage.py`、寄信詢問 TFDA 的要求**一併作廢**。
- 受試者適格性判定；病歷、病況自由文字或任何病患資料輸入。
- 招募狀態顯示或推論。**不保留 feature flag**（見 §4）。
- AI 生成試驗摘要、療效比較、試驗品質評分、risk of bias、證據等級。
- 試驗優先排序或「最適合」推薦。
- 有方向性的版本 diff（`A → B` 箭頭）。見 §7.3。
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
| 不同 protocol | 5,882（另 6 列 protocol 為空） |
| `資料更新時間` | 全部合法 `YYYY/MM/DD`，零空值、零未來日期，範圍 2024/12/20 – 2026/08/17 |
| `試驗預計執行期間` | 格式全合法，但 **7 列 end < start** |
| 單列最長文字 | `納入條件`／`排除條件` 22,490；`試驗目的` 5,512；`主要評估指標` 5,166 |

16 欄（來源順序）：`臨床試驗申請者`、`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`、`TFDA收文號`、`資料更新時間`。

平台限制：純靜態，無後端／DB／認證／runtime API；前端不得解析 166 MB CSV；`data.fda.gov.tw` 從 GitHub Actions 直抓可行，不需 proxy（對 Google IP 回 500 的限制只適用 Apps Script，與 `consumer.fda.gov.tw` 的境外 IP TLS 切斷也不同）；GitHub Actions 月排程 + `workflow_dispatch`；部署 Cloudflare Pages。

## 4. 來源沒有執行狀態

官方資料集頁面列有 `執行狀態`，**實際 16 欄沒有**。這不是抓取失敗，是來源沒給。

- 不提供招募／執行狀態的篩選、標章或排序維度。
- **不保留 `FEATURE_TRIAL_STATUS` 旗標**——永遠關閉的旗標只是一條可被誤開的路徑，且會讓 schema 與 UI 為不存在的功能保留分支。
- 來源若日後新增此欄，走 §9 的 schema 變更與規格修訂流程，不靠現成旗標上線。

**TFDA 審查通過 ≠ 目前正在招募；試驗使用 ≠ 藥品已獲 TFDA 上市核准。** 這兩句是 §10 免責聲明的必要內容。

## 5. 架構決策

### 5.1 只做 dataset 205

206–209 四份匯出檔沒有任何可驗證的 trial identifier，筆數也彼此不一致（512,140／27,774／28,800）。等公務機關回覆是無限期外部依賴，而 205 單檔已足以達成「10 秒找到相關試驗」。

代價：永久放棄藥品、執行機構、ICD-9 適應症關聯。接受。

### 5.2 部署 Cloudflare Pages

不選 GitHub Pages 的理由：`liangrxdev.github.io` 由多個既有工具共用 origin，Cache Storage 不依 service worker scope 隔離，既有專案已踩過跨 repo 互刪快取。獨立 origin 從源頭避開。

### 5.3 技術選型

Python 3.12+（標準 `csv` + 明確 dataclass／Pydantic 驗證）；TypeScript（Vite）；pytest + Vitest + Playwright。純邏輯抽為可 import 函式，供無網路 mock 測試。

## 6. 資料模型

### 6.1 命名：一列是「審查紀錄」，不是「試驗版本」

來源列稱為 **SourceRecord（審查紀錄）**。實測 18,736 列對應 5,882 個 protocol，2,821 個 protocol 有多列（最多 23 列），其中只有 61 組是 16 欄全同的純重複。

**但「一列 = 某一版試驗計畫書」是推論，不是資料證實的事實。** 資料只證明同一 protocol 有多筆審查紀錄。規格與 UI 一律用中性措辭「審查紀錄」，不稱「第 N 版」。

### 6.2 Identity normalization（與搜尋正規化分離）

**identity normalization**（只用於主鍵）：`strip` → `NFKC` → `upper`。**不做**標點移除、不做內部空白壓縮、不做前後綴剝離。

實測：此規則對 5,882 個 protocol 產生 **0 個碰撞**。

若兩個不同的 raw protocol 正規化後相同 → **硬失敗** `IDENTITY_COLLISION`，產出 collision report，不得合併。（fail-closed 而非保留為不同 Trial：合併會誤配，而保留兩個同鍵 Trial 會讓 URL 不唯一；硬失敗使月更新維持 last-known-good，是三者中唯一安全的。）

**search normalization**（只用於查詢比對）另定於 §8.1，與本節規則各自獨立驗證。

### 6.3 Trial ID 與 SourceRecord ID

**canonical serialization**：取 16 個欄位的 **raw 值**（已去 BOM，未經任何正規化），依來源欄位順序，以 `U+001F`（unit separator）連接，UTF-8 編碼。空值序列化為空字串。

**identity key**：

- protocol 非空 → `"P:" + identityNormalize(protocol)`
- protocol 為空 → `"H:" + sha256(canonicalSerialization)`；若多列的 content hash 相同，附加出現序號 `"#k"`（`k` 由 canonical serialization 排序後配置，**不依輸入列序**；因這些列逐位元相同，序號分配在內容上不可區分，輸出仍確定）

**trialId**：`"t" + sha256(identityKey)[:16]`，URL-safe 固定長度。
**recordId**：`trialId + "r" + sha256(canonicalSerialization)[:16]`；完全相同的重複列附 `"#k"`，規則同上。

**ID 穩定性的界限（必須寫進 README）**：這些 ID 只保證**對相同來源快照穩定**。上游若重排、增刪或修改欄位，ID 可能變動；不得宣稱 ID 跨快照代表同一實體。空 protocol 的 hash-based ID 尤其如此。

### 6.4 Trial 結構與同日衝突

```
Trial
  id                trialId
  protocolRaw       該 trial 的 raw protocol 值（identity 正規化後相同者，實測目前皆為單一值）
  latestSourceDate  全部可解析 資料更新時間 的最大值；全部不可解析時為 null
  latestCohort[]    latestSourceDate 當日的全部 recordId
  latestAmbiguous   latestCohort 長度 >1 且「呈現欄位」有衝突時為 true
  conflictFields[]  latestCohort 內有多個不同值的欄位名
  displayFields     latestCohort 內**無衝突**欄位的共同值（可安全顯示）
  records[]         全部 SourceRecord，依日期降序、同日依 recordId 昇序
```

**同日平手不得推定先後。** 來源沒有時間、版號或修訂序號。實測 846 個平手組的處置分布：

| 情形 | 組數 | 處置 |
|---|---:|---|
| 平手列 16 欄全同 | **689（81%）** | `latestAmbiguous=false`，顯示共同值，`records[]` 保留 multiplicity |
| 平手列有實質衝突 | **157（2.7% of 5,882）** | `latestAmbiguous=true`，見下 |

衝突組的實測欄位分布：`納入條件` 74 組（另 12 組僅空白／全形差異）、`試驗預計執行期間迄` 48、`試驗目的` 40、`主要評估指標` 34、`全球預計受試者人數` 22、`台灣預計受試者人數` 21（如 `19` vs `31`、`0` vs `4`）、`臨床試驗計畫中文名稱` 20、`臨床試驗期別` 3（如 `Phase Ⅱ` vs `Phase Ⅰ,Phase Ⅱ`）。

`latestAmbiguous=true` 時：

- 卡片**只顯示無衝突的共同欄位**；衝突欄位顯示「同日多筆資料不一致，請展開確認」，**不得任取一值**。
- 詳情頁並列該日全部紀錄，明示**順序未知**。
- **hash 只用於 cohort 內的穩定排序，不宣稱時間先後。** 不得以完整度或 hash 推定業務新舊。

（曾考慮的「取非空欄位數最多者」實測幾乎無效：846 組中只唯一決出 5 組。已棄。）

### 6.5 日期規則

- 可接受格式：`YYYY/MM/DD`（實測 `資料更新時間` 100% 符合）。
- 不可解析或空值 → **不參與** `latestSourceDate` 與全站 `sourceUpdatedAt` 計算；該 record 仍保留並標記 `dateUnparsed`，原值照顯示。
- 某 Trial 全部日期不可解析 → `latestSourceDate=null`、`latestAmbiguous=true`，卡片不顯示欄位值，改顯示「資料日期無法辨識，請查官方來源」。
- 未來日期（> build 當日）→ warning、記入 QA report、**排除於全站 `sourceUpdatedAt`**，但仍參與 trial 內排序並照原值顯示。實測目前 0 筆。
- `試驗預計執行期間` end < start（實測 **7 列**）→ warning，兩值都原樣顯示並標記「期間起迄順序異常」，不自動交換、不隱藏。

### 6.6 sentinel 依欄位型別分開處理

| 型別 | 實測 sentinel | 資料層 | UI |
|---|---|---|---|
| 分類 | `臨床試驗期別="0"` 156 筆；`本臨床試驗規模="0"` 266 筆 | 判定為 sentinel，typed value 為 `null`；**raw 值保留於 SourceRecord** | 顯示「未提供」；**不進篩選選單、不進搜尋索引的 facet** |
| 數值 | `全球預計受試者人數="0"` 1,080 筆 | **保留為數值 `0`**，加 `sourceZero: true` | 顯示「0（來源填 0）」。**不得**呈現為「確定沒有受試者」或「零收案」 |
| 文字 | `排除條件` `N/A` 469／`NA` 67；`納入條件` `NA` 42；`主要評估指標` `NA` 61 | 保留原文，三者（`N/A`／`NA`／`""`）**互相可區分** | 原文照顯示；QA report 分別計數 |

分類欄位的 `"0"` 不可能是合法期別，放行會讓篩選選單出現垃圾選項。但數值 0 與文字 `NA` 可能是上游真實意思，改寫就是造假。

## 7. 呈現層的資料來源（逐項寫死）

### 7.1 各功能使用哪一層

| 功能 | 資料層 |
|---|---|
| 結果卡欄位 | `displayFields`（僅無衝突共同值）＋ `latestAmbiguous` 標記 |
| 篩選 | `displayFields`。衝突欄位的 trial 在該維度歸入「同日多筆不一致」分組，**不任取一值** |
| 統計卡 | 以 **Trial** 為分母並明寫「試驗」；衝突或 sentinel 的 trial 計入 `未提供／不一致` 類別。另可提供以「審查紀錄」為分母的次要統計，須明確標示分母 |
| 搜尋 | **涵蓋全部 SourceRecord（含歷史）** |
| 詳情頁 | 全部 `records[]` |

### 7.2 搜尋涵蓋歷史時的命中標示

搜尋涵蓋歷史紀錄（漏報成本高於多報），但因此**命中標籤必須指出來源紀錄**：

- 標示命中的**欄位名**與該紀錄的**資料更新時間**。
- 命中來自非最新紀錄時，卡片須標示「命中來自 YYYY/MM/DD 的審查紀錄」。
- **不得**把舊紀錄的命中值歸到最新紀錄上顯示。

### 7.3 版本歷史：不做方向性 diff

- 依日期分組列出完整來源紀錄，使用者點選查看原文。
- 日期之間可標示「哪些欄位存在不同值」，**不產生方向箭頭**。
- 同日多筆明示「順序未知」。

理由：日期平手時沒有可靠順序，`20 → 30` 的箭頭可能寫反——實測 21 組人數衝突正是同日平手。等來源提供版號或可靠時間戳再考慮。

### 7.4 URL 契約

- canonical 詳情 URL：`/?trial=<trialId>`（query param，靜態主機零路由設定，deep link 與重新整理必然可用）。
- 便利別名：`/?protocol=<raw protocol>`，client-side 解析後導向 canonical；protocol 為主鍵故唯一。
- 未知 `trial` 或 `protocol` → 明確顯示「找不到此試驗」與回搜尋的入口，**不得**顯示空白頁或靜默回首頁。
- 搜尋與篩選狀態亦由 query param 表達，可重現。

## 8. 搜尋規格

### 8.1 search normalization（與 §6.2 的 identity 規則獨立）

依序：`strip` → `NFKC` → `casefold` → 內部連續空白壓為單一空格。

**不做**標點移除、不做連字號正規化。（註：NFKC 會把全形數字折成半形，這是**等價**而非誤命中；v0.2 把它列為誤命中反例是錯的。）

### 8.2 可搜尋欄位（7 個）

`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗申請者`、`適應症中文`、`試驗目的`、`主要評估指標`、`TFDA收文號`。

### 8.3 多詞語意

每個詞只要命中**任一**可搜尋欄位即該詞成立；**全部**詞成立才算命中（record 層 AND，欄位層 OR）。UI 須顯示此邏輯。

### 8.4 篩選維度

`臨床試驗期別`、`本臨床試驗規模`、`試驗預計執行期間`、`台灣預計受試者人數` 區間、`臨床試驗申請者`、`資料更新時間`。

**不存在**招募／執行狀態維度——filter schema、DOM 控制項、URL parser、輸出 state 四處皆不得有，中文同義詞（如「收案情形」）亦不得出現。

## 9. ETL 與輸出契約

### 9.1 管線

```
下載至 temp（正式 artifact 不動）
→ HTTP 驗證 → ZIP 完整性 → UTF-8-BOM 解碼 → 16 欄欄名與順序、列寬驗證
→ 正規化（保留 raw）→ identity 收斂為 Trial + SourceRecord
→ 產生全部 artifact 至 staging → 整體 digest 與 referential integrity 驗證
→ 替換 public/data/ 並 commit
```

### 9.2 發布邊界是 git commit（不是逐檔 replace）

逐檔 `os.replace` **無法**構成多檔的整體原子交易。本專案的發布邊界已經是原子的：Cloudflare Pages 部署的是**一個 commit**，不是個別檔案。

- 全部 artifact 先寫進 staging 並通過整體驗證，才替換 `public/data/` 並 commit。
- 任一階段失敗 → 非零 exit、**不 commit**、working tree 中的正式資料整體等於舊版。
- 已 commit 的狀態必為完整一致，**不允許第三種混合 digest**。
- 不引入 snapshot 目錄與 manifest 指標切換（少一層元件即可達到同樣保證）。

### 9.3 輸出

```
public/data/
  manifest.json
  stats.json
  trials-index.json        卡片欄位 + displayFields + latestAmbiguous + conflictFields
  search-index.json        涵蓋全部 SourceRecord
  records/<00..ff>.json    SourceRecord 全欄位含長文字，依 trialId 前 2 hex 分片
qa/
  schema-report.json
  quality-report.json
```

`manifest.json` 必含：`schemaVersion`（整數）、`sourceDatasetId`、`sourceUpdatedAt`、`fetchedAt`、`builtAt`、`sourceSha256`、`trialCount`、`recordCount`、`bootstrap`。

**reference 方向**：`trials-index.json` 的 Trial 持有 `recordId` 清單；`records/*.json` 不反向指回 Trial 以外的物件。`latest` 以 **reference（recordId）** 表達，不嵌入重複資料。
**排序 total order**：Trial 依 `trialId` 昇序；`records[]` 依（日期降序、`recordId` 昇序）。
**referential integrity**：每個被引用的 `recordId` 必須存在於對應 shard；每個 record 必須被恰好一個 Trial 引用。
**schemaVersion 升級**：任何欄位移除、改名、型別變更或語意變更須 bump；純新增可選欄位不 bump。判準是「舊版前端讀到新資料會做什麼」。

### 9.4 `builtAt` 語意（解決與「無變動不 commit」的矛盾）

`builtAt` = **目前已發布 artifact 的建置時間**，不是「本次 workflow 執行時間」。

- 比較是否需發布時，**排除** `builtAt` 與 `fetchedAt` 這兩個 volatile 欄位。
- 其餘正規化輸出若逐位元相同 → 不發布、不 commit、`builtAt` 不變。
- UI 標籤須與此語意一致（顯示「資料建置時間」而非「最後檢查時間」）。

### 9.5 失敗分類

只接受最終 HTTP 狀態 `200`。content-type 以 `;` 前的 MIME 比對等於 `application/zip`（允許參數）。

| error code | 觸發 |
|---|---|
| `HTTP_STATUS` | 任何非 200 的最終狀態（含 4xx／5xx／429） |
| `HTTP_TIMEOUT` | 連線或讀取逾時 |
| `HTTP_TRUNCATED` | 實收位元組與 `Content-Length` 不符，或下載中斷 |
| `UPSTREAM_ERROR_PAGE` | 200 但 MIME 為 `text/html` 等非 zip |
| `ZIP_CORRUPT` | ZIP 結構或 CRC 失敗 |
| `ZIP_NO_CSV` | ZIP 內無 `.csv` |
| `CSV_DECODE` | UTF-8 解碼失敗 |
| `SCHEMA_COLUMN_MISSING` / `SCHEMA_COLUMN_RENAMED` / `SCHEMA_COLUMN_EXTRA` | 欄名或順序不符 |
| `ROW_WIDTH` | 列寬不符超過門檻 |
| `ZERO_ROWS` | schema 通過但 0 資料列 |
| `ROWCOUNT_DROP` | 驟降超過門檻（§9.6） |
| `IDENTITY_COLLISION` | §6.2 的正規化碰撞 |
| `INTEGRITY_DIGEST` | 整體 digest 或 referential integrity 失敗 |

每個 code 對應**相異的 exit code**。stderr 訊息只作輔助，不得以「訊息含某字串」作為測試判定。

**失敗絕不回空陣列。** 抓取失敗與「官方回覆空集」必須分辨：目前 205 無 sentinel 列，0 資料列一律走 `ZERO_ROWS` 硬失敗。

### 9.6 驟降門檻

分母 = 上一個**成功發布快照**的來源資料列數 `prev`；`drop = (prev - cur) / prev`，以有理數比較，不四捨五入。

| 條件 | 結果 |
|---|---|
| `drop > 0.20` | 硬失敗 `ROWCOUNT_DROP`，不發布 |
| `0.10 < drop ≤ 0.20` | warning，發布 |
| `drop ≤ 0.10` | 正常發布 |

恰好 `20.0%` 屬 warning（邊界為嚴格大於）。首次無 baseline → bootstrap 模式：不做驟降比較，要求列數 ≥1 且 schema 通過，manifest 記 `bootstrap: true`，**不假裝完成比較**。

### 9.7 併發與重入

- `schedule` 與 `workflow_dispatch` **共用同一 concurrency group**，`cancel-in-progress: false`（排隊而非取消）。
- **不得取消已進入發布階段的 run。**
- 每個 run 的 baseline 必須是啟動時可驗證的上一個正式快照；baseline 一致性喪失時 fail-closed。

## 10. 風險權重與免責

風險排序：**誤導 > 資料正確性 > XSS**（無登入、無 session、無使用者資料，XSS 竊取不到憑證）。寧可漏報不可誤報。

免責聲明須在首頁、結果頁、詳情頁**可見**，且必須表達三項核心性質：

1. 本站**不提供目前招募狀態**；
2. TFDA 審查／試驗使用**不等於藥品已獲上市核准**；
3. 試驗狀態與收案資格**須向官方資料來源、試驗執行機構與醫療專業人員確認**。

## 11. 驗收條件

全部 fixture 為**凍結**資料，不從活資料抽樣。凍結時母體不可縮成剛好等於子集。每條驗收都須能回答「什麼弱化實作會通過這條但功能其實是壞的」。

### A. 資料模型與收斂

- **A1** 不只斷言 Trial 總數。須寫死**每個來源列 fingerprint → trialId 的 group membership**，並包含一組「易被過度正規化錯合併」（如僅大小寫或全半形不同的相似 protocol）與一組「應合併」案例。（弱化版本：錯合併一組＋錯拆一組，總數仍相等。）
- **A2** fixture 每個案例都須附明確 oracle：所屬 group、record 數、`latestAmbiguous` 值、`conflictFields`、raw 保存、預期的 error／warning。fixture 須含：≥1 個 10 列以上 protocol、≥1 組 16 欄全同純重複、**≥2 筆完全相同的空 protocol 列**、≥3 組同日衝突、≥1 組同日但全同、≥1 筆 `TFDA收文號="移案BPA"`、≥1 筆收文號重複。（弱化版本：fixture「包含」案例但無期望值，實作忽略它們也通過。）
- **A3** 對 **reverse 與 ≥3 個固定 seed 的排列**重跑：先斷言輸出**檔案 inventory 完全相同**，再逐檔 SHA-256 相同，再斷言每個 tie case 的語意結果（`latestAmbiguous`、`conflictFields`、`displayFields`）相同。（弱化版本：單次 shuffle 碰巧相同；或漏輸出檔而不在 hash 清單內。）
- **A4 反向哨兵** 把同日處置改為「任取 cohort 第一筆為 latest」時，A3 必須失敗，且**須證明失敗點是指定 tie group 的 `latestAmbiguous` 由 true 變 false**，不得以任意位元差異充當殺死 mutation。
- **A5** 比對來源 canonical fingerprint 的**完整 multiset 含 multiplicity**，不只比總數。（弱化版本：漏一列同時複製另一列，總和仍等於原始列數。）
- **A6** 兩筆完全相同的空 protocol 列須各自取得**唯一 ID**、multiset 完整保留，且在 ≥3 個排列下輸出一致。（實測目前 6 列空 protocol 彼此全不同，此為防禦性條件。）
- **A7** 注入兩個不同 raw protocol 但 identity 正規化後相同的列 → 管線必須以 `IDENTITY_COLLISION` 硬失敗並產出 collision report，**不得合併**。

### B. ETL 可靠性

- **B1** 對 §9.5 的**每一個** error code 各有測試。失敗後須斷言：(a) 非零且相異的 exit code；(b) `public/data/` 的**完整檔名集合、每檔 SHA-256、manifest 指向**均不變；(c) **無新增正式檔**。content-type 測試須含帶合法參數的 `application/zip;charset=utf-8`（應通過）與 `text/html`（應失敗）。（弱化版本：只擋明列的 500；或只比既有檔 hash 而放過半套新增檔案。）
- **B2** 每個案例寫死 structured error code 與 layer；**不得**以「stderr 含某字串」作判定。（弱化版本：七種失敗共用一個 exit code，只靠模糊訊息區分。）
- **B3** 斷言 CSV schema **已通過後**才因零列失敗，明確回傳 `ZERO_ROWS`，且正式 digest 不變。（弱化版本：因任意解析錯誤失敗，日後放寬 parser 就會意外發布空集。）
- **B4** 門檻案例須含 `drop` = 0.0／0.10／**0.1001**／**0.20**／**0.2001**／整數列數邊界／首次無 baseline（bootstrap）。逐案例斷言 warning／success／hard-failure 與**是否發布**。
- **B5** 失敗注入點須涵蓋：staging 驗證、全部 artifact 產生完成、整體 digest 驗證、commit 前。每個點都斷言**不產生 commit**，且 working tree 的正式資料**整體等於舊版**；不允許第三種混合 digest。
- **B6** referential integrity：注入「Trial 引用不存在的 recordId」與「record 未被任何 Trial 引用」的 fixture → 必須以 `INTEGRITY_DIGEST` 硬失敗。

### C. Sentinel 與空值

- **C1** 對分類 sentinel 同時斷言五處：typed value 為 `null`、raw 值仍等於 `"0"`、`stats.json` 的 facet 不含 `"0"`、**實際 filter DOM 不含該選項**、卡片／詳情顯示「未提供」。（弱化版本：`stats.json` 乾淨但搜尋索引或 UI 自產 `"0"`。）
- **C2** fixture 須同時含數值 `0`、非 0、空白、malformed 四種，**逐筆**斷言 parsed value 與 `sourceZero` 真值；UI 另斷言顯示「來源填 0」字樣。（弱化版本：對所有數字都設 `sourceZero=true`，仍滿足唯一的 0 案例。）
- **C3** 寫死 `N/A`／`NA`／`""` 三類的**精確計數與對應 recordId**；並斷言詳情切換到該 record 後的**可見文字精確相等**。（弱化版本：QA report 有三個計數欄但數字錯誤；或值藏在不可達欄位。）
- **C4 反向哨兵** 拆成**三個獨立 mutation**（分類轉 null／數值 0 轉 null／文字 sentinel 轉「未提供」），分別證明 C1、C2、C3 的指定斷言被殺死。（弱化版本：三項同時失敗但源於單一共用 schema error，診斷力為零。）

### D. 搜尋與篩選

- **D1** §8.2 的**七個欄位各有唯一 canary**與精確 expected trialId 清單；另含多欄同時命中案例，斷言**命中標籤集合完全相等**（不缺漏、不多報）。（弱化版本：只實作 title 與 purpose，其他五欄完全壞掉也通過。）
- **D2** 先逐欄寫死 §8.1 的 normalization policy，fixture 以明確的 `shouldMatch`／`mustNotMatch` pair 表達，**不依賴人工裁決**（人工裁決不是可重跑 oracle）。identity normalization（§6.2）與 search normalization（§8.1）**分開驗證**，須有「identity 不合併但 search 命中」的案例證明兩者未混用。
- **D3** 對同一查詢寫死**完整結果集合**，須含：兩詞同欄正例、兩詞跨欄正例、**只命中其中一詞且必須被排除的負例**。（弱化版本：只有跨欄正例時，OR 實作可碰巧通過。）
- **D4** 移除 v0.2 那組矛盾的「sentinel 篩選」案例（§6.6 已定分類 sentinel 不進選單，該 filter 無合法語意）。每個**正式** filter 維度至少一組，斷言結果 trialId 清單逐一相同且順序相同、**canonical URL 字串精確相等**、reload 後控制項狀態精確相等。
- **D5** 斷言 **filter schema、DOM 控制項、URL parser、輸出 state 四處**均不存在 trial-status 維度，且中文同義 UI（「收案情形」「招募」等）不出現。（弱化版本：只檢查選單文字，改名或用隱藏 URL 參數即可規避。）
- **D6** `latestAmbiguous=true` 的 trial 在篩選衝突欄位時，須歸入「同日多筆不一致」分組，斷言**不會**出現在任一具體值的篩選結果中。

### E. 呈現與誤導防範

- **E1** 只對 **UI 自產生**的 badge／欄位標籤／accessible name／filter／排序做禁字斷言，**不對來源原文設無條件禁字**（納入條件裡合理出現 `active`）。另須正向斷言 §10 的三項免責文句**精確存在且可見**，並加入「開放收案」「可報名」「招募中」等暗示語的負面斷言。（弱化版本：字串黑名單誤傷來源原文，同時漏過中文暗示語。）
- **E2** 每張統計卡以**獨立 oracle** 寫死精確值、單位、分母類型；phase／scale 各類別總和須符合 §6.6 與 §7.1 的 `未提供／不一致` 規則。（弱化版本：任意數字旁放「試驗」二字即通過，分母仍可算錯。）
- **E3** 斷言**各 label 對應精確 fixture 值**（來源 `資料更新時間` 對應 record、`builtAt` 對應 manifest），不是只斷言兩者不相等。（弱化版本：把兩個值互換、或顯示任意兩個不同值都會通過。）
- **E4** XSS 分別測卡片、詳情、**版本切換**三處：斷言來源內容以**可見 text** 呈現、未生成由來源控制的元素或 event handler、且執行觀察值（如注入的 counter）保持不變。（弱化版本：惡意字串藏在不可見 DOM；或 `onerror` 未觸發而誤判為安全。）
- **E5** 逐頁斷言 §10 三項核心性質的**可見文字**，不只查節點存在。（弱化版本：任何叫「免責聲明」的空泛或隱藏文字都通過。）
- **E6** inclusion 與 exclusion **各**有長 fixture（含 22,490 字元案例）：展開後以換行正規化後的**全文精確相等**、首尾 canary 存在，切換 record 後亦相符。（弱化版本：heading 可見但展開後截斷；或只測一個長欄位。）
- **E7** `latestAmbiguous=true` 的卡片須顯示「同日多筆資料不一致」且**不顯示任何衝突欄位的具體值**；詳情頁須顯示「順序未知」。斷言衝突欄位的任一候選值都不出現在卡片 DOM。

### F. 效能

- **F1** 定義為「冷啟動到可搜尋狀態前的全部 network responses」，以 **production build 與固定 gzip 設定**量測，列出納入檔案清單與總和並寫入 CI artifact，≤1.5 MB。基線：卡片欄位 JSON 715 KiB gzip。（弱化版本：量測後才 lazy-load；或用與 production 不同的壓縮設定。）
- **F2** 在 criteria 放**唯一長 canary**，斷言所有初始 response 與 bundle 均不含其**內容**（不只檢查欄位鍵），只有開啟對應 record shard 後才出現。（弱化版本：改欄位名、改 positional array、或直接嵌入長文字值即可避過欄位鍵檢查。）
- **F3** 以 **production-scale fixture（5,888 Trial／18,736 SourceRecord）**與固定查詢 corpus（零結果、極多結果、中文、英文、多詞）量測；計時自**輸入事件到結果 DOM 完成**；逐案例或明定 percentile 均 ≤300 ms。達不到須寫**瓶頸歸因**，不調鬆數字。

### G. 無障礙

- **G1** 除 `scrollWidth ≤ clientWidth` 外，斷言可見文字、表單與 focusable elements 的 **bounding box 均在 viewport 內**，不得靠裁切滿足。（弱化版本：`overflow-x:hidden`。）
- **G2** 列出**路由 × 元件狀態矩陣**（含 hover、focus、warning、disabled、`latestAmbiguous` 標記）；每個實際文字／背景組合輸出 selector、前景、背景與 ratio，依 normal/large text 門檻判定並寫入 CI artifact。（弱化版本：只掃首頁預設狀態。）
- **G3** 對**每一類**互動元件（搜尋框、各 filter、折疊、record 切換、複製按鈕）逐項斷言 tab 可達、順序、Enter/Space 行為、focus 不遺失、無 keyboard trap；期別與警示須驗證可讀文字或 accessible name。（弱化版本：一個可見 focus 樣式即通過「完整鍵盤導航」。）
- **G4 條件式** 首版以數字卡與清單為**必須**，圖表為**可選**（依 payload 與 a11y 成本於 M2 決定）。**若**提供圖表，則其 table/list 替代須在 DOM 可讀、具標題與欄名，且 **key/value 集合與圖表資料精確相等**。（弱化版本：空 table 或與圖表不一致的 table。）

### H. CI 與自動化

- **H1** 對**每個** gate 注入一個已知失敗，斷言 workflow／job 為 failure；檢查實際執行的命令、觸發分支與 path filter，**不只檢查 step 名稱**，並斷言無 `continue-on-error`。（弱化版本：六個 step 名稱正確但空跑。）
- **H2** 以**同一凍結來源**連跑兩次：第二次 git tree、正式 artifact digest 與 HEAD 均不變。斷言 `schedule` 與 `manual` 共用同一 concurrency group。diff 摘要以獨立 oracle 驗證精確的 additions／removals／modifications。
- **H3** 上線當天手動 dispatch 一次、再跑第二次驗冪等，第二次須**重用相同 source SHA**；斷言兩次都**完整跑完 pipeline**（不是根本沒做事）且第二次明確回報 no normalized change。
- **H4** 斷言所有**直接與間接** `uses`（含 reusable workflow、container）均為不可變 SHA／digest；workflow 預設 `permissions` 為最小／read，只有唯一的資料更新 job 明示 `contents: write`，其他 job 明示無 write。

## 12. 里程碑

- **M0** 本規格通過第二輪覆審（進行中）
- **M1** repo 鷹架與 ETL（A／B／C 群驗收）。**M1 前須先封存**：identity 規則（§6.2）、同日衝突模型（§6.4）、record identity（§6.3）、輸出契約（§9.3）——這四項是最難回頭的組合，因為它們同時定義資料實體、歷史歸屬與外部連結
- **M2** 前端 MVP（D／E／F／G 群驗收）
- **M3** CI 與月更新（H 群驗收）＋ Cloudflare Pages 首次部署
- **M4** 收尾：README 更新、收進 `pharmacy-portal`、跑 `/codex-review`（以本規格的編號做規格符合度稽核）

## 13. 後續版本（不進本次範圍）

- 上游停更偵測。**不可**以「距今天數」為唯一判準——`資料更新時間` 最新值 2026/08/17 已距今約一個月，稀疏更新是常態；應以「連續 N 次 build 的 `sourceUpdatedAt` 未前進」為判準。
- 每月變更監測。`no longer present` **不得**自動稱為 terminated。
- 有方向性的版本 diff（需來源提供版號或可靠時間戳）。
- ClinicalTrials.gov cross-link（以 NCT ID／protocol number 精確比對，保留 unmatched／ambiguous）。
- Service worker／離線。若做，快取前綴須限定自家，即使在獨立 origin 上也照規矩寫。
- Email 訂閱（需另評估個資、誤報與營運責任）。

## 14. 修訂紀錄

- **v0.3（2026-09-18）** 依 `plan-verdict.md` 的 51 接受／5 部分接受改寫，並合併為單一 normative 規格（verdict 1.5、4.5）。主要變更：
  - 同日平手不再推定唯一 `latest`，改為 cohort + `latestAmbiguous` + `conflictFields` 模型（verdict 1.1、4.1，Blocker）
  - 「Revision」更名為中性的「SourceRecord」，不稱「第 N 版」（1.1）
  - 新增 §6.2 identity normalization 規則（`strip+NFKC+upper`，實測 0 碰撞）並與 §8.1 search normalization 分離（1.2、D2）
  - 新增 §6.3 canonical serialization、ID 規則與 ID 穩定性界限（1.3）
  - 新增 §7.1 各功能資料層對照表與 §7.2 歷史命中標示（1.4）
  - 新增 §6.5 日期規則，含實測補上的 7 列 end<start（1.6，嚴重度自 High 降 Medium）
  - 移除 `FEATURE_TRIAL_STATUS`（4.3）
  - 發布邊界改定義為 git commit，不引入 snapshot 目錄（2.1，部分接受）
  - 新增 §9.4 `builtAt` 語意以解除與「無變動不 commit」的矛盾（2.2）
  - 新增 §9.3 輸出契約、§9.5 失敗分類與 error code、§9.6 驟降公式與邊界、§9.7 併發語意（2.3、1.8、1.9）
  - 新增 §7.4 URL 契約（2.4）
  - §7.3 改為不做方向性 diff（4.2）
  - §10 免責補上「試驗使用不代表上市核准」（E5）
  - 驗收條件全面改寫堵死弱化實作，新增 A7、B6、D6、E7，G4 改條件式（4.4，部分接受）
