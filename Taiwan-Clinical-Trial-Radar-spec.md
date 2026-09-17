# Taiwan Clinical Trial Radar — Product Specification

> Repository: `Taiwan-Clinical-Trial-Radar`  
> Document: `spec.md`  
> Status: Draft v0.1  
> Last updated: 2026-09-12  
> Primary language: Traditional Chinese (`zh-TW`)

## 1. Executive summary

`Taiwan Clinical Trial Radar` 將 TFDA 公開的台灣藥品臨床試驗資料，轉換成可搜尋、篩選、追溯資料時間的靜態網頁工具，回答：

1. 台灣有哪些經衛生福利部審查通過的藥品臨床試驗？
2. 某疾病、試驗名稱、protocol number 或申請者涉及哪些試驗？
3. 試驗期別、規模、期間、預計收案數、主要評估指標及條件為何？
4. 公開資料最新更新到何時，使用者應到何處確認最新狀態？

MVP 定位為 **clinician-facing information retrieval tool**，不是病人試驗媒合器，也不提供受試者適格性判定。

### 核心產品邊界

- 僅呈現政府公開資料，不宣稱涵蓋台灣所有臨床試驗。
- `TFDA 審查通過` 不等於 `目前正在招募`。
- 不將 inclusion/exclusion criteria 自動轉為病人適格或推薦結果。
- 不把全球預計人數解讀為台灣實際收案人數。
- 不推論療效、安全性或試驗藥品已獲上市核准。
- 所有內容均應顯示資料日期、來源與免責聲明。

## 2. Critical data finding and feasibility gate

截至 2026-09-12，實際檢查 TFDA CSV ZIP 匯出檔的結果如下：

| ID | 資料集 | 匯出筆數 | 關鍵觀察 |
|---|---|---:|---|
| 205 | 臨床試驗現況 | 18,736 | 有 `臨床試驗計畫書編號`、`TFDA收文號`；實際 CSV 未見官方頁面所列的 `執行狀態` |
| 206 | 宣稱適應症（ICD-9） | 18,692 | 無 trial identifier |
| 207 | 試驗執行機構 | 512,140 | 無 trial identifier |
| 208 | 試驗藥品 | 27,774 | 無 trial identifier |
| 209 | 試驗藥品主成分 | 28,800 | 無 trial identifier |

後四份檔案沒有 `TFDA收文號`、protocol number 或其他可驗證的 trial key，筆數亦不一致。現階段不得以列序、row index、相鄰位置、名稱相似度或筆數分組推測關聯。

### Phase 0：go/no-go gate

在開發 Trial × Drug × Site 關聯功能前，必須完成以下任一條件：

- 官方提供穩定且有文件的共同鍵；或
- 官方確認匯出資料的關聯規則，且可用自動測試重現；或
- 找到另一個具合法授權、可用 protocol number 穩定交叉比對的權威資料源。

若未通過，MVP 僅使用 dataset 205 建立 trial-level radar；206–209 不得拼接至單一試驗。可另做「未關聯的整體統計探索頁」，但必須明確標示不能回推個別 trial。

## 3. Goals and non-goals

### 3.1 Goals

- 讓臨床藥師、醫師、研究護理師與 CRC 在 10 秒內找到相關試驗。
- 將大型 ZIP/CSV 正規化成可供靜態網站快速讀取的索引與分片。
- 保留來源欄位與 traceability，不改寫成無法追溯的 AI 摘要。
- 每月自動檢查資料更新、schema drift 與資料品質。
- 為未來安全加入 Drug、Ingredient、Site 關聯保留資料模型。

### 3.2 Non-goals (MVP)

- 病歷上傳、個人健康資料輸入或病人帳號。
- 自動判斷病人是否符合納入/排除條件。
- 招募轉介、聯絡 PI 或醫院、預約或送出表單。
- AI 生成試驗摘要、醫療建議或試驗優先排序。
- 療效比較、試驗品質評分、risk of bias 或證據等級判定。
- 推測未公開、缺失或過期的招募狀態。
- 以 Google Maps 或使用者定位實作「附近正在招募」；待 site linkage 與地址品質確認後另立規格。

## 4. Target users and jobs-to-be-done

| User | Primary job | MVP support |
|---|---|---|
| 臨床藥師 | 依藥名、疾病或 protocol 快速盤點研究 | 主檔全文搜尋；藥名命中可能來自 title/purpose，需標示欄位來源 |
| 醫師 | 確認某適應症有哪些已審查試驗 | 適應症、期別、期間篩選 |
| CRC／研究護理師 | 查試驗設計與收案條件原文 | 詳情頁呈現 endpoint、inclusion、exclusion |
| 研究者 | 觀察 sponsor、phase、疾病領域分布 | 統計卡與可重現篩選 |
| 民眾 | 初步了解公開試驗資訊 | 可瀏覽，但強制提示需向醫療團隊及執行機構確認 |

## 5. Data sources

### 5.1 Authoritative sources

| Dataset | ID | URL | Frequency | MVP use |
|---|---:|---|---|---|
| 台灣藥品臨床試驗現況 | 205 | `https://data.fda.gov.tw/data/opendata/export/205/csv` | Monthly | Primary |
| 宣稱適應症（ICD-9） | 206 | `https://data.fda.gov.tw/data/opendata/export/206/csv` | Monthly | Disabled until linkage verified |
| 試驗執行機構 | 207 | `https://data.fda.gov.tw/data/opendata/export/207/csv` | Monthly | Disabled until linkage verified |
| 試驗藥品 | 208 | `https://data.fda.gov.tw/data/opendata/export/208/csv` | Monthly | Disabled until linkage verified |
| 試驗藥品主成分 | 209 | `https://data.fda.gov.tw/data/opendata/export/209/csv` | Monthly | Disabled until linkage verified |

Dataset landing pages and license information:

- `https://data.gov.tw/dataset/177198`
- `https://data.gov.tw/dataset/177212`
- `https://data.gov.tw/dataset/177215`
- `https://data.gov.tw/dataset/177216`
- `https://data.gov.tw/dataset/177218`

授權依來源頁所示「政府資料開放授權條款－第 1 版」。README 與網站 footer 必須保留來源及授權聲明。

### 5.2 Source-of-truth policy

- 原始 ZIP 僅供 build 與稽核，不由前端直接解析。
- 來源資料若抓取失敗、ZIP 無法解壓、CSV 無法解析或 schema 驗證失敗，不得覆寫上一版 production data。
- 官方網頁的欄位說明與實際 CSV 衝突時，以實際資料作為 runtime schema；同時留下 discrepancy report，不靜默補欄位。
- `資料更新時間` 是來源欄位，不等於本站 build time；兩者必須分開保存。

## 6. Functional requirements

### 6.1 Home/search

首頁僅保留一個主要任務：搜尋台灣藥品臨床試驗。

Searchable fields:

- 臨床試驗計畫書編號
- 臨床試驗計畫中文名稱
- 臨床試驗申請者
- 適應症中文
- 試驗目的
- 主要評估指標
- TFDA 收文號

Search behavior:

- case-insensitive Latin search。
- Unicode normalization：NFKC、全半形正規化、trim、重複空白壓縮。
- 中英文字串採 substring/token matching；MVP 不做語意搜尋。
- 多詞預設 AND；UI 顯示目前邏輯。
- 顯示命中欄位，例如「命中：適應症／試驗目的」，避免使用者誤以為名稱完全相符。
- 結果由 relevance 排序，其次資料更新時間、protocol number；不得暗示臨床推薦順位。
- URL query 可重現搜尋與篩選狀態，例如 `?q=breast+cancer&phase=3`。

### 6.2 Filters

- 臨床試驗期別（保留原始值並映射 normalized value）
- 本臨床試驗規模
- 試驗預計執行期間
- 台灣預計受試者人數範圍
- 臨床試驗申請者
- 資料更新時間

不得在來源缺少 `執行狀態` 時提供 Recruiting/Active filter。UI feature flag `FEATURE_TRIAL_STATUS=false` 為預設。

### 6.3 Results list

每張結果卡顯示：

- 試驗中文名稱
- protocol number
- phase（原始值與標準化顯示）
- indication
- sponsor/applicant
- planned Taiwan enrollment
- planned study period
- source updated date
- 命中欄位

不得顯示未由來源支援的「目前招募中」標章。

### 6.4 Trial detail

完整呈現主檔所有欄位，長文字區塊依序為：

1. 試驗目的
2. 主要評估指標
3. 納入條件
4. 排除條件

Detail page requirements:

- 保留原文換行；不得任意刪節。
- 預設可折疊長段落，但 heading 與是否有資料需立即可見。
- 顯示 `TFDA收文號`、protocol number、來源資料日期、本站 build time。
- 提供複製 protocol number 與複製頁面連結。
- 顯示官方資料集連結，而不是宣稱本站狀態即時。

### 6.5 Dashboard summary

首頁可顯示：

- 全部試驗數
- 依 phase 分布
- 依研究規模分布
- 前 10 個申請者
- 前 10 個適應症字串
- 台灣預計收案人數分布（僅排除無法解析值）

所有統計應受目前搜尋與 filters 影響，並顯示 denominator。圖表點擊可套用篩選；沒有必要時以數字卡與水平長條圖取代圓餅圖。

### 6.6 Empty, missing and error states

- `null`、空字串、全形空白與缺欄需區分 raw audit，但 UI 統一顯示「未提供」。
- `0` 不可自動視為 missing。
- 日期無法解析時顯示原始值並標記「日期格式未辨識」。
- 搜尋無結果時保留 query 與 filter，提供清除篩選按鈕。
- 資料載入失敗時顯示可理解訊息與最後成功資料日期，不呈現空白頁。

## 7. Data model

### 7.1 Canonical trial record

```json
{
  "id": "sha256:<stable-hash>",
  "protocolNumber": "DS8201-A-U306",
  "tfdaReceiptNumber": "raw value or null",
  "applicant": "raw value or null",
  "titleZh": "raw value or null",
  "phase": {
    "raw": "Phase Ⅲ",
    "normalized": "phase-3"
  },
  "scale": "raw value or null",
  "purpose": "raw value or null",
  "plannedStartDate": "YYYY-MM-DD or null",
  "plannedEndDate": "YYYY-MM-DD or null",
  "plannedGlobalEnrollment": 490,
  "plannedTaiwanEnrollment": 20,
  "indicationZh": "raw value or null",
  "primaryEndpoint": "raw value or null",
  "inclusionCriteria": "raw value or null",
  "exclusionCriteria": "raw value or null",
  "sourceUpdatedAt": "ISO-8601 or null",
  "source": {
    "datasetId": 205,
    "rowNumber": 2
  }
}
```

### 7.2 Stable identifier

Preferred key order:

1. normalized `TFDA收文號`，若唯一且非空；
2. normalized `臨床試驗計畫書編號` + normalized applicant；
3. deterministic SHA-256 of selected raw identity fields。

Build 必須輸出 collision report。發生 collision 時不得任意覆蓋；保留所有 records 並附 deterministic suffix，CI 標記 warning 或 fail（依 threshold）。

### 7.3 Future relations

```text
Trial 1 ── * TrialDrug * ── 1 Drug * ── * Ingredient
Trial 1 ── * TrialSite * ── 1 Site
Trial 1 ── * TrialIndication * ── 1 ICD9
```

以上 relation table 只能由已驗證的官方或權威共同鍵產生。禁止 fuzzy join 寫入 production relation。

## 8. ETL and output architecture

```text
TFDA ZIP
  -> download to temporary path
  -> verify HTTP / content type / ZIP integrity
  -> decode UTF-8 BOM CSV
  -> validate headers and row width
  -> normalize without destroying raw values
  -> validate types and invariants
  -> generate canonical records
  -> generate search index and shards
  -> generate manifest and QA report
  -> atomic publish only after all checks pass
```

Recommended outputs:

```text
public/data/
  manifest.json
  stats.json
  search-index.json
  trials/
    00.json
    01.json
    ...
    ff.json
reports/
  schema-report.json
  quality-report.json
  linkage-report.json
```

`manifest.json` minimum fields:

```json
{
  "schemaVersion": 1,
  "sourceDatasetId": 205,
  "sourceUpdatedAt": null,
  "fetchedAt": "2026-09-12T00:00:00Z",
  "builtAt": "2026-09-12T00:00:00Z",
  "recordCount": 18736,
  "sourceSha256": "...",
  "linkageStatus": "unavailable"
}
```

前端不得載入 166 MB 原始 CSV。MVP target：首頁初始資料 payload gzip 後 ≤ 1.5 MB；詳情按需載入 shard。

## 9. Technical architecture

建議技術：

- Data pipeline: Python 3.12+
- Parser/validation: standard `csv` + Pydantic 或明確 dataclass validation
- Frontend: Vite + TypeScript；若保持單純亦可使用 vanilla TypeScript
- Tests: pytest + Vitest/Playwright
- Hosting: GitHub Pages 或 Cloudflare Pages
- Automation: GitHub Actions

不需要 backend、database、authentication 或 runtime API。所有公開資料在 CI build-time 產生靜態 artifact。

Suggested repository:

```text
Taiwan-Clinical-Trial-Radar/
  spec.md
  README.md
  LICENSE
  pyproject.toml
  package.json
  src/
  scripts/
    fetch_tfda.py
    build_data.py
    validate_schema.py
    verify_linkage.py
  tests/
    fixtures/
  public/data/
  reports/
  .github/workflows/
    update-data.yml
    ci.yml
```

## 10. Data quality rules

### Hard failures

- HTTP failure, unexpected HTML/error document, invalid ZIP or missing CSV。
- Required identity columns removed or renamed without explicit schema migration。
- CSV row width mismatch above defined threshold。
- zero records or sudden record-count drop >20% versus last successful build。
- duplicate canonical ID causing overwrite。
- generated JSON invalid or referential integrity failure。
- pipeline attempts to join datasets 206–209 without verified key configuration。

### Warnings requiring report

- record-count change >10%。
- new phase/scale/date formats。
- increasing nullness >5 percentage points in important fields。
- source landing page lists a field absent from export, including `執行狀態`。
- duplicate protocol number or TFDA receipt number。
- future dates, end before start, negative enrollment or implausible numeric values。

Warnings do not silently change interpretation. Each build retains counts, examples and comparison with prior successful build.

## 11. GitHub Actions

### CI (`pull_request`, `push`)

1. install locked dependencies;
2. lint and type-check;
3. run unit/integration tests using fixtures;
4. build frontend;
5. run accessibility smoke tests;
6. upload test/QA artifacts on failure。

### Monthly data update

- Schedule: monthly plus manual `workflow_dispatch`。
- Use concurrency lock to prevent overlapping data updates。
- Download to temp directory; keep production artifacts untouched until success。
- Generate diff summary: additions, removals, modified records, schema changes。
- Commit only when normalized outputs change。
- Commit message: `data: update TFDA clinical trial dataset YYYY-MM-DD`。
- On failure, retain last known good production data and create issue/artifact notification。
- Pin GitHub Actions to immutable commit SHA where practical; grant minimum permissions (`contents: write` only for update job)。

## 12. Clinical, ethical and privacy risk controls

| Risk | Control |
|---|---|
| 招募狀態過期或來源缺欄 | 不顯示 recruiting badge；標示資料日期並要求官方確認 |
| 把公開試驗當成治療建議 | 明示 informational use；不排序「最適合」試驗 |
| 自動適格性判定錯誤 | MVP 禁止 patient matching；不收病歷或自由文字病況 |
| 試驗藥誤認為上市核准 | 固定提示「試驗使用不代表 TFDA 上市核准」 |
| PI 姓名等公開資料再利用 | 只在必要且可驗證 trial linkage 後呈現；不建立人物績效排行 |
| 搜尋紀錄可能含病情 | 不蒐集搜尋文字、IP 或 analytics；若未來加入 analytics，禁送 query string |
| XSS from source text | 所有來源文字使用 escaping；禁止 raw HTML injection |
| 供應鏈與 CI 權限 | lockfile、dependency update、minimum token permission、artifact validation |

Footer disclaimer:

> 本站為政府開放資料之整理與檢索工具，不代表 TFDA 或任何醫療機構。資料可能有更新延遲，試驗狀態及收案資格請向官方資料來源、試驗執行機構與醫療專業人員確認。本工具不提供醫療建議或受試者適格性判定。

## 13. Accessibility and UX

- Mobile-first responsive design；360 px 寬度不可水平捲動。
- WCAG 2.2 AA 為目標；完整 keyboard navigation、visible focus、semantic headings。
- 色彩不是狀態唯一線索；phase 與 warning 同時提供文字。
- 長 criteria 具「展開全部」「返回頂部」，避免 nested scroll。
- 圖表必須有可讀的 table/list alternative。
- 使用繁體中文 UI；保留 drug/protocol 等官方英文字串原貌，不自動翻譯。
- 首屏聚焦搜尋，不放大量低價值圖卡。

## 14. Testing requirements

### Data tests

- BOM、quoted comma、embedded newline、CRLF、空欄、超長文字。
- ROC/Gregorian/invalid date formats（若來源實際出現）。
- Roman numeral phase variants：`Ⅰ`, `II`, `Phase Ⅲ`, combined/other；保留 raw。
- enrollment `0`, blank, malformed, thousands separator。
- duplicate protocol/receipt and hash collision handling。
- schema missing/extra/renamed columns。
- source failure never replaces last known good data。
- explicit test proving no row-order join across datasets 205–209。

### Frontend tests

- Chinese and English queries、full/half-width normalization。
- AND search and filter URL persistence。
- result hit-field label correctness。
- null/zero distinction。
- long criteria rendering and XSS escaping。
- mobile layout、keyboard navigation、screen-reader labels。
- 404/deep-link behavior on chosen static host。

## 15. Acceptance criteria

MVP is complete only when:

- [ ] Dataset 205 可自動下載、驗證與轉換，來源失敗不覆蓋舊資料。
- [ ] 18k+ records 可在一般手機上快速搜尋，初始 gzip payload ≤1.5 MB。
- [ ] 搜尋涵蓋 protocol、title、applicant、indication、purpose、endpoint、receipt number。
- [ ] 所有結果顯示命中欄位，filter state 可由 URL 重現。
- [ ] 詳情頁完整保留 criteria 原文與來源追溯資料。
- [ ] UI 未顯示來源實際未提供的 trial status/recruiting status。
- [ ] Dataset 206–209 未以未驗證方法連回 individual trial。
- [ ] schema drift、row count、nullness、duplicate、date/enrollment 異常有測試與報告。
- [ ] 無病患資料輸入、無自動 eligibility recommendation、無搜尋字串 analytics。
- [ ] CI、monthly update、last-known-good rollback behavior 均通過測試。
- [ ] 手機、鍵盤與基本 WCAG AA smoke test 通過。
- [ ] README 清楚列出資料來源、授權、限制與資料更新日期。

## 16. Roadmap

### Phase 0 — Data feasibility (first milestone)

- 下載並保存五個 dataset 的 headers、row counts、hash 與 sample-safe QA。
- 向 TFDA/資料提供單位確認 dataset 206–209 的 trial relation key。
- 建立 `verify_linkage.py`；結果只能是 `verified`, `unavailable`, `failed`。
- 產出 `reports/linkage-report.json`，在未驗證時關閉 relation features。

### Phase 1 — Reliable trial radar (MVP)

- Dataset 205 ETL、搜尋、filters、stats、detail page、monthly CI。
- 不承諾 drug/site/recruitment linkage。

### Phase 2 — Verified relational data

僅在 Phase 0 通過後加入：

- Trial ↔ investigational drug ↔ ingredient。
- Trial ↔ site ↔ recruitment status。
- Site filter、drug/ingredient page、trial network view。
- 每個 relation 記錄 source key 與 provenance。

### Phase 3 — Change monitoring

- 每月新增、移除、欄位變化與招募狀態變更。
- 顯示 `new`, `changed`, `no longer present`；`no longer present` 不自動稱為 terminated。
- 訂閱功能需另行評估 email、個資、誤報與營運責任。

### Deferred ideas

- ClinicalTrials.gov cross-link（以 NCT ID/protocol number 精確比對，保留 unmatched/ambiguous）。
- Hospital geocoding and nearby search（先確認地址權威來源與招募時效）。
- Eligibility structuring as decision support（高風險，需另立 clinical validation protocol）。

## 17. Versioning and decision log

- Application: Semantic Versioning。
- Data schema: integer `schemaVersion`；breaking change 必須 migration 或 major bump。
- 規格變更以 ADR 記錄，至少包括：data key、status semantics、cross-source linkage、privacy/analytics。
- Raw source 不手動修改；修正規則以 version-controlled transformation + test 實作。

## 18. Immediate next action

第一個 commit 只完成 Phase 0，不做 UI：

```text
chore(data): audit TFDA clinical trial dataset linkage
```

交付項目：

- `scripts/audit_sources.py`
- 五組 dataset 的 header/row-count/schema manifest
- `reports/linkage-report.json`
- fixture-based tests
- 一份準備寄給 TFDA 的精簡詢問：後四份資料如何以穩定 identifier 對應 dataset 205 的個別試驗？

在 linkage 得到官方可重現答案前，下一個開發 commit 才進入 dataset 205 的搜尋 MVP。
