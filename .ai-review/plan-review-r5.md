# Codex 規格覆審 — 第五輪（只審 v0.8 的修訂本身）

- **審查日期**：2026-09-21
- **審查員**：Codex（`mcp__codex__codex`，`sandbox: read-only`、`approval-policy: never`）
- **規劃文件**：`.ai-review/plan.md` v0.8
- **基準 commit**：`22903b2`（＋審前自查修掉的 4 處數字／口徑不一致，見 `plan-verdict-r5.md` 開頭）
- **審查範圍**：**只審 v0.7 → v0.8 的六項修訂本身**，不重審 v0.7 已定案部分
- **thread**：`01a0c2b2-77b5-73f1-9a01-6adc37e74b2d`

> 以下為 Codex 原始輸出，**原封不動**，不修飾不刪改。判定見 `plan-verdict-r5.md`。

---

結論：v0.8 的修正方向大致合理，也沒有違反純靜態、單一資料源或 fail-closed 架構；但確實新造出數個洞。最嚴重的是把「建置時 quality 11 的理論 brotli 大小」與「Cloudflare 實際傳輸大小」當成同一件事，導致 F1、F2、D7 與 manifest 彼此使用不同 oracle。另有兩個 High：碰撞舊契約未同步更新，以及四個長文字欄位的 `rawVariants` 失去明確承載位置。

## 1. 需求與邊界缺漏

### 1.1 §6.3.4 仍保留 v0.7 的碰撞定義

- **嚴重度：High**
- **問題：** §6.2 已改成只有 `strip(raw protocol)` 不同才是碰撞，但 §6.3.4 Iden­tity key 表仍寫「不同 raw protocol → 相同 identity key」即 `IDENTITY_COLLISION`。尾端空白不同仍同時滿足這個舊定義。
- **為什麼現在不修之後會更貴：** ETL、錯誤分類與 fixture 可以分別依兩個相反契約實作；再次連網時可能重現 exit 22，或不同驗證器得到不同結論。
- **建議修法：** 將 §6.3.4 的 identity-key 碰撞條件直接引用 §6.2，明定比較單位為 distinct `strip(raw protocol)`，不要另寫一個簡化但不等價的定義。

### 1.2 `strip()` 本身沒有封存字元語意

- **嚴重度：Medium**
- **問題：** v0.8 把 `strip(raw)` 提升為「合併或硬失敗」的邊界，但 §6.0 沒定義 strip 移除哪些 Unicode 字元。不同語言或 runtime 對 NBSP、全形空白、零寬字元等可能不同。
- **為什麼現在不修之後會更貴：** 同一快照可能因 runtime 或函式替換而改變 Trial membership、trialId 與碰撞判定。
- **建議修法：** 在 §6.0 封存 `strip` 的精確字元政策，並明定 `identityNormalize` 與碰撞前置比較使用同一個 strip 定義。這是現有 identity 契約的必要精化，不是新增功能。

### 1.3 whitespace-only variant 的群組與警告基數不明

- **嚴重度：Medium**
- **問題：** 「兩個 raw 值都保留」只覆蓋二元案例；未定義三個以上前後空白變體、重複列、前後同時有空白時：

  - `protocolRaw[]` 是 distinct raw set 還是含 multiplicity。
  - warning 是每個 Trial、每個 variant pair，或每筆 SourceRecord 一則。
  - `count` 與範例 recordId 的意義。
- **為什麼現在不修之後會更貴：** QA report、真實資料統計與 fixture oracle 會各自採用不同計數口徑。
- **建議修法：** 封存 `protocolRaw[]` 為 distinct raw 值集合或 multiset，並定義 `WHITESPACE_ONLY_PROTOCOL_VARIANT` 的計數單位及完整成員表示。

### 1.4 修訂 1 與 `nearDuplicateGroup` 的交叉案例未定義完整

- **嚴重度：Medium**
- **問題：** 一個 Trial 可以先吸收數個前後空白 variant，再以其中某個 protocol 與另一 identity key 形成同一 `looseKey`。§6.2.1 沒明定 QA group 應列出該 Trial 的全部 `protocolRaw[]`，還是只列參與 loose-key 計算的代表值。
- **為什麼現在不修之後會更貴：** UI 可能能連到 Trial，卻無法完整解釋近似判定來源；QA report 也可能無法重建分組。
- **建議修法：** 明定 `looseKey` 是以 Trial 的哪個 protocol 值集合計算，以及一個已合併 Trial 在 group/report 中只出現一次還是依 raw variant 展開。

### 1.5 collision report 的形狀不足以表達新邊界

- **嚴重度：Medium**
- **問題：** §9.8 只列「normalized 值、全部 raw protocol、fingerprint、trialId」，沒有 raw protocol 與 fingerprint 的明確對應結構，也沒有 `strip(raw)`。此外，在 identity collision 時相關 raw 會導出相同 trialId，「各自 trialId」並不能區分成員。
- **為什麼現在不修之後會更貴：** report 可能表面含齊欄位，實際無法定位是哪筆來源列形成哪個碰撞分支。
- **建議修法：** 將契約改成 collision group 及 member 的明確層級；每個 member 綁定 raw、stripped value 與來源 fingerprint。trialId 可保留，但不得當成 member 唯一識別。

### 1.6 長文字 `rawVariants` 失去合法承載位置

- **嚴重度：High**
- **問題：** §6.4.5 說 `rawVariants` 放在 `displayFields.<field>.flags`，C6 也只驗這個位置；v0.8 又把四個長文字欄位完全移出 `displayFields`，同時聲稱 `rawVariants` 仍對全部 13 欄計算。現有 schema 沒有 Trial/cohort 層級的位置可承載這四欄的結果。shard 的 `SourceRecord.fieldFlags` 是 record-scoped 結構，也未說 cohort-derived 的 `rawVariants` 應加在哪些 record。
- **為什麼現在不修之後會更貴：** 實作者只能選擇丟棄長文字的 `rawVariants`、任意複製到 record、或私自擴充 schema；三者都可能通過部分現有驗收。
- **建議修法：** 規格必須二選一：

  1. 長文字只參與 conflict 判定，不輸出 `rawVariants`，並同步限縮「全部 13 欄計算」與 C6；或
  2. 在既有 shard Trial metadata 中正式定義 cohort-level 的欄位旗標及其 schema。

### 1.7 「9 個鍵」與「衝突欄位完全省略」字面衝突

- **嚴重度：Medium**
- **問題：** §6.4.5 說 `displayFields` 的鍵為 9 個卡片欄位；同節又說衝突欄位必須完全省略。因此實際鍵數可能少於 9。
- **為什麼現在不修之後會更貴：** schema validator 可能要求 exactly 9 keys，逼迫實作違反衝突省略規則。
- **建議修法：** 改成「允許鍵的封閉集合為這 9 欄；實際鍵集合等於該集合扣除 `conflictFields` 中屬於這 9 欄者」。

### 1.8 長文字衝突目前可能只能得到泛化警示

- **嚴重度：Medium**
- **問題：** `conflictFields` 可含四個長欄位，但 E7 沒要求這些欄位必須出現在 `conflictFields`。因為它們原本就不在卡片，漏算長文字衝突仍可能得到看似合理的 9 欄卡片。
- **為什麼現在不修之後會更貴：** 只在長文字衝突的 Trial 可能被錯標為 `latestAmbiguous=false`，這直接違反「誤導優先」風險模型。
- **建議修法：** 對每個長文字欄位建立「唯一衝突來源」案例，斷言欄位名進入 `conflictFields`、`latestAmbiguous=true`，且詳情頁並列候選紀錄。

### 1.9 schemaVersion 與修訂 2 自相矛盾

- **嚴重度：High**
- **問題：** §9.3.6 明定欄位移除、型別或語意改變必須 bump schemaVersion；v0.8 從 Trial `displayFields` 移除四個鍵，但 manifest 範例仍是 `schemaVersion: 1`。`brotliBytes` 又被定義為 required 欄位。
- **為什麼現在不修之後會更貴：** 舊前端若依 v0.7 schema 讀取新 artifact，可能把欄位缺失解讀成衝突或未提供；這正是 schemaVersion 規則要避免的情況。
- **建議修法：** 明確記錄本次是否存在任何已發布或可被讀取的 schemaVersion 1 artifact。若存在，依既有規則 bump；若尚未形成外部契約，需在規格中寫明「v0.8 是首個可發布 schema，因此仍為 1」的適用理由。

### 1.10 `brotliBytes` 的 wildcard 用語與 schema 不一致

- **嚴重度：Low**
- **問題：** §9.3.5 使用 `manifest.files[*].brotliBytes`，但 record shard 條目刻意沒有此欄位。
- **為什麼現在不修之後會更貴：** 泛用 schema validator 或文件讀者會將 `*` 解讀成包含 `recordShards`。
- **建議修法：** 封存五個具名 top-level entry，或明確定義 `*` 不含 `recordShards` map。

### 1.11 F2 的 `all+all` 是增量大小還是完整切換成本不明

- **嚴重度：High**
- **問題：** `all+all` 需要 short-all 與 long-all 的資料；表中卻只寫「＋search-long-all = 1,840.7 KiB」。目前無法判定：

  - 1,840.7 KiB 是 long-all 單檔；
  - 是從 short+all 切換到 all+all 的增量；
  - 還是進入 all+all 所需全部額外下載。
- **為什麼現在不修之後會更貴：** UI 可以顯示 1,840.7 KiB 並通過「取自 manifest」驗收，但使用者實際還要下載 696.1 KiB；或反過來重複計算已快取檔案。
- **建議修法：** 對每個 scope transition 定義「必要檔案集合、已載入前提、顯示的是總量或增量」。F2 表頭也應與該口徑一致。

### 1.12 stats／F1／F2 實測沒有綁定可重現快照

- **嚴重度：Low**
- **問題：** 表格只記日期、列數與 Trial 數，沒有綁定 `sourceSha256` 或 `datasetVersion`。
- **為什麼現在不修之後會更貴：** 同日上游重新打包或內容更新後，無法判斷實測表對應哪個輸入。
- **建議修法：** 將三組實測證據綁定同一個 snapshot identifier。這是證據可重現性，不是新增產品需求。

## 2. 架構風險

### 2.1 建置時 quality 11 與 Cloudflare 實際傳輸被混成同一 oracle

- **嚴重度：Blocker**
- **問題：** 修訂 3 說 F1 必須量 Cloudflare response 的實際 `content-encoding` 與實收位元組；修訂 4 卻把 `brotliBytes` 定義為 build-time quality 11，再讓 F2、D7 把它當成實際下載大小。Cloudflare 的動態壓縮品質、header、內容協商與未壓縮小檔並不由 artifact 契約控制，因此兩者沒有必然相等關係。
- **為什麼現在不修之後會更貴：** payload gate、manifest、UI 文案與部署驗收會建立在三個不同數字上；日後即使所有測試全綠，UI 仍可能向使用者報錯大小。
- **建議修法：** 規格必須選定單一語意：

  - `brotliBytes` 是 deterministic quality-11 **估算值**，UI 明示為估算；F1 仍以實際 response 為唯一使用者成本 oracle；或
  - 宣告它是實際部署量測值，並要求其來源與更新時點確實來自目標部署 response。

  不能同時稱為 quality-11 建置值與實際傳輸值。

### 2.2 實際 response 可能是混合 encoding

- **嚴重度：Medium**
- **問題：** F1 一方面要求全部 response，另一方面括號寫「brotli」。HTML、字型、小型 manifest 或錯誤 response 可能不是 `br`。目前不清楚非 br response 是直接失敗、以其實際 encoding 計入，還是使用 fallback 值。
- **為什麼現在不修之後會更貴：** 不同 CI 環境會用不同解讀通過同一門檻。
- **建議修法：** 封存為「逐 response 依實際 `content-encoding` 計入實收 body bytes」，並另列哪些 JSON response 必須為 br；或明定所有納入 response 必須為 br。兩者擇一。

### 2.3 gzip fallback 沒有選擇規則

- **嚴重度：Medium**
- **問題：** §9.3.5 說 gzipBytes 供無 brotli 環境 fallback，但 §8.5／D7 一律取 `brotliBytes`；沒有規定 UI 在下載前如何決定應顯示哪個。
- **為什麼現在不修之後會更貴：** UI 永遠顯示 br 數字也能通過 D7，無 brotli 環境的 fallback 成為不可驗證空話。
- **建議修法：** 封存大小選擇政策及顯示標籤；D7 同時驗 br 與 fallback 分支。

### 2.4 沒有撞到純靜態限制，但增加了部署供應商耦合

- **嚴重度：Medium**
- **問題：** 六項修訂均可維持純靜態，沒有要求 backend/database/runtime API；但 F1/D7 的語意被綁到 Cloudflare 當下的壓縮政策。
- **為什麼現在不修之後會更貴：** 換 CDN、Cloudflare 改壓縮策略或 preview/production 行為不同時，資料 schema 與 UI 文案也必須跟著改。
- **建議修法：** 將 artifact 中的 deterministic 壓縮估值與部署端實際傳輸驗收分層，不讓資料 schema 宣稱控制不了的 CDN 行為。

### 2.5 最難回頭的是 identity 合併邊界，其次是 Trial schema

- **嚴重度：High**
- **問題：** 前後空白合併直接決定 Trial membership、trialId、URL 與統計分母；9 欄 `displayFields` 則成為前端與 artifact 的公開 schema。
- **為什麼現在不修之後會更貴：** 一旦發布後再改 identity 邊界，會造成 Trial 分裂與 URL 變更；再把長文字移回 index 則會重破 F1 並要求 schema 遷移。
- **建議修法：** 在發布前優先封死 §6.2／§6.3.4／A1／A7 的一致性，以及 schemaVersion 決策。這兩項比壓縮欄位更需要先定案。

## 3. 驗證策略缺口

### 3.1 A1：「另有應合併案例」可被完全相同列取代

- **嚴重度：High**
- **問題：** 弱化實作只合併完全相同 raw、仍把尾端空白 variant 判 collision，也可用「完全相同列」滿足 A1 的應合併案例。
- **為什麼現在不修之後會更貴：** v0.8 最核心的新行為沒有真正被驗收。
- **建議修法：** A1 必須指定至少包含 leading-only、trailing-only、兩端空白及三個 raw variant 的合併案例，並寫死 fingerprint → trialId membership、`protocolRaw[]` 與 warning oracle。

### 3.2 A7 與新碰撞定義直接衝突

- **嚴重度：High**
- **問題：** A7 仍寫「兩個不同 raw、identityNormalize 相同 → collision」。弱化 fixture 若使用前後空白差異，會要求與 v0.8 相反的結果。
- **為什麼現在不修之後會更貴：** 測試作者可任選案例，使正確或錯誤實作都各有一套「合規」測試。
- **建議修法：** A7 明定 collision 正例必須 `strip(raw1) != strip(raw2)`，且至少分別覆蓋大小寫折疊與 NFKC 折疊；另加 whitespace-only 的必不碰撞反例。

### 3.3 A7 未驗證完整 collision report 關聯性

- **嚴重度：Medium**
- **問題：** 只要 report 非空且含所需字串即可通過；raw、fingerprint 與 member 未必正確配對。
- **為什麼現在不修之後會更貴：** 真實 collision 發生時 report 可能無法用於定位來源列。
- **建議修法：** 斷言 group/member 完整集合與配對關係精確相等，不只是欄位存在。

### 3.4 A9 的 18 組案例沒有涵蓋 whitespace merge × looseKey

- **嚴重度：Medium**
- **問題：** 弱化實作可以先對每個 raw variant 各建一個 Trial，再讓 looseKey 把它們揭露成 near duplicate；A9 只驗分組與 A1 membership，但 A1 未指定 whitespace membership 時仍可能通過。
- **為什麼現在不修之後會更貴：** 「只揭露不合併」會錯套到本應先合併的前後空白 variant。
- **建議修法：** 加入一組同時具有前後空白 variant 與另一個內部空白 identity key 的交叉 oracle，精確斷言 Trial 數、group 成員及 raw protocol 集合。

### 3.5 C6 無法驗證四個長文字欄位的 `rawVariants`

- **嚴重度：High**
- **問題：** 弱化實作完全不計算長文字 `rawVariants`，仍可用 9 個卡片欄位通過 C6。
- **為什麼現在不修之後會更貴：** 規格聲稱的「全部 13 欄」只是不可觀察敘述。
- **建議修法：** 先解決其 schema 承載位置，再要求 C6 對 9 個短欄與 4 個長欄各至少一個 oracle；若決定長欄不輸出，則刪除「全部 13 欄 rawVariants」要求。

### 3.6 A4／D6 沒有指定長文字唯一衝突案例

- **嚴重度：Medium**
- **問題：** 弱化實作只對 9 個卡片欄位做 conflict 判定，仍可能用短欄衝突 fixture 通過 A4、D6。
- **為什麼現在不修之後會更貴：** 長文字衝突 Trial 會被標成不 ambiguous。
- **建議修法：** A4 增加四個長欄各自為唯一衝突來源的 mutation；D6 明確區分「可篩選欄位」與「仍影響 `latestAmbiguous` 的不可篩選長欄」。

### 3.7 E6 只驗 inclusion／exclusion，漏掉另兩個被移出的欄位

- **嚴重度：Medium**
- **問題：** 弱化詳情頁可完全不呈現 `試驗目的` 或 `主要評估指標`，仍通過 E6 與 F3。
- **為什麼現在不修之後會更貴：** 修訂 2 將這兩欄唯一的使用者入口改成 shard 詳情頁，若入口缺失便是資料功能遺失。
- **建議修法：** E6 對四個移出欄位逐一斷言 record 切換後全文精確相等；長度壓力案例仍可集中在 inclusion/exclusion。

### 3.8 E7 可在長文字永遠缺席時假裝通過

- **嚴重度：Medium**
- **問題：** 長文字本來就不在 `displayFields`，因此「衝突候選值不出現在卡片」無法證明 conflict 有被偵測。弱化實作忽略長欄衝突也能通過。
- **為什麼現在不修之後會更貴：** 誤導防範的核心旗標可能漏報。
- **建議修法：** 對長欄唯一衝突案例同時斷言 `conflictFields` 精確集合、`latestAmbiguous=true`、卡片泛化警示及詳情候選值完整集合。

### 3.9 F1 沒定義「實收位元組」的精確邊界

- **嚴重度：Medium**
- **問題：** 弱化量測器可以使用 `Content-Length`、解壓後 body、Resource Timing 的 `transferSize`、只計已完成 response，或忽略 readiness 時仍在 flight 的請求；都可能宣稱符合文字。
- **為什麼現在不修之後會更貴：** 1.5 MB gate 在不同 runner 或瀏覽器產生不可比較結果。
- **建議修法：** 定義計入的是壓縮後 response body bytes、是否含 headers，以及 readiness 前已發起但稍後完成的 response 是否計入；CI artifact 必須逐 response 列出 URL、encoding、body bytes 與納入理由。

### 3.10 F1 的 MB／MiB 邊界未封存

- **嚴重度：Medium**
- **問題：** 表格以 KiB 計，且 `1536 − 924 = 612` 顯示實際採 1.5 MiB；文字卻寫 1.5 MB。介於 1,500,000 與 1,572,864 bytes 的實作可依任一口徑通過。
- **為什麼現在不修之後會更貴：** bundle 接近門檻時 CI 會出現互斥判定。
- **建議修法：** 直接以整數 bytes 封存門檻，並讓表格與餘額採同一單位。

### 3.11 `brotliBytes` 沒有任何內容正確性不變量

- **嚴重度：High**
- **問題：** 弱化實作可在 manifest 填任意小數字；D7 忠實讀取、F2 也「取自 manifest」，兩者都通過。I1–I7 不會重算 gzip/brotli metadata。
- **為什麼現在不修之後會更貴：** UI 與 CI 會形成循環自證：manifest 說多少，兩邊就都相信多少。
- **建議修法：** 將五個 top-level entry 的 `bytes`、`gzipBytes`、`brotliBytes` 納入可獨立重算的 manifest 一致性斷言，並要求 B6 有數值遭竄改但檔案內容不變的獨立反例。

### 3.12 D7 只驗「來源是 manifest」，不驗顯示值代表的下載集合

- **嚴重度：High**
- **問題：** UI 顯示 `searchLongAll.brotliBytes` 即可通過，但從預設 scope 進入 all+all 可能還需 short-all；反之，已下載的檔案也可能被重複計入。
- **為什麼現在不修之後會更貴：** UI 顯示看似精確但實際低報或高報，違反本輪改用 brotli 的原始目的。
- **建議修法：** D7 對每一個起始 scope → 目標 scope 寫死必要下載檔案集合、快取前提與 expected bytes 總和。

### 3.13 F2 是自我引用 oracle

- **嚴重度：High**
- **問題：** F2 說實測取自 manifest，而 manifest 數值本身沒有獨立驗證。弱化實作同時填錯 manifest 與 CI artifact 即可通過。
- **為什麼現在不修之後會更貴：** 20% 告警完全失去偵測能力。
- **建議修法：** F2 的 CI oracle 必須來自對 artifact 的獨立量測；manifest 僅是被驗證對象，不得同時作 expected value。

### 3.14 F3 可被編碼、別名或壓縮層繞過

- **嚴重度：Medium**
- **問題：** 弱化實作可把長文字放進 Tier 0 的別名鍵、編碼字串或另一個物件；若只在壓縮 response bytes 搜尋明文 canary，也會天然找不到。
- **為什麼現在不修之後會更貴：** 初始 payload 仍可攜帶全部長文字，卻通過內容與欄位鍵檢查。
- **建議修法：** F3 明定檢查對象是解碼、解壓並解析後的 logical payload；斷言四欄 canary 在 Tier 0 所有可達 JSON value 中均不存在，且 Trial/displayFields 的允許鍵集合精確符合 9 欄減衝突欄位。

### 3.15 I7／H2／H3 無法偵測壓縮 metadata 漂移

- **嚴重度：Medium**
- **問題：** `datasetVersion` 與 `artifactDigest` 都排除 manifest；壓縮器或 `brotliBytes` 改變時，兩個 digest 仍可不變。H2/H3 只看 digest、tree/no commit 時，無法證明數值與部署實際 response 一致。
- **為什麼現在不修之後會更貴：** 冪等測試可全綠，但 D7 顯示值已失真。
- **建議修法：** H2/H3 應將壓縮 metadata 的獨立重算結果列入相等性 oracle；若採「部署實測值」語意，則應明確排除其進入 dataset 冪等，改由部署驗收負責。

### 3.16 修訂 6 只有算術閉合，仍可整體分類錯誤

- **嚴重度：Medium**
- **問題：** 弱化實作可以把 Trial 分到錯誤 bucket，只要三類總數仍為 5,888 即通過修訂文字中的 cardinality 證據。
- **為什麼現在不修之後會更貴：** 「疑慮解除」可能被誤當成 stats 正確性驗證。
- **建議修法：** 保持 I6／E2 的逐 bucket multiset 與 index 重算為真正驗收 oracle；在修訂 6 明說這些實測數字只解除 payload cardinality 疑慮，不構成分類正確性證明。

## 4. 更簡單的替代方案

### 4.1 修訂 1：沒有明顯 over-engineering

- **嚴重度：Low**
- **問題：** `strip` 後相同才合併，其餘折疊 fail-closed，是符合風險排序的最小分界。
- **為什麼現在不修之後會更貴：** 真正成本來自多份相互矛盾的碰撞定義，不是規則本身。
- **建議修法：** 不改方向；只需讓 §6.3.4、A1、A7、A9 與 §9.8 共用同一個定義與案例矩陣。

### 4.2 修訂 2：移出四個長文字是必要簡化，但「仍輸出全部 13 欄 rawVariants」反而複雜化

- **嚴重度：High**
- **問題：** 長文字只在 shard 詳情逐 record 呈現時，再維持 Trial-level `rawVariants` 並沒有明確消費者，卻需要新的承載模型。
- **為什麼現在不修之後會更貴：** 為一個沒有既定 UI surface 的旗標擴張 schema，會引入更多不變量與版本遷移。
- **建議修法：** 最簡單且與現有 UI 一致的方案，是長文字仍參與 conflict／`latestAmbiguous`，但不宣稱輸出其 `rawVariants`；詳情頁直接逐 record 顯示原文。若產品確實要顯示「等價 raw variants」，才保留新的 cohort metadata 契約。

### 4.3 修訂 3：實際傳輸量測方向正確，不算 over-engineering

- **嚴重度：Medium**
- **問題：** 複雜度來自同時保留 q11 理論值作精確使用者成本，而非實際 response 量測本身。
- **為什麼現在不修之後會更貴：** 雙 oracle 會使 CI 與 UI 永久分歧。
- **建議修法：** F1 保留實際 response oracle；建置時 q11 值只作 deterministic estimate，不與「實際傳輸」混稱。

### 4.4 修訂 4：為五個檔保存壓縮估值合理，但精確到 bytes 的 UI 承諾偏重

- **嚴重度：Medium**
- **問題：** 使用者需要的是切換 scope 前的成本級距，不一定需要一個會受 CDN 壓縮策略影響的精確 byte 數。
- **為什麼現在不修之後會更貴：** 精確值要求會把 manifest schema、CI 與 Cloudflare runtime 綁死。
- **建議修法：** 若保留 build-time q11，UI 契約可明定為四捨五入後的「約 X KiB／MiB」估值；若堅持精確值，則只能使用實際部署量測來源。前者較簡單且完全相容純靜態架構。

### 4.5 修訂 5：三個 scope 數字不足，改用檔案集合模型更簡單

- **嚴重度：Medium**
- **問題：** 以 scope 名稱記單一數字，在轉換路徑與快取存在後必然產生「總量／增量」歧義。
- **為什麼現在不修之後會更貴：** 每新增 scope 都要再解釋一組轉換數字。
- **建議修法：** 規格以「每個 scope 所需檔案集合」為唯一事實，再由集合差導出切換成本；F2 表格只記各獨立檔案的壓縮基線。

### 4.6 修訂 6：屬證據補充，沒有必要再擴成新 gate

- **嚴重度：Low**
- **問題：** 把 371／7／3 等當永久門檻會把特定快照資料誤升格成產品契約。
- **為什麼現在不修之後會更貴：** 上游合法新增 applicant 就會造成無意義失敗。
- **建議修法：** 保留為綁定快照的實測說明；正式 gate 維持 I6 的動態重算與 E2 的完整 multiset 對帳。

整體判定：**v0.8 尚不宜直接封存**。最少應先關閉 1 個 Blocker：

1. 統一「實際 Cloudflare 傳輸」與「quality-11 建置估值」的語意。

以及 5 個 High：

1. 同步 §6.3.4／A7 的碰撞定義。
2. 決定四個長文字欄位的 `rawVariants` 是否存在及其承載位置。
3. 解決 schemaVersion。
4. 定義 F2／D7 的 scope 檔案集合與增量口徑。
5. 為 `brotliBytes` 建立獨立、非循環的正確性 oracle。
