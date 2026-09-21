# 第五輪判定（`plan-review-r5.md`）

- **判定日期**：2026-09-21
- **統計**：**接受 35／部分接受 4／拒絕 0**（其中範圍蔓延 0）
- **Blocker 1／High 8**，全部已修訂，規格改為 **v0.9**

## 送審前自查已修掉的 4 處

這些是 v0.8 修訂自造、我在送審前自己掃出來的，不計入本輪統計：

| # | 問題 |
|---|---|
| S1 | §15 寫 Tier 0「923.7 KiB」，F1 表寫 924.0 KiB |
| S2 | F1 內文寫 `stats.json` 4.6 KiB brotli，同段表格寫 3.9 KiB |
| S3 | F1 驗收 (i) 仍寫「gzip 總和 ≤ 1.5 MB」，與本節定案的 brotli 口徑直接衝突 |
| S4 | §8.5 索引載入段落仍引 v0.5 的 gzip 估值（2,044／1,649／5,389 KiB），已被 F2 的 brotli 實測取代 |

**四輪的形狀第五次重演**：修訂本身會製造新洞，而且**最容易漏的是「同一個數字在兩個地方」**。

## 本輪最重要的一件事

Codex 的 Blocker 指出我犯了**本次修訂正要修掉的那個錯**。

v0.8 把 F1 從 gzip 改 brotli，理由寫得斬釘截鐵：「量一個使用者從來不會付的數字，正是自我誤導」。
然後我把 `brotliBytes` 定義成 **build-time quality 11**，再讓 F2 與 D7 拿它當「實際下載大小」——
**Cloudflare 的動態壓縮品質不由 artifact 契約控制**（一般在 q4–q5，不是 q11），所以 q11 估值
系統性**低於**實際傳輸。換句話說：我把 gzip 換成了另一個使用者同樣不會付的數字，而且這次
因為名字叫 `brotliBytes`、單位也對，更難發現。

**判定：接受。** `brotliBytes` 明定為 **deterministic 建置期估算值**，UI 顯示「約 X KiB」；
F1 的唯一 oracle 是**部署端實際 response 的實收位元組**。兩者不得互稱。
連帶後果：**規格裡 924.0 KiB 這個數字降級為估算值**，F1 的最終判定要等 M2 對真實部署量過才算數。

## 逐項判定

### 1. 需求與邊界缺漏

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| 1.1 | §6.3.4 仍留 v0.7 碰撞定義 | High | **接受** | 查證屬實：§6.3.4 表格仍寫「不同 raw protocol → 相同 identity key」。**同一契約兩份不等價定義**，且這份還是 ETL 實作最可能照著寫的那份。改為直接引用 §6.2 |
| 1.2 | `strip()` 字元語意未封存 | Medium | **接受** | §6.0 只寫 `nfkc(strip(s))`，從未定義 strip 移除哪些字元。v0.8 把它升格為「合併或硬失敗」的邊界後，這個洞從無害變成會改變 Trial membership。封存為 Unicode 空白字元集合並點名 NBSP／U+3000／零寬字元 |
| 1.3 | whitespace variant 群組與警告基數不明 | Medium | **接受** | `protocolRaw[]` 是 set 還是 multiset、warning 以什麼為單位，確實都沒寫。封存為 distinct set ＋ 每個 Trial 一則 warning |
| 1.4 | 合併後 Trial 與 `looseKey` 的交叉未定義 | Medium | **接受** | 合併後一個 Trial 有多個 raw protocol，§6.2.1 沒說 looseKey 以哪個集合算。封存為「Trial 的全部 `protocolRaw[]` 各自算 looseKey」，且一個 Trial 在 group 內只出現一次 |
| 1.5 | collision report 形狀不足 | Medium | **接受** | Codex 這一條的推理是對的且我沒想到：**碰撞成員共用同一個 identity key，因此 trialId 必然相同**，「各自的 trialId」在定義上無法區分成員。改為 group → members 的兩層結構，member 綁 raw／stripped／fingerprint |
| 1.6 | 長文字 `rawVariants` 失去承載位置 | High | **部分接受** | 問題屬實：§6.4.5 說 `rawVariants` 只放 `displayFields[field].flags`、「不另設 Trial 層級表示」，而 v0.8 把長文字移出 `displayFields` 卻仍宣稱「對全部 13 欄計算」——**那四欄的結果無處可去**。採**方案 1**（長文字參與衝突判定但不輸出 `rawVariants`）。**方案 2（在 shard 新增 cohort-level 欄位旗標 schema）判定為範圍蔓延而拒絕**：那四欄沒有任何 UI 消費者（卡片不顯示、詳情頁逐 record 顯示原文），為一個沒有讀者的旗標擴張 schema 只會多出不變量與版本遷移 |
| 1.7 | 「9 個鍵」與「衝突欄位完全省略」字面衝突 | Medium | **接受** | 兩句話同節並存，照字面實際鍵數可少於 9。改為「**允許**鍵的封閉集合為 9 欄，實際鍵集合 = 該集合扣除 `conflictFields` 中屬於這 9 欄者」 |
| 1.8 | 長文字衝突只得到泛化警示 | Medium | **接受** | 與 3.8 同源。長文字移出卡片後，「漏算長文字衝突」在 UI 上完全看不出來，而後果是 `latestAmbiguous` 漏報——**直接違反誤導優先的風險排序** |
| 1.9 | schemaVersion 與修訂 2 矛盾 | High | **部分接受** | 問題屬實（§9.3.6 明定欄位移除須 bump，而 manifest 仍是 1），但**嚴重度下修為 Medium**：本專案**尚未建 GitHub remote、尚未部署、不存在任何已發布或可被讀取的 schemaVersion 1 artifact**，因此沒有舊前端可被誤導。依 Codex 自己給的第二條路處理：在規格寫明「v0.8／v0.9 是首個可發布 schema，故仍為 1」的適用理由 |
| 1.10 | `files[*]` wildcard 與 schema 不一致 | Low | **接受** | 我刻意讓 shard 不帶 `brotliBytes`，卻用 `[*]` 寫法。改為列出五個具名 entry |
| 1.11 | F2 的 `all+all` 是增量還是總量不明 | High | **接受** | 查證屬實，我那張表的「＋`search-long-all` 1,840.7 KiB」確實三義。併入 4.5 的檔案集合模型一起改 |
| 1.12 | 實測未綁定可重現快照 | Low | **接受** | 三張實測表只記日期與列數。補綁 `sourceSha256` 與 `datasetVersion` |

### 2. 架構風險

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| 2.1 | q11 建置值與實際傳輸混成同一 oracle | **Blocker** | **接受** | 見上節。這是本輪唯一的 Blocker，也是我自己剛寫下的紀律的反例 |
| 2.2 | 實際 response 可能混合 encoding | Medium | **接受** | F1 寫「全部 network responses」又括號寫 brotli，HTML／字型／小檔未必是 `br`。封存為「逐 response 依實際 `content-encoding` 計入實收 body bytes」 |
| 2.3 | gzip fallback 沒有選擇規則 | Medium | **部分接受** | 問題屬實，但**不採「D7 同時驗 br 與 fallback 分支」**——那是為一個不存在的部署環境增加測試面。本專案部署目標唯一（Cloudflare Pages），正確作法是**刪掉 fallback 這句話**：`gzipBytes` 保留純粹供 CI 對照，不賦予它任何 UI 語意。移除不可驗證的敘述比為它補測試便宜 |
| 2.4 | 增加部署供應商耦合 | Medium | **接受** | 併入 2.1 的分層修法一併解決：artifact 內是 deterministic 估算值，部署端實際傳輸由 F1 驗收 |
| 2.5 | 最難回頭的是 identity 邊界與 Trial schema | High | **接受** | 排序正確。§6.2／§6.3.4／A1／A7 的一致性與 schemaVersion 優先於壓縮欄位，本次修訂依此順序處理 |

### 3. 驗證策略缺口

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| 3.1 | A1 的「應合併案例」可用完全相同列充數 | High | **接受** | 查證屬實：A1 現行文字只說「另須有『應合併』案例」，沒指名型態。**v0.8 最核心的新行為完全沒有被驗收**。指名 leading-only／trailing-only／兩端／三變體四類 |
| 3.2 | A7 與新碰撞定義直接衝突 | High | **接受** | A7 原文仍是「兩個不同 raw protocol 但 identity 正規化後相同」，**與 v0.8 相反**。明定正例須 `strip(raw1) != strip(raw2)`，並加 whitespace-only 的必不碰撞反例 |
| 3.3 | A7 未驗 collision report 關聯性 | Medium | **接受** | 現行只要求「非空且符合 §9.8」。配合 1.5 的兩層結構，改為斷言 group／member 集合與配對精確相等 |
| 3.4 | A9 未涵蓋 whitespace merge × looseKey | Medium | **接受** | 交叉案例確實會讓「先各建 Trial 再用 looseKey 揭露」的弱化實作通過 |
| 3.5 | C6 無法驗長文字 `rawVariants` | High | **部分接受** | 問題屬實，但**修法由 1.6 的方案 1 決定**：既然長文字不輸出 `rawVariants`，C6 不需要為它們加 oracle；改為**明確斷言長文字欄位的 `rawVariants` 不出現在任何輸出**（堵死「私自擴充 schema」那條路），並刪除規格中「輸出全部 13 欄 rawVariants」的敘述 |
| 3.6 | A4／D6 未指定長文字唯一衝突案例 | Medium | **接受** | 與 1.8／3.8 同源，一併補 |
| 3.7 | E6 只驗 inclusion／exclusion | Medium | **接受** | 修訂 2 把 `試驗目的`／`主要評估指標` 的**唯一使用者入口**改成詳情頁，而 E6 不驗這兩欄——入口整個不見也會全綠 |
| 3.8 | E7 可在長文字永遠缺席時假裝通過 | Medium | **接受** | 「候選值不出現在卡片」對本來就不在卡片的欄位是恆真斷言，證明不了衝突有被偵測 |
| 3.9 | F1「實收位元組」邊界未定義 | Medium | **接受** | `Content-Length`／解壓後 body／`transferSize`／in-flight request 各有不同答案。逐項封存，CI artifact 須逐 response 列出 URL、encoding、body bytes 與納入理由 |
| 3.10 | MB／MiB 未封存 | Medium | **接受** | 查證屬實：表格用 KiB 且 `1536 − 924 = 612` 是 MiB 算法，文字卻寫 1.5 MB。**依「不調鬆數字」紀律採較嚴的十進位**：封存為 **1,500,000 bytes**，餘裕隨之由 612.0 KiB 修正為 540.8 KiB |
| 3.11 | `brotliBytes` 無內容正確性不變量 | High | **接受** | 查證屬實：I1–I7 不重算任何大小 metadata，manifest 填任意數字時 D7 與 F2 都會通過——**循環自證**。新增不變量 I8 |
| 3.12 | D7 只驗「來源是 manifest」 | High | **接受** | 併入 4.5 的檔案集合模型：D7 改為對每個 scope transition 寫死必要下載檔案集合與 expected 總和 |
| 3.13 | F2 是自我引用 oracle | High | **接受** | F2 說「取自 `manifest.files[*].brotliBytes`」而 manifest 本身無人驗證。CI oracle 改為對 artifact 獨立重算，manifest 降為被驗證對象 |
| 3.14 | F3 可被編碼／別名／壓縮層繞過 | Medium | **接受** | 特別是「在壓縮後的 response bytes 裡搜明文 canary 天然找不到」——那是會**永遠全綠**的假斷言。明定檢查對象為解壓解析後的 logical payload 全部可達 JSON value |
| 3.15 | I7／H2／H3 偵測不到壓縮 metadata 漂移 | Medium | **接受** | 兩個 digest 都排除 manifest，故 `brotliBytes` 變動不會讓冪等測試轉紅。由 I8 一併解決 |
| 3.16 | 修訂 6 只有算術閉合 | Medium | **接受**（嚴重度下修 Low） | 我寫的「I6 成立」確實只證明三類總和閉合，不證明分類正確。補一句話澄清這些數字只解除 payload cardinality 疑慮 |

### 4. 更簡單的替代方案

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| 4.1 | 修訂 1 方向正確，成本在多份定義 | Low | **接受** | 不改方向，只統一 §6.3.4／A1／A7／A9／§9.8 的定義與案例矩陣 |
| 4.2 | 「仍輸出全部 13 欄 rawVariants」反而複雜化 | High | **接受** | 與 1.6 方案 1 同。**沒有消費者的欄位不該進 schema** |
| 4.3 | 修訂 3 方向正確，複雜度來自雙 oracle | Medium | **接受** | 與 2.1 同 |
| 4.4 | 精確到 byte 的 UI 承諾偏重 | Medium | **接受** | UI 契約改為四捨五入的「約 X KiB」。使用者要的是切換前的成本級距，不是一個會被 CDN 策略推翻的精確值 |
| 4.5 | 改用「每個 scope 所需檔案集合」模型 | Medium | **接受** | 這比記三個 scope 數字更簡單且無歧義，同時解決 1.11 與 3.12。F2 表格降為「各獨立檔案的壓縮基線」 |
| 4.6 | 修訂 6 不該擴成新 gate | Low | **接受** | 我本來就沒打算把 371／7／3 當門檻，但文字沒說清楚。補一句「綁定快照的實測說明，非產品契約」 |

## 結論

**需重審 → 已修訂為 v0.9，可以動工（M2）。**

Blocker 與 8 個 High 全部已修訂進 `plan.md`。本輪 **0 項範圍蔓延**，唯一被拒絕的是 1.6 的方案 2
（在 shard 新增 cohort-level 旗標 schema），理由是那四個欄位沒有任何 UI 消費者。

依 §14 的既有紀律，**修訂本身還沒被審過**。但本輪 39 項中沒有任何一項動到架構
（identity 邊界、Trial schema、檔案清單、壓縮策略的**方向**都不變，改的是定義精度與驗收斷言），
故不觸發「架構整段更動須重跑」的條件。M2 實作前不再排第六輪 prose 覆審——
**第五輪最大的收穫恰恰是「prose 覆審抓不到規格與現實的落差」的反面：
這一輪抓到的全部是規格內部一致性問題，那正是 prose 覆審擅長而實跑不會顯形的類別。**
兩種手段互補，不可互相取代。
