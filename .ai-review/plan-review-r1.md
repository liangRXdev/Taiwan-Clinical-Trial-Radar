# Codex 規格覆審原始輸出

- **審查日期**：2026-09-18
- **Codex 版本**：codex-cli 0.153.4（MCP `mcp__codex__codex`，`sandbox: read-only`、`approval-policy: never`）
- **thread id**：`01a0b1cd-7c88-7b31-b2ca-d71b230a302c`
- **受審文件**：`.ai-review/plan.md` v0.2（2026-09-18），連同 repo 內 `Taiwan-Clinical-Trial-Radar-spec.md` v0.1（2026-09-12）
- **受審 commit**：`8a5d1c5`（plan.md v0.2 於此 commit 後新增，尚未進版）

以下為 Codex 輸出，**原封不動**未修飾、未刪改。判定見 `plan-verdict.md`。

---

## 1. 需求與邊界缺漏

整體判定：§5.1、§5.3、§5.4 方向成立；§5.2 的 protocol 收斂可以保留，但「一列＝一個 Revision」及單值 `latest` 尚不足以安全上線。OPEN-1 目前建議不可採用。OPEN-2 應先採最小版本歷史，不應先產生帶方向性的 diff。

### 1.1 最高日期平手不能被稱為唯一 `latest`

- **嚴重度：Blocker**
- **問題：** SHA-256 或「非空欄位較多」只能決定輸出穩定性，不能證明哪筆在業務上較新。來源沒有時間、版號或修訂序號；846 組最高日期平手，其中只要欄位不同，就不存在可證實的唯一最新版。「一列＝某一版試驗計畫書」本身也是推論，資料只證明同 protocol 有多筆審查紀錄。
- **為什麼現在不修之後會更貴：** `latest` 會滲入卡片、搜尋、篩選、統計、URL 結果與 diff。完成後才改成多候選模型，需重做資料 schema、索引、UI 與多數測試。
- **建議修法：** 把來源列稱為中性的 `SourceRecord` 或「審查紀錄」。最高日期只有一筆，或同日紀錄在呈現欄位完全相同時，才可產生唯一 `latest`；最高日期存在實質衝突時，資料模型須表達 `latestCandidates[]`／`latestAmbiguous=true`，UI 明示「同一最新資料日期有多筆不同紀錄」。不得以完整度或 hash 推定業務先後。hash 僅可作排序穩定器。

### 1.2 protocol identity normalization 未定義

- **嚴重度：High**
- **問題：** 「protocol number 正規化後為主鍵」沒有列出允許的轉換。若沿用搜尋的 NFKC、大小寫或標點處理，可能把不同 protocol 錯誤合併；這與「寧漏勿誤」相反。
- **為什麼現在不修之後會更貴：** 主鍵規則決定 Trial 數、URL、shard、歷史歸屬及月更新 diff。規則改動會造成大量 ID 變更與連結失效。
- **建議修法：** 分開定義「identity normalization」與「search normalization」。前者只允許逐項列明且經凍結 fixture 證實安全的轉換；遇到正規化碰撞但 raw protocol 不同時須 fail-closed 或保留為不同 Trial 並產出 collision report，不可直接合併。

### 1.3 空 protocol 的 stable ID 規則不完整

- **嚴重度：High**
- **問題：** `row hash` 未定義 hash 的序列化、欄位順序、空值表示與重複 hash 處理。兩筆空 protocol 且 16 欄完全相同時會產生相同 ID；若用列序 suffix，又違反 A6。
- **為什麼現在不修之後會更貴：** ID 一旦進入 URL、shard 與月更新 diff，碰撞處理改版會破壞既有連結與歷史比對。
- **建議修法：** 規格寫死 canonical serialization、hash 範圍及碰撞策略。完全相同的多重列應按內容 hash 加「同內容出現序號」形成 deterministic multiset ID；序號由完整 canonical record 排序後配置，不依輸入列序。並明示這類 ID 只保證對相同來源快照穩定，不能宣稱跨上游重排或增刪仍代表同一實體。

### 1.4 搜尋、篩選與統計到底使用哪一層未定義

- **嚴重度：High**
- **問題：** 卡片寫明使用 `latest`，但搜尋欄位、filters、relevance、phase 統計及申請者排名未說只看最新紀錄或包含全部歷史。若歷史適應症命中、卡片卻只顯示另一個最新適應症，使用者會誤以為卡片內容就是命中來源。
- **為什麼現在不修之後會更貴：** 搜尋索引與 stats schema 會依此定型；後補版本語意需重建索引並改寫前端。
- **建議修法：** 逐項寫死：

  - 卡片、filter、dashboard 的資料層。
  - 搜尋是否涵蓋歷史。
  - 若涵蓋歷史，命中標籤必須指出日期／紀錄，不得把舊值歸到最新紀錄。
  - 最新日期有衝突時，統計採何種保守規則；不可任取其中一筆。

### 1.5 v0.1 仍生效條文與四項定案互相衝突

- **嚴重度：High**
- **問題：** v0.2 只宣告取代 v0.1 的 §2、§6.6、§7.1–§7.3、§16；但仍生效的 v0.1 §3.1 要為未來 relation 保留模型、§5.1 列 206–209 為來源、§8 保留 `linkageStatus`／`linkage-report`、§9 列 `verify_linkage.py`、§14 要測 206–209 join、§18 更要求第一個 commit audit 五份資料並寄信。這些直接違反 §5.1 定案。
- **為什麼現在不修之後會更貴：** 實作者依不同條文會產生不同 backlog、輸出 schema 與驗收結果，可能真的建立已取消的元件。
- **建議修法：** 擴大明確失效清單，至少涵蓋上述句段；最好合併成一份單一 normative 規格，不再依「衝突時 v0.2 優先」人工判讀。

### 1.6 日期異常時無法執行「最新版」規則

- **嚴重度：High**
- **問題：** v0.1 要求無法解析日期時保留 raw 並警示，但 v0.2 沒定義空日期、無效日期、未來日期如何參與排序；`sourceUpdatedAt=max()` 也沒有相應規則。
- **為什麼現在不修之後會更貴：** 日期處理會同時影響 latest、全站資料日期、結果排序與統計；後補規則會改變大量輸出。
- **建議修法：** 明定可接受格式、空值／無效值的排序資格，以及是否因「某 Trial 全部日期不可解析」而禁止生成單值 latest。全站 `sourceUpdatedAt` 只能由成功解析且通過合理性規則的日期計算，並另外報告被排除的原值。

### 1.7 sentinel 的 UI 語意仍有洞

- **嚴重度：Medium**
- **問題：** `sourceZero` 只定義資料旗標，沒有規定 UI 必須避免把來源 `0` 解讀為「確定沒有受試者」。此外 D4 的「sentinel 篩選」與 §5.3「0 不進篩選選單」矛盾。
- **為什麼現在不修之後會更貴：** 資料模型不必重做，但卡片、詳情、filter 與測試會各自形成不同語意。
- **建議修法：** 明定數值 0 的顯示文字必須表達「來源填 0」，而非推論為零收案；D4 改成已正式定義的 filter 狀態，或先刪除該組案例。

### 1.8 ETL 門檻、基準與失敗分類未完整定義

- **嚴重度：Medium**
- **問題：** 驟降的分母、比較對象、四捨五入、恰好 20.0%、首次 build 無 baseline 時的行為均未定義。HTTP 只列 500，未說其他非 2xx、redirect、429、timeout、截斷下載及帶參數的 content-type 如何分類。
- **為什麼現在不修之後會更貴：** 不同實作都能宣稱符合 B4；月更新首次遇到邊界值時才會暴露。
- **建議修法：** 門檻以來源資料列數對上一個「成功發布快照」計算，公式、精度及 `>20%` 的開閉邊界寫死。所有非允許 HTTP 狀態及不完整回應歸入明確失敗類別；首次無 baseline 時使用獨立 bootstrap 規則，不假裝完成驟降比較。

### 1.9 併發／重入只有 workflow 名稱，沒有狀態語意

- **嚴重度：Medium**
- **問題：** `concurrency 序列化` 未定義 schedule 與手動執行是否共用 group、是否允許取消 running run、上一個 run 在下載後下一個 run 讀哪個 baseline。
- **為什麼現在不修之後會更貴：** 問題只會在實際 Actions 重疊時發生，通常已涉及 production data 或重複 commit。
- **建議修法：** 規格明定所有資料更新入口共用同一 concurrency group、不得取消已進入發布階段的 run，且每個 run 的 baseline 必須是啟動時可驗證的上一個正式快照；失去 baseline 一致性時 fail-closed。

---

## 2. 架構風險

### 2.1 多檔案 `os.replace` 不能構成整體原子發布

- **嚴重度：High**
- **問題：** manifest、stats、index 與多個 shard 無法靠逐檔 `os.replace` 形成單一原子交易。任一檔替換後程序中止，仍可能留下新舊混合資料；B5 只注入「寫 manifest 前」也沒有覆蓋所有 promotion 邊界。
- **為什麼現在不修之後會更貴：** 輸出目錄與載入契約一旦固定，改成 snapshot 型發布會影響路徑、manifest、Cloudflare build 與測試。
- **建議修法：** 規格把「產生完成」與「對外發布」分開：完整資料先形成不可變快照並驗證整體 digest／referential integrity，Cloudflare 只部署完整快照。若 repo 內保留正式資料，manifest 指向的 snapshot 必須最後才切換；不得聲稱逐檔替換等於整體原子。

### 2.2 `builtAt` 與「無變動不 commit」互相矛盾

- **嚴重度：High**
- **問題：** 每次 workflow 都更新 `builtAt`，則 normalized output 每次必變，H2/H3 的第二次無 commit 不可能成立。
- **為什麼現在不修之後會更貴：** 會影響 manifest 語意、diff、冪等測試及 UI 顯示日期。
- **建議修法：** 明定 `builtAt` 是「目前已發布資料 artifact 的建置時間」。若來源正規化結果無變化，新的暫存 build 不發布，正式 manifest 的 `builtAt` 也不變。比較是否需 commit 時，必須先定義 volatile metadata 是否排除，且 UI 標籤與此語意一致。

### 2.3 Trial／Revision schema 缺少完整輸出契約

- **嚴重度：High**
- **問題：** 未定義 revision ID、Trial 到 shard 的映射、`latest` 是嵌入資料或 reference、排序 total order、重複紀錄、schemaVersion 升級及 referential integrity。兩層概念正確，但不足以生成可驗收 artifact。
- **為什麼現在不修之後會更貴：** shard 與前端載入方式是最難遷移的靜態 API。
- **建議修法：** 在規格層補上最小輸出契約：每一類物件的 stable identity、reference 方向、排序鍵、衝突表示、完整性不變量及 schemaVersion 變更條件。不要規定程式碼結構。

### 2.4 Cloudflare Pages 路由策略未定案

- **嚴重度：Medium**
- **問題：** v0.1 要測 404／deep link，但 v0.2 沒決定詳情 URL 是可直接重新整理的路由、hash route 或靜態頁。D4 只測 query state，不能證明詳情頁 deep link 可用。
- **為什麼現在不修之後會更貴：** URL 形狀一旦被引用或分享，後改會造成斷鏈。
- **建議修法：** 在規格中選定一種靜態主機相容的 canonical URL，並要求直接開啟、重新整理及未知 Trial ID 都有明確結果。

### 2.5 最難回頭的決策排序

- **嚴重度：High**
- **問題：** 目前最難回頭的不是 Cloudflare Pages，而是「identity normalization + 單值 latest + URL/shard identity」的組合。
- **為什麼現在不修之後會更貴：** 它同時定義資料實體、歷史歸屬與外部連結。
- **建議修法：** M1 前依序封存：identity 規則、同日衝突模型、revision identity、shard/reference 契約；Cloudflare Pages、純靜態、無 PWA、只用 dataset 205 均與限制相容，無須翻案。

---

## 3. 驗證策略缺口

以下每條都回答「什麼弱化實作仍能通過」，並給出堵洞斷言。

### A. 資料模型與收斂

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| A1 | **High**：錯誤的 protocol normalization 只要 fixture 的寫死總數剛好相同仍會通過；也可錯合併一組、錯拆一組而總數不變。 | 錯誤會進入全部 ID 與統計。 | 不只斷言總數；寫死每個來源列 fingerprint 對應的 Trial ID／group membership，加入一組「易被過度正規化錯合併」與一組「應合併」案例。 |
| A2 | **Medium**：只要求 fixture「包含」案例，實作完全忽略它們也可通過。 | 會產生看似豐富但無 oracle 的 fixture。 | 每個案例都附明確期望：group、revision 數、latest 狀態、raw 保存、錯誤／警告結果。 |
| A3 | **Medium**：只測一次 shuffle，列序第一筆可能碰巧仍相同；也可漏輸出檔而被不完整 hash 清單忽略。 | 非確定性可能只在月更新出現。 | 對 reverse 與多個固定 seed 排列測試；先斷言完整檔案 inventory 相同，再逐檔 hash；另斷言每個 tie case 的語意結果。 |
| A4 | **Medium**：A3 可能因 JSON 陣列順序等無關原因失敗，仍被算作殺死 mutation。 | 會誤以為 tie-break 已被驗證。 | 反向哨兵必須證明失敗點是指定 tie group 的候選選擇不同，而非任意位元差異；若採 ambiguous latest，mutation 改成「任取第一筆」並斷言 ambiguity 消失時測試失敗。 |
| A5 | **High**：可漏一列同時複製另一列，總和仍等於原始列數。 | 靜默錯置會污染臨床內容。 | 比對來源 canonical fingerprint 的完整 multiset，包含每個 fingerprint 的 multiplicity；不能只比總數。 |
| A6 | **High**：六列若內容都不同，無法揭露兩筆完全相同空 protocol 的 hash collision；只測一次 shuffle 也不足。 | fallback ID 上線後難以遷移。 | fixture 加入兩筆完全相同的空 protocol 列；斷言六列均有唯一 ID、完整 multiset 保留，且多個排列輸出一致。 |

### B. ETL 可靠性

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| B1 | **Medium**：只處理明列的 HTTP 500，其他非 2xx 可能漏掉；只比既有檔 hash/mtime，新增半套檔案仍可通過。 | 首次真實網路異常才暴露。 | 對所有不允許 status 建立同一性質斷言；快照需比較完整檔名集合、內容 hash、正式 manifest 指向及無新增正式檔。content-type 比對須容許合法參數但拒絕 HTML。 |
| B2 | **Medium**：「exit code 或錯誤碼」允許七種都用同一 exit code，只靠模糊訊息區分。 | 維運時無法可靠判斷失敗層。 | 每個案例寫死 structured error code 與 layer；stderr 只作輔助，不得以任意文字包含判定。 |
| B3 | **Low**：可因任意解析錯誤失敗，而非因 zero-row policy 失敗。 | 日後放寬 parser 可能意外發布空集。 | 斷言 CSV schema 已通過後，明確回傳 `ZERO_ROWS` 類別，且正式 snapshot digest 不變。 |
| B4 | **Medium**：19.9/20.1 未釘住恰好 20.0、計算分母、rounding 與首次無 baseline。 | 門檻在不同資料量下會漂移。 | 寫死公式及整數案例，加入 10.0、10.1、20.0、首次 build；斷言 warning、success、hard failure 的精確結果及是否發布。 |
| B5 | **High**：只在單一時間點注入失敗；逐檔替換可在其他 promotion 點留下混合資料。 | 原子性問題需改輸出架構。 | 對 staging 驗證、snapshot 完成、manifest 切換、commit/deploy 前各失敗點測試；正式 snapshot 必須整體等於舊版或整體等於新版，不允許第三種混合 digest。 |

### C. Sentinel 與空值

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| C1 | **Medium**：`stats.json` 不含 `"0"`，但搜尋索引或 UI filter 仍可自行產生 `"0"`；也未驗證 UI 顯示「未提供」。 | 前端與資料層可能分歧。 | 同時斷言 typed value、raw value、stats option、實際 filter DOM 與卡片／詳情顯示。 |
| C2 | **Medium**：實作可對所有數字都設 `sourceZero=true`，仍滿足唯一的 0 案例。 | 旗標失去稽核意義。 | 同時放入 0、非 0、空白、malformed；逐筆斷言 parsed value 與 `sourceZero` 真值。UI 另斷言顯示「來源填 0」。 |
| C3 | **Medium**：QA 只要有三個計數欄即可，數字錯誤仍通過；輸出中也可能藏在不可達欄位。 | QA report 會提供錯誤安全感。 | 寫死三類精確計數及對應 record ID；詳情切換到該 revision 後的可見文字須精確相等。 |
| C4 | **Low**：三項「全部失敗」可能因單一共用 schema error 失敗，而非真的守住三種語意。 | mutation test 診斷力低。 | 分三個獨立 mutation／fixture，分別證明分類 raw、數值 0、文字 sentinel 的指定斷言被殺死。 |

### D. 搜尋與篩選

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| D1 | **High**：只實作 title 與 purpose 搜尋即可通過，其他五個規定欄位可完全壞掉。 | 搜尋 index schema 需重做。 | 七個 searchable fields 各有唯一 canary 與精確 expected Trial IDs；另測多欄同時命中，命中標籤集合須完全相等，不可缺漏或多報。 |
| D2 | **High**：「人工裁決」不是可重跑 oracle；全形數字在 NFKC 下本來就會等價，與「誤命中反例」描述衝突。 | 正規化策略會污染 identity 與查詢。 | 先逐欄寫死 normalization policy；fixture 以明確的 `shouldMatch`／`mustNotMatch` pair 表示。identity normalization 與 search normalization 分開驗證。 |
| D3 | **Medium**：只有跨欄位正例；OR 實作可透過特製資料碰巧通過。 | 多詞語意錯誤會廣泛誤報。 | 對同一查詢寫死完整結果集合；包含「只命中其中一詞」且必須排除的 Trial，以及兩詞同欄、兩詞跨欄正例。 |
| D4 | **High**：「含 sentinel 篩選」目前沒有合法產品語意；實作可忽略該 filter，重載前後仍相同。 | URL 契約上線後難改。 | 移除矛盾案例或先定義「未提供」filter。每個正式 filter 維度至少一組；除結果 ID 外，同時斷言 query/filter 控制項、canonical URL 與 reload 後狀態精確相等。 |
| D5 | **Medium**：只檢查選單文字，改名為「收案情形」或接受隱藏 URL 參數仍可通過。 | 仍可能形成招募暗示。 | 斷言 filter schema、DOM controls、URL parser 與輸出 state 均不存在 trial-status 維度；中文同義 UI 不得出現。 |

### E. 呈現與誤導防範

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| E1 | **High**：字串黑名單會誤傷來源原文中的 `active`，同時漏過「開放收案」「可報名」等暗示。 | 高風險誤導仍可能通過。 | 測 UI 自產生的 badge、欄位、accessible name、filter 與排序，不對來源原文做無條件禁字；另以精確免責文句正向斷言「本站不提供目前招募狀態」。 |
| E2 | **High**：任意數字旁放「試驗」即可通過，分母可算錯。 | 錯誤統計直接影響判讀。 | 每張卡以獨立 oracle 寫死精確值、單位與分母類型；phase/scale 總和須符合已定義的 unknown／ambiguous 規則。 |
| E3 | **High**：把兩個值交換、或顯示任意兩個不同值仍會通過。 | 資料日期是誤導防線。 | 斷言各 label 對應精確 fixture 值，而非只斷言不相等；來源日期、artifact build time 都必須匹配 manifest／record。 |
| E4 | **Medium**：惡意字串可藏在不可見 DOM；`onerror` 未實際觸發也可能讓測試誤判。 | shard 或不同 revision 仍可能有注入點。 | 對卡片、詳情及版本切換分別測試；斷言來源內容為可見 text、未生成來源控制的元素或 event handler，且執行觀察值保持不變。 |
| E5 | **High**：任何名為「免責聲明」的空泛或隱藏文字都能通過；目前 footer 也未包含「試驗使用不代表上市核准」。 | 直接漏掉最高權重的兩種誤讀。 | 寫死必須可見的核心性質：不提供目前招募狀態、TFDA 審查／試驗使用不等於藥品上市核准、須向官方確認；逐頁斷言，不只查節點存在。 |
| E6 | **Medium**：heading 可見但展開後文字被截斷；只測一個長欄位，另一欄仍可壞。 | 長文字元件完成後才會發現資料遺失。 | inclusion 與 exclusion 各有長 fixture；展開後以換行正規化後的全文精確相等、首尾 canary 存在，切換 revision 後也須相符。 |

### F. 效能

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| F1 | **Medium**：可把資料在量測完成後立即 lazy-load，或使用與 production 不同的壓縮設定而通過。 | 實際首屏仍可能超標。 | 定義冷啟動到可搜尋狀態前的全部 network responses；以 production build 與固定 gzip 設定計算，列出納入檔案及總和。 |
| F2 | **Medium**：改名、用 positional array 或直接嵌入長文字值即可避過欄位鍵檢查。 | 166 MB 資料邊界可能被繞過。 | 除欄位鍵外，在 criteria 放唯一長 canary，斷言所有初始 response／bundle 均不含其內容；只有開啟對應詳情 shard 後才出現。 |
| F3 | **Medium**：使用容易命中的單一查詢、排除 debounce 或在 DOM paint 前停止計時即可通過。18,736 列也不是前端實際 Trial 數。 | 效能問題通常要改索引或渲染策略。 | 指定以完整 production-scale Trial/index fixture、固定查詢 corpus（零結果、極多結果、中英、多詞）量測；時間從輸入事件到結果 DOM 完成，逐案例或明定 percentile 均須 ≤300 ms。 |

### G. 無障礙

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| G1 | **Medium**：設定 `overflow-x:hidden` 即可通過，但內容可能被裁切。 | 行動版完成後才發現需重排元件。 | 除 scrollWidth 外，斷言可見文字、表單及 focusable elements 的 bounding box 均位於 viewport；不得靠裁切滿足。 |
| G2 | **Medium**：只掃首頁預設狀態即可聲稱「所有組合」；hover、focus、warning、disabled、圖表文字可漏測。 | 色彩系統定型後修正成本增加。 | 列出路由與元件狀態矩陣；每個實際文字／背景組合輸出 selector、前景、背景與 ratio，依 normal/large text 門檻判定。 |
| G3 | **High**：一個可見 focus 樣式即可通過「完整鍵盤導航」，即使版本切換、折疊、圖表 filter 不可操作。 | 互動元件完成後需逐一返工。 | 對每類互動元件列出 tab 可達、順序、Enter/Space 行為、focus 不遺失及無 keyboard trap 的具體斷言；期別／警示須驗證可讀文字或 accessible name。 |
| G4 | **Medium**：放一個空 table 或內容與圖表不一致即可通過。 | 圖表資料與替代呈現可能分叉。 | 每張圖表的 table/list 必須在 DOM 可讀、具有標題與欄名，且 key/value 集合與圖表資料精確相等。 |

### H. CI 與自動化

| 條件 | 嚴重度 / 問題 | 為什麼晚修更貴 | 建議修法 |
|---|---|---|---|
| H1 | **Medium**：六個名稱正確但實際空跑、或使用 `continue-on-error`，仍可通過文件檢查。 | CI 會形成錯誤安全感。 | 對每個 gate 注入一個已知失敗，斷言 workflow/job 為 failure；檢查實際命令、觸發分支與 path filter，不只檢查 step 名稱。 |
| H2 | **High**：`builtAt` 每次變動使「僅資料變動才 commit」無法成立；concurrency key 不同也可表面上都有設定。 | 會造成每月噪音 commit 或重疊發布。 | 用同一凍結來源連跑兩次；第二次 git tree、正式 snapshot 與 HEAD 不變。schedule／manual 共用同一 group，diff 摘要以獨立 oracle 驗證 exact additions/removals/modifications。 |
| H3 | **High**：兩次讀活端點，來源可能真的變動；只檢查「沒有 commit」也可能是 workflow 根本沒做事。 | 上線當天的證據不可重現。 | 第二次須重用相同 source SHA；斷言兩次均成功完成完整 pipeline，第二次 HEAD/tree 不變且明確回報 no normalized change。先解決 `builtAt` 語意。 |
| H4 | **Medium**：只 pin 頂層 `uses`，reusable workflow／container 未固定；或整個 workflow 預設已有 write 權限。 | 供應鏈問題通常晚至依賴更新才暴露。 | 斷言所有直接與間接 `uses` 均為不可變 SHA／digest；workflow 預設 permissions 為 read/minimal，只有唯一更新 job 明示 `contents: write`，其他 job 明示無 write。 |

---

## 4. 更簡單的替代方案

### 4.1 OPEN-1：不要發明 tie-break，直接保存不確定性

- **嚴重度：Blocker**
- **問題：** 「非空最多，再取 hash 最小」增加規則卻沒有增加真實性，反而把不確定資料包裝成確定最新版。
- **為什麼現在不修之後會更貴：** 一旦所有前端依賴單值 `latest`，再引入 ambiguity 會全面返工。
- **建議修法：** 最簡單且符合「寧漏勿誤」的方案是：

  - 依 protocol 分組。
  - 依日期降序分成 date cohort。
  - 最新 cohort 若只有一筆，顯示該筆。
  - 最新 cohort 多筆但呈現欄位相同，可顯示共同值並保留 multiplicity。
  - 最新 cohort 欄位衝突，卡片只顯示無衝突的共同欄位；衝突欄位顯示「同日多筆資料，請展開確認」。
  - hash 只負責 cohort 內穩定排序，不宣稱時間先後。

這比抽樣判斷「清空是否代表取消」更穩健；抽樣無法證明未來資料的語意。

### 4.2 OPEN-2：MVP 不做有方向性的 `A → B` diff

- **嚴重度：High**
- **問題：** 日期平手時沒有可靠順序，`20 → 30` 可能把方向寫反；長文字 diff 也容易暗示後者取代前者。
- **為什麼現在不修之後會更貴：** diff schema、前端元件與 shard 體積都會被鎖定。
- **建議修法：** MVP 只做：

  - 依日期分組列出完整來源紀錄。
  - 日期間可標示「哪些欄位存在不同值」，但不產生方向箭頭。
  - 同日多筆明示「順序未知」。
  - 使用者點選後查看原文。

等來源未來提供版號或可靠時間，再考慮有方向性的 diff。

### 4.3 移除 `FEATURE_TRIAL_STATUS`，而非保留永遠關閉的功能旗標

- **嚴重度：Medium**
- **問題：** 本次已定案不提供 status，保留旗標增加一條可能被誤開的路徑。
- **為什麼現在不修之後會更貴：** 搜尋 schema、UI 與測試會開始為不存在的功能保留分支。
- **建議修法：** 本版資料模型與前端完全不含 status feature。未來來源新增欄位時，依既定 schema change／規格修訂流程新增，不靠現成旗標直接上線。

### 4.4 首版可不做圖表

- **嚴重度：Low**
- **問題：** v0.1 §6.5 用語是「可顯示」，但 G4 把圖表替代呈現變成必驗項，形成不必要元件。
- **為什麼現在不修之後會更貴：** 圖表會增加 payload、a11y、互動 filter 與統計一致性測試。
- **建議修法：** 首版使用數字卡、文字清單或原生 table 即可；若沒有圖表，G4 改成條件式驗收「若提供圖表，則必須有等價 table/list」。不減少既有資訊需求。

### 4.5 合併 normative 規格，取消跨文件覆蓋鏈

- **嚴重度：Medium**
- **問題：** v0.2 + 部分仍生效 v0.1 迫使實作者自行解衝突，已實際留下 206–209 與第一個 commit 的矛盾。
- **為什麼現在不修之後會更貴：** 每次修訂都會增加 precedence 判斷，驗收也無法指出唯一規範來源。
- **建議修法：** v0.2 通過後產生單一 consolidated specification；舊版保留為歷史文件但不再具 normative 效力。這是文件簡化，不新增產品需求。
