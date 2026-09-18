# 規格覆審判定（第二輪）

- **判定日期**：2026-09-18
- **受審對象**：`.ai-review/plan.md` v0.3（commit `2ffa7c7`），範圍限定 v0.2 → v0.3 的修訂
- **Codex 原始輸出**：`.ai-review/plan-review-r2.md`（codex-cli 0.153.4，thread `01a0b1f3`）

## 統計

| 判定 | 數量 |
|---|---:|
| 接受 | 53 |
| 部分接受 | 1（F3） |
| 拒絕 | 0（範圍蔓延 0） |
| **Codex 發現合計** | **54** |
| 我方自行發現（不在 Codex 輸出中） | 2（S1、S2） |

嚴重度：**Blocker 0**、High 17、Medium 27、Low 10。Codex 主動標「無缺口」5 項（A6、B3、C3、E6、H4）。

**五項偏離的覆核結果：2 項維持、3 項被否決。**

| 偏離 | Codex 判定 | 我的處置 |
|---|---|---|
| 2.1 git commit 為 promotion 邊界 | 不成立 | **接受否決**（詳 §偏離 1） |
| B5 四個失敗注入點 | 不成立 | **接受否決** |
| 1.6 日期規則降 Medium | 不成立 | **接受否決**，回復 High |
| A6 空 protocol 碰撞降 Medium | 成立 | 維持 Medium |
| 4.4 圖表由產品決策決定 | 成立 | 維持 |

第一輪有 2 個 Blocker，第二輪 **0 個**——方向已穩定，剩餘全部是「精確度不足」而非「方向錯誤」。

---

## 對五項偏離的判定

### 偏離 1：git commit 為 promotion 邊界 → **接受 Codex 的否決，我錯了**

Codex 拆成三點，三點都成立：

**(a) working tree 混合窗口**（同 X2）。我 §9.2 寫「任一階段失敗 → working tree 中的正式資料整體等於舊版」。這是**錯的**：從第一個檔案被替換到 commit 完成前，working tree 就是混合狀態，而 commit 的原子性不回復 working tree。程序崩潰或被取消時保證不成立。

修法：這個保證本來就下在錯誤的邊界。CI runner 的 working tree 是**用後即棄、沒有任何讀者**，真正需要保證的是「**被 commit 與 push 出去的 tree 永遠是完整的**」。v0.4 改為這個說法，並明寫 runner 短暫性；同時所有 artifact 先寫 staging，替換與 `git add -A` + commit 收攏為管線最後步驟。

**(b) 瀏覽器／CDN 跨版本混用**（同 N8）。**這點我完全沒想到，而且它比 (a) 嚴重。** 所有 artifact 用固定 URL（`manifest.json`、`trials-index.json`、`records/ab.json`），瀏覽器或 CDN 快取會讓一次 session 混用舊 manifest 與新 shard → 出現不存在的 reference，或顯示錯誤紀錄。對臨床工具而言這是直接的誤導風險。

修法（不需 snapshot 目錄，與純靜態相容）：**內容雜湊檔名 + 單一版本化入口**。`manifest.json` 是唯一固定 URL（短快取），內含 `datasetVersion` 與所有其他檔案的雜湊路徑（`trials-index.<hash>.json`、`records/ab.<hash>.json`，長快取 immutable）。一次載入只能解析同一版本；舊檔留在快取但已無人引用。前端另斷言每個載入檔案宣告的 `datasetVersion` 等於 manifest 的值，不符即 fail-closed 顯示「資料版本不一致，請重新載入」。

**(c) 規格缺少部署鏈結保證**。接受：須寫明 Cloudflare build 使用哪個 SHA、何時視為正式部署、部署失敗時哪一版為 authoritative。

**結論**：我原本的推論只對了一半（commit 對 repo tree 確實原子），但把它當成「整條發布鏈都原子」是過度延伸。保留不採 snapshot 目錄的決定仍可行，但必須另補跨檔版本綁定與快取一致性——這不是我原本主張的「少一層元件」，而是換一層元件。

### 偏離 2：B5 四個失敗注入點 → **接受 Codex 的否決**

四點確實避開了最危險的窗口。Codex 列的七個邊界（部分替換後、刪 orphan 途中、git index 只含部分變更、commit 失敗、commit 成功但 push 失敗、push 成功但部署失敗、非例外式終止）都屬實。我原本的「commit 前」若指全部替換完成後，就完全沒測部分替換窗口——**B5 現況可以讓非原子的逐檔替換實作通過**，正是我想堵的那種弱化實作。

### 偏離 3：日期規則降 Medium → **接受 Codex 的否決，回復 High**

我的降級理由是「實測 18,736 筆日期全部乾淨」。Codex 的反駁成立：這是**每月重跑的 ingestion contract，不是一次性資料清理**，現況乾淨只降低當下發生率，不降低規格缺口的修正成本。

更關鍵的是 Codex 指出兩個我自己造的洞使這一區整體為 High：

- **I2**：§6.4 定義 `latestAmbiguous = cohort>1 且有衝突`，§6.5 卻說全日期不可解析時「無條件 `latestAmbiguous=true`」，而此時 cohort 未定義。這是模型矛盾。
- **N3**：我讓未來日期「排除於全站 `sourceUpdatedAt` 但仍參與 trial 內排序」，等於**讓單筆打錯的 2099/01/01 永久支配該試驗的卡片**。這直接命中最高風險（誤導）。

兩者都會改動 Trial 收斂模型、`displayFields`、篩選與統計，依我自己給的嚴重度定義就是 High。**補出 7 列 end<start 有價值，但抵不掉這兩個洞。**

### 偏離 4：A6 降 Medium → **Codex 判定成立，維持**

並同意其附帶提醒：N1（canonical serialization 非一對一 + 截短 ID 碰撞）是 v0.3 新產生的另一個 High，不因 A6 降級而豁免。

### 偏離 5：圖表由產品決策決定 → **Codex 判定成立，維持**

Codex 明確同意「不提供圖表」本來就是合規產品形態，需要修的是 G4 在有圖表時的可證偽性。

---

## 1. 修訂自造的新洞

| # | 嚴重度 | 判定 | 理由與處置 |
|---|---|---|---|
| N1 | High | **接受** | 屬實。實測補強：**U+001F 不存在於本快照**（控制字元只有 CR/LF/TAB；58,140 個欄位含換行、10,725 個含 TAB），故 U+001F 當分隔符目前安全——但規格必須**主動拒絕**遇到 U+001F 的輸入而非假設它不出現。**16-hex 截短在本快照 0 碰撞**（16,328 個不同紀錄），仍須偵測並 fail-closed。v0.4 明定：encoding 對 16 欄 tuple 一對一（含長度前綴或拒絕分隔符）、identity key／trialId／recordId 三者各自的碰撞偵測與 fail-closed。 |
| N2 | High | **接受** | 屬實且是我造的洞：`latestAmbiguous` 依賴未定義的「呈現欄位」集合，實作者排除期別或人數就能讓衝突消失。**且比較模式的選擇有實測影響**：raw 比較得 157 組 ambiguous，NFKC+空白正規化比較得 **143 組**，差 **14 組**。v0.4 明定封閉欄位集合，並選定「以 NFKC＋空白正規化值判定衝突、以 raw 值顯示」——那 14 組只差空白或全半形，標成「不一致」是假警報，會訓練使用者忽略警示。 |
| N3 | High | **接受** | 屬實，見偏離 3。v0.4 在 Codex 給的兩個選項中**明確選擇**：未來日期**排除於 `latestSourceDate` 選擇**（不只排除於全站 `sourceUpdatedAt`），該紀錄仍出現在歷史並標記「日期超出合理範圍」。理由：單筆打錯不應讓整張卡片空白，顯示最新的**合理**紀錄並附可見警示，是誤導最小的選項。 |
| N4 | Medium | **接受** | 屬實，我只定了正規化與 AND/OR，沒定 matching operator。v0.4 寫死：query 以空白切分為 terms；每個 term 對正規化後欄位文字做 **substring 比對**（中文無空白，token 化不可行）；純空白或空查詢 → 不執行搜尋，顯示瀏覽狀態。 |
| N5 | Medium | **接受** | 屬實。v0.4 封存每個維度的 typed value、bucket 邊界、null／衝突歸類，並寫死**同維度多選 = OR、跨維度 = AND**。 |
| N6 | Medium | **接受** | 屬實，且 D4 的「canonical URL 精確相等」目前沒有唯一 oracle。v0.4 補完整 URL state schema（參數名、順序、編碼、重複參數、空值與無效值處理），並明定 `protocol=` 別名以 identity normalization 後比對。 |
| N7 | Medium | **接受** | 屬實，是 §6.5 與 §7.2 交互產生的洞。v0.4 明定不可解析／空日期的命中標示為「資料日期不明」，**不得偽造成合法日期**。 |
| N8 | High | **接受** | 見偏離 1(b)。這是本輪最有價值的發現。 |

## 2. 修訂不完整

| # | 嚴重度 | 判定 | 理由與處置 |
|---|---|---|---|
| I1 | High | **接受** | 屬實：§9.3 只列檔名與少數欄位，不足以驗收。前端與 ETL 可各做出通過局部測試但互不相容的格式。v0.4 補逐檔 top-level shape、required／nullable／型別、`stats.json` 與 `search-index.json` 結構與 posting 語意、shard 結構、artifact inventory 與「整體 digest」的涵蓋範圍。**M1 前封存。** |
| I2 | High | **接受** | 屬實，模型矛盾（見偏離 3）。v0.4 引入**獨立旗標 `dateUnknown`**，不重用 `latestAmbiguous`，並定義該情形下 cohort、排序、`conflictFields` 各為何。 |
| I3 | Medium | **接受** | 屬實：欄位 rename 同時滿足 MISSING 與 EXTRA，無客觀判定。v0.4 **移除 `SCHEMA_COLUMN_RENAMED` 這個獨立 code**（無法客觀辨認者不列為必然 code），改為 `SCHEMA_MISMATCH` 攜帶 detail；並定義多重失敗的 precedence 順序（transport → archive → decode → schema → content）。 |
| I4 | Medium | **接受** | 屬實：只要求「產出 collision report」，空 JSON 也能通過。v0.4 規定 report 須能唯一定位每個 collision group、相關 raw protocol、identity-normalized 值與來源 fingerprint。 |
| I5 | High | **接受** | 屬實且切中：GitHub `concurrency` 讓第二個 run 排隊，但 `actions/checkout` 預設取**觸發時的 SHA**，不是排隊結束時的分支 tip——第二個 run 會用到前一個 run 發布前的舊 baseline。v0.4 明定：取得發布權後須顯式 fetch 並 checkout 預設分支最新 tip；promotion 前再次驗證正式版本未變；不符即 fail-closed。並新增兩個真正重疊 run 的驗收情境。 |

## 3. 矛盾

| # | 嚴重度 | 判定 | 理由與處置 |
|---|---|---|---|
| X1 | High | **接受** | 屬實，A1 與 §6.2／A7 正面衝突：我把「僅大小寫或全半形不同」當成「不應合併」的反例，但 §6.2 的 NFKC+upper **正是會折疊**這些差異，依 A7 應該是 `IDENTITY_COLLISION`。**我方實測直接提供了正確的替代反例**——§6.2 明確不折疊的差異：連字號有無（`MK-3475-158` / `MK3475-158`）、空格有無（`9785-CL- 0123` / `9785-CL-0123`）、括號閉合（`ROR-PH-301(APD811-301` / `...301)`）。見 S1。 |
| X2 | High | **接受** | 見偏離 1(a)。 |
| X3 | Medium | **接受** | 屬實且細緻：上游若以相同資料重新打包，`sourceSha256` 會變而正規化資料不變，使「no normalized change」有兩種合法解讀。v0.4 明定 no-change 比較**排除 `sourceSha256`**（它是 provenance 不是資料），但每次抓取的 `sourceSha256` 記入 QA report 以保留追溯。 |
| X4 | Medium | **接受** | 屬實，**這是 v0.3 的實質錯誤**：C4 要求 mutation「分類轉 null」被 C1 殺死，但 §6.6／C1 本來就**規定** typed value 為 null——那個 mutation 是正確行為。照原樣寫下去，實作者只能破壞正確規則來讓測試失敗。v0.4 改為真正違規的 mutation：raw 值遺失、facet 保留 `"0"`、或 UI 顯示 `"0"`。 |
| X5 | Low | **接受** | 屬實：`trialId` 首字元固定為 `t` 不是 hex，「前 2 hex」講不通。v0.4 明定 shard key 為 `trialId` 第 2–3 字元（即雜湊的前 2 hex），並加邊界 oracle。 |

## 4. 驗收條件的可證偽性缺口

全部 36 項中 35 項**接受**，1 項（F3）**部分接受**。以下只記需要說明的：

| # | 嚴重度 | 判定 | 說明 |
|---|---|---|---|
| A2 | High | 接受 | fixture 未強制含四類日期異常，故 §6.5 的防禦規則目前**未被任何測試證實**。這正是偏離 3 被否決的第四個理由。 |
| A5 | High | 接受 | 最精準的一項：若 source fingerprint 與 record identity **共用同一個非一對一的 serialization**，兩邊會一致地漏列而通過——形成自我驗證。oracle 的 row identity 必須獨立且無歧義。 |
| C2 | High | 接受 | 切中一個我沒察覺的結構性錯誤：我的 C2 要求 fixture 含 empty 與 malformed 並斷言 expected parsed value，但 §6.6 **從未定義**這兩類的解析結果——於是**驗收條件反過來創造 normative 規則**，oracle 可任意制定。v0.4 先在正文定義 empty／malformed 數值的 typed value、warning 與顯示，再寫 oracle。 |
| C4 | High | 接受 | 同 X4。 |
| D3 | High | 接受 | 屬實：我 §8.3 定為 record 層 AND，但 D3 沒有「兩詞分別命中同一 Trial 的不同 SourceRecord 必須排除」的案例，Trial 層 AND 可冒充 record 層 AND 而大幅多報。 |
| B1 | High | 接受 | 屬實：commit／push／deploy 失敗不在 error code 集合與狀態斷言內。v0.4 把 promotion、repository publish、deployment activation 分層定義並各有狀態 oracle。 |
| F2 | High | 接受 | 屬實：單一 canary 可被特判移除，其餘長 criteria 仍塞進初始 bundle。改為多筆分散 canary + 斷言初始 payload schema 不含長欄位鍵。 |
| H2 | High | 接受 | 屬實：只驗 concurrency group 字串與連續兩跑，沒測真正重疊、排隊與 baseline 改變。與 I5 合併處理。 |
| F3 | Medium | **部分接受** | 「固定量測環境」屬實有必要，但對單人維護專案**釘住硬體不現實**。改為：以 **GitHub Actions runner 類別**為基準環境、固定 CPU throttle 倍率、固定樣本數與 **p95** 為判定門檻，並在規格明寫「跨時間比較僅在同 runner 類別內有效」。不假裝取得實驗室級可比性。 |
| A3 | Low | 接受 | 同意降為 Low 並加系統性 permutation／property invariant。 |
| D5／E1 | Low | 接受 | 同意：「中文同義詞」不是封閉集合，無法形成可證偽測試。改以封閉的 selector／schema invariant 為主 oracle，列舉禁字只作 mutation guard。 |
| 其他 | — | 接受 | A1、A4、A7、B2、B4、B5、B6、C1、D1、D2、D4、D6、E2–E5、E7、F1、G1–G4、H1、H3 全部接受，修法照採。 |

---

## 我方自行發現（不在 Codex 輸出中）

### S1｜High／`strip+NFKC+upper` 會把同一個試驗拆成兩個 Trial（18 組）

§6.2 刻意不剝標點、不壓內部空白。實測這個決定的代價是 **18 組 protocol 其實是同一個試驗的不同寫法**，將變成 36 個 Trial：

| 差異類型 | 實例 |
|---|---|
| 多一個空格 | `9785-CL- 0123` / `9785-CL-0123`；`219288 (B-Well 2)` / `219288(B-Well 2)` |
| 全形括號＋空格 | `LOXO-RET-17001 (J2G-OX-JZJA)` / `LOXO-RET-17001（J2G-OX-JZJA）` |
| 括號未閉合（打字錯誤） | `ROR-PH-301(APD811-301` / `ROR-PH-301(APD811-301)`；`ROR-PH-303(...` 同型 |
| 連字號有無 | `MK-3475-158` / `MK3475-158`；`CA209-9DW` / `CA2099DW`；`CA224-1093` / `CA2241093`；`CA239-0004` / `CA2390004`；`CA204-219` / `CA204219`；`SNR-04` / `SNR04`；`NHRI-FV-001` / `NHRIFV001`；`GS-US-563-5925` / `GS-US-5635925`；`ALXN2220-ATTR-CM-301` / `ALXN2220-ATTRCM-301` |
| 上游刪除標記前綴 | `BGB-16673-303` / **`刪_BGB-16673-303`** |

後果：藥師搜 `MK-3475-158` 會看到一張卡，但 `MK3475-158` 那筆的審查紀錄**不在裡面**——同一試驗的紀錄被無聲拆散。

處置：**維持不自動合併**（自動合併會誤配，違反「寧可漏報不可誤報」），但 v0.4 必須：

1. QA report 偵測並計數這類「正規化後近似」的 protocol 群組（以剝除非英數字後比對），列出全部 raw 值；
2. 詳情頁顯示「其他寫法近似的計畫書編號」提示與連結，讓藥師自行判斷，**不自動合併也不無聲漏掉**；
3. `刪_` 這類前綴另列 QA 警示——上游用它標記刪除，若不處理會出現一個叫「刪_…」的試驗。

這同時提供 X1 所需的正確反例：A1 的「不應合併」案例應改用這些 §6.2 不折疊的差異。

### S2｜Medium／protocol 欄位含上游測試資料與非編號值（9+ 列）

§6.3 只處理「protocol 為空」的 6 列，未處理「非空但不是 protocol number」：

- **上游測試列**：`系統測試`、`計畫書編號系統測試`、`計畫書編號123`、`計畫書編號A`（申請者 `CDE`、標題 `計畫書標題（名稱)test 收案到哪一個欄位中A`）、`臨床試驗計畫初版編號`（欄位標題洩漏進資料）
- **真實試驗但無編號**：`未列編號`（榮總，123I-IBZM 精神分裂症診斷）、`未列編號。第二版，97/10/3`（新光，肉毒桿菌治膝關節炎）、`科技部研究計畫(申請中)`（長庚）、`IRB編號：KMUHIRB-F(I)-20200122`（高醫）
- **欄位填錯**：`聯亞生技開發股份有限公司`（申請者名稱填進 protocol 欄）

後果：產生 identity key `"P:系統測試"`，成為可搜尋的「試驗」並進入統計分母；`?protocol=系統測試` 這種別名 URL 也不合理。

處置：v0.4 新增判定——protocol 值**不含任何英數字元**時標記 `protocolNonIdentifier`（實測 7 個不同值、9 列）。**不刪除資料**（刪資料是改寫上游），改為：UI 顯示「來源未提供計畫書編號」、不作為 `?protocol=` 別名、統計卡歸入「未提供編號」類別、QA report 完整列出。另把疑似上游測試列（申請者與標題皆空，或標題含 `test`）單獨計數警示，但同樣不自動刪除。

---

## 結論

**方向已穩定，但需要 v0.4，且 v0.4 仍有架構級變更。**

- 第一輪 Blocker 2 → 第二輪 **Blocker 0**，且第二輪無一項質疑四項定案決策或既有非目標邊界。剩餘問題全是「規格不夠精確」而非「方向錯誤」。
- 但 N8＋X2（發布契約改為內容雜湊檔名＋版本綁定）、N1（ID 契約）、N2／N3／I2（衝突與日期模型）、I1（逐檔 schema）都會改動 M1 的產物形狀，**不是純文件修訂**。

建議第三輪**限縮範圍**，只審這五類架構級變更（發布與快取契約、ID 契約、衝突判定集合與比較模式、日期模型、逐檔輸出 schema），不再重審全部驗收條件——驗收條件的精確度到某個程度後，寫 fixture 比再讀一遍 prose 更能找出問題。
