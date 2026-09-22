# Taiwan Clinical Trial Radar — 規格 v0.9（consolidated）

> **這是唯一具規範效力的規格。** `Taiwan-Clinical-Trial-Radar-spec.md` v0.1 與本檔 v0.2–v0.4 均降為歷史文件，**不再具 normative 效力**。
> 依據：2026-09-18 dataset 205 實測 ＋ Codex **四輪**覆審（`plan-review-r1`～`r4.md`、`plan-verdict-r1`～`r4.md`）＋ fixture 反驗（`fixture-findings-a.md`、`fixture-findings-m05.md`）。
> 狀態：**14 項動工前契約已封存**（§14）。**v0.8 由 2026-09-21 的首次連網實跑觸發**——管線在真實資料上 exit 22，並量出 §6.4.5 與 F3 的直接衝突。**v0.9 是對 v0.8 修訂本身的第五輪限縮覆審結果**（`plan-review-r5.md`／`plan-verdict-r5.md`，Blocker 1／High 8，接受 35／部分接受 4／拒絕 0）。見 §15。
> 原狀態：M0.5 完成後撞出 GAP-8～GAP-12 並改寫為 v0.6；第四輪限縮覆審（**Blocker 0**）指出 v0.6 的修訂自造 3 個 High、6 個 Medium，本版 v0.7 已全部修訂。**四輪 Blocker 走勢：2 → 0 → 1 → 0。**

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
| `strip(s)` | 移除**前後**的 Unicode 空白字元。封閉定義：`White_Space=Yes` 的全部碼點（含 U+0020、U+0009、U+000A、U+000D、**U+00A0 NBSP**、**U+3000 全形空格**）。**零寬字元不算空白**（U+200B ZWSP、U+FEFF BOM、U+200C／U+200D）——它們不會被 strip 移除，因此兩個只差零寬字元的 protocol 是**碰撞**不是合併 |
| `identityNormalize(s)` | `nfkc(strip(s))` 後轉大寫。**不做**標點移除、不做內部空白壓縮、不做前後綴剝離 |
| `looseKey(s)` | `nfkc(s)` 後移除**所有非 ASCII 英數字元**，再轉大寫。**僅用於偵測近似 protocol，絕不用於收斂** |
| `conflictText(s)` | `nfkc(s)` 後移除**全部空白**（含全形空白）。用於 §6.4 文字欄位的比較鍵 |
| `searchNormalize(s)` | `nfkc(strip(s))` → casefold → 內部連續空白壓為單一空格。見 §8.1 |

**`strip` 必須封存字元集合（v0.9）**：v0.8 把 `strip(raw)` 升格為「合併或硬失敗」的邊界，而在那之前它只是正規化的一個步驟，定義模糊無害。現在它決定 Trial membership、`trialId` 與 URL——不同 runtime 對 NBSP 與零寬字元的處理若有差異，同一份快照會產出不同的 Trial 集合。**零寬字元刻意排除在 strip 之外**：它們不可見，把不可見差異靜默合併等於讓兩個不同計畫書變成一個，而 fail-closed 的代價只是一次人工確認。

**「ASCII 英數字元」必須明定，否則實作會相反。** Python 的 `"系統測試".isalnum()` 回傳 **`True`**（中文被視為字母）——若以 `isalnum()` 實作 §6.2.2，`系統測試` 將**不會**被標記為 `protocolNonIdentifier`，與意圖完全相反。判定一律先 `nfkc` 再套 ASCII 字元集合。

### 6.1 命名

來源列稱 **SourceRecord（審查紀錄）**。18,736 列對應 5,882 protocol，2,821 個 protocol 有多列（最多 23 列），其中只有 61 組 16 欄全同。

「一列 = 某一版試驗計畫書」是推論不是事實；資料只證明同 protocol 有多筆審查紀錄。規格與 UI 一律用「審查紀錄」，**不稱「第 N 版」**。

### 6.2 Identity normalization（與搜尋正規化分離）

主鍵一律用 `identityNormalize`（§6.0）。

**碰撞的定義（v0.8 修訂）**：兩列的 `strip(raw protocol)` **不同**、而 `identityNormalize` 後**相同** → 硬失敗 `IDENTITY_COLLISION` 並產出 collision report（內容契約見 §9.8），**不得合併**。（fail-closed 而非保留為不同 Trial：合併會誤配，保留兩個同鍵 Trial 會讓 URL 不唯一，硬失敗使月更新維持 last-known-good。）

**僅前後空白不同者不是碰撞，直接合併為同一 Trial**，全部 raw 值保留在 `protocolRaw[]`，並在 QA report 記 `WHITESPACE_ONLY_PROTOCOL_VARIANT` 警告。

**基數封存（v0.9）**，二元案例以外的情況照此推：

- `protocolRaw[]` 是 **distinct raw 值的集合**（非 multiset），依碼點昇序。出現幾列不影響其內容——**列數屬於 `recordCount`，不該在兩個地方各記一次**。
- `WHITESPACE_ONLY_PROTOCOL_VARIANT` **以 Trial 為單位，一個 Trial 最多一則**，攜帶該 Trial 的 `trialId`、`identityNormalized` 與**全部** raw variant（不是 pair 展開）。三個以上變體仍是一則。
- 前後同時有空白、以及「有變體但其中一個 raw 出現多列」都不改變上述兩條。

> **v0.7 的規則照字面是自相矛盾的，2026-09-21 首次連網實跑才顯形。** `identityNormalize` 的定義本身含 `strip()`，「不同 raw 正規化後相同即碰撞」等於要求正規化不准折疊任何東西——那樣正規化就沒有作用。實資料 18,736 列有 **4 組**僅尾隨一個空白的 protocol（`CYTB323J12201` 15 列 vs `CYTB323J12201 ` 2 列、`BIO89-100-131` 4/3、`RMC-6236-301` 2/1、`CGMH 2311280002` 1/2），照 v0.7 字面全部硬失敗，**管線在真實資料上一次都跑不完**。
>
> **v0.7 的「實測 0 個碰撞」是量錯了**：5,882 是 distinct **identity-normalized** 值的個數（扣掉空 protocol 一組），從未與 distinct **raw** 值（5,887）對照，於是「正規化把幾個 raw 折成一個」這件事在量測中根本不可見。§9.3.5 自己寫的 `trialCount: 5888` 反而是**合併後**的數字——規格的兩個實測數字本來就互相矛盾。
>
> 界線畫在 `strip` 而非「全部折疊」的理由：尾隨空白在任何識別碼體系都不承載語意，不可能用來區分兩個不同試驗；而大小寫與 NFKC 全形折疊**可能**（`abc-1` 與 `ABC-1` 未必同一個計畫書），故那兩類維持 fail-closed。§11 A7 的碰撞案例用的正是大小寫與全形，不受本修訂影響。
>
> 注意 §6.2.1 所列「多一個空格」指的是 **protocol 內部**的空格（`CGMH 2311280002` vs `CGMH2311280002`），`identityNormalize` 不壓內部空白，那仍是兩個 Trial 並成為 `nearDuplicateGroup`。兩者不可混為一談。

`searchNormalize` 與 `identityNormalize` **各自獨立驗證，不得共用實作**。

#### 6.2.1 近似 protocol 不自動合併，但必須揭露

§6.2 不剝標點、不壓空白，代價是**同一個試驗的不同寫法會成為兩個 Trial**。實測 18 組（多一個空格、全形括號、括號未閉合、連字號有無、上游刪除標記前綴 `刪_`）。

維持不自動合併（自動合併會誤配，違反寧可漏報不可誤報），但必須：

1. **偵測**：以 `looseKey(protocol)` 分組。**只有當一組含 ≥2 個不同 identity key 時**才輸出 `nearDuplicateGroup`（值為該 loose key）；單一成員為 `null`。
   **已合併 Trial 的算法（v0.9）**：一個 Trial 在 §6.2 合併後可能持有多個 raw protocol，此時 **`protocolRaw[]` 中每一個 raw 各自計算 `looseKey`**（不是只取代表值——代表值的選擇與近似判定無關，用它會讓結果取決於一個任意選擇）。該 Trial 落入其任一 raw 命中的每個 group，但**在同一 group 內只出現一次**。分組的成員單位自始至終是 **identity key**，不是 raw 值。
   **可證明：一個 Trial 恰好落入 0 或 1 個 group**，故 `nearDuplicateGroup` 維持單值欄位。證明：同一 Trial 的各 raw 依 §6.2 只差前後空白；`looseKey` 移除**全部**非 ASCII 英數字元（含空白），因此它們的 `looseKey` **必然相同**。此性質是 `looseKey` 定義的推論，**不是額外約束**——但若日後放寬 §6.2 的合併條件（例如連內部空白也折疊），這個推論即失效，屆時必須先改回多值欄位再放寬。
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
| identity key | **依 §6.2 的碰撞定義**：不同 `strip(raw protocol)` → 相同 identity key | `IDENTITY_COLLISION` |
| trialId | 不同 identity key → 相同 trialId（16-hex 截短碰撞） | `ID_TRUNCATION_COLLISION` |
| recordId | 不同 canonical serialization → 相同 recordId | `ID_TRUNCATION_COLLISION` |

實測 16,328 個不同紀錄的 16-hex 截短 **0 碰撞**。仍須偵測。

> **第一層的比較單位是 `strip(raw protocol)`，不是 raw**（v0.9 修訂）。v0.8 改了 §6.2 卻沒同步這張表，留下**同一契約的兩份不等價定義**——而這張表是 ETL 實作最可能照著寫的那份。僅前後空白不同者在此**不得**計為碰撞。

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

**比較鍵的索引鍵是「合法的 `(typed, flags)` 組合」，不是單一旗標。**

v0.6 曾寫成「本表必須涵蓋 §9.3.3 旗標封閉集合的每一個狀態」——**那個等號是錯的**：旗標不互斥。`numericRange + numericOutOfRange` 是**複合**（超界的區間），`sourceZero` 是合法整數的**附加**旗標而非另一種比較狀態。照旗標逐一對應，實作遇到複合組合時沒有唯一答案：先看到 `numericRange` 會拿到 `typed=null`，先看到 `numericOutOfRange` 才得到規格預期的 raw-based key。

因此改以**封閉的組合表**索引（下表的「狀態組合」欄即為唯一索引鍵）。`rawVariants` 不參與索引——它是比較的**結果**不是輸入。

| # | 欄位型別 | 狀態組合（`typed` ＋ field flags） | 比較鍵 |
|---:|---|---|---|
| 1 | 文字 | `typed` 為字串或 `null`，無 flags | `("text", conflictText(raw))` |
| 2 | 數值 | `typed` 為整數，flags `[]` | `("int", typed)` |
| 3 | 數值 | `typed` 為整數 `0`，flags `[sourceZero]` | `("int", 0)`——與第 2 列同鍵，`sourceZero` **不影響比較** |
| 4 | 數值 | `typed` 為 `{min,max}`，flags `[numericRange]` | `("range", min, max)` |
| 5 | 數值 | `typed` 為 `null`，flags `[numericMissing]` | `("numericMissing",)`——只有同為缺值才相等 |
| 6 | 數值 | `typed` 為 `null`，flags `[numericUnparsed]` | `("numericUnparsed", conflictText(raw))` |
| 7 | 數值 | `typed` 為 `null`，flags `[numericImplausible]` | `("numericImplausible", conflictText(raw))` |
| 8 | 數值 | `typed` 為 `null`，flags `[numericRangeInvalid]` | `("numericRangeInvalid", conflictText(raw))` |
| 9 | 數值 | `typed` 為 `null`，flags `[numericOutOfRange]`（序 2 超界） | `("numericOutOfRange", conflictText(raw))` |
| 10 | 數值 | `typed` 為 `null`，flags `[numericRange, numericOutOfRange]`（**序 3 超界**） | `("numericOutOfRange", conflictText(raw))`——**與第 9 列同鍵** |
| 11 | 分類 | `typed` 為 `null`，flags `[categoricalUnprovided]` | `("unprovided",)` |
| 12 | 分類 | `typed` 為 `null`，flags `[categoricalUnknown]` | `("categoricalUnknown", conflictText(raw))` |
| 13 | 分類 | `typed` 為合法值，flags `[]` | `("cat", typed)` |
| 14 | 期間日期 | `typed` 為 ISO 日期，flags `[]` | `("date", typed)` |
| 15 | 期間日期 | `typed` 為 `null`，flags 為四個 `period*` 之一 | `(旗標名, conflictText(raw))` |

**第 9／10 列同鍵是刻意的**：兩者都是「超出可表示範圍」，比較時只看 raw 原文。
保留 `numericRange` 旗標僅供 UI 說明來源形狀（§6.6.3），**不進比較鍵**——否則
`9007199254740992` 與 `1-9007199254740992` 會因為旗標不同而被判為衝突，但它們本來就是不同的 raw，
比 `conflictText(raw)` 已經足以區分，多一個維度只是把同一件事判兩次。

**第 3 列同理**：`sourceZero` 只影響 UI 文案（「0（來源填 0）」），不影響「兩筆是不是同一個值」。

**比較鍵相同即不衝突**，即使 raw 不同。

**三個新增狀態為什麼採 `(旗標名, conflictText(raw))`**：它們的 typed 都是 `null`，唯一帶資訊的是 raw 原文，而 UI 本來就要顯示 raw 加異常提示。若改比 typed（皆 `null`）會判為不衝突並任取一筆 raw——那正是第三輪否決 GAP-5 建議的理由。`40-20` 與 `50-30` 都是順序異常，但它們是兩筆**不同的來源錯誤**，任取一筆呈現等於替上游決定哪一筆才算數。採本規則後這三組**皆判為衝突**，與「寧可漏報不可誤報」一致。

**封閉性檢查以「組合」為單位**：實作須對 `(欄位型別, typed 的形狀, 排序後的 flags 集合)` 做窮盡 match，**遇到不在上表的組合必須硬失敗**，不得 fallback 到「比 raw」或「視為相等」。

**為什麼一定要以組合為單位**：以單一旗標做窮盡檢查時，一個「合法 range 正確、scalar 超界正確、但複合的超界 range 壞掉」的實作**會通過**——那正是本規格最怕的「測試全綠但功能是壞的」。上表第 10 列就是為此存在。

未涵蓋的組合是規格缺口，靜默 fallback 會把缺口變成一個看不見的行為。新增任何 field flag 時，**必須先問它會與哪些既有旗標共存**，再決定要新增哪幾列。

#### 6.4.3 `rawVariants`：欄位層級旗標

比較鍵相同但 cohort 內該欄位的 **distinct raw value 數 > 1** 時，該欄位的 `flags` 加入 `rawVariants`。

- `rawVariants` 是**欄位層級**，不是 Trial 層級。
- **`rawVariants = true` 不代表衝突**，只表示多個 raw 值映射到同一比較鍵。
- **只對 9 個卡片欄位輸出**（v0.9）。四個長文字欄位仍**計算**比較鍵與衝突（`conflictFields` 照收），但**不輸出 `rawVariants`**——它們不在 `displayFields` 內，而 §6.4.5 明定 `rawVariants` 只放 `displayFields[field].flags`、**不另設 Trial 層級表示**。
  這不是資訊遺失：長文字的唯一使用者入口是詳情頁，而詳情頁本來就逐 record 顯示每一筆原文（下一條），`rawVariants` 對它沒有任何增益。**實作不得為此私自擴充 schema**；§11 C6 有專門的反向斷言堵這條路。
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
  conflictFields[]       衝突的呈現欄位名（**全部 13 個**呈現欄位皆可入列），依 canonical 欄位順序
  displayFields          見 §6.4.5。**只含 9 個卡片欄位，不含 4 個長文字欄位**
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

**`displayFields` 的鍵：允許集合為 9 個卡片欄位**（v0.8 引入，v0.9 精化）＝ 13 個呈現欄位扣除 `試驗目的`、`主要評估指標`、`納入條件`、`排除條件`。
**實際鍵集合 = 該允許集合 − `conflictFields` 中屬於這 9 欄者**，因此可以少於 9 個。寫成「恰好 9 個鍵」的 schema validator 會逼實作違反「衝突欄位完全省略」，兩條規範不可同時照字面滿足。那四個長文字欄位**不在 Trial 層級輸出**，詳情頁一律逐 record 從 shard 取原文（§7.3 本來就要求逐 record 呈現，不呈現「收斂後的長文字」）。

> **這是把 §6.4.4／§6.4.5 改成與 F3 一致，不是新決策。** F3 早已要求「初始 payload 的 schema **不含這些欄位鍵**」，而 v0.7 的 §6.4.5 卻說 `displayFields` 涵蓋全部 13 個呈現欄位——兩條直接衝突，實作照 §6.4.5 寫就必然違反 F3。2026-09-21 實測坐實了代價：照字面實作的 `trials-index` 是 **15,621 KiB gzip**，其中排除條件 39.6 MiB ＋ 納入條件 37.6 MiB ＋ 主要評估指標 6.9 MiB ＋ 試驗目的 5.9 MiB 佔 raw 位元組的 **92.6%**。移出後降為 1,611 KiB gzip／915 KiB brotli。
>
> 收斂語意**不受影響**：§6.4.2 的衝突判定、§6.4.3 的 `rawVariants` 仍對全部 13 個呈現欄位計算，`conflictFields` 仍可含長文字欄位。改變的只有「Trial 層級把哪些欄位序列化進 `trials-index`」。

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

**解析分兩階段**：先依下表**依序**比對（第一個命中者決定分類），再套用**後置的可表示範圍檢查**。

v0.5 把「可表示範圍」寫成表後的獨立段落而沒有序位，與「第一個命中者決定結果」字面矛盾——`9007199254740992` 先命中序 2 得 typed 值，再被範圍檢查改成 `null`。分成兩階段即解開。

**階段一**：對 `nfkc(strip(raw))` 依下列順序比對，第一個命中者決定分類（固定順序使每個值只有一個分類）：

| 序 | 條件（對 `nfkc(strip(raw))`） | typed | 旗標 | UI | 分級 |
|---:|---|---|---|---|---|
| 1 | 空字串 | `null` | `numericMissing` | 「未提供」 | 正常 |
| 2 | `^\d+$`（**不接受**正負號、千分位、內部空白；**接受前導零**） | 該整數 | 為 0 時加 `sourceZero` | 數字；為 0 時顯示「0（來源填 0）」，**不得**呈現為「確定沒有受試者」 | 正常 |
| 3 | `^\d+\s*(?:[-~～〜–—]\|至)\s*\d+$` 且 `min ≤ max` | `{min, max}` | `numericRange` | 顯示 **raw 原文**，篩選以區間重疊判定 | 正常 |
| 4 | 同上但 `min > max` | `null` | `numericRangeInvalid` | 顯示 raw + 「數值區間順序異常」 | **warning** |
| 5 | `^-\d+$` | `null` | `numericImplausible` | 顯示 raw + 「數值超出合理範圍」 | **warning** |
| 6 | 其他非空 | `null` | `numericUnparsed` | 顯示 raw + 「來源以文字描述人數」 | **warning** |

**前導零**：實測有 3 筆（`026`、`024`、`08`）。typed 為 26／24／8，但**raw 一律顯示**——顯示 typed 就是改寫來源。

**階段二（後置的可表示範圍檢查）**：只在階段一命中**序 2 或序 3**（即產生了 typed 整數）時套用。typed 整數（含 range 的 `min`／`max`）必須落在 `0 … 2^53-1`（JSON number 可精確表示的整數上限）。

| 情形 | typed | 旗標 | 分級 | `enroll` 篩選 |
|---|---|---|---|---|
| 序 2 命中且整數超界 | `null` | `numericOutOfRange` | **warning** | 歸「未提供」 |
| 序 3 命中且**任一端**超界 | `null`（**整個範圍**，不保留任何一端） | `numericRange` ＋ `numericOutOfRange` | **warning** | 歸「未提供」 |

**單端超界時整個 typed 為 `null`，不得保留 `{min: 1, max: null}`**——半個區間無法參與 §8.4 的重疊判定，而一個「有 min 沒有 max」的物件會讓前端與篩選各自猜測邊界。保留 `numericRange` 旗標是為了讓 UI 說得出「來源是一個區間，但數值超出可表示範圍」，與「來源根本不是區間」可區分。

raw 一律照顯示，**不得輸出失真數字**。實測兩欄最大值為 100,000 與 4,236，目前無任何值超界——**正因為恆不觸發，更容易被省略或寫錯**。

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

**scope → 所需檔案集合（v0.9 定案，唯一事實）**。切換成本一律由**集合差**導出，規格不記「某個 scope 要下載幾 KiB」那種數字：

| scope | 所需檔案集合（Tier 0 三檔恆含，此處省略） |
|---|---|
| `short`+`latest`（預設） | ∅（`searchShortLatest` 併在 `trials-index` 內，§9.3.4） |
| `short`+`all` | `search-short-all` |
| `all`+`latest` | `search-long-latest` |
| `all`+`all` | `search-short-all` ＋ `search-long-latest` ＋ `search-long-all` |

**由此導出的切換成本** = `目標 scope 的集合 − 已載入集合`，再加總各檔的 `brotliBytes`。已在快取中的檔案**不得重複計入**。

> **v0.8 以 scope 名稱記單一數字是有歧義的**：`all`+`all` 那格寫「＋`search-long-all` 1,840.7 KiB」，讀者無法判定那是單檔大小、從 `short`+`all` 切過去的增量、還是從預設切過去的全部額外下載——三者差距達 696 KiB。**UI 顯示低報或高報都違反改用實際編碼的初衷。** 改用集合模型後每新增一個 scope 不必再解釋一組轉換數字。

**UI 硬性要求**（避免把預設縮小變成靜默漏報）：擴大 scope 的兩個控制項必須在搜尋結果區可見，不得藏在設定或選單深處；切換前顯示需下載的大小（依上表的集合差，逐檔取 `manifest.files.<entry>.brotliBytes` 加總，**不得前端寫死**；因為那是建置期估算值而非實際傳輸量，**UI 一律顯示為四捨五入的「約 X KiB」級距**，不得呈現精確到 byte 的數字）；結果區持續顯示目前 scope；零結果時提示可擴大的 scope 與其大小；載入失敗則退回上一個 scope 並說明，不得靜默維持舊結果集。

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
  "schemaVersion": 1,   // 見本節末的 schemaVersion 適用說明
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
    "trialsIndex":      { "path": "trials-index.<h>.json", "bytes": 0, "gzipBytes": 0, "brotliBytes": 0 },
    "stats":            { "path": "stats.<h>.json", "bytes": 0, "gzipBytes": 0, "brotliBytes": 0 },
    "searchShortAll":   { "path": "...", "bytes": 0, "gzipBytes": 0, "brotliBytes": 0 },
    "searchLongLatest": { "path": "...", "bytes": 0, "gzipBytes": 0, "brotliBytes": 0 },
    "searchLongAll":    { "path": "...", "bytes": 0, "gzipBytes": 0, "brotliBytes": 0 },
    "recordShards":     { "<shard>": { "path": "records/<shard>.<h>.json", "bytes": 0, "gzipBytes": 0 } }
  }
}
```

**`brotliBytes` 是 deterministic 的建置期估算值，不是實際傳輸大小**（v0.9 修訂，**Blocker 級修正**）：

- 定義：對該檔**最終位元組**以 **brotli quality 11** 壓縮後的長度。由 artifact 契約完全決定，可被任何人獨立重算（§9.3.6 I8）。
- **它不等於使用者實際下載的位元組。** Cloudflare 的動態壓縮品質、內容協商與小檔門檻都不在本專案控制範圍內（實務上動態壓縮約 q4–q5，**比 q11 大**）。
- 因此：**F1 的唯一 oracle 是部署端實際 response 的實收位元組**（見 F1）；`brotliBytes` 只用於 §8.5 的 UI 級距顯示與 F2 的基線比較。**兩者不得互稱，也不得相加。**
- `gzipBytes` 保留**純供 CI 對照**，不具任何 UI 語意。（v0.8 曾寫它是「無 brotli 部署環境的 fallback」——本專案部署目標唯一，那是一句不可驗證的敘述，v0.9 刪除；不可驗證的承諾比沒有承諾更糟。）

> **為什麼這是 Blocker：v0.8 犯的正是它自己要修的錯。** v0.8 把 F1 從 gzip 改 brotli，理由寫的是「量一個使用者從來不會付的數字，正是自我誤導」——然後把 q11 建置值當成實際下載大小交給 UI。那同樣是使用者不會付的數字，只是因為名字叫 `brotliBytes`、單位也對，**更難發現**。

**`brotliBytes` 只出現在五個具名 top-level entry**：`trialsIndex`、`stats`、`searchShortAll`、`searchLongLatest`、`searchLongAll`。**`recordShards` 的條目沒有這個欄位**——它們不在 §8.5 的 scope 切換器上、也不在 F1 的 Tier 0 內，對 256 個 shard 跑 quality 11 會讓月更新多花數分鐘卻沒有任何讀者。（v0.8 寫成 `files[*]`，那個 wildcard 照字面涵蓋 `recordShards`，與此處刻意的排除矛盾。）

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

**facet 名單為封閉集合，恰為三個**：`phase`、`scale`、`applicant`。

| §8.4 維度 | 是否為 facet | 理由 |
|---|---|---|
| `phase` | **是** | 每個 Trial 恰好落在一個值、未提供或不一致 |
| `scale` | **是** | 同上 |
| `applicant` | **是** | 同上 |
| `enroll` | 否 | 區間重疊可跨 bucket（§6.6.3 的 `numericRange`），計數會重複，`buckets + unprovided + conflicted` 的等式不成立 |
| `period` | 否 | §8.4 是**重疊**語意，同一 Trial 可落入多個期間區間，理由同 `enroll` |
| `updated` | 否 | 值域是連續日期而非固定 bucket，bucket 切法屬 UI 決策；統計卡改以「全站 `sourceUpdatedAt`」單一數字呈現（§7.2） |

**本清單是 facet widget 的唯一來源，不是「全部統計呈現」的唯一來源。**

呈現層分兩類，**各由不同契約約束**：

| 類別 | 是什麼 | oracle 來源 |
|---|---|---|
| **facet widget** | 依某個維度分組計數的統計卡（`phase`／`scale`／`applicant`） | 本清單，E2 雙向對帳 |
| **非 facet metadata** | 單值的資料來源資訊，如全站 `sourceUpdatedAt`、`builtAt`、Trial／SourceRecord 總數 | §9.3.5 的 `denominators` 與 manifest，由 E3 驗證 |

v0.6 曾寫成「E2 的統計卡 oracle 以本清單為唯一來源」，那會使**合法的 `sourceUpdatedAt` 卡必須使測試失敗**——而 §9.3.5 自己在上表才剛指定 `updated` 要以那張卡呈現。兩段互相矛盾。分開之後：新增 facet 須改本節，新增 metadata surface 走 E3，兩者都不得只改前端。

每個 facet 的 `buckets` 計數 + `unprovided` + `conflicted` **必須等於** `denominators.trials`。

**`stats.json` 與 `trials-index` 的一致性**：每個 facet 的 bucket 計數必須等於依 `trials-index` 的 `displayFields`／`conflictFields` 重新計算的結果。這是 §9.3.6 的不變量之一（見下），否則一份 bucket 計數全錯但總和恰好正確的 `stats.json` 會通過所有其他檢查。

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

**每條不變量只宣告自己的必要前置條件，不設全域順序。** 前置條件不成立時，該條回報「**無法評估**」而非「違規」；對外行為不變（一律 `INTEGRITY_DIGEST` 硬失敗），變的是 report 的歸因。

為什麼需要前置條件：`recordIds` 的排序鍵取自該 record 的 `資料更新時間`，而那筆資料在 shard 裡——record 放錯 shard 時排序鍵**取不到**，硬算會把「查不到」當成「不可採計日期→置末」而同時誤報排序違規。反例一旦必然連帶觸發另一條，**只實作其中一條檢查的驗證器也會通過測試**（B6 的「各自獨立反例」就白寫了）。

**但前置條件是逐條的，不是流水號。** v0.6 曾寫成全域七步，那會讓一個 shard 錯誤**遮蔽**同時存在的 stats 或 digest 錯誤——那兩條根本不依賴 record 歸屬。多缺陷時只能逐輪修、逐輪重跑，CI 的歸因能力反而比平鋪列出還弱。

| # | 不變量 | 內容 | 必要前置條件 |
|---:|---|---|---|
| I1 | **inventory** | `manifest.files` 列出的路徑集合 == `public/data/` 中**除 `manifest.json` 外**的全部檔案 | 無 |
| I2 | **跨檔版本綁定** | 每個非 manifest 檔案的 top-level `datasetVersion` == `manifest.datasetVersion` | 該檔可讀且為合法 JSON |
| I3 | **referential integrity** | 每個 `recordId` 存在於 `trial.shard` 指定的 shard；每個 record 被**恰好一個** Trial 引用**一次**（同一 Trial 內重複引用亦違規）；**shard 內不得有零 Trial 引用的 record**；`latestCohort ⊆ recordIds` | `trials-index` 與相關 shard 可讀 |
| I4 | **計數一致** | `trial.recordCount` == 該 shard 內 `trials[trialId].recordIds` 長度；`trial.latestCohortCount` == `latestCohort` 長度。**（方案 B 的必要防漂移條件。）** | 同 I3 |
| I5 | **排序 total order** | `trials` 依 `trialId` 昇序；`recordIds` 依（可採計日期降序、不可採計者置末、`recordId` 昇序）；`latestCohort` 依 `recordId` 昇序 | `trials` 的順序無前置；**某 Trial 的 `recordIds` 排序只在該 Trial 通過 I3 時評估**（否則取不到排序鍵） |
| I6 | **stats 一致性** | 每個 facet 的 bucket 計數 == 依 `trials-index` 重算的結果；且 `buckets + unprovided + conflicted` == `denominators.trials`（§9.3.5） | `trials-index` 與 `stats.json` 可讀。**不依賴 I3／I4／I5** |
| I7 | **`datasetVersion`／`artifactDigest`** | 依 §9.3.2 可重算且與 manifest 所載相符 | `manifest.files` 列出的檔案全部可讀。**不依賴 I3～I6** |
| I8 | **大小 metadata 可重算**（v0.9 新增） | 每個 `manifest.files` 條目的 `bytes` == 該檔實際位元組長度；`gzipBytes` == 對該位元組的 gzip 長度；五個具名 top-level entry 的 `brotliBytes` == 對該位元組的 brotli **quality 11** 長度；`recordShards` 條目**不得**有 `brotliBytes` | 該檔可讀。**不依賴 I1～I7** |

「無法評估」須逐條記入 report 並註明是哪個前置條件不成立；**不得**與「通過」混為一談。

**I8 為什麼非有不可**（v0.9）：`datasetVersion` 與 `artifactDigest` **都不含 `manifest.json` 自身**（§9.3.2），所以把 `brotliBytes` 改成任意數字**不會**讓 I7、H2、H3 的冪等比較轉紅。而 §8.5 的 UI 與 F2 的基線都讀這個值——**manifest 說多少，兩邊就都相信多少，形成循環自證**。I8 是唯一打斷這個循環的地方，因此它的前置條件刻意只有「該檔可讀」。

**schemaVersion 升級**（非逐次檢查的不變量，是修訂規則）：欄位移除、改名、型別或語意變更須 bump；純新增可選欄位不 bump。判準是「舊版前端讀到新資料會做什麼」。

**本次（v0.8／v0.9）不 bump 的適用理由**（v0.9 補記）：v0.8 從 `displayFields` 移除四個鍵、v0.9 新增 `brotliBytes`，依上述規則前者本應 bump。**但本專案至今沒有建立 GitHub remote、沒有任何部署、不存在任何已發布或可被外部讀取的 schemaVersion 1 artifact**——沒有舊版前端可被誤導，規則所要保護的情境不存在。**v0.9 是首個可發布的 schema，故仍為 1。** 第一次 promotion 成功之後，本段失效，此後任何欄位移除一律照規則 bump。

**孤兒檔不會改變 `artifactDigest`**——§9.3.2 只走 `manifest.files` 列出的路徑。因此序 1 的 inventory 不變量**無可取代**：沒有它，`public/data/` 裡多一個沒人引用的檔案是完全靜默的。

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
| `BASELINE_MOVED` | publish | promotion 前的再驗證發現遠端分支 tip 已前進，或無法確認其未變（M3 新增，見下） |

**`BASELINE_MOVED` 是 M3 依 H2 補上的**（2026-09-22）。H2 要求「promotion 前再驗證版本未變，不符即 fail-closed」，而 v0.9 的 §9.5 沒有給這個失敗一個 code——照原表實作只能沿用 `PROMOTION_FAILED`，那會讓「另一個 run 已發布」與「push 壞掉」在 exit code 上分不開，而前者該重跑、後者該查基礎設施。**「無法確認 tip 未變」與「tip 已變」共用同一個 code**：在發布安全性上兩者是同一件事，問不到就不准發布。

**移除了** `SCHEMA_COLUMN_RENAMED`／`MISSING`／`EXTRA` 三個分立 code：欄位 rename 同時滿足 missing 與 extra，無客觀判定方式。改為單一 `SCHEMA_MISMATCH` 攜帶 detail。

**多重失敗的 precedence**（由外而內，先觸發者勝）：`transport` → `archive` → `decode` → `schema` → `content` → `publish`。

每個 code 對應**相異的 exit code**。stderr 訊息只作輔助，**不得以「訊息含某字串」作為測試判定**。

失敗絕不回空陣列。抓取失敗與「官方回覆空集」必須分辨：目前 205 無 sentinel 列，0 資料列一律走 `ZERO_ROWS` 硬失敗。

### 9.6 驟降門檻與 warning 的落點

分母 = 上一個**成功發布快照**的來源資料列數 `prev`；`drop = (prev - cur) / prev`。

**比較前不得四捨五入或截斷到固定小數位。** 這是可驗證的要求：`drop = 0.2001` 四捨五入到兩位小數會得 `0.20`，於是**照樣發布**——上游掉了 20.01% 的資料而沒有硬失敗。B4 的 `0.1001` 與 `0.2001` 兩例即為此而設。

（v0.5 寫的是「以有理數比較」。實測 `prev ∈ [3, 20000]`——本資料集 18,736 列——在兩個門檻鄰域的全部 `cur`，float 與有理數的判定**沒有任何一組相異**，故「有理數」在本專案規模下**測不出違反**，是一條讓驗收清單看起來比實際強的要求。仍建議以有理數實作：它便宜，且資料規模改變時不需要重新評估。）

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

`qa/collision-report.json` 須能**唯一定位**每個 collision group。**空 report 或只含 error code 者視為不合規。**

**兩層結構（v0.9 修訂）**：

```
groups[]
  identityNormalized   該群共用的 identity key 值
  trialId              該群共用的 trialId（見下方警語）
  members[]            **≥2 筆**，依 strippedRaw 碼點昇序
    raws[]             對應到該 strippedRaw 的全部原始值（未經任何處理），昇序
    strippedRaw        strip(raw)；群內**兩兩相異**，這正是碰撞的定義
    fingerprints[]     產生這些 raw 的全部來源列 fingerprint（canonical serialization 的
                       sha256hex，見 §11 A5），昇序
```

> **`trialId` 不可用來區分 member。** 碰撞的成員共用同一個 identity key，而 `trialId = "t" + sha256hex(identityKey)[:16]`——**它們的 trialId 必然相同**。v0.8 以前的契約寫「各自的來源 fingerprint 與 trialId」，照字面實作出來的 report 在事故當下無法回答「是哪一筆來源列造成的」，而那是這份 report 存在的唯一理由。
> `strippedRaw` 必須寫進 report：它是**判定成立的依據本身**。少了它，看 report 的人無法分辨這是真碰撞，還是實作漏了 §6.2 的 strip 而誤報。
> **`raws[]` 固定為陣列**：一個 member 可以對應多個原始值（`"ABC "` 與 `" ABC"` 的 `strip` 相同，屬**同一個** member），型別時而字串時而陣列會讓讀 report 的人與 schema validator 各自猜一種。

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

- **A1** 寫死**每個來源列 fingerprint → trialId 的 group membership**（不只總數）。「不應合併」反例須採用 §6.2 **明確不折疊**的差異——連字號有無（`MK-3475-158` / `MK3475-158`）、空格有無（`9785-CL- 0123` / `9785-CL-0123`）、括號閉合（`ROR-PH-301(APD811-301` / `...301)`）；**不得**使用大小寫或全半形差異（那些會折疊，屬 A7）。**「應合併」案例須指名四類**（v0.9，原文只說「另須有應合併案例」，可被「兩筆逐位元相同的列」充數——**那樣 v0.8 最核心的新行為完全沒有被驗收**）：僅**前導**空白、僅**尾隨**空白、**前後皆有**空白、**同一 identity key 有三個以上 raw variant**。四類各自寫死 fingerprint → trialId 的 group membership、`protocolRaw[]` 的精確集合，以及 `WHITESPACE_ONLY_PROTOCOL_VARIANT` 的 warning oracle。另須含 **U+3000／NBSP** 各一（§6.0 的 strip 封閉集合）與 **U+200B 零寬字元**一例——**零寬字元不被 strip，故該例必須判為碰撞**，它是 strip 字元集合邊界的反向哨兵。
- **A2** fixture 每個案例附明確 oracle。**必含**：≥1 個 10 列以上 protocol、≥1 組 16 欄全同純重複、≥2 筆完全相同的空 protocol 列、**≥1 筆空白-only protocol**、≥3 組同日衝突、≥1 組同日但比較鍵全同、≥1 組同日僅空白／全半形差異（須判**不衝突**且帶 `rawVariants`）、≥1 筆 `TFDA收文號="移案BPA"`、≥1 筆收文號重複、≥1 個 `nearDuplicateGroup`、≥1 筆 `protocolNonIdentifier`、≥1 筆 `suspectedTestRow`（含 `TEST` 值型）。**日期異常各 ≥1**：不可解析、空值、未來日期、`buildDate` 當日（須可採計）、`buildDate+1`（須 `dateFuture`）、`試驗預計執行期間` end<start、期間任一端不可解析。**數值各型 ≥1**：`0`、正整數、前導零、空、嚴格範圍、`min>max` 範圍、負數、文字描述、超界值。
- **A3** 對 reverse 與 ≥3 個固定 seed 的排列，外加涵蓋「重複列 × 平手 × 空 protocol」交叉組合的 property invariant：先斷言輸出**檔案 inventory 完全相同**，再逐檔 SHA-256 相同，再斷言每個 tie case 的語意結果相同。
- **A4 反向哨兵** 把同日處置改為「任取 cohort 第一筆為 latest」時，須斷言失敗發生在**指定 tie group 的 `latestAmbiguous` 由 true 變 false**，且 mutation oracle 須涵蓋 `displayFields`、篩選分組與統計輸出。
  **另須含四個長文字欄位各自為唯一衝突來源的 mutation**（v0.9）：該 Trial 的 9 個卡片欄位全部一致、只有某一個長文字欄位在同日 cohort 內衝突。斷言 `conflictFields` 恰含該欄位、`latestAmbiguous=true`。**只對卡片欄位做衝突判定的實作能通過原本的 A4**——因為它的 fixture 用的是短欄衝突。
- **A5** 比對來源 canonical fingerprint 的**完整 multiset 含 multiplicity**。oracle 的 row identity 必須**獨立於 §6.3 的 canonical serialization**，並含分隔符／長度前綴的邊界 fixture。
- **A6** 兩筆完全相同的空 protocol 列須各自取得唯一 ID（`#0`／`#1`）、multiset 完整保留、多排列輸出一致。另須斷言**單筆空 protocol 也帶 `#0`**（§6.3.2）。
- **A7** 注入兩列，其 **`strip(raw)` 相異**而 `identityNormalize` 後相同 → `IDENTITY_COLLISION` 硬失敗。**正例須分別覆蓋大小寫折疊與 NFKC 全形折疊各 ≥1**，且每個正例都須滿足 `strip(raw1) != strip(raw2)`（v0.9：原文寫「兩個不同 raw protocol」，**與 v0.8 的新定義相反**，照原文挑一組僅尾隨空白的案例會要求一個 v0.8 明令禁止的結果）。
  **必含反例**：僅前後空白不同者**不得**觸發 `IDENTITY_COLLISION`（與 A1 的應合併案例同源，但這裡斷言的是「不硬失敗」）。
  collision report 須符合 §9.8：斷言 **group 與 member 的完整集合與配對關係精確相等**（每個 member 的 `raw`／`strippedRaw`/`fingerprints[]` 逐一比對），不是「欄位存在且非空」。**空 report 必須使測試失敗**；只檢查「report 含某個字串」的斷言同樣不合格——那證明的是檔案裡有那個字串，不是 member 配對正確。
- **A8（測試替身例外）** 以**注入的雜湊函式**（刻意截短為極少位元）驅動碰撞偵測分支：測試仍須使用**兩個不同的 identity key**（及 recordId 情形下不同的 canonical serialization），斷言回傳 `ID_TRUNCATION_COLLISION`、**停止發布**、且正式 artifact 不變。
- **A9** `nearDuplicateGroup` 偵測 18 組實測案例；`looseKey` 為空者**不入任何 group**；**單一成員的 group 輸出 `null`**；且偵測用的 loose key **不影響**任何 Trial 的收斂結果（以 A1 的 group membership 再驗一次）。
  **必含 whitespace-merge × looseKey 的交叉案例**（v0.9）：一個 Trial 先依 §6.2 吸收 ≥2 個前後空白 variant，其 `protocolRaw[]` 中某個 raw 再與**另一個** identity key 共享 looseKey。斷言 Trial **總數**、該 group 的成員（單位是 **identity key** 不是 raw）、該 Trial 在 group 內**只出現一次**，以及 `protocolRaw[]` 的精確集合。
  **這條堵的弱化實作是**：對每個 raw variant 各建一個 Trial（完全不合併），再讓 looseKey 把它們揭露成近似群——UI 上看起來「有揭露」，實際卻把 §6.2 要求合併的東西降級成了「只揭露不合併」。
- **A10** 「ASCII 英數字元」的字元集合：注入 `系統測試`（中文，`isalnum()` 為 `True`）→ 必須標記 `protocolNonIdentifier`。以 Unicode alphanumeric 實作者必須失敗。

### B. ETL 與發布可靠性

- **B1** §9.5 **每一個** error code 各有測試，斷言：(a) 非零且相異的 exit code；(b) 已發布狀態未變（完整檔名集合、每檔 SHA-256、`manifest.files` 指向、`artifactDigest` 均不變）；(c) **無新增正式檔**。content-type 須測 `application/zip;charset=utf-8`（通過）與 `text/html`（失敗）。
- **B2** 每個案例寫死 structured error code 與 layer；**不得**以 stderr 字串判定。另須有**多重異常** fixture 驗證 §9.5 的 precedence。
- **B3** 斷言 CSV schema **已通過後**才因零列失敗，明確回傳 `ZERO_ROWS`，且已發布 digest 不變。
- **B4** 門檻案例須含 `drop` = 0.0／0.10／0.1001／**0.20**／0.2001／整數列數邊界／首次無 baseline（含 bootstrap 但 0 列 → 仍走 `ZERO_ROWS`）。逐案例斷言 warning／success／hard-failure 與**是否發布**，且 warning 須出現在 `qa/quality-report.json` 的結構化欄位。**兩個固定小數例（`0.1001`／`0.2001`）只殺得死「四捨五入到 2 位」，必須另加真實基線的邊界例。** 實測 `prev = 18736`（本資料集列數）時：

| `cur` | 精確 drop | 正確判定 | 四捨五入到 2／3／4 位 |
|---:|---:|---|---|
| 16862 | 0.10002135 | publish + **warning** | 0.1 → **warning 消失** |
| 14988 | 0.20004270 | **hard-fail** | 0.2 → **照樣發布** |

這兩個 `cur` 恰好是各自門檻「**最接近且嚴格超過**」的整數，四捨五入到 4 位仍然漏判（要 6 位才抓得到）。B4 須對每個門檻各斷言三種位置——**正下、正好、最接近且嚴格超過**——且分類與精確比例 oracle 完全一致。以 `(prev, cur)` 整數對驅動，不需造大 CSV。
- **B5** 失敗注入點須涵蓋**每一個正式狀態變更之後**：替換第一個／部分／最後一個 artifact 後、刪除 orphan artifact 途中、`git add` 只含部分變更、commit 失敗、commit 成功但 push 失敗、push 成功但部署啟用失敗，以及**非例外式終止**（SIGTERM／取消）。每個點斷言：**不存在部分發布的 commit**。
- **B6** §9.3.6 的每一條不變量各有**獨立**反例：record 被兩個 Trial 引用、同一 Trial 重複引用、record 放錯 shard、`latestCohort ⊄ recordIds`、**`recordCount` 與 shard 清單長度不符**、**`latestCohortCount` 與 `latestCohort` 長度不符**、三種排序各自未排序、`manifest.files` 與實際檔案集合不符（**孤兒檔**與**列出但不存在**兩種形狀）、facet bucket 計數與 index 不符 → 全部須 `INTEGRITY_DIGEST` 硬失敗。
  三條硬性要求：(a) **缺陷須注入在計算 digest 之前**，使 artifact 的 digest 自洽——改完最終位元組不重算的話，測到的只是 digest 本身，referential integrity 那幾條永遠不會被執行到；每個反例另須斷言 digest 相關的不變量**未**觸發。(b) **斷言違規集合 exactly equals 預期**，不是「包含」——用「包含」的話，一個把所有檢查都回報違規的驗證器會全過。(c) 須有**未變造樣本零違規**的反向哨兵。
  註：「record 被兩個 Trial 引用」的反例必須挑**同一個 shard 內**的兩個 Trial，否則會連帶違反 shard 歸屬而無法隔離。
  **(d) mutation inventory 與 §9.3.6 的 I1–I8 須雙向對帳**：每條不變量至少一個反例，每個反例對應得到某條不變量；缺任一方向即為未涵蓋。特別容易漏的三類——**零 Trial 引用的 orphan record**（只數已被引用者的 owner count 會漏掉）、**跨檔 `datasetVersion` 與兩種 digest 各自的獨立反例**（省略整類重算仍可通過其餘 mutation）、**三個 facet 各自的 bucket mismatch**（只驗一個 facet 也能通過單一 facet 的 mutation）。
  **I8 的反例須為「檔案內容不變、只竄改 manifest 的大小數值」**（v0.9）：分別竄改 `bytes`、`gzipBytes`、`brotliBytes` 各一，另加「在某個 `recordShards` 條目上**多加**一個 `brotliBytes`」一例。**這四個 mutation 不會改變 `datasetVersion` 或 `artifactDigest`**（兩者都不含 manifest 自身），因此 I7 抓不到——若 I8 的反例沒單獨建立，整類竄改在測試上完全隱形。
  **(e) 「無法評估」也要有反例**：注入一個使某條前置條件不成立的缺陷，斷言下游那條回報「無法評估」而非「通過」——把兩者混為一談的驗證器必須被殺死。
- **B7** 跨版本綁定：注入「manifest 為新版但某 shard 為舊 `datasetVersion`」→ 前端 fail-closed 顯示「資料版本不一致，請重新載入」，**不得**混用渲染。另斷言除 `manifest.json` 外所有檔名都帶內容雜湊、且 manifest 為唯一固定 URL。
- **B8 `datasetVersion` 的可計算性與敏感性** 對同一輸入兩次 build 得到相同 `datasetVersion`（**證明無循環定義**）；任一欄位值改變一個字元 → `datasetVersion` 改變；**兩個檔案內容互換** → `datasetVersion` 改變（證明邏輯檔名已納入）；`artifactDigest` 與 `datasetVersion` 為不同值且各自依 §9.3.2 可重算。
- **B9 no-change 冪等** 同一凍結來源連跑兩次，`datasetVersion` 相同 → 第二次不發布、不 commit、`builtAt` 不變；改變 `sourceSha256` 但 logical payload 不變 → 仍不發布。

### C. Sentinel、分類與數值

- **C1** **兩個**分類欄位**各自**通過五處斷言：typed `null`、raw 仍等於 `"0"`、`stats.json` facet 不含 `"0"`、filter DOM 不含該選項、卡片／詳情顯示「未提供」。另測非合法值 → `categoricalUnknown` + warning。
- **C2** **兩個數值欄位（`全球預計受試者人數`／`台灣預計受試者人數`）各自跑完整矩陣**，不得只驗其中一欄——否則另一欄可以走一套完全不同的錯誤邏輯而通過。矩陣為 §6.6.3 的兩個階段：階段一的每一列（空／正整數／前導零／`0`／嚴格範圍／`min>max`／負數／文字），以及階段二的兩種超界（**序 2 命中後超界**、**序 3 命中且單端超界**）。
  逐例斷言 typed、**field flag 集合（完全相等，不是「包含」）**、warning 分級、UI 文字與 `enroll` 歸類。**旗標用「包含」比對時，實作可以額外附加 `numericUnparsed` 等錯誤旗標而通過，錯誤會經由 §6.4.2 的組合表擴散到衝突判定與 UI。** `sourceZero` 只在值為 0 時為 true。**前導零須斷言 raw 顯示為 `026` 而非 `26`**。單端超界須斷言 typed 為**整個 `null`**（不得留 `{min:1, max:null}`）、旗標為 `[numericRange, numericOutOfRange]`、`enroll` 歸「未提供」。
- **C3** 寫死 `N/A`／`NA`／`""` 三類的**精確計數與對應 recordId**（**計數須數全部列，不是為該案例設計的列**），並斷言詳情切換到該 record 後的**可見文字精確相等**。
- **C4 反向哨兵**（三個**獨立**且**確為違規**的 mutation；**不得**使用「分類 typed 轉 null」，那是 §6.6.1 規定的正確行為）：
  1. 分類 sentinel 的 **raw 值遺失** → C1 的 raw 斷言須失敗
  2. `stats.json` facet **保留 `"0"`** → C1 的 facet 與 filter DOM 斷言須失敗
  3. 文字 sentinel 三型**塌成同一值** → C3 須失敗
- **C5 semantic comparison key** **§6.4.2 表中每一列各有一組正例**，不得只測其中幾型。至少含：`""` vs `"-5"` **衝突**（typed 皆 null 但語意狀態不同）；`"20"` vs `"２０"`（全形）**不衝突**且帶 `rawVariants`；`"20-40"` vs `"20～40"` **不衝突**且帶 `rawVariants`；`"20-40"` vs `"20-41"` **衝突**；`"40-20"` vs `"50-30"`（皆 `numericRangeInvalid`）**衝突**；`"第三期"` vs `"Phase III"`（皆 `categoricalUnknown`）**衝突**；`2^53` vs `2^53+1`（皆 `numericOutOfRange`）**衝突**。
  **必含複合狀態**：`1-9007199254740992` vs `2-9007199254740992`（皆為 §6.4.2 第 10 列的超界 range，raw 不同）須判**衝突**；`1-9007199254740992` vs `１-９００７１９９２５４７４０９９２`（NFKC 後等價）須判**不衝突**且帶 `rawVariants`。
  **exhaustiveness 測試以「狀態組合」為單位**，不是單一旗標：斷言 dispatch 涵蓋 §6.4.2 組合表的 15 列，且遇到表外組合時**硬失敗而非 fallback**。
  **以單一旗標做窮盡檢查是不夠的**——一個「合法 range 正確、scalar 超界正確、複合的超界 range 壞掉」的實作會通過那種檢查，而那正是本規格最怕的「測試全綠但功能是壞的」。
- **C6 `rawVariants` 的層級** 斷言 `rawVariants` 出現在**該 9 個卡片欄位之一的 `flags`**，且 Trial 層級**不存在**等義旗標；**另斷言四個長文字欄位的 `rawVariants` 不出現在任何輸出**——不在 `trials-index`、不在 shard 的 `fieldFlags`、不在任何新增鍵下（v0.9：§6.4.3 已定案長文字不輸出 `rawVariants`，這條反向斷言堵的是「實作私自擴充 schema 替它找個位置」）；代表值為 `recordId` 字典序最小者的 raw；詳情頁列出 cohort 中**每一筆** record 的原始值（不得只列去重文字）。

### D. 搜尋與篩選

- **D1** §8.5 短欄 5 欄與全欄 2 欄**各有唯一 canary** 與精確 expected trialId 清單；**另有 9 個不可搜尋欄位的負面 canary**。多欄同時命中時命中標籤集合須**完全相等**。
- **D2** 逐欄寫死 §8.1 policy 與 §8.2 operator，fixture 以 `shouldMatch`／`mustNotMatch` pair 表達。須含 substring／prefix／完整詞的邊界正反例、中文無空白字串、空查詢與純空白查詢（須**不執行搜尋**）。`identityNormalize` 與 `searchNormalize` **分開驗證**，須有「identity 不合併但 search 命中」的案例。
- **D3** 對同一查詢寫死完整結果集合，須含：兩詞同欄正例、兩詞跨欄正例、只命中其中一詞的必排除負例，以及**兩詞分別命中同一 Trial 的不同 SourceRecord 的必排除案例**。
- **D4** 每個正式 filter 維度至少一組，另加同維度多選（OR）、跨維度組合（AND）、每個 bucket 的閉區間端點、`period` 的重疊語意邊界、重複 query param、未知 param、無效值。斷言結果 trialId 清單逐一相同且順序相同、**canonical URL 字串精確相等**、reload 後控制項狀態精確相等。
- **D5** 以**封閉的 filter schema 與 DOM selector invariant** 為主 oracle：斷言 filter schema、DOM 控制項、URL parser、輸出 state 四處均不存在 trial-status 維度。列舉中文同義詞只作 mutation guard。
- **D6** **每一個可篩選且可能衝突的欄位**各有一組 `latestAmbiguous` oracle，斷言該 trial 歸入「不一致」分組且**不出現**在任一具體值的篩選結果中。
  **另須含「不可篩選但仍影響 `latestAmbiguous` 的長文字欄位」各一組**（v0.9）：四個長文字欄位**不是**篩選維度，但它們**照樣進 `conflictFields` 並使 `latestAmbiguous=true``**。只驗可篩選欄位的實作會把「只有長文字衝突」的 Trial 標成不 ambiguous，而那是**漏報**——直接違反誤導優先的風險排序。
- **D7** scope 切換：四種組合各自的結果集、URL 的 `fields`／`history` 可重現、scope 指示持續可見、零結果時提示可擴大的 scope、索引載入失敗時退回上一個 scope 並顯示說明。
  **顯示大小的驗收以「檔案集合」為單位，不是「來源是 manifest」**（v0.9）：對**每一個** `起始 scope → 目標 scope` 的轉換（含由非預設 scope 出發者），寫死 (a) 必須下載的檔案集合（依 §8.5 的集合差）、(b) 已在快取中的前提、(c) expected 總 bytes ＝ 該集合各檔 `brotliBytes` 之和、(d) UI 實際顯示的「約 X KiB」級距。
  **原文只驗「取自 manifest」，而那是一個顯示任何單一檔案數字都能通過的斷言**：由預設 scope 進入 `all`+`all` 時 UI 若只顯示 `searchLongAll.brotliBytes`，少報了 `search-short-all` 與 `search-long-latest` 共 2,173.7 KiB，照樣「取自 manifest」。**低報與高報都違反改用實際編碼的初衷。**
- **D8 `enroll` 的區間重疊** 一筆 `台灣預計受試者人數 = "20-40"` 須**同時**出現在 `11-30` 與 `31-100` 兩個 bucket 的篩選結果中，且卡片顯示 raw `20-40`（不得顯示為單一數字）。另斷言 `numericUnparsed`／`numericImplausible` 等歸「未提供」而**不進任何數值 bucket**。

### E. 呈現與誤導防範

- **E1** 以「**允許呈現的狀態概念封閉清單** + §10 三項免責文句的正向精確斷言」為主 oracle；禁字只作 mutation guard。**不對來源原文設無條件禁字**。
- **E2** 分兩層，**對象不同、oracle 來源不同**（§9.3.5）：
  **(a) facet widget**：inventory 以 §9.3.5 的封閉 facet 名單（`phase`／`scale`／`applicant`）雙向對帳——DOM 中有而清單中無者失敗，清單中有而 DOM 中無者亦失敗。每張卡斷言完整的 bucket `value/count` **multiset 完全相等**（不是只比幾個值或只比總和）、`unprovided`、`conflicted`、單位與分母類型。各 facet 的 `buckets + unprovided + conflicted` 須等於 `denominators.trials`。
  **(b) 非 facet metadata surface**（`sourceUpdatedAt`、`builtAt`、總數）：由 E3 驗證，不納入 facet inventory。
  **統計 surface 的辨識不得只依 CSS class 或 card selector**——否則弱化前端把未核准的統計放進一般 section 或 badge 就能繞過整個 inventory。須以「使用者可見的統計概念」為辨識依據（例如可見文字中出現分組計數的區塊），並在測試中寫死該辨識規則。
- **E3** 斷言各 label 對應**精確 fixture 值**（來源 `資料更新時間` 對應 record、`builtAt` 對應 manifest），覆蓋首頁、結果頁、詳情頁與 record 切換後。
- **E4** 建立**來源資料可到達的輸出 surface 封閉 inventory**（卡片、詳情、record 切換、filter option、搜尋命中標籤、統計 label、accessible name、URL 顯示），逐一測 XSS fixture。
- **E5** 逐頁斷言 §10 三項核心性質的**可見文字**，可見性綁定 G1／G2 的 viewport、最小字級與對比 oracle。
- **E6** **四個被移出 index 的長文字欄位各自**都要斷言詳情頁呈現完整：`納入條件`／`排除條件`／`試驗目的`／`主要評估指標`，展開後換行正規化後**全文精確相等**、首尾 canary 存在、切換 record 後亦相符。長度壓力案例（22,490 字元）仍集中在 inclusion／exclusion 兩欄。
  **v0.9 補上後兩欄的理由**：修訂 2 把 `試驗目的`／`主要評估指標` 移出 `trials-index` 後，**詳情頁成為它們唯一的使用者入口**。原文只驗 inclusion／exclusion，詳情頁完全不渲染另外兩欄時 E6 與 F3 **都會全綠**——F3 驗的是「不該出現的地方沒出現」，恰好與「該出現的地方沒出現」同向。
- **E7** `latestAmbiguous=true` 的卡片須顯示「同日多筆資料不一致」；對**全部衝突候選值**做等價檢查——斷言候選值不出現在卡片的可見文字、accessible name、attribute 或 data-state 中（含**截斷與正規化後**的形式）。另斷言衝突欄位在 `displayFields` 中**完全省略**而非 `{typed:null}`。
  **長文字欄位須另立案例**（v0.9）：對「只有某個長文字欄位衝突」的 Trial，斷言 `conflictFields` 的**精確集合**、`latestAmbiguous=true`、卡片顯示泛化警示、詳情頁並列**全部**候選紀錄。
  **對長文字沿用原本的斷言是恆真的**：那四欄本來就不在 `displayFields`，「候選值不出現在卡片」無論衝突有沒有被偵測到都會成立——**一條永遠不會紅的斷言，證明不了任何事**。
- **E8** `dateUnknown=true` 顯示「資料日期無法辨識，請查官方來源」；`protocolNonIdentifier=true` 顯示「來源未提供計畫書編號」且 `?protocol=` 不接受該值；`nearDuplicateGroup` 非空時詳情頁顯示近似編號提示與連結；`numericRange` 顯示 raw 原文。

### F. 效能（分層預算）

- **F1** **Tier 0（預設 scope 的冷啟動）≤ 1,500,000 bytes，以實際傳輸編碼量測**。**門檻以整數 bytes 封存（v0.9）**：v0.8 寫「1.5 MB」而表格用 KiB、餘裕又以 1,536 KiB 反推，等於同時存在 1,500,000 與 1,572,864 兩個門檻，落在中間的 bundle 可依任一口徑宣告通過。依「不調鬆數字」紀律採**較嚴的十進位**。定義為「冷啟動到**可搜尋 readiness**」的全部 network responses；readiness 以**功能性 probe** 判定（執行一個固定查詢並取得正確結果集才算就緒）。以 production build 量測，列出納入檔案清單與總和寫入 CI artifact。
  **量測對象定案為「部署端實際 response 的實收位元組」（v0.8 引入，v0.9 封存邊界）**：部署在 Cloudflare Pages，對 `application/json` 實際送的是 brotli。v0.7 全程以 gzip 計，而同一份位元組兩者差約 43%——**量一個使用者從來不會付的數字，正是 F1 自己警告的那種自我誤導**。
  **封存的量測邊界**，四條缺一不可（每一條都對應一種能通過文字但量錯東西的實作）：

  1. **計入的是壓縮後的 response body bytes**，逐 response 依其**實際** `content-encoding` 計算。**不得**使用 `Content-Length` header 值、**不得**使用解壓後長度、**不得**使用 Resource Timing 的 `transferSize`（它含 header 與連線開銷，跨瀏覽器不可比）。**不含 header bytes。**
  2. **混合 encoding 是正常的，不是失敗**：HTML／JS／CSS／字型／小型 response 未必是 `br`（Cloudflare 對極小檔可能不壓）。逐 response 依**實際**編碼計入即可，**不得**因為某個 response 不是 `br` 就排除它或改用估算值。
  3. **readiness 前已發起的 request 一律計入**，即使它在 readiness 判定之後才完成。只計「已完成」會讓實作用一個提早觸發的 readiness 把大檔排除在量測外。
  4. **`manifest.files[*].brotliBytes` 不得作為 F1 的量測來源**——那是建置期 quality 11 估算值（§9.3.5），與實際傳輸沒有必然相等關係（Cloudflare 動態壓縮約 q4–q5，**比 q11 大**）。以估算值申報 F1 通過，與 v0.7 用 gzip 申報是同一個錯。

  CI artifact 須**逐 response** 列出 URL、`content-encoding`、body bytes 與納入／排除理由。
  **口徑定案：1.5 MB 量的是「全部 network responses」，含 HTML、JS、CSS、字型與資料檔。** 這是使用者真正付的冷啟動成本；只量資料層會讓 CI 在真實冷啟動超標時仍顯示合格。
  **資料層子集合（封閉，須恰好等於這三個）**：`manifest.json` ＋ `trials-index.<h>.json` ＋ `stats.<h>.json`。三者都在冷啟動路徑上——首頁要顯示統計卡（E2）、篩選控制項的值域來自 `stats.json` 的 facet buckets（§9.3.5）。子集合另立斷言，**不取代**總和斷言。
  **readiness probe 不得早於這三個檔載入完成就判定就緒**——否則把必要的 response 排除在量測之外，等於自己放水。
  **Tier 0 建置期估算（2026-09-21，§6.4.5 的 9 欄 `displayFields`）**
  **快照綁定**：`sourceSha256`（ZIP）`ff182257442fa53078b308afa0a5a0cae3b162f9d5a36f0740f787e87e303f3c`／CSV `46cd2b9e1e33743d630c69547c88c7ecc0825e5d7259a4192575e010303e47cf`／18,736 列／5,888 Trial。**沒有綁定快照的效能數字無法判斷它對應哪個輸入**，上游同日重新打包就失去意義。

  | 檔案 | raw | gzip | brotli |
  |---|---:|---:|---:|
  | `trials-index.<h>.json` | 11,119.6 KiB | 1,611.0 KiB | 914.8 KiB |
  | `stats.<h>.json` | 22.8 KiB | 4.5 KiB | 3.9 KiB |
  | `manifest.json` | 28.7 KiB | 7.0 KiB | 5.4 KiB |
  | **Tier 0 合計** | | **1,622.6 KiB** | **924.0 KiB** |

  **這三個數字是 quality 11 的建置期估算值，不是 F1 的驗收結果**（v0.9）。brotli 欄合計 946,176 bytes，對 1,500,000 bytes 的門檻餘 **553,824 bytes（540.8 KiB）** 給 HTML／JS／CSS／字型——但 Cloudflare 動態壓縮約 q4–q5，**實際傳輸會大於此值**，真正的餘裕只會更少。
  **F1 的通過與否要等 M2 對真實部署量過才算數**，本表只用來判斷「方向對不對、還有沒有數量級的問題」。以 gzip 計則為 1,661,478 bytes，已超標——**改用實際傳輸編碼是量對東西，不是把門檻調鬆。**
  `manifest.json` 有 256 個 shard 條目故達 28.7 KiB；它是唯一不帶內容雜湊、`Cache-Control: no-cache` 的檔，每次冷啟動都重取，因此必須計入 Tier 0。
  **`stats.json` 的大小疑慮解除**：三個 facet 的實測 bucket 數為 `applicant` **371**、`phase` 7、`scale` 3；`unprovided` 為 109／109／187，`conflicted` 為 8／3／0，三者各自的 `buckets + unprovided + conflicted` 均**恰等於** `denominators.trials = 5888`（§9.3.6 I6 成立）。`applicant` 的 cardinality 是三者中唯一過百的，但 371 個字串 bucket 壓縮後整份 `stats.json` 僅 **3.9 KiB brotli**——v0.7「其大小主要由 applicant cardinality 決定」的擔憂在這個量級下不成立。
  **這些數字只解除 payload 大小疑慮，不構成分類正確性的證據**（v0.9 補記）：三類總和閉合於 5,888 是**算術性質**，把 Trial 分到錯誤 bucket 仍然可以閉合。分類正確性的 oracle 是 I6 的逐 bucket 重算與 E2 的完整 multiset 對帳。**371／7／3 也不是門檻**——上游合法新增一個申請者就會變動，把它寫成 gate 只會製造無意義的紅燈。
  **超標時先報瓶頸歸因，不調鬆數字**（§10 把效能排在誤導與資料正確性之後——超標是要解的工程問題，不是安全問題；而「量了一個不是使用者成本的數字然後宣告合格」才是會誤導自己的那種錯）。
  **驗收須同時斷言兩件事**：(i) readiness 前的**全部 response** 以**實收位元組**（brotli；取自各 response 的 `content-encoding` 與實際長度）計的總和 ≤ 1.5 MB，清單寫入 CI artifact；(ii) 其中的資料檔集合**恰好等於**上述三個。只做 (ii) 的量測器會漏掉 JS／CSS／字型。
  > 門檻自 v0.4 的 1.0 MB 上調為 1.5 MB：原基線「715–900 KiB」是估算值，實測有誤。`recordIds` 移入 shard 後省 299 KiB；**拆成獨立檔反而更大**（903+693=1,596 > 1,236），故 `searchShortLatest` 不拆。
  > **v0.7 的 1,236 KiB 基線本身也是估算值。** 2026-09-21 實測重建了這條線：9 欄 `displayFields` ＋ `searchShortLatest` 的 index 為 1,611 KiB gzip（v0.7 估 1,236）。估算偏低 23%，但不影響結論——瓶頸從來不是這 30% 的誤差，而是 v0.7 的 §6.4.5 把 4 個長文字欄位也放進 index（15,621 KiB，12.6 倍）。
- **F2** **各按需檔案**的壓縮基線記錄於規格與 CI artifact，**不計入 F1**，超出記錄值 20% 須在 CI 告警。**以檔案為單位，不以 scope 為單位**（v0.9）——scope 的成本由 §8.5 的集合差導出，在這裡再記一次 scope 數字必然產生「總量還是增量」的歧義。

  | 檔案 | brotli（q11 估算） | v0.5 的 gzip 估值 |
  |---|---:|---:|
  | `search-short-all` | 696.1 KiB | 1,649 KiB |
  | `search-long-latest` | 1,477.6 KiB | 2,044 KiB |
  | `search-long-all` | 1,840.7 KiB | 5,389 KiB |

  快照綁定同 F1。三者全部低於 v0.5 的估值，最多低 66%——**估算一路偏保守，但偏的方向不一致**（F1 的 index 估值偏低 23%），所以估值一律不可當驗收基準。

  **CI 的 oracle 必須是對 artifact 位元組的獨立重算，不得讀 `manifest.files[*].brotliBytes`**（v0.9）：v0.8 寫「取自 manifest」，而 manifest 的數值本身沒有任何東西驗證（§9.3.6 I8 是 v0.9 才補的）。**同時填錯 manifest 與 CI artifact 的實作會讓 20% 告警完全失去偵測能力**——manifest 在此是被驗證對象，不得兼任 expected value。
- **F3** 長文字隔離：在 `納入條件`／`排除條件`／`試驗目的`／`主要評估指標` 放**多筆分散的唯一 canary**（≥5 筆，跨不同 shard）。
  **檢查對象是解壓、解碼、解析後的 logical payload**（v0.9），不是 response 的原始位元組：

  1. 斷言四欄的 canary **不出現在 Tier 0 任何 response 解析後的任何可達 JSON value 中**（遞迴走訪全部字串葉節點，不是只看已知鍵）。
  2. 斷言每個 Trial 的 `displayFields` 鍵集合**恰等於** 9 個卡片欄位 − `conflictFields` 中屬於這 9 欄者（§6.4.5）。這同時堵死「換個鍵名塞同樣的文字」。
  3. 斷言 bundle（JS／CSS）不含 canary。

  **在壓縮後的 response bytes 裡搜明文 canary 是一條永遠找不到東西的斷言**——brotli 壓過的內容當然不含明文，那種量測器在長文字整個洩進初始 payload 時仍會全綠。**別名鍵、Base64 或其他編碼、塞進另一個物件，三條也都要能擋。**
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

- **M0 完成**：規格通過三輪覆審 ＋ A 群 fixture 反驗；動工前契約封存（見 §14）
- **M0.5 完成**：A 群補 v0.5 案例（73 列／45 Trial）、最小 artifact 樣本（8 Trial／12 個非 manifest 檔）、B 群失敗注入（12 個輸入）、§9.3.6 不變量反例（11 種）、C4 的三個 mutation。M0.5 結案時 240 條斷言，v0.6 收斂後 **244 條**。**取代了第四輪 prose 覆審，並撞出 GAP-8～GAP-12（本版 v0.6 已併入）。**
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

## 14. 動工前已封存的契約（14 項）

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
| 11 | semantic comparison key 以**封閉的 `(typed, flags)` 組合表**（15 列）索引，表外組合硬失敗不 fallback | §6.4.2 | M0.5 GAP-8 ＋ r4 1.1／C5 |
| 12 | §9.3.6 每條不變量**各自宣告必要前置條件**，「無法評估」≠「通過」 | §9.3.6 | M0.5 GAP-11 ＋ r4 1.2 |
| 13 | `stats.json` 的 **facet 名單封閉為三個**，只約束 facet widget；非 facet metadata 走 E3 | §9.3.5／E2 | M0.5 GAP-10 ＋ r4 2.1 |
| 14 | **F1 的 1.5 MB 量的是全部 network responses**，三個資料檔只是須恰好相等的子集合 | §11 F1 | r4 2.2／F1，使用者定案 |

## 15. 修訂紀錄

- **v0.9（2026-09-21）** 第五輪 `/codex-checkplan` **只審 v0.8 的修訂本身**（接受 35／部分接受 4／拒絕 0，範圍蔓延 0）。**39 項發現沒有一項是幻覺，也沒有一項是 v0.7 遺留——全部是 v0.8 修訂自己造的**，第五次應驗「修訂會製造新洞」。另有 4 處（`plan-verdict-r5.md` 的 S1–S4）是送審前自查修掉的，形狀一致：**最容易漏的是「同一個數字寫在兩個地方」**。主要變更：
  - **Blocker：`brotliBytes` 降為建置期 q11 估算值，F1 的唯一 oracle 改為部署端實際 response 的實收位元組。** v0.8 犯的正是它自己要修的錯——它把 F1 從 gzip 改成 brotli，理由寫「量一個使用者從來不會付的數字就是自我誤導」，然後把 q11 建置值交給 UI 當實際下載大小。Cloudflare 動態壓縮約 q4–q5，**比 q11 大**。連帶把 Tier 0 的 924.0 KiB 降級為估算值，F1 的通過與否要等 M2 對真實部署量過才算數
  - **§6.3.4 的碰撞條件改為引用 §6.2。** v0.8 改了 §6.2 卻沒同步這張表，留下同一契約的兩份不等價定義，而那張表是 ETL 最可能照著寫的那份
  - **§6.0 封存 `strip` 的字元集合**（`White_Space=Yes`，含 NBSP／U+3000；**零寬字元刻意排除**，只差零寬字元者是碰撞不是合併）。v0.8 把 `strip` 升格為「合併或硬失敗」的邊界，它在那之前只是正規化的一步，定義模糊無害
  - **長文字欄位不輸出 `rawVariants`。** v0.8 一邊把四個長文字移出 `displayFields`，一邊聲稱「`rawVariants` 仍對全部 13 欄計算」——而 §6.4.5 明定 `rawVariants` 只放在 `displayFields[field].flags`、不另設 Trial 層級表示，**那四欄的結果無處可去**。它們沒有任何 UI 消費者，故不輸出；C6 加反向斷言堵「私自擴充 schema」
  - **新增不變量 I8（大小 metadata 可重算）。** 兩個 digest 都不含 manifest 自身，故竄改 `brotliBytes` 不會讓 I7／H2／H3 轉紅，而 §8.5 的 UI 與 F2 都讀它——**manifest 說多少兩邊就信多少，循環自證**
  - **§8.5 改為「scope → 所需檔案集合」模型**，切換成本由集合差導出。v0.8 以 scope 記單一數字，`all`+`all` 那格三義，差距達 696 KiB；D7 連帶改為對每個 scope transition 寫死檔案集合與 expected 總和
  - **F1 門檻以整數 bytes 封存為 1,500,000**（v0.8 的「1.5 MB」與表格的 1,536 KiB 反推並存，中間地帶可依任一口徑宣告通過；依「不調鬆數字」採較嚴的十進位），並封存四條量測邊界（壓縮後 body bytes／混合編碼正常／in-flight 計入／不得用 manifest 估算值申報）
  - **F2 的 CI oracle 改為對 artifact 獨立重算**，manifest 降為被驗證對象——v0.8 寫「取自 manifest」而 manifest 無人驗證，20% 告警形同虛設
  - **F3 的檢查對象改為解析後的 logical payload。** 原文可被「在壓縮後的 bytes 裡搜明文 canary」滿足，**那是一條永遠不會紅的斷言**
  - **A1／A7／A9／A4／C6／D6／E6／E7 補指名反例類別。** 最嚴重的是 A7 原文與 v0.8 的新定義**相反**，以及 A1 的「應合併案例」可用兩筆逐位元相同的列充數——**v0.8 最核心的新行為原本完全沒有被驗收**
  - **schemaVersion 維持 1 並寫明適用理由**：尚未建 remote、尚未部署、不存在任何可被外部讀取的 v1 artifact，規則要保護的情境不存在；第一次 promotion 成功後本段失效
  - **教訓**：v0.8 的教訓是「prose 覆審抓不到規格與現實的落差」，v0.9 是它的反面——**本輪 39 項全部是規格內部一致性問題，那正是 prose 覆審擅長而實跑永遠不會顯形的類別。** 兩種手段互補，不可互相取代。

- **v0.8（2026-09-21）** **首次連網實跑觸發**，不是覆審觸發。前七版全部靠凍結 fixture 與 prose 覆審推進，M1 的 141 個測試全綠，而真實資料一跑就在第一道硬失敗停住。兩項修訂都是「規格內部本來就矛盾，只是沒有東西去碰它」：
  - **§6.2 的碰撞定義限縮為「`strip(raw)` 不同而正規化後相同」**。v0.7 字面上把 `identityNormalize` 自己的 `strip()` 也算成碰撞，等於要求正規化不准折疊任何東西。實資料 4 組僅尾隨一個空白的 protocol 使管線 exit 22，**一次都跑不完**。v0.7 宣稱的「實測 0 碰撞」是量錯了——5,882 數的是 distinct **normalized** 值，從未與 5,887 個 distinct **raw** 對照，那個量法在定義上就看不見碰撞。§9.3.5 自己寫的 `trialCount: 5888` 是合併後的數字，規格的兩個實測數字本來就互相矛盾
  - **§6.4.4／§6.4.5 的 `displayFields` 改為 9 個卡片欄位**，與早已存在的 **F3**（「初始 payload 的 schema 不含四個長文字欄位鍵」）一致。v0.7 的 §6.4.5 說涵蓋全部 13 欄——照 §6.4.5 寫就必然違反 F3，照 F3 寫就違反 §6.4.5，**兩條規範直接衝突而四輪覆審都沒抓到**。實測代價：照字面實作的 index 是 15,621 KiB gzip（F1 門檻的 10.2 倍），長文字佔 raw 位元組 92.6%
  - **F1 的量測編碼定案為 brotli**，並補上 Tier 0 的實測表（**924.0 KiB brotli**，餘 612.0 KiB 給 bundle）。v0.7 全程以 gzip 計，但部署在 Cloudflare Pages 實際送 brotli——**量一個使用者從來不會付的數字，正是 F1 自己那段話警告的自我誤導**。同時把 §8.5／D7 的 UI 下載大小來源由 `gzipBytes` 改為 `brotliBytes`
  - **`stats.json` 的 cardinality 疑慮解除**：`applicant` 實測 371 bucket、`phase` 7、`scale` 3，三者的 `buckets + unprovided + conflicted` 均恰等於 5,888，整份 3.9 KiB brotli
  - **教訓**：凍結 fixture 證明的是「實作符合規格」，證明不了「規格符合現實」。v0.5 起反覆用 fixture 反驗規格找出 12 個 GAP，但 fixture 是照規格寫的，規格與真實資料的落差它結構上看不見。**新專案的第一次連網實跑要排在規格定案之後、實作完成之前**，不是排在最後當驗收。

- **v0.7（2026-09-18）** 依 `plan-verdict-r4.md`（接受 9／部分接受 2／拒絕 0／Blocker 0）改寫。**本輪 11 項發現全部是 v0.6 修訂自己造的，沒有一項是 v0.5 遺留**——第四次應驗「修訂會製造新洞」。形狀一致：**為了關掉一個洞而引入的新概念，本身沒有被定義清楚。** 主要變更：
  - **§6.4.2 的比較鍵改以「合法 `(typed, flags)` 組合」索引**（15 列封閉表）。v0.6 寫的「涵蓋旗標封閉集合的每一個狀態」**那個等號是錯的**——旗標不互斥：`numericRange + numericOutOfRange` 是複合、`sourceZero` 是附加。照旗標逐一對應時，複合組合沒有唯一答案。新表明定第 9／10 列同鍵（超界只看 raw）、第 3 列與第 2 列同鍵（`sourceZero` 不影響比較）
  - **§9.3.6 的全域七步順序改為「每條各自的必要前置條件」**。v0.6 為了隔離一個排序案例而設全域流水號，反而讓一個 shard 錯誤**遮蔽**同時存在的 stats 或 digest 錯誤——那兩條根本不依賴 record 歸屬。另補上 I3 的「shard 內不得有零 Trial 引用的 record」
  - **§9.3.5 分離「facet widget」與「非 facet metadata surface」**。v0.6 一邊寫「`updated` 改以全站 `sourceUpdatedAt` 單一數字呈現」，一邊寫「E2 的統計卡 oracle 以本清單為唯一來源」——照字面實作，那張合法的卡必須使測試失敗。同一節內自相矛盾
  - **F1 口徑定案為「全部 network responses」**（使用者決定），三個資料檔降為**須恰好相等的子集合斷言**。v0.6 兩種口徑並存無法唯一判定。代價寫進規格：資料層已佔 1,236 KiB，只剩約 264 KiB 給 `stats.json` 加整個 bundle，**超標先報瓶頸歸因不調鬆數字**
  - **B4 補真實基線的邊界例**：`prev=18736` 時 `cur=16862`／`14988` 恰為兩門檻「最接近且嚴格超過」的整數，**四捨五入到 2／3／4 位全部漏判**（要 6 位才抓得到）。原本的 `0.1001`／`0.2001` 只殺得死 2 位
  - **B6 補 (d) 與 §9.3.6 的 I1–I7 雙向對帳、(e) 「無法評估」也要有反例**。特別點名三類容易漏的反例：零 Trial 引用的 orphan record、跨檔版本與兩種 digest 各自的獨立反例、三個 facet 各自的 bucket mismatch
  - **C2 明定兩個數值欄位各自跑完整矩陣、旗標集合須「完全相等」**（用「包含」比對時可附加錯誤旗標而通過）
  - **C5 的 exhaustiveness 改以「狀態組合」為單位**，並必含複合的超界 range 兩組案例。以單一旗標做窮盡檢查時，「合法 range 對、scalar 超界對、複合超界 range 壞掉」的實作會通過
  - **E2 拆為 (a) facet widget 雙向對帳 ＋ 完整 bucket multiset、(b) 非 facet metadata 走 E3**，並規定統計 surface 的辨識**不得只依 CSS class 或 card selector**
- **v0.6（2026-09-18）** 依 `.ai-review/fixture-findings-m05.md` 的 GAP-8～GAP-12 改寫。**這五個洞不是讀 prose 讀出來的，是把 v0.5 的契約真的做出來時撞到的。** 主要變更：
  - **§6.4.2 補上三個漏掉的語意狀態**（`numericRangeInvalid`／`numericOutOfRange`／`categoricalUnknown`），皆採 `(旗標名, conflictText(raw))`。v0.5 的表看起來很完整（10 列），但與 §9.3.3 的旗標封閉集合有三個差集——**兩張表都在本文件內，只是沒有人對過**。另要求以窮盡 dispatch 實現，遇未涵蓋狀態**硬失敗不 fallback**
  - **§6.6.3 拆成兩階段**：階段一是原本的序 1–6，階段二是後置的可表示範圍檢查。v0.5 把範圍檢查寫成表後的獨立段落而沒有序位，與「第一個命中者決定結果」字面矛盾。並明定**單端超界時整個 typed 為 `null`**（不得留 `{min:1, max:null}`，半個區間無法參與 §8.4 的重疊判定）
  - **§9.3.5 封閉 facet 名單為三個**（`phase`／`scale`／`applicant`），逐一寫出 `enroll`／`period`／`updated` 被排除的理由，並讓 **E2 以它為唯一 oracle 來源**。另把「`stats.json` 與 `trials-index` 的計數一致性」列為不變量——否則一份 bucket 計數全錯但總和恰好正確的 `stats.json` 會通過所有其他檢查
  - **§9.3.6 改為有序的 7 條並定義「無法評估」**。平鋪列出做不到 B6 要求的「各自獨立反例」：`recordIds` 的排序鍵取自 shard 內的 record，record 放錯 shard 時排序鍵取不到，硬算會同時誤報排序違規。**反例一旦必然連帶觸發另一條，只實作其中一條檢查的驗證器也會通過測試**
  - **§9.6 把「以有理數比較」改為「不得先四捨五入或截斷到固定小數位再比較」**。實測 `prev ∈ [3, 20000]` 的門檻鄰域內 float 與有理數判定無一組相異，故原文是一條**測不出違反**的要求；真正守得住的是四捨五入那條（`drop=0.2001` 會被判成 `0.20` 而照樣發布）
  - **F1 補上 Tier 0 的封閉檔案清單**（`manifest.json` ＋ `trials-index` ＋ `stats.json`）。v0.5 的 1,236 KiB 基線只量了 `trials-index`，而 `stats.json` 也在冷啟動路徑上且**從未量測**。**補量之前不得調整 1.5 MB 門檻**
  - 驗收條件同步：C2 補階段二的兩種超界、C5 改為「§6.4.2 表中每一列各有正例」＋ exhaustiveness 測試、B4 寫明兩個殺 rounding 的案例、B6 補三條硬性要求（注入在 digest 之前／exactly equals／反向哨兵）與同 shard 的限制、E2 綁定封閉 facet 名單
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
