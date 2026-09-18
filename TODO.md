# TODO

狀態：**M0 規格已過第一輪覆審，待第二輪。** 規格本體是 `.ai-review/plan.md` v0.3，驗收編號 A1–H4。

**M0 未結案前不要寫實作程式碼。**

---

## M0 — 規格修訂與覆審

- [x] 依實測推翻 v0.1 的六節（§2／§6.6／§7.1／§7.2／§7.3／§16）→ 產出 v0.2
- [x] 第一輪 `/codex-checkplan`（`plan-review-r1.md`，56 項發現）
- [x] 逐項判定（`plan-verdict-r1.md`，接受 51／部分接受 5／拒絕 0）
- [x] 依判定改寫為 v0.3 單一 normative 規格，v0.1／v0.2 降為歷史文件
- [ ] **第二輪 `/codex-checkplan`，只審 v0.2 → v0.3 的變更**。第一輪 56 項裡有 11 項是 v0.2 修訂自造的洞，第二輪不能省
- [ ] 第二輪判定與（若需要）v0.4

### 兩項未定案已在 v0.3 定案

- ~~D1 tie-break 規則~~ → 改為**不做 tie-break**。同日衝突以 `latestAmbiguous` + `conflictFields` 表達，卡片只顯示無衝突共同欄位（plan.md §6.4）。實測 846 平手組中 689 組全同、157 組真衝突。
- ~~D2 版本歷史呈現深度~~ → 改為**不做方向性 diff**。只標示「哪些欄位存在不同值」，同日多筆明示「順序未知」（plan.md §7.3）。原本想做的「20 → 30」箭頭方向可能寫反。

## M1 — repo 鷹架與 ETL（驗收 A／B／C 群）

**M1 前先封存這四項**（最難回頭，同時定義資料實體、歷史歸屬與外部連結）：

- [ ] identity normalization 規則（plan.md §6.2）
- [ ] 同日衝突模型（§6.4）
- [ ] Trial／SourceRecord ID 與 canonical serialization（§6.3）
- [ ] 輸出契約與 shard 映射（§9.3）

然後：

- [ ] `git init` 後首個 commit 已完成；建 GitHub repo（public／private 待定）
- [ ] `.gitignore`（排除下載的 ZIP／CSV 與大型 QA 檔）、`LICENSE`、`pyproject.toml`、`package.json`
- [ ] `scripts/fetch_tfda.py` — fail-closed 下載與驗證，error code 依 §9.5，每種相異 exit code
- [ ] `scripts/validate_schema.py` — 釘住 16 欄欄名與順序
- [ ] `scripts/build_data.py` — identity 收斂、cohort 與 ambiguity 判定、sentinel 分型、日期規則、產出 §9.3 全部 artifact
- [ ] 整體 digest 與 referential integrity 驗證；**發布邊界為 git commit**，不用逐檔 `os.replace`
- [ ] `builtAt` 語意依 §9.4（比較時排除 `builtAt`／`fetchedAt`）
- [ ] QA report：筆數、收斂前後數量、平手組與衝突組計數、nullness、sentinel 三類計數、日期異常（含 end<start）、與前次成功 build 比較

### 測試（fixture 驅動，不連網）

- [ ] A1 fingerprint → trialId 的 group membership，含「易被過度正規化錯合併」與「應合併」案例
- [ ] A2 fixture 每個案例附 oracle（含 ≥2 筆完全相同的空 protocol 列、≥3 組同日衝突、≥1 組同日全同）
- [ ] A3 reverse + ≥3 seed 排列 → 檔案 inventory 相同 + 逐檔 hash 相同 + tie case 語意相同
- [ ] A4 反向哨兵：改成「任取 cohort 第一筆」時 A3 須失敗，且證明失敗點是 `latestAmbiguous` 翻轉
- [ ] A5 canonical fingerprint 完整 multiset 含 multiplicity
- [ ] A6 兩筆相同空 protocol 各取得唯一 ID
- [ ] A7 identity 碰撞 → `IDENTITY_COLLISION` 硬失敗
- [ ] B1 §9.5 每個 error code 各一測試；斷言完整檔名集合、每檔 hash、manifest 指向不變、無新增正式檔
- [ ] B2 structured error code + layer，不以 stderr 字串判定
- [ ] B3 schema 通過後才因零列失敗
- [ ] B4 drop = 0.0／0.10／0.1001／0.20／0.2001／bootstrap 邊界
- [ ] B5 四個失敗注入點都不產生 commit，正式資料整體等於舊版
- [ ] B6 referential integrity 反例
- [ ] C1 分類 sentinel 五處斷言
- [ ] C2 0／非 0／空白／malformed 逐筆斷言 `sourceZero` 真值
- [ ] C3 `N/A`／`NA`／`""` 精確計數與 recordId
- [ ] C4 三個獨立 mutation 分別殺死 C1／C2／C3
- [ ] BOM、quoted comma、embedded newline、CRLF、22,490 字元超長文字
- [ ] 期別羅馬數字變體保留 raw

## M2 — 前端 MVP（驗收 D／E／F／G 群）

- [ ] 首頁單一任務搜尋；7 個可搜尋欄位（§8.2）；search normalization（§8.1）
- [ ] 多詞語意：record 層 AND、欄位層 OR，UI 顯示邏輯（§8.3）
- [ ] **搜尋涵蓋全部 SourceRecord（含歷史）**，命中標籤須指出欄位與該紀錄日期；命中非最新者標示「命中來自 YYYY/MM/DD 的審查紀錄」（§7.2）
- [ ] 篩選六維度（§8.4）；**無招募狀態維度**；衝突欄位歸入「同日多筆不一致」分組
- [ ] 結果卡：`displayFields` + `latestAmbiguous` 標記；衝突欄位不顯示具體值
- [ ] 詳情頁：全部 records 依日期分組、同日明示「順序未知」；長文字保留原文換行不截斷
- [ ] 統計卡以 Trial 為分母並明寫「試驗」；衝突與 sentinel 計入「未提供／不一致」
- [ ] URL 契約（§7.4）：`?trial=`、`?protocol=` 別名、未知 ID 的明確訊息
- [ ] 免責三項核心性質在三個頁面可見（§10）
- [ ] 數字卡與清單為必須；**圖表可選**，依 payload 與 a11y 成本決定
- [ ] D1–D6、E1–E7、F1–F3、G1–G4 測試

## M3 — CI 與月更新（驗收 H 群）

- [ ] `ci.yml`：lint、type-check、pytest、vitest、build、a11y smoke；每個 gate 注入已知失敗驗證會 fail；無 `continue-on-error`
- [ ] `update-data.yml`：月排程 + `workflow_dispatch`，**schedule 與 manual 共用同一 concurrency group**、`cancel-in-progress: false`
- [ ] baseline 一致性檢查；失去一致性時 fail-closed
- [ ] 失敗時保留 last known good 並開 issue／通知
- [ ] Actions 所有直接與間接 `uses` pin 不可變 SHA；預設 permissions 最小，只有更新 job 有 `contents: write`
- [ ] **上線當天手動 dispatch 一次，再跑第二次驗冪等**（重用相同 source SHA，斷言兩次都完整跑完且第二次 tree 不變）
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
- AI 生成試驗摘要、療效比較、試驗品質評分。
- 醫院 geocoding 與「附近正在招募」。
- 搜尋字串 analytics。
- PI 姓名的人物績效排行。
- Service worker／PWA。
