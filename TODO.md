# TODO

狀態：Phase 1 規劃中。依序執行，**M0 未完成前不要寫實作程式碼**。

---

## 未定案決策（阻塞 M1）

### D1. 「取最新版」的 tie-break 規則 ⛔ 阻塞

2,821 個多列 protocol 裡有 **846 組（30%）** 的最新 `資料更新時間` 平手。日期只有 `YYYY/MM/DD` 精度，無時間、無版號可再細分。

- 不可靠 CSV 列序決定（非穩定契約，會讓 build 輸出不確定）。
- 建議規則：平手時取**非空欄位數最多**者為主版本；仍平手則取 16 欄正規化後字串的 SHA-256 字典序最小者。兩段都與列序無關，結果確定且可測。
- 需確認：這條規則會不會讓「最完整」與「最新意圖」不一致？例如某版刻意把 `排除條件` 留空表示取消該條件——實測 `排除條件` 有 364 筆空值，需抽樣看平手組裡是否出現這種情形。
- **待使用者定案。** 定案前不要先寫「取第一筆」的實作。

### D2. 版本歷史要呈現到什麼程度

已定案要保留審查紀錄歷史，但呈現深度未定：

- 最小：詳情頁列出各版 `資料更新時間` 清單，點選切換檢視。
- 建議：另加「欄位變更摘要」，主動標示如「台灣預計人數 20 → 30」「納入條件曾修訂」。實測有 395 組收案人數變動、1,927 組納入條件變動，這些變更本身有臨床意義。
- 代價：欄位層級 diff 會增加 shard 體積與前端複雜度，需先量測。

---

## M0 — 規格修訂與覆審

規格 v0.1（2026-09-12）已有五處被 2026-09-18 實測推翻，**不能直接照它實作**。

- [ ] §2「Critical data finding and feasibility gate」— 整節刪除。決策已改為永久不納入 206–209，不再有 go/no-go gate。
- [ ] §6.6「`0` 不可自動視為 missing」— 改為依欄位型別分開處理（分類／數值／文字三類，見 CLAUDE.md 表）。
- [ ] §7.1 canonical trial record — 目前假設一列一試驗，錯誤。改為 trial（protocol 收斂）＋ revision（審查紀錄）兩層模型，`source.rowNumber` 移到 revision 層。
- [ ] §7.2 stable identifier — 三段 key order 第 1、2 選在實際資料上不成立（`TFDA收文號` 2,788 個重複鍵／266 空值／30 筆 `移案BPA`；`protocol + applicant` 2,885 個重複鍵）。改為 protocol 為主鍵、空 protocol 走 row hash。
- [ ] §7.3 Future relations — 整節刪除（206–209 不做）。
- [ ] §16 Roadmap — Phase 0 與 Phase 2 刪除，重編為 Phase 1（MVP）／Phase 2（變更監測）。
- [ ] 補寫 tie-break 規則（待 D1 定案）與版本歷史資料模型（待 D2 定案）。
- [ ] §9 部署段落定案為 Cloudflare Pages。
- [ ] §15 驗收條件依上述修訂重編，每條給可引用編號。
- [ ] 修訂後跑 `/codex-checkplan`，**第二輪只審「修訂本身」**——上次經驗是 17 項發現裡有 4 項是第一輪修訂自己造出來的洞。

## M1 — repo 鷹架與 ETL

- [ ] `git init`、首個 commit、建 GitHub repo（private 或 public 待定）。
- [ ] `.gitignore`（排除下載的 ZIP／CSV 與 `reports/` 大檔）、`LICENSE`、`pyproject.toml`、`package.json`。
- [ ] `scripts/fetch_tfda.py` — 複用 `../TFDA-drug-shortage-dashboard/scripts/fetch_fda_data.py` 的 fail-closed 骨架：HTTP 驗證、ZIP 完整性、UTF-8-BOM 解碼、非零退出不覆寫正式資料、`os.replace` 原子替換。
- [ ] `scripts/validate_schema.py` — 釘住 16 個欄名與順序；缺欄／改名／多欄各自分級（硬失敗 vs warning）。
- [ ] `scripts/build_data.py` — protocol 收斂、版本排序、sentinel 分型處理、產生 `manifest.json` / `stats.json` / `search-index.json` / `trials/*.json`。
- [ ] `manifest.json` 必含 `sourceUpdatedAt`（來源欄位最大值）與 `builtAt`（本站 build time），**兩者分開**。
- [ ] QA report：筆數、收斂前後數量、nullness、sentinel 計數、平手組數、與前次成功 build 的比較。

### ETL 測試（fixture 驅動，不連網）

- [ ] BOM、quoted comma、embedded newline、CRLF、超長文字（單列 22,490 字元）。
- [ ] 期別羅馬數字變體（`Phase Ⅰ`／`Phase Ⅱ`／`Phase Ⅰ,Phase Ⅱ`／`其他`／`0`）保留 raw 值。
- [ ] 收案人數 `0`、空值、非數字（`maxlen` 為 30，需確認是否有千分位或範圍寫法）。
- [ ] protocol 重複、空 protocol、`TFDA收文號` 重複與 `移案BPA` 非數字值。
- [ ] tie-break 規則的確定性：同一份輸入跑兩次輸出必須逐位元相同；打亂列序後輸出仍相同。
- [ ] 來源失敗（HTTP 500／HTML 錯誤頁／壞 ZIP／空 CSV）時，既有正式 JSON 未被覆寫。
- [ ] 筆數驟降 >20% 硬失敗、>10% 產出 warning。

## M2 — 前端 MVP

- [ ] 首頁單一任務：搜尋。搜尋欄位 = protocol、試驗中文名稱、申請者、適應症中文、試驗目的、主要評估指標、`TFDA收文號`。
- [ ] Unicode 正規化（NFKC、全半形、trim、壓縮重複空白）；多詞預設 AND 並在 UI 標示邏輯。
- [ ] **顯示命中欄位**（「命中：適應症／試驗目的」），避免誤以為名稱完全相符。
- [ ] 篩選：期別、規模、預計執行期間、台灣預計人數區間、申請者、資料更新時間。**不得有招募狀態篩選。**
- [ ] URL query 可重現搜尋＋篩選狀態。
- [ ] 結果卡欄位依 spec §6.3；**不顯示任何招募中標章**。
- [ ] 詳情頁：試驗目的 → 主要評估指標 → 納入條件 → 排除條件，保留原文換行、可折疊但 heading 立即可見；顯示來源資料日期與 build time；複製 protocol／連結；連回官方資料集。
- [ ] 詳情頁的審查紀錄歷史（依 D2 定案）。
- [ ] 統計卡：試驗數、期別分布、規模分布、前 10 申請者、前 10 適應症、台灣預計人數分布。**每張卡都要寫出分母是試驗還是審查紀錄。**
- [ ] 空值／錯誤狀態：統一顯示「未提供」但 raw 可稽核；日期無法解析顯示原值並標記；無結果保留 query 與清除篩選鈕；載入失敗顯示最後成功資料日期。

### 前端測試

- [ ] 中英文查詢、全半形正規化、AND 邏輯、篩選 URL 持久化。
- [ ] 命中欄位標籤正確性。
- [ ] 分類 sentinel 不出現在篩選選單；數值 0 仍顯示為 0。
- [ ] 長條件渲染與 XSS escape（來源文字含引號、角括號）。
- [ ] 360 px 無水平捲動、鍵盤導航、focus 可見、WCAG 2.2 AA 對比**當場量測不憑印象**。
- [ ] 圖表有 table／list 替代呈現。
- [ ] Cloudflare Pages 上的 404 與 deep-link 行為。

## M3 — CI 與月更新

- [ ] `ci.yml`：lint、type-check、pytest、vitest、build、a11y smoke，失敗上傳 artifact。
- [ ] `update-data.yml`：月排程 + `workflow_dispatch`，`concurrency` 序列化，下載到 temp、成功才發布，產出 diff 摘要，僅在正規化輸出有變動時 commit。
- [ ] 失敗時保留 last known good 並開 issue／通知。
- [ ] Actions pin commit SHA，`contents: write` 只給更新 job。
- [ ] **上線當天手動 dispatch 一次，再跑第二次驗冪等**——早退路徑只在「穩定態＋無事可做」時才顯形，單一函式測試驗不到。
- [ ] Cloudflare Pages 專案設定與首次部署。

## M4 — 收尾

- [ ] README 更新為「已上線」，補實際網址與最新資料日期。
- [ ] 加入 `pharmacy-portal` 的 `tools.json` 與首頁。
- [ ] 跑 `/codex-review` 覆審程式碼。
- [ ] 決定是否需要 service worker。若要做，快取前綴必須限定自家（即使在獨立 origin 上也照規矩寫）。

---

## 明確不做（勿在後續迭代偷偷加回來）

- dataset 206–209 的任何 join。
- 受試者適格性判定、病歷／病況輸入。
- 招募狀態顯示或推論（含把 `no longer present` 稱為 terminated）。
- AI 生成試驗摘要、療效比較、試驗品質評分。
- 醫院 geocoding 與「附近正在招募」。
- 搜尋字串 analytics。
- PI 姓名的人物績效排行。
