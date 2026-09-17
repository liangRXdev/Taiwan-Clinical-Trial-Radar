# Taiwan-Clinical-Trial-Radar — 專案規則

台灣藥品臨床試驗檢索站。Python ETL（build-time）+ TypeScript 靜態前端 + GitHub Actions，部署 **Cloudflare Pages**。只用 TFDA dataset 205。

**現況：Phase 1 規劃中，repo 內只有規格與文件，尚無程式碼。** 規格 `Taiwan-Clinical-Trial-Radar-spec.md` 是 2026-09-12 的 v0.1，**其中 §2／§6.6／§7.1／§7.2／§16 已被 2026-09-18 的實測推翻，改規格前先讀 TODO.md 的「規格修訂」段**。

---

## 四項已定案決策（2026-09-18，勿自行翻案）

1. **只做 dataset 205**。206–209 永久不納入，spec §2 的 go/no-go gate、§7.3 的 relation 模型、`verify_linkage.py` 與寄給 TFDA 的詢問信全部取消。不要因為「資料看起來對得上」而重啟 join。
2. **以 protocol number 收斂試驗單位**，顯示最新版＋保留版本歷史（見下節）。
3. **sentinel 依欄位型別分開處理**（見下節）。
4. **Cloudflare Pages**，不用 GitHub Pages。理由：`liangrxdev.github.io` 由多個工具共用 origin，Cache Storage 不依 service worker scope 隔離，既有專案已踩過跨 repo 互刪快取。獨立 origin 從源頭避開。

## 三個會咬人的地方

### 1. 一列不是一個試驗

18,736 列只對應 5,882 個 protocol。2,821 個 protocol 有多列（最多 23 列），且 **2,821 組裡只有 61 組是純重複**——其餘在 `資料更新時間`、`納入條件`、`排除條件`、`台灣預計受試者人數`、甚至 `臨床試驗期別` 上有實質差異。

所以：

- 任何「試驗總數」統計都要講清楚分母是**試驗（≈5,888）**還是**審查紀錄（18,736）**，UI 上必須寫出來。phase 分布若直接用列數會被多版本試驗重複計數而偏斜。
- **`TFDA收文號` 不可當主鍵**：2,788 個重複鍵、266 筆空值、30 筆是 `移案BPA` 這種非數字字串。spec §7.2 的三段 key order 在實際資料上第 1、2 選都不成立（`protocol + applicant` 仍有 2,885 個重複鍵）。
- 6 列 protocol 為空，各自 fallback 成獨立試驗單位（deterministic row hash），不要丟掉也不要合併。

### 2. 「取最新版」有 846 組平手，必須是確定性規則

以 `資料更新時間` 取最新版時，**2,821 個多列 protocol 裡有 846 組（30%）的最新日期是平手的**。日期只有 `YYYY/MM/DD` 精度，沒有時間或版號可再細分。

**不可以靠 CSV 列序決定**——列序不是穩定契約，靠它會讓每次 build 的輸出不確定，也違反本專案不依賴列序的立場。tie-break 規則尚未定案，見 TODO.md；**在定案前不要先寫「取第一筆」的實作**，那會變成靜默的不確定行為。

### 3. 來源沒有 `執行狀態` 欄位

官方資料集頁面列了 `執行狀態`，實際 16 個欄位裡沒有。這不是抓取失敗，是來源本身就沒給。

- 不得提供 Recruiting／Active 篩選，不得顯示招募中標章。`FEATURE_TRIAL_STATUS` 預設 `false`。
- 若未來某次 build 發現這一欄真的出現了，那是 schema 變更，走 warning report 與規格修訂，**不要順手接上去就上線**——招募狀態誤導的臨床後果高於少一個功能。

## sentinel 處理（依欄位型別，勿統一化）

spec §6.6 寫「`0` 不可自動視為 missing」，那條**只對數值欄位成立**。實測：

| 型別 | 實測 sentinel | 處理 |
|---|---|---|
| 分類 | `臨床試驗期別` = `"0"`（156 筆）、`本臨床試驗規模` = `"0"`（266 筆） | 判定為 sentinel，UI 顯示「未提供」，**不進篩選選單** |
| 數值 | `全球預計受試者人數` = `"0"`（1,080 筆） | **保留為 0** 並加注「來源填 0」，不替上游決定它是缺值 |
| 文字 | `排除條件` `"N/A"` 469 筆／`"NA"` 67 筆、`納入條件` `"NA"` 42 筆、`主要評估指標` `"NA"` 61 筆 | 保留原文顯示，只在 QA report 計數 |

三類都必須保留 raw 值可稽核。分類欄位的 `"0"` 不可能是合法期別，放行會讓篩選選單出現垃圾選項；但數值 0 與文字 `NA` 有可能是上游的真實意思，替它改寫就是造假。

## 風險排序：誤導 > 資料缺漏 > XSS

本站無登入、無 session、無使用者資料，XSS 竊取不到憑證。但**讓藥師誤以為某試驗正在招募、或誤讀成已核准上市，會直接影響臨床溝通**。

修補優先序：

1. 任何會讓使用者誤判試驗狀態／核准狀態的呈現（缺資料日期、缺免責、招募暗示）
2. 資料正確性（收斂錯誤、版本取錯、統計分母錯）
3. 渲染層 XSS（來源文字一律 escape，禁止 raw HTML 注入）

安全掃描報告若把 XSS 排前面，照上述順序處理。

## ETL 不可退讓的行為

- **fail-closed**：HTTP／ZIP／CSV 解析／schema 驗證任一失敗即以非零狀態結束，**不覆寫既有正式 JSON**。全部通過才 `os.replace` 原子替換。
- **失敗絕不回空陣列**。抓取失敗與「官方回覆空集」必須分辨，後者才是資料。
- 骨架直接複用 `../TFDA-drug-shortage-dashboard/scripts/fetch_fda_data.py`（sentinel 辨識、原子替換、驟降門檻、concurrency lock 都已驗證過），不要從零寫。
- `資料更新時間` 是**來源欄位**，與本站 build time 是兩回事，manifest 必須分開存、UI 必須分開顯示。
- 純邏輯抽成可 import 的函式，讓 pytest 在無網路下 mock 測試。

## 抓取環境

`data.fda.gov.tw` 從 GitHub Actions runner 直接抓**沒有問題**，不需要 proxy。memory 裡記的「TFDA 回 500」只發生在 **Google IP**（Apps Script），與 Actions（Azure）無關；`TFDA-drug-shortage-dashboard` 的排程長期直打同一網域成功。

注意這與 `consumer.fda.gov.tw` 不同——那個網域對所有境外 IP 在 TLS 層切斷，只能台灣本機抓。本專案用的 `data.fda.gov.tw` 不受此限。

## 資料規模的實務含意

- 解壓後 166 MB，單列 `納入條件`／`排除條件` 最長 **22,490 字元**。前端絕不解析原始 CSV。
- 實測以 protocol 收斂後的卡片欄位 JSON 為 **715 KiB gzip**（spec 上限 1.5 MB），長文字走按需載入 shard。改動卡片欄位清單時重新量測，別憑印象說還在預算內。
- 本機跑 ETL 前先確認 stdout 已 UTF-8 reconfigure；Windows 主控台預設 Big5，直接印中文欄名會變亂碼（除錯時把結果寫成 UTF-8 檔再讀，不要靠終端輸出判斷資料對錯）。

## 文件慣例

- `Taiwan-Clinical-Trial-Radar-spec.md` — 規格本體。**raw source 不手動修改**；修正規則一律以版本控制的 transformation + 測試實作。
- `TODO.md` — 待辦與未定案決策。
- `PROGRESS.md` — 進度紀錄，每個里程碑一段，附實測數字。
- 規格改完要**再審一輪，且第二輪只審「修訂本身」**（走 `/codex-checkplan`）。規劃者與審查者不同人。
- Commit message：`type(scope): 說明`，type 為 `feat`／`fix`／`refactor`／`docs`／`chore`；資料更新用 `data: update TFDA clinical trial dataset YYYY-MM-DD`。
