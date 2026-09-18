# Taiwan Clinical Trial Radar — 規格 v0.5（consolidated）

> **這是唯一具規範效力的規格。** `Taiwan-Clinical-Trial-Radar-spec.md` v0.1 與本檔 v0.2–v0.4 均降為歷史文件，**不再具 normative 效力**。
> 依據：2026-09-18 dataset 205 實測 ＋ Codex 三輪覆審（`plan-review-r1/r2/r3.md`、`plan-verdict-r1/r2/r3.md`）＋ A 群 fixture 反驗（`fixture-findings-a.md`）。
> 狀態：**十項動工前契約已封存。** 下一步不是第四輪 prose 覆審，而是 B 群 fixture ＋ 最小 artifact 樣本，實證這些契約可實作。

---

## 1. 目標

台灣藥品臨床試驗檢索站。把 TFDA dataset 205 轉成可搜尋、可篩選、可追溯資料日期的靜態網頁，回答：

1. 台灣有哪些經衛福部審查的藥品臨床試驗？
2. 某疾病、試驗名稱、protocol number 或申請者涉及哪些試驗？
3. 試驗期別、規模、期間、預計收案數、主要評估指標與納入／排除條件為何？
4. 公開資料更新到何時、該去哪裡確認最新狀態？

使用者：臨床藥師、醫師、CRC／研究護理師、研究者。單次查詢情境。

## 2. 非目標

- **dataset 206–209 的任何 join**（v0.1 §3.1／§5.1／§8／§9／§14／§18 中所有 206–209、`linkageStatus`、`linkage-report`、`verify_linkage.py`、寄信詢問 TFDA 的要求**一併作廢**）。
- 受試者適格性判定；病歷、病況自由文字或任何病患資料輸入。
- 招募狀態顯示或推論。**不保留 feature flag。**
- AI 生成試驗摘要、療效比較、試驗品質評分、risk of bias、證據等級。
- 試驗優先排序或「最適合」推薦。
- 有方向性的版本 diff（`A → B` 箭頭）。
- **自動合併近似的 protocol 寫法**（§6.2.1）。
- **從約略值推論數字**（`約400` → 400、`至少480` → 480 等，§6.6.3）。
- 醫院 geocoding 與「附近正在招募」。
- 搜尋字串、IP 或任何 analytics 蒐集。
- PI 姓名的人物績效排行。
- Service worker／PWA。

## 3. 資料來源與平台限制

實測（2026-09-18）：

| 項目 | 值 |
|---|---|
| 端點 | `https://data.fda.gov.tw/data/opendata/export/205/csv` → `200`、`application/zip` |
| 內含檔 | `205_2.csv`，UTF-8 with BOM |
| ZIP／解壓後 | 42 MB／166,450,190 bytes |
| 列數／欄數 | 18,736／16 |
| 不同 protocol | 5,882（另 6 列 protocol 為空）→ 5,888 個 Trial |
| 最新 cohort 紀錄數 | 6,921 |
| `latestAmbiguous` 為 true 的 Trial | **143**（實測全量跑過模型確認） |
| `dateUnknown` 為 true 的 Trial | **0** |
| `資料更新時間` | 全部合法 `YYYY/MM/DD`，零空值、零未來日期，範圍 2024/12/20 – 2026/08/17 |
| `試驗預計執行期間` | 格式全合法，但 **7 列 end < start** |
| 控制字元 | **無 U+001F**；58,140 個欄位含換行、10,725 個含 TAB |
| 單列最長文字 | `納入條件`／`排除條件` 22,490；`試驗目的` 5,512；`主要評估指標` 5,166 |

16 欄（來源順序，此順序為 canonical 欄位順序）：`臨床試驗申請者`、`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`、`TFDA收文號`、`資料更新時間`。

平台限制：純靜態，無後端／DB／認證／runtime API；前端不得解析 166 MB CSV；`data.fda.gov.tw` 從 GitHub Actions 直抓可行不需 proxy（對 Google IP 回 500 只適用 Apps Script，與 `consumer.fda.gov.tw` 的境外 IP TLS 切斷亦不同）；GitHub Actions 月排程 + `workflow_dispatch`；部署 Cloudflare Pages。

## 4. 來源沒有執行狀態

官方資料集頁面列有 `執行狀態`，實際 16 欄沒有。不提供招募／執行狀態的篩選、標章或排序維度，**不保留旗標**。來源若日後新增此欄，走 §9.5 的 schema 變更與規格修訂流程。

**TFDA 審查通過 ≠ 目前正在招募；試驗使用 ≠ 藥品已獲 TFDA 上市核准。** 這兩句是 §10 免責的必要內容。

## 5. 架構決策

**5.1 只做 dataset 205。** 206–209 無可驗證 trial identifier，筆數不一致（512,140／27,774／28,800）。代價是永久放棄藥品、機構、ICD-9 關聯，接受。

**5.2 部署 Cloudflare Pages。** 不選 GH Pages：`liangrxdev.github.io` 多工具共用 origin，Cache Storage 不依 SW scope 隔離，既有專案已踩過跨 repo 互刪快取。

**5.3 選型。** Python 3.12+（標準 `csv` + dataclass／Pydantic 驗證）；TypeScript（Vite）；pytest + Vitest + Playwright；純邏輯抽為可 import 函式供無網路 mock 測試。

## 6. 資料模型

### 6.0 字元集與正規化的基礎定義（其餘各節引用）

| 名稱 | 定義 |
|---|---|
| **ASCII 英數字元** | 僅 `A–Z`、`a–z`、`0–9`。**不含**任何非 ASCII 字元 |
| `nfkc(s)` | Unicode NFKC 正規化 |
| `identityNormalize(s)` | `nfkc(strip(s))` 後轉大寫。**不做**標點移除、不做內部空白壓縮、不做前後綴剝離 |
| `looseKey(s)` | `nfkc(s)` 後移除**所有非 ASCII 英數字元**，再轉大寫。**僅用於偵測近似 protocol，絕不用於收斂** |
| `conflictText(s)` | `nfkc(s)` 後移除**全部空白**（含全形空白）。用於 §6.4 文字欄位的比較鍵 |
| `searchNormalize(s)` | `nfkc(strip(s))` → casefold → 內部連續空白壓為單一空格。見 §8.1 |

**「ASCII 英數字元」必須明定，否則實作會相反。** Python 的 `"系統測試".isalnum()` 回傳 **`True`**（中文被視為字母）——若以 `isalnum()` 實作 §6.2.2，`系統測試` 將**不會**被標記為 `protocolNonIdentifier`，與意圖完全相反。判定一律先 `nfkc` 再套 ASCII 字元集合。

### 6.1 命名

來源列稱 **SourceRecord（審查紀錄）**。18,736 列對應 5,882 protocol，2,821 個 protocol 有多列（最多 23 列），其中只有 61 組 16 欄全同。

「一列 = 某一版試驗計畫書」是推論不是事實；資料只證明同 protocol 有多筆審查紀錄。規格與 UI 一律用「審查紀錄」，**不稱「第 N 版」**。

### 6.2 Identity normalization（與搜尋正規化分離）

主鍵一律用 `identityNormalize`（§6.0）。實測對 5,882 個 protocol 產生 **0 個碰撞**。

兩個不同 raw protocol 正規化後相同 → 硬失敗 `IDENTITY_COLLISION` 並產出 collision report（內容契約見 §9.8），**不得合併**。（fail-closed 而非保留為不同 Trial：合併會誤配，保留兩個同鍵 Trial 會讓 URL 不唯一，硬失敗使月更新維持 last-known-good。）

`searchNormalize` 與 `identityNormalize` **各自獨立驗證，不得共用實作**。

#### 6.2.1 近似 protocol 不自動合併，但必須揭露

§6.2 不剝標點、不壓空白，代價是**同一個試驗的不同寫法會成為兩個 Trial**。實測 18 組（多一個空格、全形括號、括號未閉合、連字號有無、上游刪除標記前綴 `刪_`）。

維持不自動合併（自動合併會誤配，違反寧可漏報不可誤報），但必須：

1. **偵測**：以 `looseKey(protocol)` 分組。**只有當一組含 ≥2 個不同 identity key 時**才輸出 `nearDuplicateGroup`（值為該 loose key）；單一成員為 `null`。
2. `looseKey` 為空字串者（protocol 不含任何 ASCII 英數字元）**不納入**任何 group，否則會把所有非編號值錯歸成一群。
3. **QA report** 列出每個 group 的全部 raw protocol 與 trialId。
4. **UI**：詳情頁顯示「其他寫法近似的計畫書編號」與連結。不自動合併、也不無聲漏掉。

#### 6.2.2 protocol 非識別碼值

實測 protocol 欄位含 7 個不同值、共 9 列不含任何 ASCII 英數字元：`系統測試`、`計畫書編號系統測試`、`臨床試驗計畫初版編號`、`未列編號`、`無`、`科技部研究計畫(申請中)`、`聯亞生技開發股份有限公司`（申請者名稱填錯欄位）。另有含 ASCII 英數字但顯非編號者，如 `計畫書編號123`、`計畫書編號A`、`未列編號。第二版，97/10/3`、`IRB編號：KMUHIRB-F(I)-20200122`。

規則：

- `looseKey(protocol)` 為空字串時（**含 raw 為空字串與空白-only 的情形**），Trial 標記 `protocolNonIdentifier: true`。空 protocol 是這條規則的退化情形，不是例外——兩者語意相同，都是「來源未提供可用編號」。
- **不刪除任何資料。** UI 顯示「來源未提供計畫書編號」，統計歸入「未提供編號」類別，**不得作為 `?protocol=` 別名**。
- **疑似上游測試列**：符合下列任一者單獨計數警示，同樣不自動刪除——
  (a) `臨床試驗申請者` 與 `臨床試驗計畫中文名稱` 皆為空；
  (b) 任一呈現欄位的 `nfkc` 後 casefold 值等於 `test`（實測 `全球預計受試者人數` 與 `台灣預計受試者人數` **各有 9 筆 `TEST`**）；
  (c) protocol 含 `系統測試` 或 `計畫書編號` 字樣。
- QA report 完整列出上述兩類的 raw 值與 trialId。

### 6.3 Canonical serialization 與 ID

**canonical serialization 必須對 16 欄 tuple 一對一。** 作法：對 16 欄的 **raw 值**（已去 BOM、未經任何正規化），依 §3 的 canonical 欄位順序，逐欄輸出 `<UTF-8 位元組長度的十進位 ASCII>` + `U+001F` + `<欄位 UTF-8 位元組>`，欄位之間再以 `U+001F` 分隔。長度前綴使任何欄位內容（含分隔符本身）都不造成歧義。

**額外硬性檢查**：任一欄位含 `U+001F` 時硬失敗 `SOURCE_CONTROL_CHAR`。實測本快照無 U+001F，故此檢查目前恆不觸發，但不得省略。

#### 6.3.1 identity key

- `identityNormalize(protocol)` **非空** → `"P:" + identityNormalize(protocol)`
- `identityNormalize(protocol)` **為空**（含 raw 空字串與空白-only） → `"H:" + sha256hex(canonicalSerialization) + "#" + k`

**判定依據是 `identityNormalize` 後是否為空，不是 raw 是否為空。** 空白-only 的 protocol 走 `H:` 分支，raw 仍完整保留供稽核。

#### 6.3.2 ordinal 一律存在，從 `#0` 起

`k` 為**同一內容雜湊內的出現序號，一律存在且從 `0` 起**，即單筆也寫 `#0`。

理由：若單筆不帶後綴，日後上游新增一筆內容相同的列時，原本的 `H:x` 會變成 `H:x#0`，URL 失效。ordinal 恆存在使 ID 形狀**不隨鄰居增減而改變**。

`k` 由 canonical serialization 排序後配置，**不依輸入列序**。這些列逐位元相同，序號分配在內容上不可區分，輸出仍確定。

**同一規則套用於 `recordId`**：duplicate ordinal 亦一律存在、從 `#0` 起。

#### 6.3.3 ID 與 shard

- **`trialId`** = `"t" + sha256hex(identityKey)[:16]`
- **`recordId`** = `trialId + "r" + sha256hex(canonicalSerialization)[:16] + "#" + k`
- **shard key** = `trialId` 的**第 2–3 個字元**（即 sha256 的前 2 hex；`trialId` 第 1 字元固定為字面 `t`），值域 `00`–`ff`

#### 6.3.4 三層碰撞偵測，全部 fail-closed

| 層級 | 條件 | error code |
|---|---|---|
| identity key | 不同 raw protocol → 相同 identity key | `IDENTITY_COLLISION` |
| trialId | 不同 identity key → 相同 trialId（16-hex 截短碰撞） | `ID_TRUNCATION_COLLISION` |
| recordId | 不同 canonical serialization → 相同 recordId | `ID_TRUNCATION_COLLISION` |

實測 16,328 個不同紀錄的 16-hex 截短 **0 碰撞**。仍須偵測。

#### 6.3.5 ID 穩定性界限（須寫進 README）

只保證**對相同來源快照穩定**。上游重排、增刪或修改欄位時 ID 可能變動；不得宣稱 ID 跨快照代表同一實體。

### 6.4 Trial 結構、比較鍵與同日衝突

#### 6.4.1 呈現欄位（封閉集合，13 欄）

16 欄扣除 `臨床試驗計畫書編號`（已是主鍵）、`TFDA收文號`（非呈現用途、且 2,788 個重複鍵）、`資料更新時間`（cohort 的判定依據本身）：

`臨床試驗申請者`、`臨床試驗計畫中文名稱`、`臨床試驗期別`、`本臨床試驗規模`、`試驗目的`、`試驗預計執行期間起`、`試驗預計執行期間迄`、`全球預計受試者人數`、`台灣預計受試者人數`、`適應症中文`、`主要評估指標`、`納入條件`、`排除條件`。

#### 6.4.2 semantic comparison key（依欄位型別與語意狀態）

衝突判定**不是**單純比較正規化 raw，也**不是**單純比較 typed value。兩者都會出錯：

- 只比正規化 raw → 14 組僅差空白／全半形者被誤判為衝突（假警報，會訓練使用者忽略警示）。
- 只比 typed value → `""`（`numericMissing`，UI 顯示「未提供」）與 `"-5"`（`numericImplausible` warning，須顯示 raw 與異常提示）的 typed 皆為 `null`，判為不衝突並任取一筆 raw 會**隱藏異常**，或把正常缺值呈現成負數 warning。後者是更糟的誤導。

因此定義 **semantic comparison key**：

| 欄位型別／語意狀態 | 比較鍵 |
|---|---|
| 文字欄位 | `conflictText(raw)` |
| 合法數值（單值） | `("int", typed)` |
| 合法數值（範圍，§6.6.3） | `("range", min, max)` |
| 數值缺值 | `("numericMissing",)`——只有同為缺值才相等 |
| 數值無法解析 | `("numericUnparsed", conflictText(raw))` |
| 數值不合理 | `("numericImplausible", conflictText(raw))` |
| 分類 sentinel | `("unprovided",)` |
| 合法分類 | `("cat", canonical typed value)` |
| 日期欄位（可解析） | `("date", ISO 日期)` |
| 日期欄位（不可解析／缺值） | `(旗標名, conflictText(raw))` |

**比較鍵相同即不衝突**，即使 raw 不同。

#### 6.4.3 `rawVariants`：欄位層級旗標

比較鍵相同但 cohort 內該欄位的 **distinct raw value 數 > 1** 時，該欄位的 `flags` 加入 `rawVariants`。

- `rawVariants` 是**欄位層級**，不是 Trial 層級。
- **`rawVariants = true` 不代表衝突**，只表示多個 raw 值映射到同一比較鍵。
- 代表值取 `latestCohort` 中 `recordId` 字典序最小者的 raw。
- **詳情頁須呈現 cohort 中每一筆 SourceRecord 的原始值**，不得只列去重後文字而失去 record 對應。

#### 6.4.4 Trial 結構（方案 B：`recordIds` 移入 shard）

```
Trial（在 trials-index.json 內）
  id                     trialId
  protocolRaw[]          raw protocol 值（identity 正規化後相同者），昇序
  protocolNonIdentifier  bool（§6.2.2）
  suspectedTestRow       bool（§6.2.2 的疑似上游測試列）
  nearDuplicateGroup     loose key 或 null（§6.2.1）
  latestSourceDate       可採計日期的最大值（§6.5）；無可採計日期時為 null
  dateUnknown            bool；latestSourceDate 為 null 時為 true
  latestCohortCount      latestSourceDate 當日的 record 數；dateUnknown 時為全部 record 數
  recordCount            全部 record 數
  latestAmbiguous        latestCohortCount > 1 且呈現欄位（依 §6.4.2 比較鍵）有衝突時為 true
  conflictFields[]       衝突的呈現欄位名，依 canonical 欄位順序
  displayFields          見 §6.4.5
  searchShortLatest      見 §9.3.4
  shard                  shardKey
```

**`recordIds[]` 與 `latestCohort[]` 不放在 trials-index，改放在 shard**（§9.3.5）。

實測依據：18,736 個 recordId 是高熵 hex、壓縮率差，放在 index 內使 `trials-index` 由 **1,236 KiB 膨脹到 1,535 KiB gzip**，而它們**只有詳情頁用得到**。recordId 以 trialId 為前綴，shard 因此可自我描述。

另實測：把搜尋文字也拆成獨立檔**反而更大**（903 + 693 = 1,596 KiB > 1,236 KiB）——拆檔失去跨欄位的壓縮共享。故 `searchShortLatest` 留在 index 內。

index 只留 `recordCount` 與 `latestCohortCount` 兩個計數；§9.3.6 的不變量要求它們**必須等於** shard 內對應清單的長度，否則計數會與 shard 漂移。

#### 6.4.5 `displayFields` 的形狀

```json
"displayFields": {
  "<呈現欄位名>": { "raw": "<string>", "typed": <見 §9.3.3>, "flags": ["<field-scoped 旗標>"] }
}
```

- `raw` 固定為 string（永不為 `null`；來源空值即空字串）。
- `typed` 的型別與 nullability 依欄位，見 §9.3.3。
- `flags` 是**該欄位的**旗標，不是整筆 record 的無歸屬字串。`rawVariants` 放在此處，**不另設 Trial 層級表示**（兩種表示並存會分歧）。
- **衝突欄位在 `displayFields` 中完全省略**，不是給 `{typed: null}`——後者會與「未提供」混淆，而混淆正是本專案最怕的誤導。前端據 `conflictFields` 得知該欄位為衝突，顯示「同日多筆資料不一致，請展開確認」。

#### 6.4.6 `dateUnknown` 與 `latestAmbiguous` 是兩個獨立旗標

| 情形 | `dateUnknown` | `latestAmbiguous` | 卡片 |
|---|---|---|---|
| 單筆最新、日期正常 | false | false | 正常顯示 |
| 同日多筆、比較鍵全同 | false | false | 顯示共同值（可能帶 `rawVariants`） |
| 同日多筆、有衝突 | false | **true** | 衝突欄位省略並標示不一致 |
| 無任何可採計日期 | **true** | 依全部 record 判定 | 顯示「資料日期無法辨識，請查官方來源」；仍顯示無衝突欄位 |

實測 846 個平手組：**689 組（81%）16 欄全同**；**157 組 raw 有差異**，其中 **143 組**依比較鍵仍衝突、**14 組**只差空白或全半形（判不衝突，帶 `rawVariants`）。全量跑過模型確認 `latestAmbiguous` 為 true 的 Trial 恰為 **143 個**、`dateUnknown` 為 **0 個**。

衝突組欄位分布（raw 比較）：`納入條件` 74、`試驗預計執行期間迄` 48、`試驗目的` 40、`主要評估指標` 34、`全球預計受試者人數` 22、`台灣預計受試者人數` 21、`臨床試驗計畫中文名稱` 20、`臨床試驗期別` 3。

`latestAmbiguous=true` 時：詳情頁並列該日全部紀錄並明示**順序未知**；**hash 只用於 cohort 內穩定排序，不宣稱時間先後**，不得以完整度或 hash 推定業務新舊。

（曾考慮的「取非空欄位數最多者」實測幾乎無效：846 組中只唯一決出 5 組。已棄。）

### 6.5 日期規則

#### 6.5.1 `buildDate`

- 型別為 **ISO calendar date**（`YYYY-MM-DD`），**不是 timestamp**。
- **可注入**參數；測試一律注入固定值（凍結 fixture 的必要條件）。
- production 值以 **`Asia/Taipei` 日曆日**產生，**不得取決於 GitHub Actions runner 的 UTC 日期**——runner 為 UTC，台灣時間 08:00 前 UTC 仍是前一天，會使「未來日期」判定差一天。
- 同一次 build 中**所有 record 使用同一個 `buildDate` 值**。

#### 6.5.2 `資料更新時間`

**可採計日期**：`nfkc(strip(raw))` 後符合 `^\d{4}/\d{2}/\d{2}$`、可解析為實際日曆日、且**不晚於 `buildDate`**。實測 18,736 筆全部符合。

| 情形 | 處置 |
|---|---|
| 格式不符或非實際日曆日 | 不可採計；record 保留、標記 `dateUnparsed`、原值照顯示、記入 QA report |
| 空值 | 不可採計，標記 `dateMissing` |
| **晚於 `buildDate`** | **不可採計**，標記 `dateFuture`、warning、原值照顯示，且**排除於 `latestSourceDate` 選擇與全站 `sourceUpdatedAt`** |
| 某 Trial 無任何可採計日期 | `latestSourceDate=null`、`dateUnknown=true`、`latestCohort` = 全部 recordId |

**未來日期不得支配卡片。** 單筆打錯的 `2099/01/01` 若參與 latest 選擇，會永久遮蔽該試驗所有正常紀錄並讓卡片以它的值代表 Trial——那是最高風險（誤導）。該紀錄仍出現在歷史並標記「日期超出合理範圍」。實測目前 0 筆。

邊界：日期**等於** `buildDate` 為可採計；`buildDate + 1 日` 為 `dateFuture`。

全站 `sourceUpdatedAt` 只由可採計日期計算；被排除的原值記入 QA report。

#### 6.5.3 `試驗預計執行期間起／迄`

- 接受格式同 §6.5.2（`^\d{4}/\d{2}/\d{2}$` 且為實際日曆日）。實測兩欄格式**目前 100% 合法**。
- 任一端不可解析或為空 → 該端 typed 為 `null`，標記 `periodStartUnparsed`／`periodEndUnparsed`（或 `...Missing`），raw 照顯示。
- **只有兩端皆可解析時才比較順序。** `end < start`（實測 **7 列**）→ warning `periodEndBeforeStart`，兩值都原樣顯示並標記「期間起迄順序異常」，**不自動交換、不隱藏**。
- 此兩欄**不套用** `buildDate` 上限——試驗預計執行到未來是正常的。

### 6.6 sentinel、分類與數值解析

#### 6.6.1 分類欄位

`臨床試驗期別`、`本臨床試驗規模`。

- 合法值：期別 7 個（`Phase Ⅰ`／`Ⅱ`／`Ⅲ`／`Ⅳ`／`Phase Ⅰ,Phase Ⅱ`／`Phase Ⅱ,Phase Ⅲ`／`其他`）；規模 3 個（`多國多中心`／`台灣單中心`／`台灣多中心`）。
- `"0"`（實測各 156／266 筆）→ typed `null`、旗標 `categoricalUnprovided`，**raw 保留於 SourceRecord**；UI 顯示「未提供」，**不進篩選選單、不進 facet**。
- 其他非合法值 → typed `null`、旗標 `categoricalUnknown`、warning、raw 照顯示。

#### 6.6.2 文字欄位

`N/A`／`NA`／`""` **互相可區分**（實測 `排除條件` 469／67、`納入條件` 42、`主要評估指標` 61）。保留原文，UI 原文照顯示，QA report 分別計數。**不得塌成同一值。**

#### 6.6.3 數值欄位的 lexical grammar 與解析順序

`全球預計受試者人數`、`台灣預計受試者人數`。

**解析一律先 `nfkc(strip(raw))`**，然後**依下列順序**比對，第一個命中者決定結果（固定順序使每個值只有一個分類）：

| 序 | 條件（對 `nfkc(strip(raw))`） | typed | 旗標 | UI | 分級 |
|---:|---|---|---|---|---|
| 1 | 空字串 | `null` | `numericMissing` | 「未提供」 | 正常 |
| 2 | `^\d+$`（**不接受**正負號、千分位、內部空白；**接受前導零**） | 該整數 | 為 0 時加 `sourceZero` | 數字；為 0 時顯示「0（來源填 0）」，**不得**呈現為「確定沒有受試者」 | 正常 |
| 3 | `^\d+\s*(?:[-~～〜–—]\|至)\s*\d+$` 且 `min ≤ max` | `{min, max}` | `numericRange` | 顯示 **raw 原文**，篩選以區間重疊判定 | 正常 |
| 4 | 同上但 `min > max` | `null` | `numericRangeInvalid` | 顯示 raw + 「數值區間順序異常」 | **warning** |
| 5 | `^-\d+$` | `null` | `numericImplausible` | 顯示 raw + 「數值超出合理範圍」 | **warning** |
| 6 | 其他非空 | `null` | `numericUnparsed` | 顯示 raw + 「來源以文字描述人數」 | **warning** |

**前導零**：實測有 3 筆（`026`、`024`、`08`）。typed 為 26／24／8，但**raw 一律顯示**——顯示 typed 就是改寫來源。

**可表示範圍**：typed 整數（含 range 的 min／max）必須落在 `0 … 2^53-1`（JSON number 可精確表示的整數上限）。超界 → typed `null`、旗標 `numericOutOfRange`、warning、raw 照顯示，**不得輸出失真數字**。實測兩欄最大值為 100,000 與 4,236，目前無任何值超界。

**只解析嚴格範圍，不從約略值推論。** 實測回收量：`台灣預計受試者人數` **1,347／1,705** 個非純整數值（7.2% of 全部 18,736）、`全球預計受試者人數` **356／766**，且 **0 筆 `min > max`**。維持 `numericUnparsed` 的包括 `約400`、`至少480`、`148(最多266)`、`約26-30(競爭)`、`240=90+150`、`接受本品治療之病人`，以及 `ˋ40`（注音符號 `ˋ` U+02CB 誤打，9 筆）。

理由：把 `20-40` 讀成區間是**結構解讀**；把 `約400` 讀成 400 會丟掉「約」，那是**推論**，與專案「嚴格區分客觀資料與推論」的紀律衝突（§2 非目標）。

實測組成（`台灣預計受試者人數`／`全球預計受試者人數`）：純整數 16,858／17,792；範圍 1,340／336；約略 159／191；其他 179／144；`NA` 23／80；千分位與界限 4／15；空 173／178。

三類 sentinel 均保留 raw 值可稽核。

## 7. 呈現層

### 7.1 各功能使用哪一層

| 功能 | 資料層 |
|---|---|
| 結果卡欄位 | `displayFields` ＋ `latestAmbiguous`／`dateUnknown`／`protocolNonIdentifier` 標記 |
| 篩選 | `displayFields` 的 typed 值。衝突欄位的 trial 在該維度歸入「同日多筆不一致」分組，**不任取一值** |
| 統計卡 | 以 **Trial** 為分母並明寫「試驗」；衝突、sentinel、`protocolNonIdentifier` 各歸入明確的「未提供／不一致／未提供編號」類別。另可提供以「審查紀錄」為分母的次要統計，須明確標示分母 |
| 搜尋 | 依使用者選定的 **scope**（§8.5），預設為「最新 cohort × 短欄」 |
| 詳情頁 | shard 內該 Trial 的全部 record |

### 7.2 命中標示

- 命中紀錄有可採計日期 → 標示該日期；命中來自非最新 cohort 時，卡片標示「命中來自 YYYY/MM/DD 的審查紀錄」。
- 命中紀錄**無可採計日期** → 標示「資料日期不明」，**不得偽造成合法日期**、不得省略標示。
- **不得**把非最新紀錄的命中值歸到最新紀錄上顯示。
- 多欄同時命中時須列出**全部**命中欄位。

### 7.3 版本歷史：不做方向性 diff

依日期分組列出完整來源紀錄，使用者點選查看原文；日期之間可標示「哪些欄位存在不同值」，**不產生方向箭頭**；同日多筆明示「順序未知」；無可採計日期者置末並標示「資料日期不明」。

理由：日期平手時沒有可靠順序，`20 → 30` 的箭頭可能寫反（實測 21 組人數衝突正是同日平手）。

### 7.4 URL state schema

canonical query string：**只輸出非預設值的參數，依本表順序排列，值以 `encodeURIComponent` 編碼。**

| 參數 | 值域 | 預設 | 備註 |
|---|---|---|---|
| `q` | 字串 | 無 | 搜尋字串（raw，不預先正規化） |
| `trial` | trialId | 無 | 詳情頁 canonical 入口 |
| `protocol` | raw protocol | 無 | 別名；以 **`identityNormalize` 後**比對，命中後 client-side 導向 canonical `?trial=`；`protocolNonIdentifier` 的值不接受 |
| `phase` | 多值 | 無 | 同維度多選 |
| `scale` | 多值 | 無 | 同維度多選 |
| `applicant` | 多值 | 無 | 值為 raw 申請者字串 |
| `enroll` | bucket id 多值 | 無 | 見 §8.4 |
| `period` | `YYYY-MM-DD..YYYY-MM-DD` | 無 | 試驗預計執行期間 |
| `updated` | `YYYY-MM-DD..YYYY-MM-DD` | 無 | 資料更新時間 |
| `fields` | `short` \| `all` | `short` | 搜尋欄位 scope（§8.5） |
| `history` | `latest` \| `all` | `latest` | 搜尋歷史 scope（§8.5） |

- **重複參數**：同維度多值以重複參數表達（`phase=X&phase=Y`），值依字典序排列後輸出。
- **未知參數**：忽略但保留於 URL 不改寫。
- **無效值** → 顯示明確訊息與回搜尋入口，**不得空白頁、不得靜默回首頁、不得靜默丟棄該條件**。
- **scope 必須編碼進 URL**，否則分享的連結重現不出同一結果集。

## 8. 搜尋規格

### 8.1 search normalization

`searchNormalize`（§6.0）。**不做**標點移除、不做連字號正規化。

（註：NFKC 會把全形數字折成半形，這是**等價**而非誤命中。）

### 8.2 matching operator

- query 先套 `searchNormalize`，再以**空白切分**為 terms。
- 每個 term 對正規化後的欄位文字做 **substring 比對**（中文無空白，token 化不可行）。
- **空查詢或純空白查詢 → 不執行搜尋**，顯示瀏覽狀態（全部 Trial 依 `latestSourceDate` 降序），不視為「命中全部」。
- 不做 prefix-only、不做模糊比對、不做同義詞擴展。

### 8.3 多詞語意

每個 term 只要命中**任一**在 scope 內的可搜尋欄位即該 term 成立；**同一個 SourceRecord 內全部 term 成立**才算該 record 命中（**record 層 AND，欄位層 OR**）。

**兩個 term 分別命中同一 Trial 的不同 SourceRecord 時不算命中**——那是 Trial 層 AND，會大幅多報。§9.3.4 的 `searchShortLatest` 逐-record shape 就是為了讓這條可被保留與驗證。

### 8.4 篩選維度、值域與組合語意

| 維度 | typed value | null／衝突歸類 |
|---|---|---|
| `phase` | §6.6.1 的 7 個合法值 | `categoricalUnprovided`／`categoricalUnknown` → 未提供；衝突 → 不一致 |
| `scale` | §6.6.1 的 3 個合法值 | 同上 |
| `applicant` | raw 申請者字串 | 空 → 未提供；衝突 → 不一致 |
| `enroll` | `台灣預計受試者人數` bucket：`0`（等於 0）、`1-10`、`11-30`、`31-100`、`101-`；**閉區間** | 見下 |
| `period` | `試驗預計執行期間起` ≤ 區間末 且 `迄` ≥ 區間首（**重疊**語意） | 任一端 typed `null` → 未提供 |
| `updated` | `latestSourceDate` 落於閉區間內 | `dateUnknown` → 未提供 |

**`enroll` 的範圍值語意**：typed 為 `{min, max}`（`numericRange`）時，只要 `[min, max]` 與 bucket 區間**有交集**即命中該 bucket——因此一筆 `20-40` 會同時出現在 `11-30` 與 `31-100`。卡片顯示 raw 原文（`20-40`），使用者看得出它是區間而非單值。其餘旗標（`numericMissing`／`numericUnparsed`／`numericImplausible`／`numericRangeInvalid`／`numericOutOfRange`）→ 歸「未提供」。

**組合語意**：**同維度多選 = OR，跨維度 = AND。** 「未提供」與「不一致」是每個維度的可選值，選中時只回傳該類 trial。

篩選**不存在**招募／執行狀態維度——filter schema、DOM 控制項、URL parser、輸出 state 四處皆不得有。

### 8.5 搜尋 scope 分層（實測驅動）

v0.3 曾同時要求「搜尋涵蓋全部歷史紀錄」「7 個可搜尋欄位」「初始 payload ≤1.5 MB gzip」——實測三者不可能同時成立：

| 索引範圍 | gzip |
|---|---:|
| 最新 cohort × 5 短欄 | 601 KiB |
| 全部紀錄 × 5 短欄 | 1,649 KiB |
| 最新 cohort × 2 長欄 | 2,044 KiB |
| 最新 cohort × 7 欄 | 2,607 KiB |
| 全部紀錄 × 2 長欄 | 5,389 KiB |
| 全部紀錄 × 7 欄 | 6,958 KiB |

因此搜尋分為兩個獨立 scope 維度，**預設為最小者**：

- **短欄（`fields=short`，預設）**：`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗申請者`、`適應症中文`、`TFDA收文號`
- **全欄（`fields=all`）**：另加 `試驗目的`、`主要評估指標`
- **最新（`history=latest`，預設）**：只搜 `latestCohort` 內的 record
- **全部（`history=all`）**：搜全部 record

索引載入：`short`+`latest` 併入 `trials-index`（§9.3.4）不需額外載入；`all`+`latest` 載 `search-long-latest` 2,044 KiB；`short`+`all` 載 `search-short-all` 1,649 KiB；`all`+`all` 另加 `search-long-all` 5,389 KiB。

**UI 硬性要求**（避免把預設縮小變成靜默漏報）：擴大 scope 的兩個控制項必須在搜尋結果區可見，不得藏在設定或選單深處；切換前顯示需下載的大小（取自 `manifest.files[*].gzipBytes`，**不得前端寫死**）；結果區持續顯示目前 scope；零結果時提示可擴大的 scope 與其大小；載入失敗則退回上一個 scope 並說明，不得靜默維持舊結果集。

## 9. ETL、發布與輸出契約

### 9.1 管線

```
下載至 temp（正式 artifact 不動）
→ HTTP 驗證 → ZIP 完整性 → UTF-8-BOM 解碼 → 16 欄欄名與順序、列寬驗證
→ 控制字元檢查 → 正規化（保留 raw）→ identity 收斂為 Trial + SourceRecord
→ 三層碰撞偵測 → 計算 datasetVersion（§9.3.2）→ 產生全部 artifact 至 staging
→ 計算 artifactDigest、驗證 referential integrity 與 inventory
→ promotion（§9.2）
```

### 9.2 發布契約

v0.3 曾聲稱「git commit 是原子發布邊界」，這只對了一半。commit 對 repository tree 確實是原子快照，但不能保證 (a) 中途崩潰時 working tree 完整；(b) 瀏覽器或 CDN 不跨版本混用固定 URL 的檔案。

#### 9.2.1 保證下在正確的邊界

CI runner 的 working tree 是**用後即棄、無任何讀者**。因此保證為：

> **被 commit 並 push 出去的 tree 永遠是完整一致的；不存在部分發布的 commit。**

**不聲稱** working tree 在中途失敗後「整體等於舊版」——逐檔替換做不到，而 commit 的原子性不回復 working tree。

作法：全部 artifact 先寫進 staging 目錄並通過整體驗證；替換 `public/data/`、`git add -A`、`git commit` 收攏為管線**最後三個步驟**；任一步失敗即非零 exit，runner 隨即丟棄。

#### 9.2.2 跨檔版本綁定

- `manifest.json` 是**唯一固定 URL**，`Cache-Control: no-cache`。
- 其餘全部檔案帶內容雜湊，`Cache-Control: public, max-age=31536000, immutable`。
- manifest 內含 `datasetVersion` 與所有檔案的雜湊路徑；**一次前端資料載入只能解析同一個 manifest 版本**。
- 每個非 manifest 檔案的 top-level 都含 `datasetVersion`；前端載入後**斷言等於 manifest 的值**，不符即 fail-closed，顯示「資料版本不一致，請重新載入」，**不得混用**。
- 舊雜湊檔案留在使用者快取中但已無人引用，不需清理。

#### 9.2.3 部署鏈

- Cloudflare Pages 以 `main` 的 commit SHA 建置；該 commit 即 build 輸入的唯一來源。
- 部署啟用成功後該版本才是 authoritative；啟用失敗時**前一個成功部署仍為 authoritative**，資料不回退、不混合。
- 部署失敗須產生通知；下一次月更新的 baseline 仍以「最後一個成功發布快照」為準。

### 9.3 輸出契約

#### 9.3.1 檔案清單

```
public/data/
  manifest.json                        固定 URL，不帶雜湊
  trials-index.<h>.json
  stats.<h>.json
  search-short-all.<h>.json            全部紀錄 × 5 短欄（按需）
  search-long-latest.<h>.json          最新 cohort × 2 長欄（按需）
  search-long-all.<h>.json             全部紀錄 × 2 長欄（按需）
  records/<shard>.<h>.json             只輸出非空 shard
qa/
  schema-report.json
  quality-report.json
  collision-report.json                僅在碰撞時產生
```

`<h>` = 該檔案 **logical payload** 的 `sha256hex` 前 **16 hex**（演算法與長度在此封存）。

`records/` **只輸出非空 shard**（不固定產生 256 個）。

#### 9.3.2 `datasetVersion` 與 `artifactDigest`（解開循環定義）

v0.4 同時要求「每個非 manifest 檔案內含 `datasetVersion`」與「`datasetVersion` = 這些檔案**最終位元組** digest 的前 16 hex」。檔案位元組包含 `datasetVersion` → **循環，一般情況無固定點**，照文字寫不出合規 artifact。

分離為兩個概念：

**`datasetVersion`** — 由 **logical payload** 計算，該 payload **不含** `datasetVersion` 欄位本身：

1. 對每個非 manifest 輸出檔，取其 logical payload = 該檔 JSON 物件**移除 top-level `datasetVersion` 鍵之後**，以 canonical JSON 序列化（鍵依字典序、無多餘空白、UTF-8、不轉義非 ASCII）。
2. 對每個檔案計算 `sha256(logical payload bytes)`，取 **hex 字串**。
3. 依**邏輯檔名**（不含 `<h>`，如 `trials-index.json`、`records/ab.json`）字典序排序，將各檔的 `"<邏輯檔名>" + ":" + <sha256 hex>` 以 `"\n"` 連接。
4. `datasetVersion` = 該連接字串的 `sha256hex` 前 16 hex。

**串接的是 hex 字串而非 raw bytes，且納入邏輯檔名**（避免不同檔案內容互換而 digest 不變）。**不納入** `<h>`（它由 payload 導出，納入會再度形成循環）。

**`artifactDigest`** — 待 `datasetVersion` 寫入最終檔案後，對**最終檔案位元組**計算，供完整性驗證：

1. 依**實際發布路徑**（含 `<h>`）字典序排序 `manifest.files` 的全部路徑。
2. 將各檔的 `"<發布路徑>" + ":" + sha256hex(檔案位元組)` 以 `"\n"` 連接。
3. `artifactDigest` = 該連接字串的完整 `sha256hex`（64 hex），寫入 `manifest.artifactDigest`。
4. **不含** `manifest.json` 自身。

#### 9.3.3 typed 值的封閉型別表

| 欄位 | typed JSON 型別 | nullable |
|---|---|---|
| `臨床試驗申請者` | string | 是（空字串視為 null typed） |
| `臨床試驗計畫中文名稱` | string | 是 |
| `臨床試驗期別` | string（§6.6.1 的 7 個合法值之一） | 是 |
| `本臨床試驗規模` | string（3 個合法值之一） | 是 |
| `試驗目的` | string | 是 |
| `試驗預計執行期間起` | string（`YYYY-MM-DD`） | 是 |
| `試驗預計執行期間迄` | string（`YYYY-MM-DD`） | 是 |
| `全球預計受試者人數` | integer 或 `{min:integer, max:integer}` | 是 |
| `台灣預計受試者人數` | integer 或 `{min:integer, max:integer}` | 是 |
| `適應症中文` | string | 是 |
| `主要評估指標` | string | 是 |
| `納入條件` | string | 是 |
| `排除條件` | string | 是 |
| `資料更新時間` | string（`YYYY-MM-DD`） | 是 |
| `TFDA收文號` | string | 是 |

**field-scoped 旗標的封閉集合**：`categoricalUnprovided`、`categoricalUnknown`、`numericMissing`、`sourceZero`、`numericRange`、`numericRangeInvalid`、`numericImplausible`、`numericUnparsed`、`numericOutOfRange`、`dateMissing`、`dateUnparsed`、`dateFuture`、`periodStartMissing`、`periodStartUnparsed`、`periodEndMissing`、`periodEndUnparsed`、`rawVariants`。

**record-level 旗標**（與 field-scoped 分開，不得混在同一陣列）：`periodEndBeforeStart`、`suspectedTestRow`。

#### 9.3.4 `searchShortLatest` 的逐-record shape

```json
"searchShortLatest": [
  { "r": "<recordId>", "f": ["<protocol>", "<titleZh>", "<applicant>", "<indicationZh>", "<receiptNo>"] }
]
```

- **每一筆 latest-cohort record 保留獨立 `recordId` 與五欄陣列。**
- `f` 的順序固定為：`臨床試驗計畫書編號`、`臨床試驗計畫中文名稱`、`臨床試驗申請者`、`適應症中文`、`TFDA收文號`。
- 值為 `searchNormalize` 後的文字。
- **不得跨 record 合併文字**——合併後兩個 term 可能分別命中不同 record，違反 §8.3 的 record 層 AND，且違反方式是靜默多報。

#### 9.3.5 各檔 schema

**`manifest.json`**（全部欄位 required）：

```json
{
  "schemaVersion": 1,
  "datasetVersion": "<16 hex>",
  "artifactDigest": "<64 hex>",
  "sourceDatasetId": 205,
  "sourceUpdatedAt": "YYYY-MM-DD | null",
  "fetchedAt": "<ISO-8601>",
  "builtAt": "<ISO-8601>",
  "buildDate": "YYYY-MM-DD",
  "sourceSha256": "<64 hex>",
  "trialCount": 5888,
  "recordCount": 18736,
  "bootstrap": false,
  "files": {
    "trialsIndex":      { "path": "trials-index.<h>.json", "bytes": 0, "gzipBytes": 0 },
    "stats":            { "path": "stats.<h>.json", "bytes": 0, "gzipBytes": 0 },
    "searchShortAll":   { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "searchLongLatest": { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "searchLongAll":    { "path": "...", "bytes": 0, "gzipBytes": 0 },
    "recordShards":     { "<shard>": { "path": "records/<shard>.<h>.json", "bytes": 0, "gzipBytes": 0 } }
  }
}
```

`files[*].gzipBytes` 是 §8.5 的 UI 顯示下載大小的來源，**不得在前端寫死**。

**`trials-index.<h>.json`**：`{ "datasetVersion": "<16 hex>", "trials": [ /* §6.4.4 的 Trial，依 trialId 昇序 */ ] }`

**`stats.<h>.json`**：

```json
{
  "datasetVersion": "<16 hex>",
  "denominators": { "trials": 5888, "records": 18736 },
  "facets": {
    "<name>": {
      "denominatorKind": "trials",
      "buckets": [ { "value": "<string>", "count": 0 } ],
      "unprovided": 0,
      "conflicted": 0
    }
  }
}
```

每個 facet 的 `buckets` 計數 + `unprovided` + `conflicted` **必須等於** `denominators.trials`。（註：`enroll` 因區間重疊可跨 bucket，故 `enroll` **不列為 facet**，只作篩選維度；facet 僅含互斥維度。）

**搜尋索引檔**：`{ "datasetVersion", "fields": [...], "records": [ { "r": "<recordId>", "t": "<trialId>", "d": "YYYY-MM-DD | null", "f": ["<正規化文字>"] } ] }`。`f` 順序對應 `fields`。`d` 為 `null` 表示該 record 無可採計日期（供 §7.2 標示「資料日期不明」）。

**`records/<shard>.<h>.json`**：

```json
{
  "datasetVersion": "<16 hex>",
  "trials": {
    "<trialId>": { "latestCohort": ["<recordId>"], "recordIds": ["<recordId>"] }
  },
  "records": {
    "<recordId>": {
      "raw": { "<16 欄欄名>": "<string>" },
      "typed": { "<16 欄欄名>": <依 §9.3.3> },
      "fieldFlags": { "<欄位名>": ["<field-scoped 旗標>"] },
      "recordFlags": ["<record-level 旗標>"]
    }
  }
}
```

`trials` 對映即方案 B 移出 index 的 `recordIds`／`latestCohort`。

#### 9.3.6 不變量

- **排序 total order**：`trials` 依 `trialId` 昇序；`recordIds` 依（可採計日期降序、不可採計者置末、`recordId` 昇序）；`latestCohort` 依 `recordId` 昇序。
- **referential integrity**：每個 `recordId` 存在於 `trial.shard` 指定的 shard；每個 record 被**恰好一個** Trial 引用；`latestCohort ⊆ recordIds`。
- **計數一致**：`trial.recordCount` == 該 shard 內 `trials[trialId].recordIds` 長度；`trial.latestCohortCount` == `latestCohort` 長度。**（方案 B 的必要防漂移條件。）**
- **inventory**：`manifest.files` 列出的路徑集合 == `public/data/` 中**除 `manifest.json` 外**的全部檔案。
- `datasetVersion` 依 §9.3.2；`artifactDigest` 依 §9.3.2。
- **schemaVersion 升級**：欄位移除、改名、型別或語意變更須 bump；純新增可選欄位不 bump。判準是「舊版前端讀到新資料會做什麼」。

### 9.4 `builtAt` 與「無變動不發布」

`builtAt` = **目前已發布 artifact 的建置時間**，不是本次 workflow 執行時間。

**no-change 比較的排除清單**：`builtAt`、`fetchedAt`、`sourceSha256`、`artifactDigest`。

排除 `sourceSha256` 的理由：上游若以相同資料重新打包，ZIP metadata 或列序變動會改變 source SHA 而正規化資料不變；把它算進比較會每月產生噪音 commit。它是 provenance 不是資料，每次抓取的值記入 QA report 以保留追溯。排除 `artifactDigest` 是因為它由其餘內容導出。

判準：**`datasetVersion` 相同即無變動** → 不發布、不 commit，`builtAt` 與 manifest 均不變。

UI 標籤須與此語意一致：顯示「資料建置時間」，**不得**顯示為「最後檢查時間」。

### 9.5 失敗分類

只接受最終 HTTP 狀態 `200`。content-type 以 `;` 前的 MIME 比對等於 `application/zip`（允許參數）。

| error code | 層 | 觸發 |
|---|---|---|
| `HTTP_STATUS` | transport | 任何非 200 的最終狀態（含 4xx／5xx／429） |
| `HTTP_TIMEOUT` | transport | 連線或讀取逾時 |
| `HTTP_TRUNCATED` | transport | 實收位元組與 `Content-Length` 不符，或下載中斷 |
| `UPSTREAM_ERROR_PAGE` | transport | 200 但 MIME 非 zip |
| `ZIP_CORRUPT` | archive | ZIP 結構或 CRC 失敗 |
| `ZIP_NO_CSV` | archive | ZIP 內無 `.csv` |
| `CSV_DECODE` | decode | UTF-8 解碼失敗 |
| `SOURCE_CONTROL_CHAR` | decode | 欄位含 `U+001F`（§6.3） |
| `SCHEMA_MISMATCH` | schema | 欄名集合或順序與 16 欄不符；**detail 須載明 missing／extra／order 三類差異** |
| `ROW_WIDTH` | schema | 列寬不符超過門檻 |
| `ZERO_ROWS` | content | schema 通過但 0 資料列 |
| `ROWCOUNT_DROP` | content | 驟降超過門檻（§9.6） |
| `IDENTITY_COLLISION` | content | §6.2 的正規化碰撞 |
| `ID_TRUNCATION_COLLISION` | content | §6.3.4 的 trialId／recordId 截短碰撞 |
| `INTEGRITY_DIGEST` | publish | §9.3.6 的不變量失敗（含 referential integrity、計數一致、inventory） |
| `PROMOTION_FAILED` | publish | 替換、`git add`、commit 或 push 失敗 |

**移除了** `SCHEMA_COLUMN_RENAMED`／`MISSING`／`EXTRA` 三個分立 code：欄位 rename 同時滿足 missing 與 extra，無客觀判定方式。改為單一 `SCHEMA_MISMATCH` 攜帶 detail。

**多重失敗的 precedence**（由外而內，先觸發者勝）：`transport` → `archive` → `decode` → `schema` → `content` → `publish`。

每個 code 對應**相異的 exit code**。stderr 訊息只作輔助，**不得以「訊息含某字串」作為測試判定**。

失敗絕不回空陣列。抓取失敗與「官方回覆空集」必須分辨：目前 205 無 sentinel 列，0 資料列一律走 `ZERO_ROWS` 硬失敗。

### 9.6 驟降門檻與 warning 的落點

分母 = 上一個**成功發布快照**的來源資料列數 `prev`；`drop = (prev - cur) / prev`，以有理數比較，**不四捨五入**。

| 條件 | 結果 |
|---|---|
| `drop > 0.20` | 硬失敗 `ROWCOUNT_DROP`，不發布 |
| `0.10 < drop ≤ 0.20` | warning，發布 |
| `drop ≤ 0.10` | 正常發布 |

恰好 `20.0%` 屬 warning（邊界為**嚴格大於**）。首次無 baseline → bootstrap 模式：不做驟降比較，要求列數 ≥1 且 schema 通過，manifest 記 `bootstrap: true`，**不假裝完成比較**。

**所有 warning 必須出現在 `qa/quality-report.json` 的結構化欄位中**（含 code、計數、範例 recordId），不得只印在 log。

### 9.7 併發、baseline 與重入

- `schedule` 與 `workflow_dispatch` **共用同一 concurrency group**，`cancel-in-progress: false`。
- **不得取消已進入 promotion 階段的 run。**
- **baseline 取樣時點為取得發布權之後**：`actions/checkout` 預設取觸發時的 SHA，排隊結束後那已是舊的。取得發布權後必須**顯式 fetch 並 checkout 預設分支最新 tip**，再據此決定 baseline。
- **promotion 前須再次驗證**正式版本自 baseline 取樣以來未變；不符即 fail-closed。

### 9.8 collision report 內容契約

`qa/collision-report.json` 須能**唯一定位**每個 collision group：group 的 identity-normalized 值、全部相關 raw protocol、各自的來源 fingerprint 與 trialId。**空 report 或只含 error code 者視為不合規。**

## 10. 風險權重與免責

風險排序：**誤導 > 資料正確性 > XSS**。寧可漏報不可誤報。

免責須在首頁、結果頁、詳情頁**可見**（可見性定義綁定 §11 G1／G2 的 viewport、尺寸與對比 oracle），且必須表達三項核心性質：

1. 本站**不提供目前招募狀態**；
2. TFDA 審查／試驗使用**不等於藥品已獲上市核准**；
3. 試驗狀態與收案資格**須向官方資料來源、試驗執行機構與醫療專業人員確認**。

## 11. 驗收條件

fixture 為**凍結**資料，不從活資料抽樣；凍結時母體不可縮成剛好等於子集。

> **唯一例外：A8。** 真實的 64 位元雜湊碰撞需約 `2^32` 次運算，不是「凍結的來源資料」而是刻意搜出的人工構造。A8 改以**注入的雜湊替身**驅動偵測分支，見下。

每條驗收都須能回答「什麼弱化實作會通過這條但功能其實是壞的」。

### A. 資料模型與收斂

- **A1** 寫死**每個來源列 fingerprint → trialId 的 group membership**（不只總數）。「不應合併」反例須採用 §6.2 **明確不折疊**的差異——連字號有無（`MK-3475-158` / `MK3475-158`）、空格有無（`9785-CL- 0123` / `9785-CL-0123`）、括號閉合（`ROR-PH-301(APD811-301` / `...301)`）；**不得**使用大小寫或全半形差異（那些會折疊，屬 A7）。另須有「應合併」案例。
- **A2** fixture 每個案例附明確 oracle。**必含**：≥1 個 10 列以上 protocol、≥1 組 16 欄全同純重複、≥2 筆完全相同的空 protocol 列、**≥1 筆空白-only protocol**、≥3 組同日衝突、≥1 組同日但比較鍵全同、≥1 組同日僅空白／全半形差異（須判**不衝突**且帶 `rawVariants`）、≥1 筆 `TFDA收文號="移案BPA"`、≥1 筆收文號重複、≥1 個 `nearDuplicateGroup`、≥1 筆 `protocolNonIdentifier`、≥1 筆 `suspectedTestRow`（含 `TEST` 值型）。**日期異常各 ≥1**：不可解析、空值、未來日期、`buildDate` 當日（須可採計）、`buildDate+1`（須 `dateFuture`）、`試驗預計執行期間` end<start、期間任一端不可解析。**數值各型 ≥1**：`0`、正整數、前導零、空、嚴格範圍、`min>max` 範圍、負數、文字描述、超界值。
- **A3** 對 reverse 與 ≥3 個固定 seed 的排列，外加涵蓋「重複列 × 平手 × 空 protocol」交叉組合的 property invariant：先斷言輸出**檔案 inventory 完全相同**，再逐檔 SHA-256 相同，再斷言每個 tie case 的語意結果相同。
- **A4 反向哨兵** 把同日處置改為「任取 cohort 第一筆為 latest」時，須斷言失敗發生在**指定 tie group 的 `latestAmbiguous` 由 true 變 false**，且 mutation oracle 須涵蓋 `displayFields`、篩選分組與統計輸出。
- **A5** 比對來源 canonical fingerprint 的**完整 multiset 含 multiplicity**。oracle 的 row identity 必須**獨立於 §6.3 的 canonical serialization**，並含分隔符／長度前綴的邊界 fixture。
- **A6** 兩筆完全相同的空 protocol 列須各自取得唯一 ID（`#0`／`#1`）、multiset 完整保留、多排列輸出一致。另須斷言**單筆空 protocol 也帶 `#0`**（§6.3.2）。
- **A7** 注入兩個不同 raw protocol 但 identity 正規化後相同的列 → `IDENTITY_COLLISION` 硬失敗，且 collision report 須符合 §9.8。**空 report 必須使測試失敗。**
- **A8（測試替身例外）** 以**注入的雜湊函式**（刻意截短為極少位元）驅動碰撞偵測分支：測試仍須使用**兩個不同的 identity key**（及 recordId 情形下不同的 canonical serialization），斷言回傳 `ID_TRUNCATION_COLLISION`、**停止發布**、且正式 artifact 不變。
- **A9** `nearDuplicateGroup` 偵測 18 組實測案例；`looseKey` 為空者**不入任何 group**；**單一成員的 group 輸出 `null`**；且偵測用的 loose key **不影響**任何 Trial 的收斂結果（以 A1 的 group membership 再驗一次）。
- **A10** 「ASCII 英數字元」的字元集合：注入 `系統測試`（中文，`isalnum()` 為 `True`）→ 必須標記 `protocolNonIdentifier`。以 Unicode alphanumeric 實作者必須失敗。

### B. ETL 與發布可靠性

- **B1** §9.5 **每一個** error code 各有測試，斷言：(a) 非零且相異的 exit code；(b) 已發布狀態未變（完整檔名集合、每檔 SHA-256、`manifest.files` 指向、`artifactDigest` 均不變）；(c) **無新增正式檔**。content-type 須測 `application/zip;charset=utf-8`（通過）與 `text/html`（失敗）。
- **B2** 每個案例寫死 structured error code 與 layer；**不得**以 stderr 字串判定。另須有**多重異常** fixture 驗證 §9.5 的 precedence。
- **B3** 斷言 CSV schema **已通過後**才因零列失敗，明確回傳 `ZERO_ROWS`，且已發布 digest 不變。
- **B4** 門檻案例須含 `drop` = 0.0／0.10／0.1001／**0.20**／0.2001／整數列數邊界／首次無 baseline。逐案例斷言 warning／success／hard-failure 與**是否發布**，且 warning 須出現在 `qa/quality-report.json` 的結構化欄位。
- **B5** 失敗注入點須涵蓋**每一個正式狀態變更之後**：替換第一個／部分／最後一個 artifact 後、刪除 orphan artifact 途中、`git add` 只含部分變更、commit 失敗、commit 成功但 push 失敗、push 成功但部署啟用失敗，以及**非例外式終止**（SIGTERM／取消）。每個點斷言：**不存在部分發布的 commit**。
- **B6** §9.3.6 的每一條不變量各有獨立反例：record 被兩個 Trial 引用、同一 Trial 重複引用、record 放錯 shard、`latestCohort ⊄ recordIds`、**`recordCount` 與 shard 清單長度不符**、**`latestCohortCount` 與 `latestCohort` 長度不符**、`manifest.files` 與實際檔案集合不符 → 全部須 `INTEGRITY_DIGEST` 硬失敗。
- **B7** 跨版本綁定：注入「manifest 為新版但某 shard 為舊 `datasetVersion`」→ 前端 fail-closed 顯示「資料版本不一致，請重新載入」，**不得**混用渲染。另斷言除 `manifest.json` 外所有檔名都帶內容雜湊、且 manifest 為唯一固定 URL。
- **B8 `datasetVersion` 的可計算性與敏感性** 對同一輸入兩次 build 得到相同 `datasetVersion`（**證明無循環定義**）；任一欄位值改變一個字元 → `datasetVersion` 改變；**兩個檔案內容互換** → `datasetVersion` 改變（證明邏輯檔名已納入）；`artifactDigest` 與 `datasetVersion` 為不同值且各自依 §9.3.2 可重算。
- **B9 no-change 冪等** 同一凍結來源連跑兩次，`datasetVersion` 相同 → 第二次不發布、不 commit、`builtAt` 不變；改變 `sourceSha256` 但 logical payload 不變 → 仍不發布。

### C. Sentinel、分類與數值

- **C1** **兩個**分類欄位**各自**通過五處斷言：typed `null`、raw 仍等於 `"0"`、`stats.json` facet 不含 `"0"`、filter DOM 不含該選項、卡片／詳情顯示「未提供」。另測非合法值 → `categoricalUnknown` + warning。
- **C2** 依 §6.6.3 的解析順序表，對**每一列**（空／正整數／前導零／`0`／嚴格範圍／`min>max`／負數／文字／超界）逐筆斷言 typed、旗標、warning 分級與 UI 文字。`sourceZero` 只在值為 0 時為 true。**前導零須斷言 raw 顯示為 `026` 而非 `26`**。
- **C3** 寫死 `N/A`／`NA`／`""` 三類的**精確計數與對應 recordId**（**計數須數全部列，不是為該案例設計的列**），並斷言詳情切換到該 record 後的**可見文字精確相等**。
- **C4 反向哨兵**（三個**獨立**且**確為違規**的 mutation；**不得**使用「分類 typed 轉 null」，那是 §6.6.1 規定的正確行為）：
  1. 分類 sentinel 的 **raw 值遺失** → C1 的 raw 斷言須失敗
  2. `stats.json` facet **保留 `"0"`** → C1 的 facet 與 filter DOM 斷言須失敗
  3. 文字 sentinel 三型**塌成同一值** → C3 須失敗
- **C5 semantic comparison key** 逐型別驗證：`""` vs `"-5"` 須**判為衝突**（typed 皆 null 但語意狀態不同）；`"20"` vs `"２０"`（全形）須判**不衝突**且帶 `rawVariants`；`"20-40"` vs `"20～40"` 須判**不衝突**且帶 `rawVariants`；`"20-40"` vs `"20-41"` 須判**衝突**。
- **C6 `rawVariants` 的層級** 斷言 `rawVariants` 出現在**該欄位的 `flags`**，且 Trial 層級**不存在**等義旗標；代表值為 `recordId` 字典序最小者的 raw；詳情頁列出 cohort 中**每一筆** record 的原始值（不得只列去重文字）。

### D. 搜尋與篩選

- **D1** §8.5 短欄 5 欄與全欄 2 欄**各有唯一 canary** 與精確 expected trialId 清單；**另有 9 個不可搜尋欄位的負面 canary**。多欄同時命中時命中標籤集合須**完全相等**。
- **D2** 逐欄寫死 §8.1 policy 與 §8.2 operator，fixture 以 `shouldMatch`／`mustNotMatch` pair 表達。須含 substring／prefix／完整詞的邊界正反例、中文無空白字串、空查詢與純空白查詢（須**不執行搜尋**）。`identityNormalize` 與 `searchNormalize` **分開驗證**，須有「identity 不合併但 search 命中」的案例。
- **D3** 對同一查詢寫死完整結果集合，須含：兩詞同欄正例、兩詞跨欄正例、只命中其中一詞的必排除負例，以及**兩詞分別命中同一 Trial 的不同 SourceRecord 的必排除案例**。
- **D4** 每個正式 filter 維度至少一組，另加同維度多選（OR）、跨維度組合（AND）、每個 bucket 的閉區間端點、`period` 的重疊語意邊界、重複 query param、未知 param、無效值。斷言結果 trialId 清單逐一相同且順序相同、**canonical URL 字串精確相等**、reload 後控制項狀態精確相等。
- **D5** 以**封閉的 filter schema 與 DOM selector invariant** 為主 oracle：斷言 filter schema、DOM 控制項、URL parser、輸出 state 四處均不存在 trial-status 維度。列舉中文同義詞只作 mutation guard。
- **D6** **每一個可篩選且可能衝突的欄位**各有一組 `latestAmbiguous` oracle，斷言該 trial 歸入「不一致」分組且**不出現**在任一具體值的篩選結果中。
- **D7** scope 切換：四種組合各自的結果集、URL 的 `fields`／`history` 可重現、切換前顯示的大小取自 `manifest.files[*].gzipBytes`（**非前端寫死**）、scope 指示持續可見、零結果時提示可擴大的 scope、索引載入失敗時退回上一個 scope 並顯示說明。
- **D8 `enroll` 的區間重疊** 一筆 `台灣預計受試者人數 = "20-40"` 須**同時**出現在 `11-30` 與 `31-100` 兩個 bucket 的篩選結果中，且卡片顯示 raw `20-40`（不得顯示為單一數字）。另斷言 `numericUnparsed`／`numericImplausible` 等歸「未提供」而**不進任何數值 bucket**。

### E. 呈現與誤導防範

- **E1** 以「**允許呈現的狀態概念封閉清單** + §10 三項免責文句的正向精確斷言」為主 oracle；禁字只作 mutation guard。**不對來源原文設無條件禁字**。
- **E2** 由**實際 DOM／card schema 反向比對** oracle inventory：任何存在於 DOM 但不在 oracle 清單中的統計卡**必須使測試失敗**。每張卡寫死精確值、單位、分母類型；各 facet 的 `buckets + unprovided + conflicted` 須等於 `denominators.trials`。
- **E3** 斷言各 label 對應**精確 fixture 值**（來源 `資料更新時間` 對應 record、`builtAt` 對應 manifest），覆蓋首頁、結果頁、詳情頁與 record 切換後。
- **E4** 建立**來源資料可到達的輸出 surface 封閉 inventory**（卡片、詳情、record 切換、filter option、搜尋命中標籤、統計 label、accessible name、URL 顯示），逐一測 XSS fixture。
- **E5** 逐頁斷言 §10 三項核心性質的**可見文字**，可見性綁定 G1／G2 的 viewport、最小字級與對比 oracle。
- **E6** inclusion 與 exclusion **各**有長 fixture（含 22,490 字元案例）：展開後換行正規化後**全文精確相等**、首尾 canary 存在、切換 record 後亦相符。
- **E7** `latestAmbiguous=true` 的卡片須顯示「同日多筆資料不一致」；對**全部衝突候選值**做等價檢查——斷言候選值不出現在卡片的可見文字、accessible name、attribute 或 data-state 中（含**截斷與正規化後**的形式）。另斷言衝突欄位在 `displayFields` 中**完全省略**而非 `{typed:null}`。
- **E8** `dateUnknown=true` 顯示「資料日期無法辨識，請查官方來源」；`protocolNonIdentifier=true` 顯示「來源未提供計畫書編號」且 `?protocol=` 不接受該值；`nearDuplicateGroup` 非空時詳情頁顯示近似編號提示與連結；`numericRange` 顯示 raw 原文。

### F. 效能（分層預算）

- **F1** **Tier 0（預設 scope 的冷啟動）≤1.5 MB gzip**。定義為「冷啟動到**可搜尋 readiness**」的全部 network responses；readiness 以**功能性 probe** 判定（執行一個固定查詢並取得正確結果集才算就緒）。以 production build 與固定 gzip 設定量測，列出納入檔案清單與總和寫入 CI artifact。**資料層實測基線：`trials-index`（含 `searchShortLatest`、不含 `recordIds`）1,236 KiB gzip。**
  > 門檻自 v0.4 的 1.0 MB 上調為 1.5 MB：原基線「715–900 KiB」是估算值，實測有誤。卡片資料本身即 903 KiB；`recordIds` 移入 shard 後省 299 KiB；**拆成獨立檔反而更大**（903+693=1,596 > 1,236），故不拆。
- **F2** 各按需 tier 的實測 gzip 上限記錄於規格與 CI artifact（`all`+`latest` 2,044 KiB；`short`+`all` 1,649 KiB；`all`+`all` 另加 5,389 KiB），**不計入 F1**，超出記錄值 20% 須在 CI 告警。
- **F3** 長文字隔離：在 `納入條件`／`排除條件`／`試驗目的`／`主要評估指標` 放**多筆分散的唯一 canary**（≥5 筆，跨不同 shard），斷言 Tier 0 的全部 response 與 bundle 均不含其**內容**，且**初始 payload 的 schema 不含這些欄位鍵**。
- **F4** 以 production-scale fixture（5,888 Trial／18,736 SourceRecord）與固定查詢 corpus（零結果、極多結果、中文、英文、多詞、protocol）量測；計時自**輸入事件到結果 DOM 完成**；基準環境為 **GitHub Actions runner 類別 + 固定 CPU throttle 倍率**，固定樣本數，門檻 **p95 ≤300 ms**。規格明寫「跨時間比較僅在同 runner 類別內有效」。達不到須寫**瓶頸歸因**，不調鬆數字。

### G. 無障礙

- **G1** 最低 viewport matrix：360×640、390×844、768×1024、1280×800。除 `scrollWidth ≤ clientWidth` 外，斷言可見文字、表單與 focusable elements 的 **bounding box 均在 viewport 內**。
- **G2** 規格列出**最低必測的路由 × 狀態矩陣**（首頁／結果／詳情 × default／hover／focus／disabled／warning／`latestAmbiguous`／`dateUnknown`／`protocolNonIdentifier`／`numericRange`／零結果／載入失敗），並與實際元件狀態 inventory **雙向對帳**。每組輸出 selector、前景、背景與 ratio 並寫入 CI artifact。**當場計算，不憑目視。**
- **G3** 每一類互動元件逐項斷言 tab 可達、順序、Enter/Space 行為、focus 不遺失、無 keyboard trap，**並同時斷言 accessible name、role、state 與錯誤訊息關聯**。
- **G4 條件式** 首版以數字卡與清單為**必須**，圖表為**可選**。若提供圖表：替代 table/list 須在 **accessibility tree 可達**、具標題與欄名，且 key/value 集合與圖表**實際呈現的資料**精確相等。

### H. CI 與自動化

- **H1** 規格列出**最低 gate 集合**（lint、type-check、pytest、vitest、Playwright、a11y、payload 量測）並與 workflow jobs **雙向對帳**。對每個 gate 注入一個已知失敗，斷言 job 為 failure；斷言無 `continue-on-error`。
- **H2** 以同一凍結來源連跑兩次：第二次 git tree、`artifactDigest` 與 HEAD 均不變。**另須測真正的重疊情境**：兩個 run 同時排隊、前一個發布後第二個須**重新 checkout 分支 tip 並重取 baseline**，以及 promotion 前的版本再驗證會在版本已變時 fail-closed。
- **H3** 上線當天手動 dispatch 一次、再跑第二次驗冪等。第二次**重新下載並驗證 source SHA 相同**（不是快取第一次的下載結果），列出必經 stage；斷言兩次都完整跑完 pipeline、第二次回報 no normalized change 且不產生 commit。
- **H4** 斷言所有**直接與間接** `uses`（含 reusable workflow、container digest）均為不可變 SHA／digest；workflow 預設 `permissions` 為最小／read，只有唯一的資料更新 job 明示 `contents: write`。
- **H5 buildDate 時區** 斷言 production 的 `buildDate` 由 `Asia/Taipei` 日曆日產生：注入 UTC 時間為某日 16:00–23:59（台灣已是次日）→ `buildDate` 須為次日。以 runner 的 UTC 日期實作者必須失敗。

## 12. 里程碑

- **M0 完成**：規格通過三輪覆審 ＋ A 群 fixture 反驗；十項動工前契約已封存（見 §14）
- **M0.5**：B 群 fixture ＋ 產出一份**最小 artifact 樣本**（含 manifest、trials-index、一個 shard），實證 §9.3 的 schema 與 §9.3.2 的 digest 計算可實作。**這取代第四輪 prose 覆審。**
- **M1** repo 鷹架與 ETL（A／B／C 驗收）
- **M2** 前端 MVP（D／E／F／G 驗收）
- **M3** CI 與月更新（H 驗收）＋ Cloudflare Pages 首次部署
- **M4** 收尾：README（含 §6.3.5 的 ID 穩定性界限）、收進 `pharmacy-portal`、跑 `/codex-review` 以 A1–H5 做規格符合度稽核

## 13. 後續版本（不進本次範圍）

- 上游停更偵測。**不可**以「距今天數」為唯一判準；應以「連續 N 次 build 的 `sourceUpdatedAt` 未前進」為判準。
- 每月變更監測。`no longer present` **不得**自動稱為 terminated。
- 有方向性的版本 diff（需來源提供版號或可靠時間戳）。
- 近似 protocol 的**人工裁決合併表**（由藥師逐組確認後才合併，不自動化）。
- 約略值與界限值的結構化（`約400`、`至少480`、`148(最多266)`）——需先決定如何在 UI 表達「約」而不失真。
- ClinicalTrials.gov cross-link。
- Service worker／離線。
- Email 訂閱。

## 14. 動工前已封存的十項契約

| # | 契約 | 章節 | 來源 |
|---|---|---|---|
| 1 | `datasetVersion`／`artifactDigest` 分離，解開循環定義；hash 表示、檔名 hash、inventory 範圍 | §9.3.1／§9.3.2／§9.3.6 | r3 Blocker |
| 2 | SourceRecord 的 field-scoped `typed`／`fieldFlags`／`recordFlags` schema | §9.3.3／§9.3.5 | r3 High |
| 3 | `displayFields` 三元組 ＋ 欄位層級 `rawVariants` ＋ semantic comparison key | §6.4.2／§6.4.3／§6.4.5 | GAP-1／GAP-3／GAP-5 |
| 4 | protocol 空值分支（`identityNormalize` 後為空走 `H:`）、空白-only、ASCII 英數字元 | §6.0／§6.2.2／§6.3.1 | r3 High／Medium、GAP-4 |
| 5 | identity key 與 recordId 的 ordinal **一律從 `#0` 起** | §6.3.2 | GAP-2 |
| 6 | `searchShortLatest` 逐-record shape，保住 record 層 AND | §9.3.4 | r3 High |
| 7 | `buildDate` 的 `Asia/Taipei` 語意與可注入；試驗期間日期 grammar；數值 lexical grammar 與可表示範圍 | §6.5.1／§6.5.3／§6.6.3 | GAP-7／r3 Medium ×2 |
| 8 | manifest file-set 不變量修正；只輸出非空 shard | §9.3.1／§9.3.6 | r3 Medium |
| 9 | 方案 B 的 index／shard 職責切分與計數不變量；F1 改 ≤1.5 MB | §6.4.4／§9.3.6／F1 | 實測 S3，使用者定案 |
| 10 | 嚴格範圍解析 `numericRange` 與 `enroll` 的區間重疊語意 | §6.6.3／§8.4／D8 | 實測 S4，使用者定案 |

## 15. 修訂紀錄

- **v0.5（2026-09-18）** 依 `plan-verdict-r3.md`（接受 12／不成立 1／Blocker 1）與 `fixture-findings-a.md` 改寫。主要變更：
  - **§9.3.2 解開 `datasetVersion` 與整體 digest 的循環定義**（r3 Blocker，且是 v0.4 修 N8 時自造的）。分離為 `datasetVersion`（logical payload，不含版本欄位本身）與 `artifactDigest`（最終位元組），並封存 hash 演算法／長度、串接形式（hex + 邏輯檔名）、是否納入路徑
  - 新增 §6.0 字元集與正規化的基礎定義。**「ASCII 英數字元」必須明定**——Python 的 `"系統測試".isalnum()` 為 `True`，naive 實作會與 §6.2.2 的意圖完全相反（新增 A10 驗收）
  - §6.3.1 protocol 空值分支改依 `identityNormalize` 後是否為空（涵蓋空白-only）；§6.3.2 ordinal **一律從 `#0` 起且同步套用於 `recordId`**（GAP-2 原只修一半）
  - §6.4.2 新增 **semantic comparison key**。**GAP-5 的原建議被否決**：只比 typed 會把 `""`（未提供）與 `"-5"`（warning）判為不衝突而隱藏異常，比只比 raw 更糟
  - §6.4.3／§6.4.5 `displayFields` 改為 `{raw, typed, flags}` 三元組，`rawVariants` 為**欄位層級**；**衝突欄位完全省略而非 `{typed:null}`**（後者會與「未提供」混淆）
  - §6.4.4 採**方案 B**：`recordIds`／`latestCohort` 移入 shard，index 只留計數並加不變量防漂移。F1 門檻自 1.0 MB 改 **≤1.5 MB**，基線 1,236 KiB——原基線是估算值且實測有誤，且**拆檔反而更大**
  - §6.5.1 `buildDate` 為可注入的 ISO 日期，production 以 **`Asia/Taipei`** 日曆日產生（新增 H5 驗收）；§6.5.3 補試驗期間的日期 grammar
  - §6.6.3 補數值的完整 lexical grammar、解析順序、前導零、可表示範圍；**新增嚴格範圍解析 `numericRange`**（實測回收 1,347／1,705，7.2% of 全部），`enroll` 改區間重疊語意（§8.4／D8）
  - §6.2.2 疑似測試列的判定補上 `TEST` 值型（實測兩個數值欄位各 9 筆）
  - §9.3.4 `searchShortLatest` 封存逐-record shape，防止跨 record 合併而靜默違反 record 層 AND
  - §9.3.6 inventory 不變量改為「除 `manifest.json` 外」；`records/` 只輸出非空 shard
  - §11 A8 改以**注入的雜湊替身**驅動（真實 64 位元碰撞需 `2^32` 次運算，不可建構），並在凍結原則加上此唯一例外
  - 新增驗收 A10、B8、B9、C5、C6、D8、H5
  - §12 新增 **M0.5**：以 B 群 fixture ＋ 最小 artifact 樣本取代第四輪 prose 覆審
