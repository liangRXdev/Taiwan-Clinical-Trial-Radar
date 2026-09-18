# Codex 規格覆審原始輸出（第三輪，限縮範圍）

- **審查日期**：2026-09-18
- **Codex 版本**：codex-cli 0.153.4（MCP `mcp__codex__codex`，`sandbox: read-only`、`approval-policy: never`）
- **thread id**：`01a0b224-c258-7c80-935e-45f149068095`
- **受審對象**：`.ai-review/plan.md` v0.4（commit `270de34`）的 §6.2–§6.6、§8.5、§9.2、§9.3，以及 `fixture-findings-a.md` 的 7 個洞
- **明確排除**：目標與非目標、四項定案決策、§4、§7.1–§7.4、§8.1–§8.4、§9.4–§9.7、§10、§12、§13、§11 全部驗收條件（唯一例外 A8）

以下為 Codex 輸出，**原封不動**未修飾、未刪改。判定見 `plan-verdict-r3.md`。

---

## 1. 對 7 個洞的判定

### GAP-1：建議成立

**嚴重度：High，評級正確。**

以 `recordId` 字典序最小者作為 deterministic raw representative，能補上「比較後相同、raw 不同」時沒有共同 raw 值的矛盾。

但契約需再明定：

- `rawVariants` 是**欄位層級**旗標，不是 Trial 整體旗標。
- 判定方式為 `latestCohort` 中該欄位的 distinct raw value 數量大於 1。
- `rawVariants=true` 不代表衝突；只表示多個 raw 值映射到同一比較值。
- 詳情頁呈現的是 cohort 中各 SourceRecord 的原始值，不得只列去重後文字而失去 record 對應。

### GAP-2：建議成立，但必須同步修正 `recordId`

**嚴重度：Medium，評級正確。**

空 protocol 的 identity key 一律使用 `H:<hash>#k`，單筆為 `#0`，確實能固定 ID 形狀。

相同問題也存在於：

> 完全相同的重複列附 `#k`

若單一 record 不帶後綴，日後加入相同列時，其 `recordId` 仍會由無後綴變成 `#0`。因此必須同步明定：

- identity key 的 ordinal 永遠存在，從 `#0` 開始。
- recordId 的 duplicate ordinal 也永遠存在，從 `#0` 開始。

否則 GAP-2 只修了一半。

### GAP-3：建議成立

**嚴重度：High，評級正確。**

`displayFields[field] = { raw, typed, flags }` 是合適的資料契約，可避免前端重新實作 sentinel／數值解析。

仍需一併封存：

- `raw` 固定為 string。
- `typed` 對各欄位的 JSON 型別及 nullability。
- `flags` 為該欄位的旗標，而非整筆 record 的無欄位歸屬字串。
- GAP-1 的 `rawVariants` 應置於該欄位的 `flags`，或另設明確的欄位層級 boolean；不得兩種表示並存。
- 衝突欄位在 `displayFields` 中是完全省略，而不是 `{typed:null}`；否則會與「未提供」混淆。

### GAP-4：建議成立

**嚴重度應由 Medium 降為 Low。**

空字串在「不含任何英數字元」的規則下理應包含在內，而且語意同樣是來源未提供可用編號。

這是必要澄清，但只影響分類計數與文件契約，不需改架構或資料模型，因此屬 Low。

### GAP-5：建議不成立

**嚴重度：Medium，評級正確。**

問題存在，但「數值與分類只比較 typed value」會過度收斂。

`""` 與 `"-5"` 雖然 typed 都是 `null`，語意並不相同：

- `""` 是正常的 `numericMissing`，UI 顯示「未提供」。
- `"-5"` 是 `numericImplausible` warning，必須顯示 raw 與異常提示。

若判為不衝突並任取其中一筆 raw，可能隱藏異常或把正常缺值呈現成負數 warning。

相容替代為定義欄位型別專屬的 semantic comparison key：

- 文字：比較 `NFKC + 移除全部空白`。
- 合法數值：比較 typed integer。
- 數值缺值：只有 `numericMissing` 可彼此相等。
- 無法解析：旗標類型相同，且正規化 raw 相同才相等。
- 不合理數值：旗標類型相同，且正規化 raw 相同才相等。
- 分類 sentinel：比較明確的 `unprovided` 狀態。
- 合法分類：比較 canonical typed value。
- comparison key 相同但 raw 不同時，套用 GAP-1 的 `rawVariants`。

因此 `""` vs `"-5"` 應維持衝突；兩筆只差全半形或空白、且具有相同語意狀態者才是不衝突變體。

### GAP-6：建議成立

**嚴重度應由 High 降為 Medium。**

注入測試用雜湊函式、刻意縮短輸出以驅動碰撞，是可重現且能真正守住 `ID_TRUNCATION_COLLISION` 分支的驗收方式。

須明定：

- 這是「凍結來源 fixture」原則的唯一測試替身例外。
- 測試仍須使用兩個不同 identity key／canonical serialization。
- 斷言範圍包括錯誤碼、停止發布及正式 artifact 不變。

它不需要改正式資料模型或發布架構，故 Medium 較符合本輪嚴重度定義。

### GAP-7：建議成立，但需補 production 語意

**嚴重度：Medium，評級正確。**

`buildDate` 必須是可注入的純日期參數，邊界至少包含：

- 日期等於 buildDate：可採計。
- 日期等於 buildDate + 1 日：`dateFuture`，不可採計。

另須封存：

- 參數型別是 ISO calendar date，而非 timestamp。
- production buildDate 以 `Asia/Taipei` 日曆日產生；不得取決於 GitHub Actions runner 的 UTC 日期。
- 同一 build 中所有 record 必須使用同一個 buildDate 值。

---

## 2. 限縮範圍內的其他問題

### §6.2／§6.2.1／§6.2.2

#### Medium／「英數字元」沒有精確字元集合

**問題：** Python 的 Unicode alphanumeric 判定會把中文字視為字母；但規格又將 `系統測試` 等中文值描述為「完全不含英數字元」。不同實作會得到相反的 `protocolNonIdentifier` 與 loose key。

**為什麼現在不修之後會更貴：** 會改變 Trial 標記、統計分類、QA report、近似群組及 protocol alias eligibility。

**建議修法：** 明定「英數字元」為 ASCII `A–Z`、`a–z`、`0–9`，並封存判定前是否先做 NFKC。建議 loose key 與 `protocolNonIdentifier` 均在 NFKC 後套用相同 ASCII 字元集合。另明定只有含兩個以上不同 identity key 的集合才輸出 `nearDuplicateGroup`，單一成員為 `null`。

### §6.3

#### High／「protocol 為空」的判定層級未定義

**問題：** 無法判斷空白-only protocol 應走：

- raw 非空，因此產生 `P:` identity key；或
- identity normalization 後為空，因此走 `H:` fallback。

這也影響 GAP-4 的 `protocolNonIdentifier`。

**為什麼現在不修之後會更貴：** 會直接改變 trialId、URL、shard、Trial 數量與 fixture oracle。

**建議修法：** 明定 `P:`／`H:` 分支依據。較一致的契約是：`identityNormalize(protocol)` 為空即走 `H:`；raw 仍完整保留供稽核。

除上述與 GAP-2 外，無。

### §6.4

除 GAP-1、GAP-3、GAP-5，以及下述 §9.3 的 SourceRecord schema 問題外，無。

### §6.5

#### Medium／試驗執行期間的日期解析契約仍缺失

**問題：** 規格要求偵測 `end < start`，但未定義 `試驗預計執行期間起／迄` 接受的格式、日曆有效性及任一端無法解析時的處理。

**為什麼現在不修之後會更貴：** ETL warning、period typed value、篩選與 fixture 可能採用不同解析器，之後需重算既有輸出。

**建議修法：** 明定接受格式、有效日曆日規則，以及只有兩端皆可解析時才比較順序；無法解析者保留 raw，並明確指定旗標與 typed value。

### §6.6

#### Medium／「純十進位整數」及 typed integer 可表示範圍未封存

**問題：** 尚未明定前後空白、正號、前導零、全形數字及超出 JavaScript safe integer 範圍的值如何分類。Python integer 與 TypeScript `number` 可得到不一致結果。

**為什麼現在不修之後會更貴：** 會影響 typed value、衝突判定、facet bucket 與前端精確顯示。

**建議修法：** 封存唯一 lexical grammar 及 typed JSON number 的精確範圍；超界值必須落入既定異常狀態，不得以失真數字輸出。解析順序也須固定，使負數、格式錯誤與超界值只有一個旗標分類。

### §8.5

無。搜尋 scope 的產品語意已足夠；其尚缺的輸出形狀列於 §9.3。

### §9.2／§9.3

#### Blocker／`datasetVersion` 與整體 digest 形成循環定義

**問題：**

1. 每個非 manifest 檔案必須先內含 `datasetVersion`。
2. `datasetVersion` 又等於這些檔案最終位元組 digest 的前 16 hex。

因此無法先決定任何一方；一般情況不存在可求得的固定點。

**為什麼現在不修之後會更貴：** M1 無法依文字產生合規 artifact。任意採用 placeholder、二次改寫或忽略內嵌版本，都會得到不同的檔名、digest 與版本值，之後必須重做整個發布模型。

**建議修法：** 分離兩個概念：

- `datasetVersion`：由不含內嵌 `datasetVersion` 的 canonical logical payload 計算。
- artifact digest：待 `datasetVersion` 寫入最終檔案後，對最終檔案位元組計算，供完整性驗證。

同時封存：

- 路徑中的 `<hash>` 使用何種演算法及長度。
- 串接的是 raw digest bytes 還是 hex 字串。
- digest 是否納入路徑本身。
- 完整 artifact digest 在 manifest 中的欄位與格式。

這是修正既有「整體 digest」要求，不是新增產品需求。

#### High／SourceRecord 的 `typed` 與 `flags` schema 仍未真正補完

**問題：** §9.3 只有 `"typed": {}`、`"flags": []`。數值欄位有兩個、日期欄位也有多個；單純 `"numericMissing"` 無法指出是哪一欄。

**為什麼現在不修之後會更貴：** ETL 與前端會各自發明形狀；GAP-3 即使補完 Trial 的 `displayFields`，詳情頁仍無法可靠讀取 SourceRecord。

**建議修法：** 封存 typed 的封閉欄位集合、各欄 JSON 型別／nullability，以及 field-scoped flags 形狀。record-level flags 與 field-level flags 必須分開。

#### High／`searchShortLatest` 未保留可驗證的 record 邊界

**問題：** 只寫「各 record 的 5 短欄正規化文字」，沒有 schema、欄位順序或 recordId 對應。若實作者把多筆 latest cohort 文字合併，兩個 term 可能分別命中不同 record，違反既定的 record 層 AND。

**為什麼現在不修之後會更貴：** 它直接決定 `trials-index` 資料模型；M2 才發現會迫使 M1 產物、搜尋邏輯與 fixture 一起重做。

**建議修法：** 明定每個 latest-cohort record 均保留獨立 recordId 與五欄陣列，並封存欄位順序；不得先跨 record 合併文字。

#### Medium／artifact inventory 不變量目前無法字面成立

**問題：**

- `manifest.files` 不列 `manifest.json`，但規格要求它等於 `public/data/` 的實際檔案集合。
- `recordShards` 未定義是固定輸出 256 個 shard，還是只輸出非空 shard。

**為什麼現在不修之後會更貴：** staging validator、殘留檔偵測及 manifest schema 會出現不同合法解讀。

**建議修法：** 將集合相等明定為「`public/data/` 中除 `manifest.json` 外的全部檔案」，並明定 shard 採固定 256 個或僅非空集合。兩者皆可，但只能選一種。

除以上問題外，§9.2 的 commit／deployment authoritative 邊界與 immutable cache 方向無其他阻礙。

---

## 3. 可否動工的判斷

**尚不足以開始撰寫 M1 ETL。**

即使補完 7 個洞，仍有一項 Blocker 與數項會改變 M1 輸出資料模型的 High 契約。動工前至少必須封存：

1. 解開 `datasetVersion`／最終 artifact digest 的循環定義，並定義 hash 表示、檔名 hash 與 inventory 範圍。
2. 補完 SourceRecord 的 field-scoped `typed`／`flags` schema。
3. 補完 `displayFields` 三元組、欄位層級 `rawVariants`，並採用修正版 GAP-5 semantic comparison key。
4. 明定 protocol 空值分支、空白-only 行為及 ASCII 英數字元規則。
5. 將 GAP-2 的固定 `#0` 規則同步套用至 identity key 與 recordId。
6. 封存 `searchShortLatest` 的逐-record shape，確保 record 層 AND 可被保留。
7. 封存 buildDate 的 `Asia/Taipei` production 語意、試驗期間日期 grammar，以及數值 lexical grammar／可精確表示範圍。
8. 修正 manifest file-set 不變量並決定 empty shard 是否輸出。

完成以上契約後，指定範圍即足以開始 M1 ETL；不需再擴張產品需求。
