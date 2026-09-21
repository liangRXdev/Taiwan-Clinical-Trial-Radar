# PROGRESS

| 里程碑 | 狀態 |
|---|---|
| M0 規格修訂與覆審 | **完成**（三輪覆審 ＋ A 群 fixture 反驗，十項契約封存） |
| M0.5 B 群 fixture ＋ 最小 artifact 樣本 | 未開始 |
| M1 repo 鷹架與 ETL | 未開始 |
| M2 前端 MVP | 未開始 |
| M3 CI 與月更新 | 未開始 |
| M4 收尾 | 未開始 |

測試：A 群 fixture 已建立（50 列／29 Trial，self-check 全綠），測試本身未寫。程式碼：尚無。部署：尚無。

規格：`.ai-review/plan.md` **v0.5**，驗收編號 A1–H5，十項動工前契約見 §14。

---

## 2026-09-18 — 專案啟動、四項決策定案、dataset 205 實測

### 決策

| # | 決策 | 取代 |
|---|---|---|
| 1 | 只做 dataset 205，206–209 永久不納入 | spec §2 的 go/no-go gate、§7.3 relation 模型、`verify_linkage.py`、TFDA 詢問信全部取消 |
| 2 | 以 protocol number 收斂試驗單位，顯示最新版＋保留版本歷史 | spec §7.1／§7.2 的「一列一試驗」模型 |
| 3 | sentinel 依欄位型別分開處理（分類／數值／文字） | spec §6.6 的「`0` 不可自動視為 missing」一體適用寫法 |
| 4 | 部署 Cloudflare Pages | spec §9 的「GitHub Pages 或 Cloudflare Pages」未定案 |

決策 4 的理由：`liangrxdev.github.io` 由多個工具共用 origin，Cache Storage 不依 service worker scope 隔離，既有專案已踩過跨 repo 互刪快取。獨立 origin 從源頭避開。

### 實測 dataset 205（當日下載）

端點 `https://data.fda.gov.tw/data/opendata/export/205/csv` 回 `200`、`application/zip`、內含 `205_2.csv`。

| 項目 | 值 |
|---|---|
| ZIP／解壓後 | 42 MB／166,450,190 bytes |
| 編碼 | UTF-8 with BOM |
| 列數／欄數 | 18,736／16 |
| `資料更新時間` 範圍 | 2024/12/20 – 2026/08/17（525 個不同日期） |
| 卡片欄位 JSON（protocol 收斂後） | 3,652 KiB raw／**715 KiB gzip** |

欄位：`臨床試驗申請者`、`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`、`TFDA收文號`、`資料更新時間`。

### 推翻 spec 的三項發現

**1. 一列不是一個試驗。** 18,736 列只對應 5,882 個 protocol（另 6 列 protocol 為空）。2,821 個 protocol 有多列、最多 23 列，且這 2,821 組裡**只有 61 組**是 16 欄全同的純重複。差異欄位分布（按組數）：

```
資料更新時間        2,737
納入條件            1,927
排除條件            1,908
試驗目的              915
主要評估指標          848
試驗預計執行期間迄    683
全球預計受試者人數    418
台灣預計受試者人數    395
臨床試驗計畫中文名稱  347
試驗預計執行期間起    176
臨床試驗申請者        165
適應症中文            164
臨床試驗期別          102
本臨床試驗規模         78
TFDA收文號             73
```

所以一列 = 某一版試驗計畫書的審查紀錄。spec §7.1 的 canonical record 假設錯誤。

**2. spec §7.2 的 key order 在實際資料上不成立。** `TFDA收文號` 有 2,788 個重複鍵、266 筆空值、30 筆值為 `移案BPA`；`protocol + applicant` 仍有 2,885 個重複鍵。全欄位相同的完全重複列有 2,410 列。

**3. 分類欄位的 `"0"` 是 sentinel。** `臨床試驗期別` 8 個值裡有 156 筆 `"0"`（其餘 7 個為 `Phase Ⅰ`～`Ⅳ`、組合、`其他`）；`本臨床試驗規模` 4 個值裡有 266 筆 `"0"`。數值欄位另有 `全球預計受試者人數` 1,080 筆 `"0"`。文字欄位有字面 sentinel：`排除條件` `N/A` 469 筆／`NA` 67 筆、`納入條件` `NA` 42 筆、`主要評估指標` `NA` 61 筆。

### 另外確認

- **來源沒有 `執行狀態` 欄位**。官方資料集頁面有列，實際 16 欄沒有。`FEATURE_TRIAL_STATUS` 維持 `false`。
- **從 GitHub Actions 抓 `data.fda.gov.tw` 不需 proxy**。memory 記的「TFDA 回 500」只發生在 Google IP（Apps Script）；`TFDA-drug-shortage-dashboard` 的排程直打同一網域，2026-09-17 20:36 UTC 那次成功、耗時 25s。
- **單列最長文字 22,490 字元**（`納入條件`／`排除條件`），`試驗目的` 5,512、`主要評估指標` 5,166。長文字必須走按需載入 shard。
- 納入／排除條件混雜兩種文體：部分寫給研究人員（「經由試驗醫師…評估」），部分是直接寫給病人的第二人稱（「您必須符合下列所有情況」）。詳情頁用語與免責需考慮這點。

### 新發現的阻塞問題

**「取最新版」有 846 組平手。** 2,821 個多列 protocol 裡 30% 的最新 `資料更新時間` 相同，而日期只有日精度、無時間無版號。不可靠 CSV 列序決定。tie-break 規則待定案，見 `TODO.md` D1。

### 交付

`README.md`、`CLAUDE.md`、`TODO.md`、`PROGRESS.md`。commit `8a5d1c5`。

---

## 2026-09-18（同日，午後）— 第一輪規格覆審、規格重寫為 v0.3

### 平手組實測：原本的 tie-break 提案被自己的資料否決

早上留下的阻塞問題（846 組日期平手）實測後結論相反——**不該挑版本**：

| 情形 | 組數 | 佔比 |
|---|---:|---|
| 平手列 16 欄全同（選哪列都一樣） | 689 | 81% |
| 有實質衝突 | 157 | 2.7% of 5,882 個試驗 |

原提案「取非空欄位數最多者」在 846 組中**只唯一決出 5 組**，幾乎無效。

157 組衝突組的實測欄位分布：`納入條件` 74 組（另 12 組僅空白／全形差異）、`試驗預計執行期間迄` 48、`試驗目的` 40、`主要評估指標` 34、`全球預計受試者人數` 22、`台灣預計受試者人數` 21（實例 `19` vs `31`、`27` vs `30`、`0` vs `4`）、`臨床試驗計畫中文名稱` 20、`臨床試驗期別` 3（實例 `Phase Ⅱ` vs `Phase Ⅰ,Phase Ⅱ`、`Phase Ⅲ` vs `其他`）。

同 protocol、同日期、無任何欄位可判先後。任意挑一個顯示 = 把不確定包裝成確定，正好命中本專案排序最高的風險。

原本擔心的「刻意清空欄位表示取消」幾乎不存在（納入／排除條件只有 3 組有一側為空），該疑慮排除。

### 其他補充實測

- `資料更新時間` 18,736 筆**全部合法 `YYYY/MM/DD`**，零空值、零未來日期
- `試驗預計執行期間` 格式全合法，但 **7 列 end < start**
- 6 列空 protocol **彼此全不相同**（6 個不同簽章），hash 碰撞尚未顯現
- `strip + NFKC + upper` 對 5,882 個 protocol **零碰撞** → 可據此寫死 identity 規則
- 確認 NFKC 會把全形數字折成半形（`NFKC("１１３９０") == "11390"`），故「全形收文號」是等價而非誤命中

### Codex 第一輪覆審

codex-cli 0.153.4，read-only，thread `01a0b1cd`。原始輸出 `.ai-review/plan-review-r1.md`，判定 `.ai-review/plan-verdict-r1.md`。

| 判定 | 數量 |
|---|---:|
| 接受 | 51 |
| 部分接受 | 5 |
| 拒絕 | 0（範圍蔓延 0） |

嚴重度：Blocker 2、High 22、Medium 27、Low 5。

**零範圍蔓延**是本輪特點——Codex 未提加後端／DB／重啟 206–209／加 PWA，全部發現都在既有邊界內。噪音出現在嚴重度評估而非範圍，故 5 項部分接受都是嚴重度或修法的修正。

兩個 Blocker：

1. **單值 `latest` 不可成立**（與我方獨立實測收斂到同一結論）→ 改為 cohort + `latestAmbiguous` + `conflictFields` 模型
2. **不要發明 tie-break，直接保存不確定性** → Codex 的 cohort 方案比我的原提案好，照採

五項部分接受：

- **1.6 日期規則**：嚴重度 High → Medium（實測日期 100% 合法，問題未顯現），但補上 Codex 沒提到的 7 列 end<start
- **A6 空 protocol hash 碰撞**：High → Medium（實測 6 列全異），fixture 要求照採
- **2.1 多檔原子發布**：問題屬實但修法過重。Codex 提議建 snapshot 目錄 + manifest 指標切換；改為**把 promotion 邊界定義為 git commit**——Cloudflare Pages 部署的是一個 commit，本來就是原子的，少一層元件
- **B5**：依 2.1 調整失敗注入點
- **4.4 首版不做圖表**：驗收改條件式接受，但「做不做圖表」是產品決策不由審查代決，留給 M2 依量測決定

**11 項是 v0.2 修訂自己造出來的洞**（1.4、1.7、2.1、2.2、D2 的錯誤舉例、D4 的矛盾案例、E3 的弱斷言、E5 的漏帶、F3 的錯數字、4.4 的範圍膨脹等）。與過往「第一輪修訂自造 4 個洞」的模式一致，證明第二輪只審修訂本身是必要的。

Codex 另抓到我漏掉的一項：v0.1 有**六處**條文（§3.1／§5.1／§8／§9／§14／§18）仍在要求已取消的 206–209 關聯與 `verify_linkage.py`，而我 v0.2 的失效清單只列了六節，不完整。

### 規格重寫

產出 `.ai-review/plan.md` **v0.3，單一 normative 規格**；v0.1 與 v0.2 降為歷史文件、不再具規範效力。新增或改寫：identity／search 正規化分離、canonical serialization 與 ID 規則、ID 穩定性界限、各功能資料層對照表、歷史命中標示、日期規則、URL 契約、輸出契約、error code 表、驟降公式與邊界、併發語意、`builtAt` 語意、移除 `FEATURE_TRIAL_STATUS`、不做方向性 diff、免責補「試驗使用不代表上市核准」。驗收條件全面改寫堵死弱化實作，新增 A7／B6／D6／E7。

### 下一步

**第二輪 `/codex-checkplan`，只審 v0.2 → v0.3 的變更。** 未通過前不寫實作程式碼。

---

## 2026-09-18（同日，傍晚）— 第二輪覆審、規格改寫為 v0.4

### 覆審結果

codex-cli 0.153.4，read-only，thread `01a0b1f3`，範圍限定 v0.2 → v0.3 的修訂。

| 判定 | 數量 |
|---|---:|
| 接受 | 53 |
| 部分接受 | 1（F3 量測環境） |
| 拒絕 | 0（範圍蔓延 0） |
| 我方自行發現 | 3（S1、S2 與搜尋預算矛盾） |

嚴重度：**Blocker 0**、High 17、Medium 27、Low 10。Codex 主動標「無缺口」5 項（A6、B3、C3、E6、H4）。

**第一輪 Blocker 2 → 第二輪 0**，且無一項質疑四項定案決策或既有非目標邊界。方向已穩定，剩餘全是精確度不足。

### 我三項偏離被否決

第一輪我判定「部分接受」而改了 Codex 修法的五項，第二輪逐項覆核結果是 **2 維持、3 否決**：

**1. 「git commit 即原子發布邊界」——否決，我錯了。** 推論只對一半：

- commit 對 repo tree 確實原子，但**不回復 working tree**。我寫的「任一階段失敗 → working tree 正式資料整體等於舊版」做不到（替換第一個檔案後崩潰就是混合狀態）。保證本來就下在錯的邊界——CI runner 的 working tree 用後即棄、無讀者，要保證的是「不存在部分發布的 commit」。
- **更嚴重的是我完全漏掉的一點**：所有 artifact 用固定 URL，瀏覽器或 CDN 快取會讓一次 session 混用舊 manifest 與新 shard → dangling reference 或顯示錯紀錄。對臨床工具是直接誤導。
- 修法（仍不需 snapshot 目錄）：`manifest.json` 為唯一固定 URL（`no-cache`），其餘全部檔名帶內容雜湊（`immutable`）；每檔 top-level 帶 `datasetVersion`，前端斷言等於 manifest 值，不符即 fail-closed。

**2. B5 四個失敗注入點——否決。** 四點全避開了最危險的窗口（部分替換、刪 orphan 途中、git index 只含部分變更、commit／push／部署失敗、非例外式終止）。現況可以讓非原子的逐檔替換實作通過，正是我想堵的那種弱化實作。

**3. 日期規則降 Medium——否決，回復 High。** 我的理由是「實測日期全乾淨」，但這是每月重跑的 ingestion contract，現況乾淨只降低當下發生率。且 Codex 指出兩個我自己造的洞：`latestAmbiguous` 在「全日期不可解析」時與 §6.4 的定義矛盾；「未來日期排除於全站 sourceUpdatedAt 但仍參與 trial 內排序」等於**讓單筆打錯的 2099/01/01 永久支配該試驗的卡片**。兩者都改資料模型，是 High。

維持的兩項：A6 降 Medium（成立）、圖表由產品決策而非審查決定（成立）。

### 我方自行實測發現的三項（Codex 沒有資料可量）

**1. 搜尋範圍與 payload 預算是硬矛盾。** v0.3 同時要求「搜尋涵蓋全部歷史紀錄」「7 個可搜尋欄位」「初始 payload ≤1.5 MB gzip」，實測：

| 索引範圍 | gzip |
|---|---:|
| 最新 cohort × 5 短欄 | **601 KiB** |
| 全部紀錄 × 5 短欄 | 1,649 KiB |
| 最新 cohort × 2 長欄 | 2,044 KiB |
| 最新 cohort × 7 欄 | 2,607 KiB |
| 全部紀錄 × 2 長欄 | 5,389 KiB |
| **全部紀錄 × 7 欄（v0.3 現行）** | **6,958 KiB** |

v0.3 的規定是預算的 4.6 倍。**決策：搜尋分層，預設 `fields=short` + `history=latest`（約 715–900 KiB），擴大控制項須在結果區可見並顯示下載大小。** 預設縮小若不可見就是靜默漏報。

**2. S1：`strip+NFKC+upper` 會把同一試驗拆成兩個（18 組）。** `MK-3475-158` / `MK3475-158`、`9785-CL- 0123` / `9785-CL-0123`、`LOXO-RET-17001 (J2G-OX-JZJA)` / `LOXO-RET-17001（J2G-OX-JZJA）`、`ROR-PH-301(APD811-301` / `...301)`、`刪_BGB-16673-303` / `BGB-16673-303` 等。維持不自動合併（合併會誤配），但新增 `nearDuplicateGroup`（loose key **只用於偵測絕不用於收斂**）在 QA report 與詳情頁揭露。這同時提供 Codex X1 所需的正確反例。

**3. S2：protocol 欄位含上游測試資料與非編號值（9 列）。** `系統測試`、`計畫書編號系統測試`、`臨床試驗計畫初版編號`（欄位標題洩漏）、`計畫書編號A`（申請者 `CDE`、標題含 `test`）、`未列編號`、`無`、`科技部研究計畫(申請中)`、`聯亞生技開發股份有限公司`（申請者填錯欄）。新增 `protocolNonIdentifier` 標記，不刪資料但不作為 `?protocol=` 別名、統計歸入「未提供編號」。

### 其他補充實測

- **U+001F 不存在於資料中**（控制字元只有 CR/LF/TAB；58,140 欄含換行、10,725 欄含 TAB）→ canonical serialization 改用**長度前綴**確保一對一，並保留 `SOURCE_CONTROL_CHAR` 主動檢查
- **16-hex 截短 0 碰撞**（16,328 個不同紀錄）→ 仍須三層碰撞偵測
- **衝突比較模式**：raw 比較 157 組 ambiguous vs NFKC+空白正規化 143 組，差 14 組 → 選正規化比較（那 14 組只差空白，標「不一致」是假警報）

### v0.4 主要變更

§9.2 發布契約重寫（三小節）；§6.3 長度前綴 + 三層碰撞偵測 + shard key 更正；§6.4 封閉 13 欄呈現欄位集合 + 衝突比較模式；§6.5 `dateUnknown` 獨立旗標 + 未來日期排除於 latest；§6.6 補完數值解析（原本驗收條件反過來創造規則）；§8.2 matching operator；§8.4 值域與組合語意；§8.5 搜尋分層；§7.4 完整 URL state schema；§9.3 逐檔 schema + 整體 digest 定義；§9.4 排除 `sourceSha256`；§9.5 移除無法客觀判定的 `SCHEMA_COLUMN_RENAMED` + precedence；§9.6 warning 落在結構化 artifact；§9.7 baseline 取樣時點；C4 三個 mutation 全部改為真正違規。新增驗收 A8、A9、B7、D7、E8、F2。

### 下一步

**第三輪 `/codex-checkplan`，限縮範圍**：只審 §6.3、§6.4、§6.5、§8.5、§9.2、§9.3 這些架構級變更，不再重審全部驗收條件。

---

## 2026-09-18（同日，夜）— 先寫 A 群 fixture 反驗規格

選擇先寫 fixture 而非直接跑第三輪覆審，用意是：**寫不出來的驗收條件，就是規格的洞**。結果證實這個方向有效——找到 7 個洞，其中 3 個 High，且有 1 條驗收條件**根本無法滿足**。

### 產出

| 目錄 | 對應驗收 | 列數 |
|---|---|---:|
| `tests/fixtures/a_core/` | A1–A6、A9（兼 C1–C3 資料面） | 50 列／29 Trial |
| `tests/fixtures/a7_identity_collision/` | A7 | 5 列 |

`check_a_core.py` 全部通過（exit 0）。**尚無 ETL 實作程式碼**——`build_*.py` 只把字面值寫成 CSV，`check_*.py` 只檢查 fixture 資料本身的性質。

A2 的 12 類必含案例全部到位，含 11 列的 `BIG-001`、純重複 `DUP-002`、空白差異 `WS-003`、兩筆完全相同的空 protocol、3 組 `nearDuplicateGroup`、四類日期異常，以及 `DT-018`／`DT-019` 這組專門驗「`dateUnknown` 與 `latestAmbiguous` 互相獨立」的案例。

### 7 個規格洞

| # | 嚴重度 | 問題 |
|---|---|---|
| GAP-1 | High | §6.4 的 `displayFields` 在「正規化後相同、raw 不同」時無定義。`WS-003` 兩列同日、只差空白與全半形括號 → 不衝突 → 該欄位要進 `displayFields`，但**沒有共同 raw 值**可取。實測母體 14 組屬此類，不是邊緣情形 |
| GAP-3 | High | `displayFields` 存 raw、typed 還是三元組未定義。分類 sentinel 的 raw 是 `"0"`、typed 是 `null`、UI 要顯示「未提供」——三者不同，而 §9.3 沒說前端從哪取 typed，結果前端得**重做一次** sentinel 判定 |
| GAP-6 | High | **A8 無法以凍結 fixture 滿足。** 找出 SHA-256 的 64 位元截短碰撞需約 `2^32` 次雜湊。照原文寫下去，實作者只會跳過它或偽造假案例，碰撞偵測分支永遠沒有測試守著 |
| GAP-2 | Medium | 單一空 protocol 列是否帶 `#0` 後綴未定義 → 未來出現一筆相同內容的新列時，原本的 `H:x` 會變成 `H:x#0`，URL 失效 |
| GAP-4 | Medium | 空 protocol 算不算 `protocolNonIdentifier`。本 fixture 的計數是 5 還是 2 取決於此 |
| GAP-5 | Medium | 衝突比較套用於數值欄位會產生假警報。`NUM-022` 兩列同日、`全球預計受試者人數` 為 `""` vs `"-5"`，兩者 typed 皆 `null`（都是未提供），raw 不同卻判為衝突 → 欄位被抽掉、顯示「不一致」。而 §6.4 引入正規化比較的目的**正是**要避免假警報 |
| GAP-7 | Medium | 「不晚於 build 當日」與凍結 fixture 相牴觸。已在 oracle 注入固定 `buildDate` 迴避，但「剛好晚一天」的邊界因此無法測 |

### 兩個方法論收穫

**1. oracle 的計數要數「全部列」，不是「為該案例設計的列」。** 初版 oracle 我把 `排除條件="N/A"` 寫成 1 筆、`numericMissing` 寫成 2 筆——只數了刻意設計的列，漏掉其他列的附帶出現（實際 3 筆與 5 筆）。`check_a_core.py` 一跑就抓到三項。若沒有這支自檢，這些錯會等到實作寫完測試轉紅才發現，而那時第一反應會是「實作錯了」而非「oracle 錯了」。

**2. 宣稱一個規格洞之前，要先讓資料真的觸發它。** 最初寫下 GAP-5 時 fixture 裡沒有任何一組能觸發，self-check 直接印出「未被觸發，需補一組…」。補了 `NUM-022` 才讓它成為可證明的發現——沒補的話那只是看規格推想出來的擔憂。

### 下一步

7 個洞全部落在 M1 前須封存的範圍（§6.3／§6.4／§6.5／§6.6／§9.3／§11 A8），與第二輪要求第三輪限縮審查的範圍**完全重疊**。故建議**併入第三輪一起送審**，不要分兩次——GAP-1／GAP-3／GAP-5 都在動 `displayFields` 的形狀與衝突判定規則，分兩次會讓 §6.4 被改兩輪，重演「修訂自造新洞」。

---

## 2026-09-18（同日，深夜）— 第三輪限縮覆審、規格定案為 v0.5、十項契約封存

### 覆審結果

codex-cli 0.153.4，read-only，thread `01a0b224`。範圍限縮為 §6.2–§6.6／§8.5／§9.2／§9.3 ＋ fixture 的 7 個洞，明確排除已審過的其餘章節與驗收條件。

| 判定 | 數量 |
|---|---:|
| 接受 | 12 |
| **我的建議不成立** | **1（GAP-5）** |
| 拒絕 Codex | 0 |

7 個洞：**6 成立、1 不成立**；另在限縮範圍內找到 **1 Blocker、3 High、4 Medium**。Codex 在 §8.5 與 §6.4 明確寫「無」，沒有湊數。

三輪的 Blocker 走勢：**2 → 0 → 1**。

### 那個 Blocker 是我自己造的

**`datasetVersion` 與整體 digest 循環定義。** v0.4 §9.2.2 要求每個非 manifest 檔案的 top-level 內含 `datasetVersion`；§9.3 又定義 `datasetVersion` = 這些檔案**最終位元組** digest 的前 16 hex。檔案位元組包含 `datasetVersion` → 循環，一般情況無固定點，**照文字寫不出合規 artifact**。

這是我在 v0.4 修 N8（瀏覽器跨版本混用）時新造的。v0.5 §9.3.2 分離為兩個概念：`datasetVersion` 由**不含版本欄位本身的 logical payload** 計算；`artifactDigest` 待版本寫入最終檔案後對**最終位元組**計算。另封存 hash 演算法與長度、串接形式（hex 字串 ＋ 邏輯檔名）、是否納入路徑。新增驗收 B8 專門證明無循環。

### GAP-5 我錯了

我提議「數值與分類欄位改比 typed value，兩者皆 `null` 即不衝突」。Codex 指出這**過度收斂**：`""` 是正常的 `numericMissing`（UI 顯示「未提供」），`"-5"` 是 `numericImplausible` warning（須顯示 raw 與異常提示）——typed 皆 `null` 但語意不同。判為不衝突並任取一筆 raw 會**隱藏異常**，或把正常缺值呈現成負數 warning。

我為了消除假警報，反而造了一種更糟的誤導。改採 Codex 的 **semantic comparison key**（依欄位型別與語意狀態定義比較鍵），`""` vs `"-5"` **維持衝突**。

### 其他被指出而我沒想到的

- **GAP-2 只修了一半**：我寫了 identity key 的 `#0`，漏了 `recordId` 的 duplicate ordinal——同一個問題。
- **GAP-3 的關鍵補充**：衝突欄位在 `displayFields` 中要**完全省略**，不是給 `{typed:null}`——後者會與「未提供」混淆，而混淆正是本專案最怕的誤導。
- **GAP-7 的 production 語意**：`buildDate` 須以 **`Asia/Taipei`** 日曆日產生，不得用 runner 的 UTC 日期——runner 是 UTC，台灣時間 08:00 前 UTC 還是前一天，「未來日期」判定會差一天。新增驗收 H5。
- **「英數字元」沒有字元集合**。實測確認問題比描述更嚴重：Python 的 `"系統測試".isalnum()` 回傳 **`True`**（中文被視為字母）。naive 實作下 `系統測試` **不會**被標記為 `protocolNonIdentifier`，與 §6.2.2 意圖完全相反。我的 fixture self-check 恰好用了 ASCII regex 才沒踩到。新增 §6.0 的字元集定義與驗收 A10。

### 我方實測的兩項（Codex 無資料可量）

**S3：F1 的預算是我用錯誤估計值訂的。**

| 方案 | trials-index gzip |
|---|---:|
| v0.4 現行（`recordIds` 在 index 內） | 1,535 KiB |
| **方案 B**（`recordIds`／`latestCohort` 移入 shard） | **1,236 KiB** |
| 再把搜尋文字拆獨立檔 | 903 + 693 = **1,596 KiB** |

原基線「715–900 KiB」量的是「5,888 trial × 10 個扁平卡片欄位」，沒算 `recordIds`、`conflictFields`、`protocolRaw`、旗標與 `searchShortLatest`。卡片資料本身就 903 KiB。**而拆檔會變大不會變小**——失去跨欄位的壓縮共享。**使用者定案：採方案 B，F1 改 ≤1.5 MB。**

**S4：`numericUnparsed` 是個不同質的垃圾桶，而它決定 `enroll` 篩選。**

`台灣預計受試者人數` 的組成：純整數 16,858／**範圍 1,340**／約略 159／其他 179／`NA` 23／千分位與界限 4／空 173。依 v0.4，非純整數全部 → typed `null` ＋「數值格式未辨識」。但 **`20-40` 不是格式未辨識，是一個區間**——藥師篩「11–30 人」時看不到它，漏掉 7.2%。

**使用者定案：只解析嚴格範圍。** `^\d+\s*[-~～〜–—]|至\s*\d+$` 且 `min ≤ max` → `{min,max}` ＋ `numericRange`，`enroll` 以區間重疊判定，卡片顯示 raw 原文。`約400` → 400 會丟掉「約」，屬推論，維持 `numericUnparsed`。實測回收：台灣 **1,347／1,705**、全球 **356／766**，且 **0 筆 min>max**。

另抓到第三批上游測試資料：兩個數值欄位**各有 9 筆 `TEST`**，已併入 §6.2.2 的疑似測試列判定。

### v0.5 定案

十項動工前契約封存於 `plan.md` §14。新增驗收 A10、B8、B9、C5、C6、D8、H5。fixture oracle 的 7 個 `__SPEC_GAP__` 全部結案，self-check 仍全綠。

### 下一步：M0.5，不跑第四輪

A 群的經驗是「寫 fixture 比再讀一遍 prose 更能找出問題」。十項契約已封存，接下來要**證明它們可實作**：

1. 補 A 群缺的 v0.5 新案例（空白-only protocol、`buildDate` 兩個邊界、`numericRange` 各型、`TEST` 值型）
2. `check_a_core.py` 的分類改用 semantic comparison key
3. **產出最小 artifact 樣本**（manifest ＋ trials-index ＋ 一個 shard），實證 §9.3.2 的 digest 計算無循環（驗收 B8）
4. B 群 fixture：每個 error code 的注入、每條不變量的反例、promotion 各失敗點

---

## 2026-09-18（同日，下午）— M0.5 前半：A 群補案例 ＋ 最小 artifact 樣本

不跑第四輪 prose 覆審，改用「把 v0.5 新增的契約真的做出來」驗規格。兩件事：把 A2 要求
但尚未存在的案例補進 fixture，以及照 §9.3.2 的文字產出一份合規 artifact。

### 產出

| 項目 | 前 | 後 |
|---|---:|---:|
| `a_core` 列數 | 50 | **73** |
| `a_core` Trial 數 | 29 | **45** |
| `check_a_core.py` 斷言 | v0.4 規則 | v0.5（semantic comparison key ＋ 完整數值文法） |
| artifact 樣本 | 無 | **7 個非 manifest 檔 ＋ manifest.json，B8 四條全綠** |

新增案例：空白-only protocol（ASCII 空白 ×3、U+3000 各一）、`buildDate` 當日與 +1 日邊界、
嚴格範圍（`至`／`-` 各一）、`min > max`、超界（2^53）、前導零 `026`、約略值 `約400`／`至少480`、
`TEST` 值型、期間起不可解析、期間迄缺值、C5 的四個比較鍵型別案例。

### 又抓到 3 個規格洞（1 High、2 Medium）

| # | 嚴重度 | 章節 | 一句話 |
|---|---|---|---|
| GAP-8 | **High** | §6.4.2 | 比較鍵表漏了三個語意狀態 |
| GAP-9 | Medium | §6.6.3 | 「可表示範圍」沒有序位，與「第一個命中者決定結果」字面矛盾 |
| GAP-10 | Medium | §9.3.5／F1 | `stats.json` 的 facet 名單未封閉，且它在 Tier 0 卻沒計入 F1 基線 |

**GAP-8 是本輪最值得記的。** §6.4.2 是 v0.5 才新增、且是三項封存契約之一，表格看起來很完整
（10 列型別／語意狀態），但對照 §9.3.3 的 field-scoped 旗標封閉集合就會發現少了
`numericRangeInvalid`、`numericOutOfRange`、`categoricalUnknown` 三個。**兩份清單都在同一份規格裡，
只是沒有人對過。** 三輪 Codex 覆審也沒抓到——prose 審查不會去對兩張表的差集，寫 fixture 會。

後果不是理論的：同日兩列皆為 `40-20` 與 `50-30`（都是順序異常）時，衝突與否無法從規格導出。
比 typed（皆 null）→ 判不衝突並任取一筆，正是第三輪否決 GAP-5 建議的理由（隱藏異常）；
比 `conflictText(raw)` → 判衝突。兩種都能自圓其說，而 C5 的「逐型別驗證」因此只寫得出 4 個型別。

fixture 為此各加一組同日兩列（`CMP-035`／`CMP-036`／`CMP-037`），oracle 的 `latestAmbiguous`
與 `conflictFields` 填 `__SPEC_GAP__`，`check_a_core.py` 的 `[8]` 段獨立列出並斷言
「未定義狀態集合恰為這三個」。**規格補上後這條會轉紅，那是預期的。**

### B8 的關鍵那條

B8 要求「同一輸入兩次 build 得到相同 `datasetVersion`（證明無循環定義）」。兩次相同只證明
決定性，證不到無循環——所以另加一條 **B8-1b**：

> 從**已寫入 `datasetVersion` 的最終檔案**移除 top-level `datasetVersion` 後重算，
> 必須得到同一個 `datasetVersion`。

這才是固定點存在的操作型證據。v0.4 的寫法連一份合規 artifact 都產不出來；v0.5 產得出來且自我一致。

B8-3（兩個檔案內容互換 → digest 改變）也補了反向哨兵：**斷言互換前後的 payload hash 多重集合相同**。
沒有這條的話，「互換後 digest 改變」也可能只是因為兩個檔案內容本來就不同，證不到
「§9.3.2 步驟 3 的邏輯檔名真的有作用」。

### 計數紀律再一次應驗

`periodEndMissing` 的正確答案是 `["nonid-test", "pd031-missing"]`，不是只有為該案例設計的
`pd031-missing`——`nonid-test`（上游測試列）的期間兩端本來就都是空的。這與第一輪把
`排除條件="N/A"` 寫成 1 筆（實際 3 筆）是同一種錯。

處置：`numericStateCounts` 改為**八類互斥且加總必須等於 `列數 × 2` = 146** 的形式。
漏數一筆會直接讓總和對不上而失敗，不會悄悄少一筆。

### 樣本不是實作

`artifact_sample/build_sample.py` 沒有 identity 收斂、cohort 判定或 sentinel 分型；
兩個 Trial（`WS-003`／`PH-004`）的模型內容是手寫的。只有 canonical serialization、
`trialId`／`recordId`、`datasetVersion`、`artifactDigest` 是照規格算的，因為那正是 B8 要證明
可實作的部分。**M1 不得沿用它當實作**——規格要能被兩份獨立的程式碼各自寫出來才算寫清楚。

### 下一步（於同日後半完成，見下節）

B 群 fixture、§9.3.6 不變量反例、C4 mutation。

### 同日續：M0.5 後半，B 群 fixture ＋ 不變量反例 ＋ C4 mutation

M0.5 四項全部完成。`tests/fixtures/run_all.py`：**240 條斷言全綠**（其後 v0.6 收斂為 244 條）。

| 自檢 | 斷言數 |
|---|---:|
| A 群（資料模型與收斂） | 85 |
| B 群（§9.5 失敗分類注入） | 57 |
| B8（`datasetVersion`／`artifactDigest`） | 55 |
| B6（§9.3.6 不變量反例） | 24 |
| C4（sentinel 的三個 mutation） | 19 |

artifact 樣本由 2 個 Trial 長到 **8 個**，每一個都有職責，不是為了「多一點資料」：
`IND-005` 與 `NR-028` 進來是因為它們的 `trialId` 恰好同屬 shard `c4`——
B6 的「record 被兩個 Trial 引用」若跨 shard 就會連帶違反 shard 歸屬而**無法隔離**。
`未列編號` 帶兩個分類 `"0"` sentinel、`TXT-021A/B/C` 帶三型文字 sentinel，是 C1／C3／C4 的注入點。

### 又抓到 2 個洞

**GAP-11（Medium）§9.3.6 的不變量之間有依賴，但沒有評估順序。**
寫「record 放錯 shard」的反例時，實際違規集合是 `['I2','I4']` 而不是預期的 `['I4']`——
`recordIds` 的排序鍵是該 record 的 `資料更新時間`，而那筆資料在 shard 裡；record 放錯 shard 時
排序鍵根本取不到，驗證器只能當成「無日期→置末」而誤報排序違規。

**這不只是實作細節。** B6 明文要求「每一條不變量各有**獨立**反例」。若某缺陷必然連帶觸發另一條，
**只實作其中一條檢查的驗證器也會通過測試**——驗收就是假的。要讓反例真的獨立，
驗證器必須先評估 referential integrity、再對通過的 Trial 評估排序。那是規格該指定的事。

**GAP-12（Low）§9.6 的「以有理數比較」測不出違反。**
掃過 `prev ∈ [3, 20000]`（本資料集 18,736 列）在兩個門檻鄰域的全部 `cur`，
float 與有理數的判定**沒有任何一組相異**。真正守得住的是「不四捨五入」：
`drop = 0.2001` 時四捨五入到兩位會得 0.20 而**照樣發布**——上游掉了 20.01% 的資料卻沒有硬失敗。
建議把規格文字改成「不得先四捨五入或截斷到固定小數位再比較」。

**這兩個洞是新的形狀。** GAP-1～GAP-10 都是「規格沒寫到某個狀態」；
GAP-11／12 是**驗收條件本身不成立**——一條要求「獨立反例」但結構上做不到，
一條要求了一件測不出違反的事。這兩種只有在真的去寫那個反例時才會現形，讀 prose 讀不出來。

### 兩個方法論收穫

**1. 注入點要在算 digest 之前。** 真實威脅是「有 bug 的 ETL 產出內部自洽但違反不變量的 artifact」，
它會把自己算出來的 digest 一併寫進去。若改完最終位元組就放著不重算，測到的只是 digest 本身，
referential integrity 那幾條**永遠不會被執行到**。`check_b6.py` 每個反例另斷言 `I10`／`I11`
**未**觸發，證明測到的是不變量。

**2. 反例要斷言「違規集合 exactly equals 預期」，不是「包含」。**
用「包含」的話，一個把所有檢查都回報違規的驗證器會全過。GAP-11 就是被 exactly-equals 逼出來的。

另外補了一條證明：**孤兒檔不會改變 `artifactDigest`**（§9.3.2 只走 `manifest.files` 的路徑），
所以 inventory 不變量無可取代——沒有它，`public/data/` 裡多一個沒人引用的檔案是完全靜默的。

### 順手修掉的既有缺陷

`core.autocrlf=true` 把凍結 CSV 的 CRLF 存成 LF，Linux CI checkout 出來會變 LF——
**「凍結」的行尾其實沒被凍結**。加 `.gitattributes` 把 fixture 與 artifact 樣本標為 `-text`，
已驗證 index 與工作區位元組數相同（16,517）。這個缺陷從 A 群 fixture 建立時就存在。

### 下一步

1. **GAP-8～GAP-12 併成 v0.6**，跑一輪**只審這五項與其修訂**的 `/codex-checkplan`。
   GAP-8 的修訂會使 `check_a_core.py` 的 `[8]` 段轉紅，那是預期的。
2. 覆審判定後進 **M1**（repo 鷹架與 ETL）。

---

## 2026-09-18（同日）— 規格改寫為 v0.6，13 項契約

依 M0.5 的 GAP-8～GAP-12 改寫。**這五個洞不是讀 prose 讀出來的，是把 v0.5 的契約真的做出來時撞到的。**

| 章節 | 變更 |
|---|---|
| §6.4.2 | 補三列比較鍵（`numericRangeInvalid`／`numericOutOfRange`／`categoricalUnknown`），皆採 `(旗標名, conflictText(raw))`；要求**窮盡 dispatch**，遇表外狀態硬失敗不 fallback |
| §6.6.3 | 拆為兩階段；明定單端超界時**整個** typed 為 `null`（不留 `{min:1, max:null}`，半個區間無法參與 §8.4 的重疊判定） |
| §9.3.5 | facet 名單封閉為三個（`phase`／`scale`／`applicant`），逐一寫出排除理由；新增「stats 與 index 的計數一致性」不變量 |
| §9.3.6 | 改為**有序的 7 條** ＋「無法評估」處置 |
| §9.6 | 「以有理數比較」→「不得先四捨五入或截斷到固定小數位再比較」 |
| F1 | 補 Tier 0 的封閉檔案清單；註明 `stats.json` 從未量測，**補量前不得調整門檻** |

契約由 10 項增為 **13 項**（§14 新增 #11 比較鍵窮盡性、#12 不變量評估順序、#13 facet 名單封閉）。

### fixture 同步收斂

`CMP-035`／`CMP-036`／`CMP-037` 依新規則由 `__SPEC_GAP__` **改判為衝突**；
`check_a_core.py` 的 `[8]` 段從「列出未定義狀態」改為**驗證 dispatch 的窮盡性**：
§9.3.3 旗標封閉集合的 13 個狀態全部取得比較鍵，且注入一個表外狀態時**必須 raise**。
`run_all.py` **244 條斷言全綠**。

### 下一步

跑一輪**只審 GAP-8～GAP-12 與其修訂**的 `/codex-checkplan`。
依既往規律，**修訂本身會製造新洞**——第一輪 56 項裡 11 項、第二輪 54 項裡一批、
第三輪的 Blocker 都是前一版修訂自造的。判定後進 M1。

---

## 2026-09-18（同日）— 第四輪限縮覆審，規格定案 v0.7

只審 v0.5 → v0.6 的修訂本身。**Blocker 0**，但 11 項發現**全部是 v0.6 修訂自己造的**，沒有一項是 v0.5 遺留。

| 判定 | 數 |
|---|---:|
| 接受 | 9 |
| 部分接受 | 2（F1 口徑採使用者定案方向，非 Codex 偏好） |
| 拒絕 | 0（範圍蔓延 0） |

**四輪的 Blocker 走勢：2 → 0 → 1 → 0。**

### 形狀：為了關掉一個洞而引入的新概念，本身沒被定義清楚

v0.6 的四個修訂，四個新洞，一一對應：

| v0.6 修了什麼 | 造出什麼新洞 |
|---|---|
| 為關 GAP-8，宣稱「比較鍵表涵蓋旗標封閉集合」 | **旗標不互斥**。`numericRange + numericOutOfRange` 是複合、`sourceZero` 是附加——那個等號本身是錯的 |
| 為關 GAP-11，引入全域七步評估順序 | **過度阻斷**。一個 shard 錯誤會遮蔽同時存在的 stats 或 digest 錯誤，而那兩條根本不依賴 record 歸屬 |
| 為關 GAP-10，把 facet 名單綁成 E2 唯一 oracle | **同一節內自相矛盾**。§9.3.5 才剛寫「`updated` 改以 `sourceUpdatedAt` 單一數字呈現」，照 E2 字面那張合法的卡必須使測試失敗 |
| 為關 GAP-10 的另一半，補 Tier 0 檔案清單 | **與既有定義衝突**。F1 同時是「全部 network responses」與「三個資料檔」，無法唯一判定 |

### 最高風險那一條：C5／1.1

弱化實作可以**分別**正確處理「合法 range」與「scalar 超界」，卻處理不了**複合**的超界 range；
而 v0.6 的 C5（逐表列正例 ＋ atomic flag exhaustiveness）**會讓它通過**。
那會讓同日的超界區間任取 raw、錯判不衝突，**重新打開 v0.6 原本要關閉的誤導路徑**。

v0.7 把比較鍵改建在**封閉的 `(typed, flags)` 組合表**（15 列）上，並加兩組 fixture 釘住：
`CMP-038`（兩個 raw 不同的超界區間 → 衝突）與 `CMP-039`（NFKC 後等價 → 不衝突 ＋ `rawVariants`）。
**兩組一起才釘得住**——fallback 成「視為相等」時 CMP-038 漏判，fallback 成「比 raw 字面」時 CMP-039 誤判。

### B4：我的案例集殺不死 3／4 位小數

Codex 指出 `0.1001`／`0.2001` 只殺得死四捨五入到 2 位。**我方實測驗證後比它講的更嚴重**：

| prev | cur | 精確 drop | 正確判定 | round 2／3／4 |
|---:|---:|---:|---|---|
| 18736 | 16862 | 0.10002135 | publish + warning | 0.1 → **warning 消失** |
| 18736 | 14988 | 0.20004270 | **hard-fail** | 0.2 → **照樣發布** |

這兩個 `cur` 恰好是真實基線下兩個門檻「**最接近且嚴格超過**」的整數，四捨五入到 4 位仍漏判，要 6 位才抓得到。
v0.7 B4 改為每個門檻各要「正下、正好、最接近且嚴格超過」三種位置。

### F1 口徑：使用者定案「全部 network responses」

Codex 偏好「只量資料層」（與現有 1,236 KiB 基線相容、M1 就量得出來）。**使用者選了另一邊**：
1.5 MB 量的是使用者真正付的冷啟動成本，三個資料檔降為**須恰好相等的子集合斷言**。

代價已寫進規格：資料層已佔 1,236 KiB，只剩約 **264 KiB** 給 `stats.json` 加整個前端 bundle，
M1／M2 一量很可能超標。但規格也已寫「超標先報瓶頸歸因，不調鬆數字」——
**「量了一個不是使用者成本的數字然後宣告合格」才是會誤導自己的那種錯。**

### 順手修掉自己的一個 bug

改 B6 編號時把 `latestCohort ⊆ recordIds` 與 stats 一致性撞在同一個 `I6`。
**兩條不同的不變量共用編號，B6 的「各自獨立反例」就驗不到其中一條。**
已改為對齊 §9.3.6 的 I1–I7 加子編號（`I3.shard`／`I3.owner`／`I3.orphan`／`I3.subset` 等），
並加「mutation inventory 與 I1–I7 雙向對帳」的斷言，讓這種撞號直接失敗。

另外 I2（跨檔版本）與 I7.datasetVersion 拆開後，stale-shard 反例只觸發 I2 ＋ I7.artifactDigest——
**驗證器是對的，我的期望寫錯了**。這正是「斷言 exactly equals」的價值：用「包含」就看不到這個區別。

### 現況

`run_all.py` **289 條斷言全綠**（A 群 101／B 群 69／B8 55／B6 45／C4 19）。
a_core 77 列／47 Trial，artifact 樣本 8 Trial／12 個非 manifest 檔。

### 下一步

**M1：repo 鷹架與 ETL。** 動工時直接依 `plan.md` §14 的 14 項契約表實作，不要重新推導。

---

## 2026-09-18（同日）— M1：ETL 主體完成

`trial_radar/` 十個模組，每個 docstring 標出實作的章節；**未沿用 `artifact_sample/build_sample.py`**
（規格要能被兩份獨立的程式碼各自寫出來才算寫清楚）。結果：獨立實作與手寫 oracle 完全吻合
——47 Trial、10 個衝突組、2 個 dateUnknown、3 個 nearDuplicateGroup，A3 跨 5 種排列輸出逐位元相同。

| 測試 | 數 |
|---|---:|
| A 群（資料模型與收斂 A1–A10） | 27 |
| B 群（失敗分類 B1–B4） | 27 |
| B 群（不變量／digest B6–B9） | 27 |
| B 群（promotion B5） | 10 |
| C 群（sentinel C1–C6） | 50 |
| **pytest 合計** | **141** |
| fixture 自檢（`run_all.py`） | 289 |

### fixture 抓到兩個實作缺陷

**1. `zipfile.testzip()` 拋的是 `zlib.error` 不是 `BadZipFile`。** 只接 `BadZipFile` 會讓它
逸出成 traceback 而非 structured error code——B2 明文要求不得以 stderr 字串判定，
而一個 traceback 連 code 都沒有。

**2. `資料更新時間` 的旗標從沒寫進 artifact。** `dateMissing`／`dateUnparsed`／`dateFuture`
都在 §9.3.3 的封閉集合內，但 `artifacts.py` 只寫了呈現欄位的旗標。後果是下游光看 typed
分不出「有日期」與「可採計」——**`dateFuture` 的 typed 是一個合法 ISO 日期卻必須置末**，
於是 §9.3.6 驗證器對**未變造**的 artifact 就報 I5.records 違規。

第 2 點是「反向哨兵先紅」的價值：那條斷言一失敗，就直接指出輸出契約漏了一整類旗標，
而不是等 M2 做到 §7.2 的「資料日期不明」標示時才發現——那時已經要改資料契約。

### 三條刻意的反向哨兵

- **A4**：monkeypatch 把同日處置換成「任取 cohort 第一筆」，斷言 BIG-001 的
  `latestAmbiguous` 由 true 變 false 且衝突欄位冒出具體值。
- **A8**：注入只保留 1 hex 熵的雜湊替身驅動截短碰撞分支（真實 64 位元碰撞需約 2^32 次運算）。
- **A9**：把 `near_duplicate_groups` 換成恆空，斷言收斂結果完全不變。

### 兩個「規格沒承諾就不要斷言」

- B5 **刻意不斷言** working tree 在中途失敗後等於舊版——§9.2.1 明確不聲稱那件事。
- `promote()` 接 `BaseException` 不是筆誤：SIGTERM／workflow 取消以 `KeyboardInterrupt`／
  `SystemExit` 進來，只接 `Exception` 會讓 B5 明列的那條注入點完全沒有處置。

### tzdata 是硬依賴

Windows 與精簡 Linux 映像沒有系統 tz 資料庫。缺套件時 `ZoneInfo("Asia/Taipei")` 會拋，
**那是對的，不得軟性退回 UTC**：runner 是 UTC，台灣時間 08:00 前 UTC 仍是前一天，
「未來日期」判定會差一天（H5）。

### 下一步

1. `scripts/fetch_tfda.py` 與 `scripts/validate_schema.py` 拆成獨立 CLI（目前都在 build_data.py 內）
2. **首次連網實跑**：量 `stats.json` 大小與 `applicant` 的 distinct 值數，補 F1 的 Tier 0 總和
3. M2 前端

> 1 與 2 已於 2026-09-21 完成，見下一節——2 撞出兩個規格洞，規格改為 v0.8。

---

## 2026-09-21 — 首次連網實跑：兩個規格洞，規格改為 v0.8

M1 收尾的三件事：拆兩支獨立 CLI、首次連網實跑、量 F1。第二件把第三件變成了規格修訂。

### 先做的：三支 CLI 收斂到同一張 exit code 表

`scripts/fetch_tfda.py`（transport／archive／decode）與 `scripts/validate_schema.py`
（schema／content／U+001F）拆出來，`trial_radar/cli.py` 收攏 §9.5 的 exit code 對照、
stderr 格式與報告輸出。三支各自複製一份 try/except 遲早會漂移成「其中一支把某個 code
印成 exit 1」——而那在 CI 上看起來和成功以外的任何失敗一樣。

`tests/test_b_cli.py`（16 測試）驗的是 **process 的 exit code**，不是函式拋的 code。
兩者不可互相取代：對應表在 CLI 裡，函式層測試再綠也不會發現某支 CLI 把所有失敗都回成 1。

順手修掉一個潛在陷阱：`sourceSha256` 在 `--fetch` 下是 ZIP 的雜湊、在 `--source` 下是
CSV 的——同一個欄位兩種定義。§9.6 排除它的論據明寫「ZIP metadata 變動會改變 source SHA」，
故有 ZIP 時以 ZIP 為準，並加 `sourceKind` 標明；否則換執行模式造成的 SHA 改變會被誤讀成
上游換了內容（H3 的冪等驗證正是比這個值）。

### 然後：真實資料一跑就停在第一道硬失敗

```
$ uv run python scripts/build_data.py --source .cache/205.csv --dry-run
[IDENTITY_COLLISION] layer=content 4 個 identity 正規化碰撞群     exit 22
```

4 組僅**尾隨一個空白**的 protocol（`CYTB323J12201` 15 列 vs `CYTB323J12201 ` 2 列，
另三組同型）。`identityNormalize` 的定義本身含 `strip()`，而 §6.2 說「不同 raw 正規化後
相同即碰撞」——**照字面等於要求正規化不准折疊任何東西**，那樣正規化就沒有作用。

規格自己有兩處反證：§9.3.5 寫的 `trialCount: 5888` 是合併後的數字；而「實測 0 碰撞」的
5,882 數的是 distinct **normalized** 值，從未與 5,887 個 distinct **raw** 對照——
**那個量法在定義上就看不見碰撞**。

v0.8 把界線畫在 `strip`：尾隨空白在任何識別碼體系都不承載語意；大小寫與 NFKC 全形折疊
**可能**區分兩個不同計畫書，那兩類維持硬失敗（A7 的碰撞案例用的正是那兩類，不受影響）。
合併是靜默的，揭露不是——QA report 加 `WHITESPACE_ONLY_PROTOCOL_VARIANT`，實跑列出 4 組。

### 接著：F1 量出來是門檻的 10.2 倍

| trials-index 變體 | raw | gzip | brotli |
|---|---:|---:|---:|
| §6.4.5 字面（13 個呈現欄位全放） | 103,564 KiB | 15,621 KiB | 9,011 KiB |
| 4 個長文字欄位移出 shard | 11,120 KiB | 1,611 KiB | 915 KiB |

排除條件 39.6 MiB ＋ 納入條件 37.6 MiB ＋ 主要評估指標 6.9 MiB ＋ 試驗目的 5.9 MiB
＝ index raw 的 **92.6%**。

**這不是新決策，是 §6.4.5 與 F3 本來就直接衝突。** F3 早已要求「初始 payload 的 schema
不含這些欄位鍵」，§6.4.5 卻說 `displayFields` 涵蓋全部 13 欄——照哪一條寫都會違反另一條，
**四輪覆審都沒抓到**。收斂語意不動：§6.4.2 的衝突判定與 §6.4.3 的 `rawVariants` 仍對
全部 13 欄計算，`conflictFields` 仍可含長文字欄位，改的只是序列化進 index 的子集。

另一半是量測口徑：規格全程以 gzip 計，但部署在 Cloudflare Pages 實際送 brotli，同一份
位元組差 43%。**量一個使用者從來不會付的數字，正是 F1 自己那段話警告的自我誤導。**
manifest 因此加 `brotliBytes`（只算 5 個 top-level 檔），§8.5／D7 的 UI 下載大小改取它。

### Tier 0 實測（2026-09-21，staging 的真實 artifact）

| 檔案 | raw | gzip | brotli |
|---|---:|---:|---:|
| `trials-index.<h>.json` | 11,119.6 KiB | 1,611.0 KiB | 914.8 KiB |
| `stats.<h>.json` | 22.8 KiB | 4.5 KiB | 3.9 KiB |
| `manifest.json` | 28.7 KiB | 7.0 KiB | 5.4 KiB |
| **合計** | | **1,622.6 KiB** | **924.0 KiB** |

以 brotli 計**餘 612.0 KiB** 給 HTML／JS／CSS／字型；以 gzip 計則超標 86.6 KiB。
`stats.json` 的 cardinality 疑慮解除：`applicant` 371 bucket、`phase` 7、`scale` 3，
三者的 `buckets + unprovided + conflicted` 均恰等於 5,888（§9.3.6 I6 成立），整份 3.9 KiB。

按需 tier 的 brotli 實測全部低於 v0.5 的 gzip 估值（`short`+`all` 696.1、`all`+`latest`
1,477.6、`all`+`all` 1,840.7 KiB）——**估算一路偏保守，但偏的方向不一致**（index 估值
偏低 23%），估值一律不可當驗收基準。

### 獨立實作與規格的實測逐一相符

5,888 Trial／18,736 列／**846 平手組**／**143 衝突組**／**18 nearDuplicateGroup**／
13 protocolNonIdentifier／152 suspectedTestRow——前三個與 §6.1、§6.2.1、D1 記的數字完全一致，
而那些是規格作者用另一套一次性腳本量的。

### 測試

| 測試 | 數 |
|---|---:|
| 先前（M1 ETL 主體） | 141 |
| B 群 CLI exit code（`test_b_cli.py`） | 16 |
| §6.2 空白合併（`test_a_whitespace_merge.py`） | 6 |
| F1／F3 payload 邊界（`test_f_payload.py`） | 8 |
| **pytest 合計** | **171** |

新增的 14 條全部做過反向驗證：把兩個改動各自還原成 v0.7 行為後，**5 條轉紅**。
其中 `test_long_text_content_absent_from_index_bytes` 第一版**沒轉紅**——canary 從來源列
取值，抽中的是衝突欄位，而衝突欄位本來就從 `displayFields` 省略（§6.4.5），於是舊行為下
照樣綠。改成從 model 的 `display_fields` 取（只有那些值在舊行為下真的會被序列化）才守得住。
**「加了斷言」與「那條斷言守得住東西」是兩件事。**

### 教訓

**凍結 fixture 證明的是「實作符合規格」，證明不了「規格符合現實」。** v0.5 起反覆用 fixture
反驗規格，找出 12 個 GAP，但 fixture 是照規格寫的——規格與真實資料的落差它結構上看不見。
這兩個洞，一個讓管線一次都跑不完，一個讓 F1 超標 10 倍，四輪 prose 覆審加 289 條 fixture
斷言全數漏掉，**第一次連網 90 秒內兩個都現形**。

新專案的第一次連網實跑要排在**規格定案之後、實作完成之前**，不是排在最後當驗收。

### 下一步

**M2 前端**（D／E／F／G 群驗收）。F1 的餘裕是 612 KiB brotli，bundle 預算要照這個數字編。

---

## 2026-09-21（同日）— 第五輪覆審 v0.9，M1 收尾，M2-A／B／C

一天四件事：規格第五輪覆審、M1 落差補齊、M2 前端三段。

### 第五輪 `/codex-checkplan`：只審 v0.8 的修訂本身

**接受 35／部分接受 4／拒絕 0，範圍蔓延 0。39 項沒有一項是幻覺，也沒有一項是
v0.7 遺留——全部是 v0.8 修訂自己造的。** 第五次應驗「修訂會製造新洞」。

Blocker 只有一個，而它是 **v0.8 犯了它自己正要修的錯**：v0.8 把 F1 從 gzip 改
brotli，理由寫「量一個使用者從來不會付的數字就是自我誤導」，然後把 `brotliBytes`
定義成 build-time quality 11 再交給 UI 當實際下載大小。Cloudflare 動態壓縮約 q4–q5，
**比 q11 大**。等於把 gzip 換成另一個使用者同樣不會付的數字，而且因為名字叫
`brotliBytes`、單位也對，**更難發現**。

八個 High：§6.3.4 留了兩份不等價的碰撞定義；長文字的 `rawVariants` 無處可放；
`brotliBytes` 無人驗證形成循環自證（→ 新增不變量 I8）；§8.5 以 scope 記單一數字
三義（→ 改檔案集合模型）；F2 拿 manifest 當自己的 oracle；A7 的正例**與 v0.8 的
新定義相反**；A1 的「應合併案例」可用兩筆逐位元相同的列充數。

送審前自查另修掉 4 處，形狀一致：**最容易漏的是「同一個數字寫在兩個地方」**。

**v0.9 的教訓是 v0.8 的反面**：本輪 39 項全部是規格內部一致性問題，那正是 prose
覆審擅長而實跑永遠不會顯形的類別。兩種手段互補，不可互相取代。

### M1 收尾

實作補上 v0.9 的三項落差：§9.8 collision report 改 group → members 兩層（碰撞成員
共用 trialId，原契約無法定位來源列）、warning 加 `trialId`、不變量 **I8**。

加 I8 時 16 條既有測試轉紅——`_republish` 把 `bytes` 留 0，於是**每個 B6 反例都
順便違反 I8**，正好違反 B6 自己要求的「各自獨立反例」。修好後恢復隔離。

A 群補 v0.9 指名的反例類別：A1 四類合併案例、A4 四個長文字欄位各自為唯一衝突
來源、A9 的 whitespace × looseKey 交叉、C6 的長文字 `rawVariants` 三道不出現斷言。

pytest **171 → 202**。新增 38 條全部做過反向驗證（弱化成舊行為後分別轉紅 13／11／
4／2／1 條）。

### M2-A：前端鷹架與核心邏輯

TypeScript + Vite + Vitest。四個純邏輯模組：`search.ts`（§8.1／8.2／8.3）、
`filter.ts`（§8.4 六維度）、`scope.ts`（§8.5 檔案集合）、`urlState.ts`（§7.4）。

**測試 fixture 是由現行 Python ETL 產生的真實 artifact**，不手寫假 JSON：手寫的
形狀是「我以為 ETL 會輸出什麼」，而前端最容易出的錯正是讀一個實際不存在的欄位。
`tests/test_web_fixture.py` 斷言它與 `build_artifacts` 逐位元相同，契約一改兩邊一起紅。

### M2-B：UI

七個 render 模組。**全站不用 `innerHTML`**——E4 列的輸出 surface 有八處，逐處記得
跳脫行不通，一律 `textContent`／`setAttribute` 讓忘記跳脫在語法上不可能。

規格未涵蓋的一件事：`applicant` 實資料 **371 個 bucket**，不能全列成 checkbox。
採可搜尋計數清單，三個 facet 共用同一元件不做特例。

### M2-C：Playwright

**G2 的對比實算抓到三處真實違規**，全是 house style 警告的 4.26:1（`--text-muted`
與 `--accent` 出現在米色裸底上）。skill 早寫了這條限制，是 M2-B 漏套。修正後
8 個路由 3,075 個樣本最低 **4.81:1**。

**F4 原本不過**：極多結果 p95 574.7 ms、多詞 466.7 ms（門檻 300）。

| 查詢 | 修正前 p95 | 修正後 p95 |
|---|---:|---:|
| 極多結果（臨床） | 574.7 ms | 71.3 ms |
| 多詞（台灣 試驗） | 466.7 ms | 66.2 ms |
| 其餘四項 | 55–139 ms | 23–62 ms |

歸因實測：時間隨**卡片數**線性成長約 0.15 ms／張，與 scope 或資料量無關
（乳癌 273 張 127 ms vs 臨床 2,616 張 407 ms）——**瓶頸是 DOM 渲染不是搜尋**。
改分批渲染（50 筆／批）。總數照實顯示；把總數也截成 50 會讓使用者以為只有
50 個試驗符合，那比慢更嚴重。

**測試自己有兩個缺陷**：
1. `routes()` 在收集期求值，那時 `beforeAll` 還沒跑，trialId 是空字串 → 量的是
   錯誤頁。G1 四格詳情測試原本是**假綠**（錯誤頁小又乾淨，viewport 檢查輕鬆過）。
2. **真實資料的 `dateUnknown` 是 0 筆**。硬性斷言會讓矩陣在 production 掛掉，
   默默跳過又讓 fixture 悄悄失去覆蓋——改為依規模決定並把責任歸屬寫死。

### F1 目前

| 項目 | brotli q11 估算 |
|---|---:|
| 資料層 | 924.0 KiB |
| bundle（js 8.0 ＋ css 1.5 ＋ html 0.5） | 10.0 KiB |
| **Tier 0** | **934.0 KiB** |
| 對 1,500,000 bytes | 餘 530.8 KiB |

bundle 只吃掉 0.7% 的預算。**仍是估算值**，F1 判定要等對真實部署量過才算數。

### 測試總數

| 套件 | 數 |
|---|---:|
| pytest | 202 |
| vitest | 105 |
| Playwright（production） | 54 |

### 下一步

1. **M2 收尾**：E2(b)／E3 的 metadata surface（`sourceUpdatedAt`／`builtAt`／總數）、
   E1／E4 的完整 inventory、D1–D6／D8 的 DOM 層斷言。G4 的圖表是規格允許的「可選」，
   目前只做數字卡與清單。
2. **M3**：CI 與月更新。
3. **repo 仍未建 GitHub remote。**
