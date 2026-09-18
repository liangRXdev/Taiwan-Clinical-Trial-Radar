# Taiwan-Clinical-Trial-Radar — 專案規則

台灣藥品臨床試驗檢索站。Python ETL（build-time）+ TypeScript 靜態前端 + GitHub Actions，部署 **Cloudflare Pages**。只用 TFDA dataset 205。

**現況：M0.5 結案。** A 群 fixture 補齊（73 列／45 Trial）、最小 artifact 樣本、B 群失敗注入 fixture、§9.3.6 不變量反例與 C4 mutation 全部完成，規格經四輪覆審定案 **v0.7**（Blocker 走勢 2→0→1→0）。**M1 的 ETL 主體已完成**：`trial_radar/` 十個模組 ＋ `scripts/build_data.py`，**pytest 141 綠**、fixture 自檢 289 條斷言全綠。下一步是補 fetch/validate CLI、首次連網實跑，然後 M2 前端。

**唯一具規範效力的規格是 `.ai-review/plan.md` v0.7，動工時直接依 §14 的 14 項契約表實作，不要重新推導。** `Taiwan-Clinical-Trial-Radar-spec.md`（v0.1）與 plan.md 的 v0.2–v0.6 都已降為歷史文件，**不得作為實作或驗收依據**——v0.1 有六處條文（§3.1／§5.1／§8／§9／§14／§18）仍在要求已取消的 206–209 關聯與 `verify_linkage.py`。

---

## 四項已定案決策（2026-09-18，勿自行翻案）

1. **只做 dataset 205**。206–209 永久不納入。不要因為「資料看起來對得上」而重啟 join。
2. **以 identity-normalized protocol 收斂試驗單位**，同日平手不推定新舊（見下節）。
3. **sentinel 依欄位型別分開處理**（見下節）。
4. **Cloudflare Pages**，不用 GitHub Pages。理由：`liangrxdev.github.io` 由多個工具共用 origin，Cache Storage 不依 service worker scope 隔離，既有專案已踩過跨 repo 互刪快取。獨立 origin 從源頭避開。

**沒有 `FEATURE_TRIAL_STATUS` 旗標。** 永遠關閉的旗標只是一條可被誤開的路徑。來源若新增 `執行狀態`，走規格修訂流程，不開旗標。

## 三個會咬人的地方

### 1. 一列不是一個試驗

18,736 列只對應 5,882 個 protocol。2,821 個 protocol 有多列（最多 23 列），且 **2,821 組裡只有 61 組是純重複**——其餘在 `資料更新時間`、`納入條件`、`排除條件`、`台灣預計受試者人數`、甚至 `臨床試驗期別` 上有實質差異。

所以：

- 任何「試驗總數」統計都要講清楚分母是**試驗（≈5,888）**還是**審查紀錄（18,736）**，UI 上必須寫出來。phase 分布若直接用列數會被多版本試驗重複計數而偏斜。
- **`TFDA收文號` 不可當主鍵**：2,788 個重複鍵、266 筆空值、30 筆是 `移案BPA` 這種非數字字串。spec §7.2 的三段 key order 在實際資料上第 1、2 選都不成立（`protocol + applicant` 仍有 2,885 個重複鍵）。
- 6 列 protocol 為空，各自 fallback 成獨立試驗單位。判定依據是 **`identityNormalize` 後是否為空**（涵蓋空白-only），不是 raw 是否為空；identity key 為 `H:<hash>#k`，**`k` 一律存在且從 `#0` 起**——單筆不帶後綴會讓日後新增相同內容的列時 ID 變形、URL 失效。

### 2. 同日平手不准推定新舊——沒有 tie-break，只有 ambiguity

以 `資料更新時間` 取最新時，**2,821 個多列 protocol 裡有 846 組（30%）最新日期平手**，而日期只有日精度、無時間、無版號。其中：

- **689 組（81%）平手列 16 欄全同** → 純重複，顯示共同值即可。
- **157 組 raw 有差異，其中 143 組依比較鍵仍衝突**（另 14 組只差空白／全半形，判不衝突但帶 `rawVariants`）→ `納入條件` 74 組、`台灣預計受試者人數` 21 組（如 `19` vs `31`）、`臨床試驗期別` 3 組（如 `Phase Ⅱ` vs `Phase Ⅰ,Phase Ⅱ`）。全量跑過模型確認 `latestAmbiguous` 為 true 者恰為 **143 個**。

**這 143 組不准挑一個版本顯示。** 卡片只顯示無衝突的共同欄位，衝突欄位顯示「同日多筆資料不一致」；詳情頁並列全部紀錄並明示「順序未知」。hash 只用於 cohort 內穩定排序，**不得宣稱時間先後**。

曾經想過的「取非空欄位數最多者」實測幾乎無效（846 組只唯一決出 5 組），已棄。**也不可以靠 CSV 列序**——列序不是穩定契約。

連帶：**不做方向性 diff**（`20 → 30` 的箭頭）。同日平手時沒有可靠順序，箭頭可能寫反。只標示「哪些欄位存在不同值」。

### 2b. 三套正規化各自獨立，不可混用

- **identity**（主鍵用）：`strip → NFKC → upper`。**不做**標點移除、不做內部空白壓縮。實測零碰撞；碰撞即硬失敗 `IDENTITY_COLLISION`，不得合併。
- **search**（查詢比對用）：`strip → NFKC → casefold → 壓縮內部空白`。
- **conflictText**（衝突比較用）：`NFKC → 移除全部空白`。但**只用於文字欄位**——數值與分類欄位走 §6.4.2 的 semantic comparison key。

**「ASCII 英數字元」必須明定，否則實作會相反。** Python 的 `"系統測試".isalnum()` 回傳 **`True`**（中文被視為字母）。若用 `isalnum()` 實作 `protocolNonIdentifier`，`系統測試` **不會**被標記——與意圖完全相反。一律先 NFKC 再套 `[A-Za-z0-9]`。

混用會讓主鍵跟著查詢需求漂移。註：NFKC 會把全形數字折成半形，那是**等價**不是誤命中。

**代價已知且必須揭露**：不剝標點會讓 **18 組** 同一試驗的不同寫法變成兩個 Trial（`MK-3475-158` / `MK3475-158`、`9785-CL- 0123` / `9785-CL-0123`、`ROR-PH-301(APD811-301` / `...301)`、`刪_BGB-16673-303` / `BGB-16673-303` 等）。**維持不自動合併**（合併會誤配），但要靠 `nearDuplicateGroup`（剝非 ASCII 英數字後的 loose key，**只用於偵測絕不用於收斂**）在 QA report 與詳情頁揭露。

### 2d. 衝突判定不是比 raw，也不是比 typed

兩種單純作法都會錯：

- **只比正規化 raw** → 14 組僅差空白／全半形者被誤判為衝突（假警報，會訓練使用者忽略警示）。
- **只比 typed** → `""`（`numericMissing`，顯示「未提供」）與 `"-5"`（`numericImplausible` warning，須顯示異常）的 typed 皆為 `null`，判不衝突並任取一筆 raw 會**隱藏異常**。這比假警報更糟。

正解是 §6.4.2 的 **semantic comparison key**：依欄位型別與**語意狀態**定義比較鍵。比較鍵相同但 raw 不同 → 該**欄位**的 flags 加 `rawVariants`（不是 Trial 層級），代表值取 `recordId` 字典序最小者。

**衝突欄位在 `displayFields` 中完全省略，不是給 `{typed:null}`**——後者會與「未提供」混淆。

### 2e. `datasetVersion` 不能由最終位元組算

這是 v0.4 踩過的 Blocker：要求每個檔案內含 `datasetVersion`，又要 `datasetVersion` = 這些檔案**最終位元組** digest → 循環，無固定點。

分兩個概念（§9.3.2）：`datasetVersion` 由**移除版本欄位後的 logical payload** 算；`artifactDigest` 待版本寫入最終檔案後對**最終位元組**算。驗收 B8 專門證明無循環。

### 2f. 搜尋範圍是分層的，預設最小

v0.3 曾要求「搜尋涵蓋全部歷史 × 7 欄」，實測索引 **6,958 KiB gzip**，是 payload 預算的 4.6 倍——該要求與 F1 不可能同時成立。

現行：預設 `fields=short`（5 短欄）＋ `history=latest`（最新 cohort），實測 `trials-index` 含搜尋文字為 **1,236 KiB gzip**。擴大 scope 的控制項**必須在結果區可見**、切換前顯示下載大小（取自 `manifest.files[*].gzipBytes`，**不可前端寫死**）、結果區持續顯示目前範圍。預設縮小若不可見，就是靜默漏報。

實測各層 gzip：`all`+`latest` 2,044 KiB／`short`+`all` 1,649 KiB／`all`+`all` 另加 5,389 KiB。

### 2g. payload 的兩個反直覺實測

- **`recordIds` 放進 index 很貴**：18,736 個高熵 hex 壓縮率差，使 `trials-index` 由 1,236 → 1,535 KiB gzip。已移入 shard（只有詳情頁用得到），index 只留計數 ＋ 不變量防漂移。
- **拆檔會變大不會變小**：卡片 903 ＋ 搜尋文字 693 = 1,596 KiB > 合併的 1,236 KiB。拆開失去跨欄位壓縮共享。所以 `searchShortLatest` 留在 index 內。

F1 的 Tier 0 門檻是 **≤1.5 MB gzip**（基線 1,236 KiB）。v0.4 曾寫 1.0 MB，那是用估算基線訂的，實測後改正。

### 3. 來源沒有 `執行狀態` 欄位

官方資料集頁面列了 `執行狀態`，實際 16 個欄位裡沒有。這不是抓取失敗，是來源本身就沒給。

- 不得提供 Recruiting／Active 篩選，不得顯示招募中標章。**filter schema、DOM 控制項、URL parser、輸出 state 四處都不能有**，中文同義詞（「收案情形」「招募」）也不行——只改名就能規避「檢查選單文字」那種測試。
- 若未來某次 build 發現這一欄真的出現了，那是 schema 變更，走 warning report 與規格修訂，**不要順手接上去就上線**——招募狀態誤導的臨床後果高於少一個功能。

## sentinel 與數值解析（依欄位型別，勿統一化）

v0.1 曾寫「`0` 不可自動視為 missing」，那條**只對數值欄位成立**。完整解析順序見 plan.md §6.6.3，要點：

| 型別 | 實測 sentinel | 處理 |
|---|---|---|
| 分類 | `臨床試驗期別` `"0"` 156 筆、`本臨床試驗規模` `"0"` 266 筆 | typed `null` ＋ `categoricalUnprovided`，UI「未提供」，**不進篩選選單、不進 facet**。非合法值另歸 `categoricalUnknown` ＋ warning |
| 數值 | `"0"` 1,080 筆 | **保留為 0** ＋ `sourceZero`，UI「0（來源填 0）」，**不得**說成「確定沒有受試者」 |
| 文字 | `排除條件` `N/A` 469／`NA` 67、`納入條件` `NA` 42、`主要評估指標` `NA` 61 | 保留原文，三型**互相可區分**，QA report 分別計數 |

**`numericUnparsed` 不是垃圾桶。** 實測 `台灣預計受試者人數` 有 **1,340 筆是範圍**（`20-40`、`8-12`）——那不是「格式未辨識」，是一個區間。**只解析嚴格範圍** `^\d+\s*[-~～〜–—]|至\s*\d+$` 且 `min ≤ max` → `{min,max}` ＋ `numericRange`，`enroll` 篩選以**區間重疊**判定（一筆 `20-40` 會同時出現在 `11-30` 與 `31-100`），卡片顯示 raw 原文。實測回收 1,347／1,705。

**不從約略值推論。** `約400` → 400 會丟掉「約」，屬推論，維持 `numericUnparsed`。`至少480`、`148(最多266)` 同理。

**前導零不可改寫**：實測 3 筆（`026`、`024`、`08`）。typed 為 26／24／8 供篩選，但 **raw 一律顯示**。

三類 sentinel 都必須保留 raw 值可稽核。

## 風險排序：誤導 > 資料缺漏 > XSS

本站無登入、無 session、無使用者資料，XSS 竊取不到憑證。但**讓藥師誤以為某試驗正在招募、或誤讀成已核准上市，會直接影響臨床溝通**。

修補優先序：

1. 任何會讓使用者誤判試驗狀態／核准狀態的呈現（缺資料日期、缺免責、招募暗示）
2. 資料正確性（收斂錯誤、版本取錯、統計分母錯）
3. 渲染層 XSS（來源文字一律 escape，禁止 raw HTML 注入）

安全掃描報告若把 XSS 排前面，照上述順序處理。

## ETL 不可退讓的行為

- **fail-closed**：任一階段失敗即以非零狀態結束、**不 commit**。
- **保證下在「已 commit／push 的 tree」，不是 working tree。** 逐檔替換做不到「中途失敗後 working tree 整體等於舊版」，而 commit 的原子性不回復 working tree。CI runner 的 working tree 用後即棄、無讀者，所以要保證的是「**不存在部分發布的 commit**」。全部 artifact 先寫 staging 並通過整體驗證，替換 + `git add -A` + commit 收攏為最後三步。
- **git commit 不足以防瀏覽器跨版本混用。** 固定 URL + 快取會讓一次 session 混用舊 manifest 與新 shard → dangling reference 或顯示錯紀錄。所以：`manifest.json` 是**唯一固定 URL**（`no-cache`），其餘全部檔名帶內容雜湊（`immutable`）；每個檔案 top-level 帶 `datasetVersion`，前端載入後**斷言等於 manifest 的值**，不符即 fail-closed 顯示「資料版本不一致，請重新載入」。
- **失敗絕不回空陣列**。抓取失敗與「官方回覆空集」必須分辨。目前 205 無 sentinel 列，0 資料列一律走 `ZERO_ROWS` 硬失敗。
- **每種失敗要有相異的 exit code**（error code 清單見 plan.md §9.5）。不可七種失敗共用一個 exit code 只靠訊息區分，測試也不可以「stderr 含某字串」當判定。
- **`builtAt` 是「目前已發布 artifact 的建置時間」**，不是本次執行時間。比較是否需發布時**排除 `builtAt`／`fetchedAt`／`sourceSha256`／`artifactDigest`**，判準是 **`datasetVersion` 相同即無變動**。（排除 `sourceSha256` 是因為上游用相同資料重新打包會改變它而正規化資料不變，算進去會每月產生噪音 commit。）
- **`buildDate` 以 `Asia/Taipei` 日曆日產生，不得用 runner 的 UTC 日期。** runner 是 UTC，台灣時間 08:00 前 UTC 還是前一天，「未來日期」判定會差一天（驗收 H5）。
- 骨架可複用 `../TFDA-drug-shortage-dashboard/scripts/fetch_fda_data.py`（sentinel 辨識、驟降門檻、concurrency lock 已驗證），但**它的逐檔替換不能照搬**。
- `資料更新時間` 是**來源欄位**，與 `builtAt` 是兩回事，manifest 分開存、UI 分開顯示且標籤不同。
- 純邏輯抽成可 import 的函式，讓 pytest 在無網路下 mock 測試。

## 抓取環境

`data.fda.gov.tw` 從 GitHub Actions runner 直接抓**沒有問題**，不需要 proxy。memory 裡記的「TFDA 回 500」只發生在 **Google IP**（Apps Script），與 Actions（Azure）無關；`TFDA-drug-shortage-dashboard` 的排程長期直打同一網域成功。

注意這與 `consumer.fda.gov.tw` 不同——那個網域對所有境外 IP 在 TLS 層切斷，只能台灣本機抓。本專案用的 `data.fda.gov.tw` 不受此限。

## 資料規模的實務含意

- 解壓後 166 MB，單列 `納入條件`／`排除條件` 最長 **22,490 字元**。前端絕不解析原始 CSV。
- `trials-index`（含 `searchShortLatest`、不含 `recordIds`）實測 **1,236 KiB gzip**，F1 的 Tier 0 門檻 ≤1.5 MB。長文字走按需載入 shard。**改動 index 欄位清單時重新量測**——v0.4 就是憑估算值訂了做不到的 1.0 MB 門檻。
- 本機跑 ETL 前先確認 stdout 已 UTF-8 reconfigure；Windows 主控台預設 Big5，直接印中文欄名會變亂碼（除錯時把結果寫成 UTF-8 檔再讀，不要靠終端輸出判斷資料對錯）。

## 文件慣例

- `.ai-review/plan.md` — **唯一 normative 規格**（v0.5）。驗收條件有可引用編號 A1–H5，**十項動工前契約見 §14**，`/codex-review` 的規格符合度稽核以它為基準。
- `.ai-review/fixture-findings-a.md` — A 群 fixture 反驗規格的結果（7 個洞，全部結案）。
- `.ai-review/fixture-findings-m05.md` — M0.5 的結果（GAP-8／9／10，**全部 open**）。
- `.ai-review/plan-review-*.md` — Codex 原始輸出，原封不動落檔。
- `.ai-review/plan-verdict-*.md` — 逐項判定（接受／部分接受／拒絕）。
- `Taiwan-Clinical-Trial-Radar-spec.md` — **歷史文件，無規範效力**。不要引用它做實作或驗收。
- `TODO.md` — 待辦。`PROGRESS.md` — 進度紀錄，每個里程碑一段，附實測數字。
- **raw source 不手動修改**；修正規則一律以版本控制的 transformation + 測試實作。
- 規格改完要**再審一輪，且下一輪只審「修訂本身」**（走 `/codex-checkplan`）。第一輪 56 項裡有 11 項是 v0.2 修訂自造的洞；第二輪 54 項裡又有一批是 v0.3 修訂自造的（`latestAmbiguous` 沒有封閉欄位集合、未來日期會支配卡片、C4 第一個 mutation 是合規行為、驗收條件反過來創造 normative 規則）。**修訂會製造新洞，這是規律不是意外。**
- **四輪的 Blocker 走勢是 2 → 0 → 1 → 0。** 第三輪那個是 v0.4 修 N8 時自造的循環定義；第四輪 11 項發現**全部**是 v0.6 修訂自造的，沒有一項是 v0.5 遺留。第三、四輪都**限縮**只審修訂本身。
- **「為了關掉一個洞而引入的新概念，本身也要被定義清楚。」** v0.6 四個修訂各自造了一個新洞：宣稱「比較鍵涵蓋旗標封閉集合」（旗標不互斥）、引入全域評估順序（過度阻斷獨立檢查）、把 facet 名單綁成 E2 唯一 oracle（合法的非 facet 統計卡會被判失敗）、補 Tier 0 檔案清單（與既有「全部 network responses」定義衝突）。
- **規格審到某個程度後，改用「寫 fixture 反驗規格」比再讀一遍 prose 有效。** A 群 fixture 找到 7 個洞，包含一條（A8）**數學上無法滿足**的驗收條件。故不跑第四輪，改走 M0.5。M0.5 又找到 3 個。
- **同一份規格裡的兩張清單要對差集。** GAP-8 是 §6.4.2 的比較鍵表（10 個語意狀態）漏了 §9.3.3 旗標封閉集合裡的三個——兩張表都在 plan.md 裡，三輪 prose 覆審都沒抓到。**prose 審查不會去對兩張表的差集，寫 fixture 會。**
- **「兩次跑結果相同」證明的是決定性，不是無循環。** B8 另加 B8-1b：從已寫入版本欄位的最終檔案反算須得同值，那才是固定點存在的證據。同理 B8-3 要先斷言互換前後 payload hash 多重集合相同，否則證不到邏輯檔名有作用。
- **反例要斷言「違規集合 exactly equals 預期」，不是「包含」。** 用「包含」的話，一個把所有檢查都回報違規的驗證器會全過。GAP-11（§9.3.6 的不變量有依賴卻沒有評估順序）就是被 exactly-equals 逼出來的。
- **缺陷要注入在算 digest 之前。** 真實威脅是「有 bug 的 ETL 產出內部自洽但違規的 artifact」，它會把自己算的 digest 一併寫進去。改完最終位元組就放著不重算，測到的只是 digest 本身，referential integrity 那幾條永遠不會被執行到。
- **驗收條件本身可能不成立。** 已踩兩種：A8「數學上無法滿足」、GAP-11「要求獨立反例但結構上做不到」、GAP-12「要求了一件測不出違反的事」。**這三種讀 prose 都讀不出來，只有真的去寫那個反例才會現形。**
- **凍結 fixture 要配 `.gitattributes -text`。** `core.autocrlf=true` 會把 CRLF 存成 LF，Linux CI checkout 出來就變 LF——「凍結」的行尾其實沒被凍結。artifact 樣本同理（digest 對位元組計算）。
- **Codex 沒有資料可量，量得出來的東西要自己量。** 兩輪都沒抓到「搜尋範圍 × payload 預算」的硬矛盾與 protocol 欄位的近似重複／垃圾值，那三項都是本機實測才發現的。
- Commit message：`type(scope): 說明`，type 為 `feat`／`fix`／`refactor`／`docs`／`chore`；資料更新用 `data: update TFDA clinical trial dataset YYYY-MM-DD`。
