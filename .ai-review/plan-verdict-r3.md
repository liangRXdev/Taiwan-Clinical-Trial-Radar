# 規格覆審判定（第三輪，限縮範圍）

- **判定日期**：2026-09-18
- **受審對象**：`.ai-review/plan.md` v0.4（commit `270de34`）的 §6.2–§6.6、§8.5、§9.2、§9.3 ＋ `fixture-findings-a.md` 的 7 個洞
- **Codex 原始輸出**：`.ai-review/plan-review-r3.md`（codex-cli 0.153.4，thread `01a0b224`）

## 統計

| 判定 | 數量 |
|---|---:|
| 接受 | 12 |
| 部分接受 | 0 |
| **不成立（我的建議被否決）** | **1（GAP-5）** |
| 嚴重度被下修 | 2（GAP-4 High→Low 的 Medium→Low、GAP-6 High→Medium） |
| 拒絕 Codex 的項目 | 0（範圍蔓延 0） |

Codex 對 7 個洞的判定：**6 成立、1 不成立**。另在限縮範圍內找到 **1 個 Blocker、3 個 High、4 個 Medium**，並明確在 §8.5 與 §6.4 寫「無」。

**Codex 的結論是「尚不足以動工」，我接受。** 它列的 8 項必封存契約全部屬實。

我方另有 2 項自行實測發現（S3、S4）與 2 項使用者定案（D-B、D-R），一併記於下。

---

## 一、對 7 個洞的判定

| # | Codex 判定 | 我的處置 |
|---|---|---|
| GAP-1 | 成立，High 正確 | **接受**，並採其三項補充：`rawVariants` 是**欄位層級**旗標（非 Trial 層）、判定依據為 cohort 內該欄位 distinct raw 數 >1、`rawVariants=true` 不等於衝突、詳情頁須保留**每筆 record 的對應**不得只列去重文字 |
| GAP-2 | 成立，但**只修了一半** | **接受**。我只寫了 identity key 的 `#0`，漏了 `recordId` 的 duplicate ordinal——同一個問題（單筆無後綴，日後出現相同列時變 `#0`）。兩者一律從 `#0` 起 |
| GAP-3 | 成立，High 正確 | **接受**，並採其五項補充。最關鍵的一項是我沒想到的：**衝突欄位在 `displayFields` 中要完全省略，不是給 `{typed:null}`**——後者會與「未提供」混淆，而那正是本專案最怕的誤導 |
| GAP-4 | 成立，**Medium → Low** | **接受降級**。空字串在「不含英數字元」下理應包含，語意也相同；只影響分類計數與文件契約，不動架構 |
| **GAP-5** | **不成立** | **接受否決，我的建議是錯的。** 詳下 |
| GAP-6 | 成立，**High → Medium** | **接受降級**。依本輪嚴重度定義（High＝要改架構或資料模型），改測試策略不動資料模型，Medium 正確 |
| GAP-7 | 成立，Medium 正確 | **接受**，並採其 production 語意補充。最重要的一項是我沒想到的：**buildDate 須以 `Asia/Taipei` 日曆日產生，不得取決於 runner 的 UTC 日期**——runner 是 UTC，台灣時間 08:00 之前 UTC 還是前一天，會讓「未來日期」的判定差一天 |

### GAP-5 我錯在哪

我提議「數值與分類欄位改比 typed value，兩者皆 `null` 即不衝突」。Codex 指出這**過度收斂**：

`""` 與 `"-5"` 的 typed 都是 `null`，但語意完全不同——`""` 是正常的 `numericMissing`（UI 顯示「未提供」），`"-5"` 是 `numericImplausible` warning（必須顯示 raw 與異常提示）。判為不衝突並任取一筆 raw，會**隱藏異常**，或反過來把正常缺值呈現成負數 warning。

這正好命中本專案的風險排序：誤導 > 資料正確性。我的修法為了消除假警報，反而製造了一種更糟的誤導。

**改採 Codex 的 semantic comparison key**（依欄位型別定義比較鍵）：

| 欄位型別／狀態 | 比較鍵 |
|---|---|
| 文字 | `NFKC` + 移除全部空白 |
| 合法數值 | typed integer |
| 數值缺值 | 只有 `numericMissing` 彼此相等 |
| 無法解析 | 旗標類型相同**且**正規化 raw 相同才相等 |
| 不合理數值 | 旗標類型相同**且**正規化 raw 相同才相等 |
| 分類 sentinel | 明確的 `unprovided` 狀態 |
| 合法分類 | canonical typed value |

comparison key 相同但 raw 不同 → 套用 GAP-1 的 `rawVariants`，不算衝突。

**後果**：`NUM-022`（`""` vs `"-5"`）**維持衝突**。fixture 不必改，但 oracle 的 `__SPEC_GAP__` 現在可以填實：`latestAmbiguous=true`、`conflictFields=["全球預計受試者人數"]`。

---

## 二、限縮範圍內的其他問題

| # | 嚴重度 | 判定 | 理由與處置 |
|---|---|---|---|
| **B1 `datasetVersion` 與整體 digest 循環定義** | **Blocker** | **接受** | **屬實，且是我 v0.4 自己造的。** §9.2.2 要求每個非 manifest 檔案內含 `datasetVersion`；§9.3 又定義 `datasetVersion` = 這些檔案**最終位元組** digest 的前 16 hex。檔案位元組包含 `datasetVersion` → 循環，一般情況無固定點。照文字寫不出合規 artifact。**修法採其建議並分離兩個概念**：`datasetVersion` 由**不含內嵌版本欄位的 canonical logical payload** 計算；`artifactDigest` 待版本寫入最終檔案後對**最終位元組**計算，供完整性驗證。另封存檔名 hash 的演算法與長度、串接的是 raw bytes 還是 hex、digest 是否納入路徑、以及 artifactDigest 在 manifest 的欄位 |
| **B2 SourceRecord 的 `typed`／`flags` schema** | High | **接受** | 屬實：§9.3 只寫 `"typed": {}`、`"flags": []`。數值欄位有 2 個、日期欄位有 3 個，單純一個 `"numericMissing"` 字串**指不出是哪一欄**。且 record-level 與 field-level flags 必須分開 |
| **B3 `searchShortLatest` 未保留 record 邊界** | High | **接受** | 屬實且切中：只寫「各 record 的 5 短欄正規化文字」，若實作把 cohort 多筆文字**合併**，兩個 term 就可能分別命中不同 record → 違反 §8.3 已定案的 record 層 AND，且違反的方式是靜默多報。須明定每筆 latest-cohort record 保留獨立 `recordId` 與五欄陣列、封存欄位順序、不得跨 record 合併 |
| **B4 protocol 空值的判定層級** | High | **接受** | 屬實：空白-only 的 protocol（如 `"   "`）該走 `P:` 還是 `H:` 未定義，而這會改變 trialId、URL、shard 與 Trial 數。**採其建議**：`identityNormalize(protocol)` 為空即走 `H:`，raw 完整保留供稽核。這也順帶把 GAP-4 的空字串問題收攏成同一條規則 |
| **B5「英數字元」沒有精確字元集合** | Medium | **接受** | 屬實且我實測確認**問題比描述更嚴重**：Python 的 `"系統測試".isalnum()` 回傳 **`True`**（中文被視為字母）。照 naive 實作，`系統測試` **不會**被標記為 `protocolNonIdentifier`——與 §6.2.2 的意圖完全相反。我的 fixture self-check 恰好用了 ASCII regex 才沒踩到。須明定為 ASCII `A–Z a–z 0–9`，並明定 NFKC 在前。另採其附帶建議：`nearDuplicateGroup` 只在集合含 ≥2 個不同 identity key 時輸出，單一成員為 `null` |
| **B6 試驗執行期間的日期 grammar** | Medium | **接受** | 屬實：§6.5 要求偵測 `end < start`（實測 7 列），卻沒定義 `試驗預計執行期間起／迄` 的接受格式與任一端不可解析時的處理。實測兩欄格式**目前 100% 合法**，但與 `資料更新時間` 同樣是每月重跑的 ingestion contract |
| **B7 數值 lexical grammar 與可表示範圍** | Medium | **接受** | 屬實。實測補強：兩欄的最大值分別為 100,000 與 4,236，**無任何值超過 2^53-1**，故 JS safe integer 風險目前為零——但仍須封存 grammar（前後空白、正號、前導零、全形數字），因為實測**有 3 筆前導零**（`026`、`024`、`08`），`int()` 會給 26／24／8，顯示 typed 就等於改寫來源。規則：raw 一律顯示、typed 僅供篩選與統計 |
| **B8 artifact inventory 不變量無法字面成立** | Medium | **接受** | 屬實：`manifest.files` 不列 `manifest.json`，卻要求它等於 `public/data/` 的實際檔案集合——字面矛盾。且 `recordShards` 未定義是固定 256 個還是只輸出非空 shard。**選定**：集合相等定義為「`public/data/` 中**除 `manifest.json` 外**的全部檔案」；shard **只輸出非空者**（實測 5,888 個 trial 散在 256 個 shard，全部非空的機率高，但規則要寫死以免 validator 分歧） |

Codex 在 §8.5 與 §6.4（除已列項目外）明確寫「無」，未湊數。

---

## 三、我方自行發現（不在 Codex 輸出中）

### S3｜High／`trials-index` 的實際大小是 F1 預算的 1.5 倍，且拆檔會更大

v0.4 的 F1 訂「Tier 0 ≤1.0 MB gzip」，基線寫「715–900 KiB」。**那個基線是估的，實測後錯了。**

| 方案 | trials-index gzip |
|---|---:|
| v0.4 現行（`recordIds` + `latestCohort` 在 index 內） | **1,535 KiB** |
| 把 `recordIds`／`latestCohort` 移入 shard，index 只留計數 | **1,236 KiB** |
| 再把搜尋文字拆成獨立檔（903 + 693） | **1,596 KiB** |

三個發現：

1. 原基線 715 KiB 量的是「5,888 trial × 10 個扁平卡片欄位」，**沒算** `recordIds`、`conflictFields`、`protocolRaw`、旗標與 `searchShortLatest`。卡片資料本身就 903 KiB。
2. 可省的是 `recordIds`：18,736 個高熵 hex 壓縮率差，而它們**只有詳情頁用得到**；recordId 以 trialId 為前綴，shard 可自我描述。
3. **拆檔會變大不會變小**（1,596 vs 1,236）——拆開後失去跨欄位的壓縮共享。這推翻了「拆成按需載入就能瘦身」的直覺。

**使用者定案 D-B**：採方案 B（`recordIds`／`latestCohort` 移入 shard），F1 的 Tier 0 門檻改為 **≤1.5 MB gzip**，資料層基線 1,236 KiB，超出須寫瓶頸歸因而非調鬆數字。

附帶：index 只留 `recordCount` 與 `latestCohortCount`，§9.3 須加不變量要求它們**等於 shard 內對應清單的長度**，否則計數會與 shard 漂移。

### S4｜High／`numericUnparsed` 是個不同質的垃圾桶，而它決定 `enroll` 篩選

`台灣預計受試者人數` 是 §8.4 `enroll` 篩選的依據。實測其值的組成：

| 型態 | 台灣預計人數 | 全球預計人數 |
|---|---:|---:|
| 純整數 | 16,858 | 17,792 |
| **範圍**（`20-40`、`8-12`、`4至12`） | **1,340** | 336 |
| 約略（`約30`） | 159 | 191 |
| 其他（`約26-30(競爭)`、`至少480`、`148(最多266)`、`接受本品治療之病人`） | 179 | 144 |
| `NA` | 23 | 80 |
| 千分位、界限（`≥510`） | 4 | 15 |
| 空 | 173 | 178 |

依 v0.4，全部非純整數 → typed `null` + `numericUnparsed` + UI「數值格式未辨識」。後果：

- **`20-40` 不是「格式未辨識」，是一個區間。** 藥師篩「11–30 人」時看不到寫 `20-40` 的試驗，漏掉 1,340 筆（7.2%）。
- 又抓到上游測試資料：**`TEST` 各 9 筆**（兩欄都有），與 §6.2.2 的 `系統測試` 同源，應併入同一個「疑似上游測試列」警示。
- `ˋ40` 9 筆是注音符號 `ˋ`（U+02CB）誤打；`240=90+150`、`20 (安全性導入期)/ 562 (隨機分配期)` 是真正的自由文字。

**使用者定案 D-R**：**只解析嚴格範圍**。嚴格範圍定義為 NFKC 後符合 `^\d+\s*[-~～〜–—]|至\s*\d+$` 且 `min ≤ max`，解為 `{min, max}` 並加 `numericRange` 旗標；`enroll` 篩選以**區間重疊**判定命中；卡片一律顯示 raw 原文。`約400`、`至少480`、`148(最多266)` 等維持 `numericUnparsed`。

實測回收量：台灣 **1,347／1,705**（7.2% of 全部 18,736）、全球 **356／766**，且 **0 筆 min > max**。

理由：把 `20-40` 讀成區間是**結構解讀**；把 `約400` 讀成 400 會丟掉「約」，那是**推論**，與專案「嚴格區分客觀資料與推論」的紀律衝突。

---

## 四、結論

**尚不足以動工，需 v0.5。** 我接受 Codex 的判斷。

動工前須封存的契約（Codex 的 8 項 ＋ 我方 2 項）：

1. 解開 `datasetVersion`／`artifactDigest` 循環定義，並封存 hash 表示、檔名 hash、inventory 範圍（B1，**Blocker**）
2. SourceRecord 的 field-scoped `typed`／`flags` schema（B2）
3. `displayFields` 三元組 ＋ 欄位層級 `rawVariants` ＋ **修正版 GAP-5 semantic comparison key**（GAP-1／GAP-3／GAP-5）
4. protocol 空值分支（`identityNormalize` 後為空即走 `H:`）、空白-only 行為、ASCII 英數字元規則（B4／B5／GAP-4）
5. identity key 與 recordId 的 ordinal **一律從 `#0` 起**（GAP-2）
6. `searchShortLatest` 的逐-record shape，確保 record 層 AND 可被保留（B3）
7. buildDate 的 `Asia/Taipei` 語意與可注入參數、試驗期間日期 grammar、數值 lexical grammar 與可表示範圍（GAP-7／B6／B7）
8. manifest file-set 不變量修正、empty shard 是否輸出（B8）
9. **方案 B 的 index／shard 職責切分與計數不變量；F1 改 ≤1.5 MB**（S3，使用者定案）
10. **嚴格範圍解析 `numericRange` 與 `enroll` 的區間重疊語意**（S4，使用者定案）

三輪的 Blocker 走勢：**2 → 0 → 1**。第三輪那 1 個是我在 v0.4 修 N8 時新造的循環定義——再一次印證「修訂會製造新洞」。但這次它落在一個限縮且已封存的範圍內，v0.5 改完後**不必再跑第四輪全審**；建議改以「B 群 fixture ＋ 產出一份最小 artifact 樣本」來驗證這 10 項契約是否真的可實作——照 A 群的經驗，那比再讀一遍 prose 更能找出問題。
