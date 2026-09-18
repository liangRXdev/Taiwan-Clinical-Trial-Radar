# Codex 規格覆審原始輸出（第二輪）

- **審查日期**：2026-09-18
- **Codex 版本**：codex-cli 0.153.4（MCP `mcp__codex__codex`，`sandbox: read-only`、`approval-policy: never`）
- **thread id**：`01a0b1f3-7513-7b90-824a-e8d500fb06ff`
- **受審對象**：`.ai-review/plan.md` v0.3（commit `2ffa7c7`），**審查範圍限定為 v0.2 → v0.3 的修訂本身**
- **另要求**：覆核第一輪我判定「部分接受」而偏離 Codex 修法的五項

以下為 Codex 輸出，**原封不動**未修飾、未刪改。判定見 `plan-verdict-r2.md`。

---

以下僅審查 v0.2→v0.3 修訂造成或未封閉的規格問題；不重提已完成修正的第一輪項目。

# 1. 修訂自造的新洞

## N1｜High／canonical serialization 並非一對一

- **問題**：以 U+001F 直接連接 16 欄，卻未禁止來源欄位含 U+001F，也未定義 escaping。不同的 16 欄 tuple 可能得到相同 canonical serialization。另 `trialId`／`recordId` 只取 SHA-256 前 16 hex，但沒有規定截短碰撞時必須如何處理。
- **為什麼現在不修之後會更貴**：這些值同時成為 URL、shard reference、搜尋索引與歷史紀錄鍵。上線後才改會使 URL、bookmark、fixture oracle 與已發布資料全面失效。
- **建議修法**：規格要求 canonical encoding 必須對 16 欄 tuple 一對一，並明定完整 identity key、trialId、recordId 的碰撞檢測與 fail-closed 行為；M1 前封存。

## N2｜High／「呈現欄位」沒有封閉集合

- **問題**：§6.4 以「呈現欄位有衝突」決定 `latestAmbiguous`，但未列出哪些欄位屬於呈現欄位。實作者可排除期別、人數或主要評估指標，使衝突消失，仍表面符合條文。
- **為什麼現在不修之後會更貴**：`latestAmbiguous` 會進入 Trial schema、篩選、統計卡及 UI；日後擴大集合會改變既有 Trial 的語意及統計結果。
- **建議修法**：列出封閉欄位清單，或明定為 16 欄扣除哪些技術欄位；同時定義 `conflictFields` 是否使用 raw 或 typed value 比較。

## N3｜High／未來日期可支配卡片「最新資料」

- **問題**：未來日期被排除於全站 `sourceUpdatedAt`，卻仍參與 trial 內 latest 選擇及卡片顯示。單筆錯誤的 2099/01/01 可永久遮蔽所有正常紀錄，且卡片仍以它的值代表 Trial。
- **為什麼現在不修之後會更貴**：這會直接影響最核心的 `displayFields`，符合威脅模型中「誤導臨床人員」的高風險情境；之後修正會改動 Trial 收斂結果、統計與 UI。
- **建議修法**：未來日期不得在未經明確降級語意下支配卡片代表值。規格應在「排除於 latest」或「整個 Trial 進入不確定狀態」間明確選擇，並補相應 oracle。

## N4｜Medium／搜尋只有正規化，沒有定義 matching operator

- **問題**：§8 定義 normalization、欄位與 record-level AND，但沒有定義：
  - 詞如何切分；
  - 是否為 substring、完整詞、prefix 或 token match；
  - 空白查詢／只有空白的查詢；
  - 中文無空白字串如何處理。
- **為什麼現在不修之後會更貴**：搜尋索引格式、效能測試與 URL 狀態都會依 matching operator 決定；M2 才發現會重做索引與 D/F fixture。
- **建議修法**：把 query→terms→欄位命中的判定寫成唯一規範，並列出中文、英文、protocol、空查詢的正反例。

## N5｜Medium／篩選維度有名稱，沒有值域及組合語意

- **問題**：§8.4 沒有定義人數區間、日期區間、試驗期間的邊界，也沒定義跨維度是 AND、同維度多選是 OR 還是 AND。申請者使用 raw、displayFields 或正規化值亦未寫明。
- **為什麼現在不修之後會更貴**：filter schema、stats、URL 與 D4 oracle 會各自形成不同事實標準。
- **建議修法**：在規格層封存每個維度的 typed value、bucket 邊界、null／衝突歸類，以及單維度與跨維度組合規則。

## N6｜Medium／URL 契約不足以支持「精確 URL」驗收

- **問題**：只定義 `trial` 與 `protocol`，但搜尋／篩選 query param 的名稱、重複參數、排序、編碼、空值、無效值及 canonicalization 都未定義。`protocol=<raw protocol>` 也未寫明是 raw 精確比對還是 identity normalization 後比對。
- **為什麼現在不修之後會更貴**：一旦 URL 被分享或收藏，後續修正即成相容性問題；D4 的「canonical URL 字串精確相等」目前沒有唯一 oracle。
- **建議修法**：補完整 URL state schema 與 canonical serialization；明確定義 protocol alias 的 decode、matching 及轉址結果。

## N7｜Medium／歷史命中標示無法涵蓋不可解析日期

- **問題**：§7.2 要求標示「命中的欄位名與該紀錄的資料更新時間」，非最新命中固定寫成 `YYYY/MM/DD`；但 §6.5 允許不可解析或空日期的紀錄保留並被搜尋。
- **為什麼現在不修之後會更貴**：搜尋結果模型或 UI 會被迫自行發明 fallback，產生不同語意。
- **建議修法**：規格補上不可解析／空日期命中的固定標示語意，且不得偽造成合法日期。

## N8｜High／git commit 不能單獨形成瀏覽器讀取的資料集交易

- **問題**：commit 可保證 repository tree 是一致快照，但不能自行保證同一瀏覽器在多次 request 中不混用舊 manifest、舊快取與新 shard。所有 artifact 使用固定 URL，規格又未定義跨檔版本綁定或 cache 一致性。
- **為什麼現在不修之後會更貴**：搜尋索引、Trial index 與 record shard 一旦跨版本混用，會出現不存在的 reference 或顯示錯誤紀錄；這通常只在實際部署及快取條件下發生。
- **建議修法**：規格須明確保證「一次前端資料載入只能解析同一發布版本」，並將 Cloudflare build 所用 SHA、部署啟用邊界、瀏覽器／CDN cache 行為及版本不一致時的 fail-closed 行為納入發布契約。這不必然強制採 snapshot 目錄，但目前的 commit 論證不足。

# 2. 修訂不完整

## I1｜High／§9.3 仍不是可驗證的輸出契約

- **問題**：只列出檔名與少數欄位，沒有定義：
  - 各 JSON 的 top-level shape；
  - required／optional／nullable 欄位及型別；
  - `stats.json` 結構；
  - `search-index.json` 結構及 posting 語意；
  - shard 內容結構；
  - artifact inventory 或整體 digest 的定義。
- **為什麼現在不修之後會更貴**：前端與 ETL 可以各自做出通過局部測試但互不相容的格式；M2 才補會改動 M1 產物和全部 fixture。
- **建議修法**：M1 前封存逐檔 schema、required fields、nullability、排序及交叉 reference invariant；定義「整體 digest」究竟涵蓋哪些檔案與 metadata。

## I2｜High／全日期不可解析的修法內部不完備

- **問題**：§6.4 定義 `latestAmbiguous = latestCohort 長度 >1 且有衝突`；§6.5 卻規定某 Trial 全部日期不可解析時，無條件 `latestAmbiguous=true`。此時 `latestCohort` 是空陣列、全部不可解析紀錄，或其他集合，均未定義。
- **為什麼現在不修之後會更貴**：這會影響 Trial schema、卡片、篩選分組、統計與 records 排序，並非單純文案問題。
- **建議修法**：明確定義 null-date Trial 的 cohort、排序、ambiguity 狀態與 conflictFields；若其語意不是「同日衝突」，不應重用同一旗標而不加區分。

## I3｜Medium／error taxonomy 無法唯一分類 schema 變更

- **問題**：欄位 rename 同時滿足 `SCHEMA_COLUMN_MISSING` 與 `SCHEMA_COLUMN_EXTRA`；規格未定義 rename 如何被可靠判定或多重異常的優先順序。HTTP 中斷、Content-Length 不符等也可能同時滿足 transport error。
- **為什麼現在不修之後會更貴**：B2 要求精確 code 與 layer，但真實異常可能得到不同 code，CI 與維運判讀失去穩定性。
- **建議修法**：定義多重失敗的 precedence，以及 rename 的規範性判定條件；若無法客觀辨認 rename，便不可把它列為獨立必然 code。

## I4｜Medium／collision report 沒有內容契約

- **問題**：§6.2／A7 只要求「產出 collision report」，空 JSON 或只含 code 也能通過。
- **為什麼現在不修之後會更貴**：第一次真實 collision 發生時，無法確認是哪兩個 raw protocol、正規化結果及來源列，必須重新下載或重跑才能診斷。
- **建議修法**：規定 report 至少能唯一定位各 collision group、相關 raw protocol、identity-normalized value 與來源 fingerprint；不得只驗檔案存在。

## I5｜High／併發修法沒有封閉「排隊後 baseline 已改變」

- **問題**：§9.7 說 baseline 是 run 啟動時的上一正式快照，但 GitHub workflow 事件可能先建立、後排隊執行；前一 run 在等待期間發布後，checkout／baseline 可能仍是舊狀態。H2 只檢查 concurrency group，沒有測此情境。
- **為什麼現在不修之後會更貴**：兩次相鄰月更或 manual dispatch 可用同一舊 baseline 各自判斷，第二次覆蓋第一個結果或錯判 row-drop。
- **建議修法**：明定 baseline 的取樣時點為取得發布權之後，且 promotion 前必須再次驗證正式版本未變；新增兩個真正重疊 run 的驗收情境。

# 3. 修訂之間或與既有條文的矛盾

## X1｜High／A1 的範例與 §6.2 正面衝突

- **問題**：A1 把「僅大小寫或全半形不同的相似 protocol」列為避免過度正規化錯合併的例子；但 §6.2 明確以 NFKC＋upper 將這些差異折疊。若 raw 不同，依 §6.2/A7 應 `IDENTITY_COLLISION`，而不是保留為不同 Trial。
- **為什麼現在不修之後會更貴**：identity fixture 無法同時滿足 A1 與 A7，實作者必須自行選邊。
- **建議修法**：A1 的「不應合併」案例應改用 §6.2 明確不折疊的差異；大小寫／全半形差異則改列 collision oracle。

## X2｜High／§9.2 的 working-tree 保證與逐檔替換互斥

- **問題**：流程寫「替換 `public/data/` 並 commit」，同時宣稱任一階段失敗後 working tree 正式資料「整體等於舊版」。只要替換第一個檔案後發生例外、取消或程序終止，working tree 就已是混合狀態。git commit 的原子性不會回復 working tree。
- **為什麼現在不修之後會更貴**：B5 會被迫只測安全注入點，形成虛假的原子性證明；實際中斷才暴露問題。
- **建議修法**：移除無法由現行 promotion 定義推出的絕對保證，或把「正式資料切換」重新定義成單一可回復、可驗證的 promotion 動作；規格須涵蓋非正常終止。

## X3｜Medium／§9.4 的 no-change 規則與 `sourceSha256` 衝突

- **問題**：§9.4 說排除 builtAt/fetchedAt 後，其餘正規化輸出逐位元相同便不發布；但 manifest 包含 `sourceSha256`。ZIP metadata、列順序或等價來源編碼變動都可能改變 source SHA，而正規化 Trial 資料不變。
- **為什麼現在不修之後會更貴**：H2/H3 對「no normalized change」會有兩種合法解讀，造成不必要 commit 或遺失 provenance 更新。
- **建議修法**：明定 no-change 比較是否包含 `sourceSha256`，並清楚區分「來源位元組變更」與「正規化資料變更」。

## X4｜Medium／C4 的第一個 mutation 正是合規行為

- **問題**：C4 寫「分類轉 null」應被 C1 殺死，但 §6.6/C1 明確要求分類 sentinel 的 typed value 為 null。
- **為什麼現在不修之後會更貴**：此 mutation test 無法成立，或會迫使實作者破壞正確 sentinel 規則來讓測試失敗。
- **建議修法**：把 mutation 精確改成違反 C1 的單一行為，例如 raw 遺失、facet 保留 `"0"` 或 UI 顯示 `"0"`；不可把正確的 typed-null 當成錯誤。

## X5｜Low／shard 規則與 trialId 格式文字不一致

- **問題**：shard 寫成依 `trialId`「前 2 hex」，但 trialId 第一個字元固定為 `t`，並非 hex。
- **為什麼現在不修之後會更貴**：ETL、referential-integrity validator 與前端可能分別取 `tX`、前兩個 hash hex 或 record hash。
- **建議修法**：明定 shard key 是 trialId 中哪兩個字元，並加入邊界 oracle。

# 4. 新增／改寫驗收條件的可證偽性缺口

以下逐條回答「什麼弱化實作能通過，但功能仍壞掉」。

## A. 資料模型與收斂

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| A1 | **High**／使用大小寫、全半形作「不應合併」案例會與 §6.2 衝突。 | identity oracle 無法固定。 | 依 X1 更換反例，並分開驗證「應合併」與「應 collision」。 |
| A2 | **High**／fixture 沒有強制全日期不可解析、未來日期、單筆 invalid date、end<start；完全錯誤的 §6.5 實作仍可通過。 | 日期規則到 M2 才被 UI 發現。 | 把四類日期異常及其完整 Trial/UI oracle列為必含案例。 |
| A3 | **Low**／reverse＋3 seeds 可讓只在其他排列不穩定的實作通過。 | 非確定輸出造成無意義 commit。 | 加入系統性 permutation/property invariant；至少涵蓋 duplicate、tie、empty protocol 的交叉組合。 |
| A4 | **Medium**／只防「把 cohort 縮成第一筆」；保留 ambiguity metadata、但把第一筆值偷偷放入其他輸出層的實作仍可通過 A4。 | 任取值可能流入 stats/filter。 | mutation oracle 應涵蓋 displayFields、filter categorization 與統計輸出，不只旗標。 |
| A5 | **High**／若 source fingerprint 與 record identity 共用同一個非一對一 serialization，兩邊會一致地漏列而通過。 | 形成自我驗證。 | oracle 的 row identity 必須獨立且無歧義，並加入 separator/canonical collision fixture。 |
| A6 | **—（無）**／對目前限定的「完全相同空 protocol 重複列」沒有實質弱化缺口。 | 無。 | 無。 |
| A7 | **Medium**／只斷言 report 存在，空 report 可通過。 | 真實 collision 無法診斷。 | 驗證 report 的 collision group 與 raw protocol 完整內容。 |

## B. ETL 可靠性

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| B1 | **High**／固定失敗案例可通過，但 replacement 中斷、commit/push/deploy 失敗不在 error-code 集合與狀態斷言內。 | 發布鏈最後階段仍可留下混合或未部署狀態。 | 把 promotion、repository publish、deployment activation 分層定義並各有狀態 oracle。 |
| B2 | **Medium**／schema rename 等重疊錯誤沒有 precedence，測試可只挑單一純案例。 | 真實複合異常 code 不穩定。 | 追加多重異常與 precedence oracle。 |
| B3 | **—（無）**／已能排除「解析失敗被偽裝成空集」。 | 無。 | 無。 |
| B4 | **Low**／未明定 warning 的 machine-readable 位置；只在 log 印 warning 也可能算通過。 | 前端／QA report 無法穩定消費。 | 規定 warning 必須出現在哪個 structured artifact 與必要欄位。 |
| B5 | **High**／四點都避開「已替換部分正式檔案」及 abnormal termination；弱化實作可通過。 | 這正是 multi-file promotion 最危險窗口。 | 覆蓋每個正式狀態變更之後、commit/index 失敗及程序終止。 |
| B6 | **Medium**／未測 record 被兩個 Trial 引用、同一 Trial 重複引用、record 放錯 shard、額外未列入 inventory 的正式檔。 | ownership/inventory 仍可損壞。 | 對每條 referential invariant 各有獨立反例。 |

## C. Sentinel 與空值

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| C1 | **Medium**／若只選一個分類欄位作案例，另一個欄位把 `"0"` 當真值仍可通過。 | phase/scale 統計可能分裂。 | 明定兩個分類欄位都必須各自通過五處斷言。 |
| C2 | **High**／fixture 要求 empty、malformed 的 expected parsed value，但 §6.6 沒規定這兩類數值如何解析；oracle 可任意制定。 | 驗收條件反過來創造 normative 規則。 | 先在正文定義 empty/malformed 的 typed value、warning/error 與顯示，再寫 oracle。 |
| C3 | **—（無）**／精確計數、recordId、切換後文字足以堵住主要弱化實作。 | 無。 | 無。 |
| C4 | **High**／第一個 mutation「分類轉 null」是合規行為。 | mutation suite 無法成立。 | 依 X4 改為真正違規的 mutation。 |

## D. 搜尋與篩選

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| D1 | **Medium**／只有七個正向 canary；把第八至第十六欄也誤納搜尋索引仍可通過。 | 造成規格外誤命中。 | 加入每個不可搜尋欄位的負面 canary。 |
| D2 | **Medium**／normalization 有 pair，但 substring/prefix/fuzzy/token matching 未定，弱化 matching operator 可通過選定 pair。 | 搜尋結果跨實作不一致。 | 先補 N4，再用 operator 邊界正反例驗證。 |
| D3 | **High**／沒有明定「兩詞分別命中同一 Trial 的不同 SourceRecord」必須排除；Trial-level AND 可冒充 record-level AND。 | 歷史搜尋會大幅多報。 | 加入跨 record 拆分兩詞的必排除案例。 |
| D4 | **Medium**／逐一測每個 filter，仍可讓多 filter 組合邏輯、區間端點、重複 query param 壞掉。 | URL 與 filter state 將形成相容性負債。 | 加入同維度多選、跨維度組合、邊界值與 invalid URL oracle。 |
| D5 | **Low**／「中文同義詞等」不是封閉集合，無法形成可證偽測試。 | 驗收結果依測試者任意選詞。 | 將禁用的 UI concept 以封閉 selector/schema invariant 為主；列舉詞只作輔助。 |
| D6 | **Medium**／只用單一衝突欄位案例，可讓 phase 正確、scale/applicant/date 等其他 filterable conflict 仍任取值。 | 各 filter 維度語意分裂。 | 每個可篩選且可能衝突的欄位至少一個 oracle。 |

## E. 呈現與誤導防範

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| E1 | **Low**／負面詞不是封閉集合；「目前可收案」等同義暗示仍可通過。 | 誤導性文案可能避開字串測試。 | 以允許呈現的狀態概念與固定免責為主要 oracle，禁字只作 mutation guard。 |
| E2 | **Low**／若新增統計卡但未加入 oracle inventory，可被排除於「每張」之外。 | 新卡可能使用 SourceRecord 作錯誤分母。 | 由實際 DOM/card schema 反向比對 oracle inventory，禁止未驗證卡片。 |
| E3 | **Medium**／只測單一 fixture 值，交換其他頁面或其他 record 的日期來源仍可通過。 | 日期標籤在不同 route 語意漂移。 | 覆蓋首頁、結果、詳情及 record 切換後的來源對應。 |
| E4 | **Medium**／未測來源文字進入 filter option、搜尋命中標籤、統計 label 等其他來源控制 surface。 | XSS 或 DOM injection 仍可能從未測 surface 進入。 | 依來源資料可到達的輸出 surface 建立封閉 inventory。 |
| E5 | **Low**／「可見」若只採 DOM visibility，可用極小字、遮蓋或不可讀配置通過。 | 免責存在但實際不可讀。 | 把可見性與 G1/G2 的 viewport、尺寸、對比 oracle綁定。 |
| E6 | **—（無）**／全文、首尾 canary、換行正規化與 record 切換已封閉主要弱化路徑。 | 無。 | 無。 |
| E7 | **Medium**／只禁止候選值完整字串出現在卡片 DOM；截斷、正規化後或放入 attribute/accessible name 的候選值仍可能洩漏。 | 使用者仍可能把任取值視為最新值。 | 對卡片可見文字、accessible name、attribute/state 做候選值集合的等價檢查。 |

## F. 效能

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| F1 | **Medium**／實作可過早宣告「可搜尋」，把首次輸入後才下載的必要索引排除於 1.5 MB。 | payload 被移到量測窗外。 | 定義可搜尋 readiness 的功能性 probe，必須立即完成固定查詢。 |
| F2 | **High**／只放一個長 canary；實作可特判移除該筆，但仍把其餘所有長 criteria 塞入初始 bundle。 | 測試未證明 lazy-loading 架構。 | 驗證初始 payload schema 不含長欄位，並用多筆分散 canary。 |
| F3 | **Medium**／硬體、browser、重複次數與 percentile 下限未封存；選 p1/p50 可掩蓋長尾。 | CI 數字無法跨時間比較。 | 固定量測環境、warm/cold 條件、樣本數與最低 percentile 標準。 |

## G. 無障礙

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| G1 | **Medium**／沒有封存 viewport/orientation 集合；只測桌面即可讓手機版溢出通過。 | 響應式佈局完成後才補測成本較高。 | 列出最低 viewport matrix。 |
| G2 | **Medium**／route×state matrix 由實作者自行列，可漏列實際存在的 warning/disabled/ambiguity 組合。 | 自我宣告的 inventory 無法證明完整。 | 由規格列出最低必測矩陣，並與實際元件狀態 inventory 對帳。 |
| G3 | **Medium**／大多數控制項只驗鍵盤，不要求名稱、角色、狀態可被 assistive technology 讀取。 | 鍵盤可用但 screen reader 不可用。 | 對每類控制項同時要求 accessible name、role、state 與錯誤訊息關聯。 |
| G4 | **Low**／有圖表時，替代資料只要求「在 DOM 可讀」，hidden/inert 的表格可能通過；也未驗圖形視覺 encoding 是否與資料一致。 | 可產生有正確隱藏表格、但錯誤圖形的結果。 | 將「可讀」限定為 accessibility tree 可達；圖表存在時驗證其實際呈現資料與替代資料一致。 |

## H. CI 與自動化

| 條件 | 嚴重度 / 問題 | 為什麼之後更貴 | 建議修法 |
|---|---|---|---|
| H1 | **Medium**／「每個 gate」沒有 normative inventory；漏掉的 gate 不會被注入失敗。 | CI 可看似全綠但根本沒執行某類驗收。 | 在規格列出最低 gate 集合並與 workflow jobs 雙向對帳。 |
| H2 | **High**／只驗 concurrency group 字串與連續兩跑，沒有真正重疊 run、排隊、baseline 改變或取消測試。 | §9.7 的核心競態未被證明。 | 加入重疊執行與前一 run 發布後第二 run 重新驗 baseline 的 oracle。 |
| H3 | **Medium**／要求兩次重用同一 source SHA，可讓 workflow 快取第一次下載結果，未證明第二次下載及 HTTP 驗證路徑；「完整 pipeline」與「重用 SHA」也缺乏明確定義。 | 上線演練可能跳過實際抓取故障面。 | 明定重用 SHA 是固定輸入還是重新下載後驗證 SHA 相同，並列出第二次必經 stage。 |
| H4 | **—（無）**／直接、間接 uses、container digest 與 job permissions 已足以堵住主要弱化實作。 | 無。 | 無。 |

# 5. 對五項偏離的判定

## 1. 多檔原子發布：**不成立（依 v0.3 現行文字）**

你的推論只成立一半：

- **成立部分**：git commit 對 repository tree 是原子快照。只讀已提交 tree 的人，不會看到「半個 commit」。Cloudflare 若確實以特定 commit SHA 建置，建置輸入也是一致的。
- **不成立部分一：working tree**：`public/data/` 從第一個正式檔被替換，到全部替換並 commit 前，確實存在混合窗口。例外、取消、程序崩潰或同 workspace 的讀者都可能看到混合狀態。commit 原子性不會自動回復 working tree。
- **不成立部分二：部署／瀏覽器**：即使 Pages origin 的 deployment activation 是原子的，多次 request 仍可能因固定 URL、瀏覽器快取或 CDN cache 讀到跨版本檔案。commit 不能證明 manifest、index、shard 在一次使用者 session 中屬於同一資料版本。
- **不成立部分三：規格缺少鏈結保證**：尚未規定 Cloudflare build 必須 checkout 哪個 SHA、何時視為正式部署、部署失敗時哪一版仍為 authoritative。

結論：snapshot 目錄＋指標切換不是唯一合法方案，但「commit 本身已足夠」目前無法成立。你可以保留不採 snapshot 的產品決策，但必須另行補足跨檔版本綁定、cache 一致性及 working-tree rollback／隔離契約。

## 2. B5 四個失敗注入點：**不成立**

四點沒有覆蓋真正危險的 promotion 邊界：

- 替換第一個、部分、最後一個正式 artifact 之後；
- 刪除舊 orphan artifact 的途中；
- git index/staging 只包含部分變更；
- commit 本身失敗；
- commit 成功但 push 失敗；
- push 成功但 Cloudflare build／activation 失敗；
- 非例外式終止，例如取消或程序被中止。

尤其「commit 前」若只表示全部替換完成後，完全未測部分替換窗口。B5 目前可以讓非原子的逐檔替換實作通過。

## 3. 日期規則由 High 降為 Medium：**不成立**

「目前 18,736 列日期乾淨」足以降低當下資料發生率，但不足以降低規格缺口的修正成本與核心風險：

- 這是每月重跑的 ingestion contract，不是一次性資料清理。
- 全部日期不可解析時，§6.4 與 §6.5 已出現模型矛盾。
- 未來日期目前為零，但 v0.3 新規則會讓未來日期支配 Trial 卡片，屬誤導風險。
- A/B 驗收沒有強制覆蓋日期異常，因此防禦規則目前未被證實。

依你給的嚴重度定義，這會影響 Trial 收斂模型、displayFields、篩選及統計，不只是「多寫一些程式」；應維持 **High**。補出 7 列 end<start 是正確且有價值，但不能抵消上述缺口。

## 4. A6 空 protocol hash 碰撞降為 Medium：**成立**

理由成立：

- 現況 6 列空 protocol 各自簽章不同，完全相同空 protocol 重複列是防禦性情境。
- 根本資料模型缺口已由 §6.3 處理，A6 主要是驗證 multiplicity 與排列穩定性。
- fixture 已納入兩筆完全相同列，足以防止最直接的 deduplication 弱化實作。

因此 A6 本身評為 **Medium** 合理，不應和 1.3 重複計為 High。

但 N1 的 canonical serialization 非一對一及截短 ID 碰撞是 v0.3 新產生的另一個 **High**，不能由 A6 的降級一併豁免。

## 5. 首版不預先禁止圖表：**成立**

這確實是產品決策，不應由規格審查員代決。以下安排合理：

- 數字卡與清單為必須；
- 圖表為可選；
- M2 依 payload 與 a11y 成本決定；
- 只有實際提供圖表時才觸發 G4。

這不是驗收逃逸，因為「不提供圖表」本來就是明確允許的合規產品形態。需要修的是 G4 在有圖表時的可證偽性，不是強迫首版做或不做圖表。
