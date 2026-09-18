# TODO

狀態：**M1 進行中（ETL 主體已完成）。** 規格本體是 `.ai-review/plan.md` **v0.7**，驗收編號 A1–H5，動工前契約 **14 項**（§14）。

四項全部完成：A 群補 v0.5 案例（73 列／45 Trial）、最小 artifact 樣本（B8）、B 群失敗注入 fixture、§9.3.6 不變量反例（B6）與 C4 的三個 mutation。`tests/fixtures/run_all.py` **244 條斷言全綠**（v0.6 收斂後）。

本輪反驗出 **GAP-8（High）／GAP-9／GAP-10／GAP-11（Medium）／GAP-12（Low）**，全部 open，見 `.ai-review/fixture-findings-m05.md`。

M1 已完成 ETL 主體：`trial_radar/` 十個模組涵蓋 §6 全部規則、§9.1 取得與驗證、§9.3 輸出契約、§9.3.6 驗證器、§9.6 QA report、§9.2 promotion，＋ `scripts/build_data.py` CLI。**pytest 141 綠**（A 群 27／B 群 64／C 群 50），fixture 自檢 `run_all.py` 289 條斷言全綠。

下一步：`scripts/fetch_tfda.py` 與 `validate_schema.py` 拆成獨立 CLI、首次連網實跑、然後 **M2 前端**。

**M1 前不要寫 ETL 實作程式碼**（`artifact_sample/build_sample.py` 是 B8 的證據，不是實作，M1 不得沿用）。

---

## M0 — 規格修訂與覆審

- [x] 依實測推翻 v0.1 的六節（§2／§6.6／§7.1／§7.2／§7.3／§16）→ 產出 v0.2
- [x] 第一輪 `/codex-checkplan`（`plan-review-r1.md`，56 項發現）
- [x] 逐項判定（`plan-verdict-r1.md`，接受 51／部分接受 5／拒絕 0）
- [x] 依判定改寫為 v0.3 單一 normative 規格，v0.1／v0.2 降為歷史文件
- [x] 第二輪 `/codex-checkplan`，只審 v0.2 → v0.3 的變更（`plan-review-r2.md`，54 項、**Blocker 0**）
- [x] 第二輪判定（`plan-verdict-r2.md`，接受 53／部分接受 1／拒絕 0）；三項第一輪偏離被否決並改正
- [x] 依判定改寫為 v0.4
- [x] 先寫 A 群 fixture 反驗規格（`tests/fixtures/`，50 列／29 Trial ＋ A7 碰撞 fixture；`check_a_core.py` 全綠）。找到 **7 個規格洞**，見 `.ai-review/fixture-findings-a.md`
- [x] 第三輪 `/codex-checkplan` 限縮範圍，並一併送審 fixture 的 7 個洞（`plan-review-r3.md`：7 洞判定 6 成立 1 不成立，另 1 Blocker、3 High、4 Medium）
- [x] 第三輪判定（`plan-verdict-r3.md`，接受 12／不成立 1／拒絕 0）
- [x] 依判定產出 **v0.5**，十項契約封存（見 plan.md §14）

### A 群 fixture 反驗出的 7 個洞——全部結案

| # | 處置 | v0.5 章節 |
|---|---|---|
| GAP-1 | 已修（欄位層級 `rawVariants` ＋ `recordId` 字典序最小者為代表值） | §6.4.3 |
| GAP-2 | 已修（ordinal 一律從 `#0` 起，**並同步套用於 `recordId`**——原只修一半） | §6.3.2 |
| GAP-3 | 已修（`{raw,typed,flags}` 三元組；**衝突欄位完全省略**而非 `{typed:null}`） | §6.4.5 |
| GAP-4 | 已修（空 protocol 也算；嚴重度下修 Medium→Low） | §6.2.2 |
| GAP-5 | **建議被否決**，改用 semantic comparison key | §6.4.2 |
| GAP-6 | 已修（A8 改注入雜湊替身；嚴重度下修 High→Medium） | §11 A8 |
| GAP-7 | 已修（`buildDate` 可注入 ＋ `Asia/Taipei` ＋ 兩個邊界案例） | §6.5.1 |

### 第三輪另抓到的 Blocker

**`datasetVersion` 與整體 digest 循環定義**：v0.4 要求每個檔案內含 `datasetVersion`，而 `datasetVersion` 又等於這些檔案**最終位元組** digest 的前 16 hex → 無固定點，照文字寫不出合規 artifact。**這是我在 v0.4 修 N8 時自造的。** 已於 v0.5 §9.3.2 分離為 `datasetVersion`（logical payload）與 `artifactDigest`（最終位元組）。

### 已定案（原未定案項）

- ~~D1 tie-break 規則~~ → **不做 tie-break**。同日衝突以 `latestAmbiguous` + `conflictFields` 表達，卡片只顯示無衝突共同欄位（§6.4）。實測 846 平手組中 689 組全同、157 組 raw 有差異、其中 143 組正規化後仍衝突。
- ~~D2 版本歷史呈現深度~~ → **不做方向性 diff**。只標示「哪些欄位存在不同值」，同日多筆明示「順序未知」（§7.3）。
- ~~搜尋範圍~~ → **分層，預設最小**。預設 5 短欄 × 最新 cohort（約 715–900 KiB gzip），擴大控制項須在結果區可見（§8.5）。實測 v0.3 原訂的「全部歷史 × 7 欄」為 6,958 KiB，是預算的 4.6 倍。

## M0.5 — B 群 fixture ＋ 最小 artifact 樣本（取代第四輪 prose 覆審）

理由：A 群的經驗是「寫 fixture 比再讀一遍 prose 更能找出問題」——它抓到 7 個洞，包含一條**數學上無法滿足**的驗收條件。十項契約已封存，現在要證明它們可實作。本輪又抓到 5 個。

- [x] 補 A 群 fixture 缺的 v0.5 新案例：空白-only protocol（ASCII 空白／U+3000 各一）、`buildDate` 當日與 +1 日邊界、`numericRange` 各型（嚴格範圍／`min>max`／超界／約略值不推論）、前導零、`suspectedTestRow` 的 `TEST` 值型、期間端不可解析與缺值。**50 → 73 列、29 → 45 Trial**
- [x] `check_a_core.py` 的 [2] 分類改用 §6.4.2 的 semantic comparison key；[4] 改用 §6.6.3 的完整 lexical grammar（八類互斥、加總須等於 `列數 × 2`）
- [x] **產出最小 artifact 樣本**（`tests/fixtures/artifact_sample/`）：8 個 Trial、12 個非 manifest 檔 ＋ `manifest.json`，**B8 四條全綠**。關鍵是 B8-1b——從已寫入版本欄位的最終檔案反算得同一個 `datasetVersion`，即循環被解開的操作型證據
- [x] B 群 fixture（`tests/fixtures/b_failures/`）：12 個注入輸入涵蓋 §9.5 可用位元組表達的每個 error code；transport／publish 層列為注入點；B4 的門檻以 `(prev, cur)` 整數對驅動，不造大 CSV；B5 的 9 個 promotion 失敗點成清單
- [x] §9.3.6 每條不變量的反例（`check_b6.py`）：11 種缺陷，每個斷言**違規集合 exactly equals 預期**，另加「未變造樣本零違規」的反向哨兵
- [x] C4 的三個獨立 mutation（`check_c4.py`）：各自斷言「只有目標那組斷言轉紅」

全部自檢：`python tests/fixtures/run_all.py`（M0.5 結案時 240 條，v0.6 收斂後 **244 條**，全綠）。

### 本輪反驗出的 5 個洞（已全部併入 v0.6，待覆審）

| # | 嚴重度 | 章節 | 一句話 |
|---|---|---|---|
| GAP-8 | **High** | §6.4.2 | 比較鍵表漏了 `numericRangeInvalid`／`numericOutOfRange`／`categoricalUnknown`，同日兩列處於這些狀態時衝突與否無法從規格導出。觸發於 `CMP-035`／`CMP-036`／`CMP-037` |
| GAP-9 | Medium | §6.6.3 | 「可表示範圍」沒有序位，與「第一個命中者決定結果」字面矛盾；單端超界的範圍值行為未定義 |
| GAP-10 | Medium | §9.3.5／F1 | `stats.json` 的 facet 名單未封閉（E2 的 oracle 沒來源），且它在 Tier 0 卻沒計入 F1 的 1,236 KiB 基線 |
| GAP-11 | Medium | §9.3.6 | 不變量之間有依賴（排序鍵取自 shard 內的 record）但沒有評估順序，使 B6 的「各自獨立反例」結構上做不到 |
| GAP-12 | Low | §9.6 | 「以有理數比較」在 `prev ≤ 20,000` 的定義域內與 float 判定恆等，**測不出違反**；真正守得住的是「不四捨五入」 |

展開見 `.ai-review/fixture-findings-m05.md`。**GAP-8 修訂後 `check_a_core.py` 的 [8] 段會轉紅，那是預期的**，改 oracle 時一併移除。

## M1 — repo 鷹架與 ETL（驗收 A／B／C 群）

**十項動工前契約已封存**，見 `plan.md` §14。動工時直接依該表實作，不要重新推導。

然後：

- [ ] `git init` 後首個 commit 已完成；建 GitHub repo（public／private 待定）
- [x] `.gitignore`（排除下載的 ZIP／CSV 與產生物）
- [ ] `LICENSE`、`pyproject.toml`、`package.json`
- [ ] `scripts/fetch_tfda.py` — fail-closed 下載與驗證，error code 依 §9.5，每種相異 exit code
- [ ] `scripts/validate_schema.py` — 釘住 16 欄欄名與順序
- [ ] `scripts/build_data.py` — identity 收斂、cohort 與 ambiguity 判定、sentinel 分型、日期規則、產出 §9.3 全部 artifact
- [ ] 整體 digest 與 referential integrity 驗證；內容雜湊檔名；`manifest.json` 為唯一固定 URL
- [ ] promotion：替換 + `git add -A` + commit 收攏為最後三步；保證「不存在部分發布的 commit」（§9.2.1）
- [ ] `builtAt` 語意依 §9.4（比較時排除 `builtAt`／`fetchedAt`／**`sourceSha256`**）
- [ ] QA report（結構化，warning 不可只印 log）：筆數、收斂前後數量、平手組與衝突組計數、nullness、sentinel 三類計數、日期異常四類（含 7 列 end<start）、`nearDuplicateGroup` 全部 raw 值、`protocolNonIdentifier` 與疑似測試列、每次抓取的 `sourceSha256`、與前次成功快照比較

### 測試（fixture 驅動，不連網）

A 群 fixture **已建立並補齊 v0.5 案例**（`tests/fixtures/a_core/` 73 列、`a7_identity_collision/` 5 列），以下是待寫的**測試**本身：

- [ ] A1 fingerprint → trialId 的 group membership。「不應合併」反例用 §6.2 **不折疊**的差異（連字號／空格／括號閉合），**不可**用大小寫或全半形（那些會折疊，屬 A7）
- [ ] A2 每個案例附 oracle；必含 ≥2 筆完全相同空 protocol、≥3 組同日衝突、≥1 組同日正規化後全同、**≥1 組同日僅空白／全半形差異（須判為不衝突）**、≥1 個 `nearDuplicateGroup`、≥1 筆 `protocolNonIdentifier`、**四類日期異常各 ≥1**（不可解析／空值／未來日期／end<start）
- [ ] A3 reverse + ≥3 seed + 「重複列 × 平手 × 空 protocol」交叉 property invariant → 檔案 inventory 相同 + 逐檔 hash 相同 + tie case 語意相同
- [ ] A4 反向哨兵：改「任取 cohort 第一筆」時須失敗於**指定 tie group 的 `latestAmbiguous` 翻轉**；oracle 須涵蓋 `displayFields`、篩選分組與統計輸出（只留旗標但把第一筆值塞進 displayFields 的實作要被殺死）
- [ ] A5 canonical fingerprint 完整 multiset 含 multiplicity；oracle 的 row identity **獨立於 §6.3 的 serialization**（否則自我驗證）；含分隔符／長度前綴邊界 fixture
- [ ] A6 兩筆相同空 protocol 各取得唯一 ID
- [ ] A7 identity 碰撞 → `IDENTITY_COLLISION` 硬失敗，且 collision report 須唯一定位 group／raw 值／正規化值／fingerprint（**空 report 要使測試失敗**）
- [ ] A8 trialId／recordId 截短碰撞 → `ID_TRUNCATION_COLLISION`。**改以注入的雜湊替身驅動**（真實 64 位元碰撞不可建構，見 GAP-6），規格待第三輪修訂後定案
- [ ] A9 `nearDuplicateGroup` 偵測 18 組實測案例；`protocolNonIdentifier` 不入 group；loose key **不影響任何收斂結果**
- [ ] B1 §9.5 每個 error code 各一測試；斷言已發布狀態未變（檔名集合、每檔 hash、`manifest.files` 指向、整體 digest）且**無新增正式檔**；content-type 測 `application/zip;charset=utf-8` 通過、`text/html` 失敗
- [ ] B2 structured error code + layer，不以 stderr 字串判定；**多重異常 fixture 驗 precedence**（transport→archive→decode→schema→content→publish）
- [ ] B3 schema 通過後才因零列失敗
- [ ] B4 drop = 0.0／0.10／0.1001／**0.20**／0.2001／整數邊界／bootstrap；warning 須落在 `qa/quality-report.json` 結構化欄位（只印 log 要失敗）
- [ ] B5 失敗注入點涵蓋**每個正式狀態變更之後**：替換第一個／部分／最後一個 artifact、刪 orphan 途中、`git add` 只含部分變更、commit 失敗、push 失敗、部署啟用失敗、**SIGTERM／取消**。每點斷言「不存在部分發布的 commit」
- [ ] B6 referential integrity 反例各自獨立（record 被兩個 Trial 引用／同 Trial 重複引用／放錯 shard／`manifest.files` 與實際檔案集合不符／引用不存在的 recordId）
- [ ] B7 跨版本綁定：manifest 新版 + shard 舊 `datasetVersion` → 前端 fail-closed「資料版本不一致，請重新載入」；斷言除 manifest 外全部檔名帶內容雜湊
- [ ] C1 **兩個**分類欄位各自通過五處斷言
- [ ] C2 依 §6.6 表格逐筆斷言 0／正整數／空／無法解析／負數的 typed value、旗標、warning 分級、UI 文字（對所有數字都設 `sourceZero` 要失敗）
- [ ] C3 `N/A`／`NA`／`""` 精確計數與 recordId
- [ ] C4 三個獨立且**確為違規**的 mutation：raw 值遺失／facet 保留 `"0"`／文字 sentinel 塌成同一值。**不可用「分類 typed value 轉 null」**（那是 §6.6 規定的正確行為）
- [ ] BOM、quoted comma、embedded newline、CRLF、TAB、22,490 字元超長文字
- [ ] 期別羅馬數字變體保留 raw

## M2 — 前端 MVP（驗收 D／E／F／G 群）

- [ ] 首頁單一任務搜尋；search normalization（§8.1）與 matching operator（§8.2：空白切詞、substring、空查詢不搜尋）
- [ ] 多詞語意：**record 層 AND、欄位層 OR**，UI 顯示邏輯（§8.3）
- [ ] **搜尋 scope 分層**（§8.5）：預設 `fields=short`+`history=latest`；擴大控制項在結果區可見、切換前顯示大小（取自 `manifest.files[*].gzipBytes`）、scope 指示持續可見、零結果提示可擴大、載入失敗退回上一個 scope
- [ ] 命中標示（§7.2）：欄位名 + 來源紀錄日期；非最新標「命中來自 YYYY/MM/DD」；無可採計日期標「資料日期不明」**不得偽造日期**
- [ ] 篩選六維度（§8.4）含值域、bucket 閉區間、`period` 重疊語意；**同維度 OR、跨維度 AND**；**無招募狀態維度**
- [ ] 結果卡：`displayFields` + `latestAmbiguous`／`dateUnknown`／`protocolNonIdentifier` 標記；衝突欄位不顯示任何候選值
- [ ] 詳情頁：全部 records 依日期分組、同日明示「順序未知」、無日期者置末；長文字保留原文換行不截斷；`nearDuplicateGroup` 顯示近似編號提示與連結
- [ ] 統計卡以 Trial 為分母並明寫「試驗」；`buckets + unprovided + conflicted` 須等於 `denominators.trials`
- [ ] URL state schema（§7.4）：參數名／順序／編碼／重複參數／未知參數保留／無效值明確訊息；`?protocol=` 以 identity 正規化後比對並導向 canonical
- [ ] 免責三項核心性質在三個頁面可見（§10），可見性綁定 G1／G2 oracle
- [ ] 數字卡與清單為必須；**圖表可選**，依 payload 與 a11y 成本決定
- [ ] D1–D7、E1–E8、F1–F4、G1–G4 測試

## M3 — CI 與月更新（驗收 H 群）

- [ ] `ci.yml`：lint、type-check、pytest、vitest、build、a11y smoke；每個 gate 注入已知失敗驗證會 fail；無 `continue-on-error`
- [ ] `update-data.yml`：月排程 + `workflow_dispatch`，**schedule 與 manual 共用同一 concurrency group**、`cancel-in-progress: false`
- [ ] **baseline 取樣時點為取得發布權之後**：顯式 fetch 並 checkout 預設分支最新 tip（`actions/checkout` 預設取觸發時 SHA，排隊後會是舊的）；promotion 前再驗證版本未變，不符即 fail-closed
- [ ] 失敗時保留 last known good 並開 issue／通知
- [ ] Actions 所有直接與間接 `uses` pin 不可變 SHA；預設 permissions 最小，只有更新 job 有 `contents: write`
- [ ] **上線當天手動 dispatch 一次，再跑第二次驗冪等**：第二次**重新下載並驗證 source SHA 相同**（不是快取第一次結果），斷言兩次都完整跑完 pipeline、第二次回報 no normalized change 且不產生 commit
- [ ] H2 的真正重疊情境測試（兩 run 同時排隊、前一個發布後第二個須重取 baseline）
- [ ] Cloudflare Pages 專案設定與首次部署

## M4 — 收尾

- [ ] README 更新為「已上線」，補網址與最新資料日期；補 §6.3 的 ID 穩定性界限說明
- [ ] 加入 `pharmacy-portal` 的 `tools.json` 與首頁
- [ ] 跑 `/codex-review`，以 plan.md 的 A1–H4 編號做規格符合度稽核

---

## 明確不做（勿在後續迭代偷偷加回來）

- dataset 206–209 的任何 join。
- 受試者適格性判定、病歷／病況輸入。
- 招募狀態顯示或推論。**也不保留 feature flag。**
- 有方向性的版本 diff（`A → B` 箭頭）。
- **自動合併近似的 protocol 寫法**（18 組已知，僅揭露不合併；人工裁決合併表列為後續版本）。
- AI 生成試驗摘要、療效比較、試驗品質評分。
- 醫院 geocoding 與「附近正在招募」。
- 搜尋字串 analytics。
- PI 姓名的人物績效排行。
- Service worker／PWA。
