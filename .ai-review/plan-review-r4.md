# Codex 第四輪覆審（限縮：v0.5 → v0.6 的修訂本身）

- 審查日期：2026-09-18
- Codex：codex-cli 0.153.4（MCP，`sandbox: read-only`、`approval-policy: never`）
- 規劃文件：`.ai-review/plan.md` v0.6，commit `af1c295`
- 審查範圍：只審 §6.4.2、§6.6.3、§9.3.5、§9.3.6、§9.6、§11 的 B4／B6／C2／C5／E2／F1、§14 契約表第 11–13 列、§15 的 v0.6 條目
- 核心提問：**這些修訂本身有沒有製造新洞？**
- thread：`01a0b348-277d-7de1-a4c9-e00b28c83d3f`

以下為 Codex 原始輸出，**原封不動**落檔，不修飾不刪改。

---

結論：v0.6 的方向正確，未發現 Blocker；但修訂本身新造出 2 個 High、數個 Medium 缺口。最高風險是把「旗標集合」誤當成互斥「語意狀態」，以及 F1 同時把 1.5 MB 定義成全部 network responses、又只封閉三個資料檔。前者可能重新造成同日衝突任取值，後者可能到 M2 才發現預算口徑根本不同。

## 1. 需求與邊界缺漏

### 1.1 複合旗標沒有對應的 semantic state

- **嚴重度：High**
- **問題：** §6.4.2 宣稱比較鍵涵蓋 §9.3.3 每個 field flag，但 flags 並不是互斥狀態。例如超界範圍同時具有 `numericRange + numericOutOfRange`；`sourceZero` 是合法整數的附加旗標，不是另一種比較狀態。規格沒有定義複合旗標的狀態判定優先序。實作若先看到 `numericRange`，會遇到 `typed=null`；若先看到 `numericOutOfRange`，才會得到規格預期的 raw-based key。
- **為什麼現在不修之後會更貴：** 這會同時改變 `latestAmbiguous`、`conflictFields`、`displayFields` 省略結果、facet 與篩選分組。等 artifact 與前端都依其中一種解讀完成後再修，需重算資料模型與所有相關 oracle；也是本次最高「誤導」風險。
- **建議修法：** 不再宣稱「flags 封閉集合＝semantic states」。改列出封閉的合法狀態組合，例如合法 range、超界 scalar、超界 range、零值整數等，並為每一組指定唯一比較鍵；未列組合才硬失敗。這不是新增需求，而是讓既有兩階段模型可被唯一導出。

### 1.2 「無法評估」採全域線性順序，遮蔽無依賴的錯誤

- **嚴重度：Medium**
- **問題：** §9.3.6 規定任何上游步驟失敗，所有下游項目都回報「無法評估」。但 stats 一致性不依賴 record 排序或 shard referential integrity；digest 在檔案仍可讀時也不依賴 stats 語意正確。一個 shard 錯誤會遮蔽同時存在的 stats 或 digest 錯誤。
- **為什麼現在不修之後會更貴：** 對外仍會 fail-closed，所以不是發布安全洞；代價是多缺陷只能逐輪修復、逐輪重跑，CI report 的歸因能力會比 v0.6 宣稱的弱。
- **建議修法：** 將「無法評估」限制在真正缺少前置資料的檢查，而非序號較後的全部檢查。至少明定：inventory／可讀性是共同前置；referential integrity 只阻擋需要解析 record 的排序檢查；stats 與 digest 在其輸入可得時獨立評估。

## 2. 架構風險

### 2.1 E2 的唯一 oracle 與合法的非 facet 統計互相矛盾

- **嚴重度：Medium**
- **問題：** §9.3.5 一方面說 `updated` 不屬 facet，改以 `sourceUpdatedAt` 單一統計卡呈現；另一方面又規定 E2 的統計卡唯一清單只能是 `phase／scale／applicant`。這也與 §7.1 允許明確標示分母的審查紀錄次要統計衝突。照 E2 字面實作，合法的 `sourceUpdatedAt` 卡也必須失敗。
- **為什麼現在不修之後會更貴：** 前端資訊架構與 DOM oracle 會被迫二選一；到 M2 才處理會連動首頁、E2、E3、F1 readiness 與 payload。
- **建議修法：** 分開封閉「facet widgets」與「非 facet metadata/statistics」。E2 的三項雙向對帳只約束 facet widgets；`sourceUpdatedAt` 等非 facet surface 另由既有 E3 契約驗證。無須增加新功能。

### 2.2 F1 的預算口徑自相矛盾

- **嚴重度：High**
- **問題：** F1 先定義 Tier 0 為冷啟動至 readiness 的「全部 network responses」，隨後新增的封閉清單卻只列三個資料檔。HTML、JS、CSS、字型等到底是否計入 1.5 MB，無法唯一判定。
- **為什麼現在不修之後會更貴：** 這是最難回頭的架構風險。若 M1 依三個 JSON 過關、M2 才按全部 response 計算，可能需要重新切 bundle、字型或載入路徑；反之只算資料檔，CI 可在實際冷啟動超標時仍顯示合格。
- **建議修法：** 現在就二選一並改名一致：若 1.5 MB 是資料預算，明寫「Tier 0 data payload」；若是完整冷啟動預算，封閉清單只能作資料子集合，總和必須包含 readiness 前的所有 response。這是釐清既有預算，不是新增需求。

### 2.3 三 facet 決策本身沒有 over-engineering，但與 UI 卡片綁得過緊

- **嚴重度：Low**
- **問題：** 封閉 `stats.json.facets` 為三項是合理的；新洞來自把資料 schema 的 facet inventory 直接等同所有 UI 統計卡 inventory。
- **為什麼現在不修之後會更貴：** 後續任何合法的 provenance 或分母資訊，都會被誤判成 schema 擴張，迫使修改資料契約。
- **建議修法：** 保留三 facet 封閉集合，只解除「facet＝全部統計呈現」的等號。這是最小修訂。

## 3. 驗證策略缺口

### B4

- **嚴重度：Medium**
- **問題：** 弱化實作可先四捨五入到 4 位小數，仍通過 `0.1001／0.2001`，但在真實基線附近壞掉。例如 `prev=18736, cur=16862` 的 drop 約 `0.10002135`，四捨五入 4 位成 `0.1000`，warning 消失；`cur=14988` 的 drop 約 `0.20004270`，會被壓成 `0.2000` 而錯誤發布。
- **為什麼現在不修之後會更貴：** 這直接允許超過 20% 的驟降通過，是 last-known-good 邊界的破口。
- **建議修法：** B4 不只列兩個固定小數；應斷言一組整數 `(prev, cur)` 在 10%／20% 門檻正下、正好、以及「最接近且嚴格超過」時，分類與精確比例 oracle 完全一致。至少納入上述 18,736 基線兩例。

### B6

- **嚴重度：Medium**
- **問題：** 「每一條不變量」與列出的 mutation 不一致。弱化驗證器可以完全省略跨檔 `datasetVersion`、`artifactDigest` 重算，仍通過 B6；也可以只檢查已被引用 record 的 owner count，漏掉 shard 中存在但零 Trial 引用的 orphan record。另只驗一個 facet，也能通過單一 facet mutation。
- **為什麼現在不修之後會更貴：** 會再次出現「測試很強但驗證器少做整類檢查」；資料可內部自洽地遺失 record 關聯或錯置統計。
- **建議修法：** B6 的 mutation inventory 必須與 §9.3.6 七列雙向對帳；補上跨檔版本、兩種 digest、零 owner record，以及三個 facet 各自的 bucket mismatch。每例仍維持 exactly-equals 與必要的「無法評估」集合。

### C2

- **嚴重度：Medium**
- **問題：** 弱化實作可只讓 `台灣預計受試者人數` 正確、讓全球人數走另一套錯誤邏輯；目前沒有明定兩欄都跑完整矩陣。另外「斷言旗標」未明說集合完全相等，實作可額外附加 `numericUnparsed` 等錯誤旗標仍通過。
- **為什麼現在不修之後會更貴：** 多餘旗標會進一步改變 C5 的狀態 dispatch、warning 與 UI 文案，錯誤會跨層擴散。
- **建議修法：** 對兩個數值欄位各跑完整兩階段矩陣；逐例斷言 typed、field flag 集合、warning 分級、UI 與 enroll 歸類皆「完全相等」，不是僅包含預期值。

### C5

- **嚴重度：High**
- **問題：** 弱化實作可以分別正確處理合法 `numericRange` 與 scalar `numericOutOfRange`，卻無法處理 `numericRange + numericOutOfRange`；現有逐表列正例與 atomic flag exhaustiveness 仍會通過。這正是 1.1 的可驗收版本。
- **為什麼現在不修之後會更貴：** 會讓同日超界範圍任取 raw、錯判不衝突，重新打開 v0.6 原本要關閉的誤導路徑。
- **建議修法：** exhaustiveness 的 oracle 改為合法「狀態組合」而非單一 flags；至少加入兩個 raw 不同的超界 range 必須衝突，以及 NFKC 後等價的超界 range 必須不衝突且帶 `rawVariants`。

### E2

- **嚴重度：Medium**
- **問題：** 弱化前端可把未核准統計放進一般 section／badge，而不使用測試辨識的 card schema；三張核准卡則只顯示正確分母，卻省略或錯排 bucket，仍可能通過目前的 inventory 與總和斷言。
- **為什麼現在不修之後會更貴：** 測試會驗證元件命名，而非使用者實際看到的統計概念；也會掩蓋 2.1 的 `sourceUpdatedAt` 矛盾。
- **建議修法：** 先分開 facet 與 metadata surface；facet DOM 的名稱集合及每張卡的完整 bucket `value/count` multiset、`unprovided`、`conflicted`、單位與分母類型都須雙向完全相等。統計 surface 的辨識不可只依 CSS/card selector。

### F1

- **嚴重度：High**
- **問題：** 弱化量測器只加總新增封閉清單中的三個 JSON，即可通過；大型 JS、CSS、字型或 readiness 前其他 response 全部不計。反向弱化則可在固定查詢成功時停止計時，忽略仍在載入但 F1 又宣稱必要的 `stats.json`。
- **為什麼現在不修之後會更貴：** 會直到真實部署或效能回歸才發現 CI 的 1.5 MB 並非使用者冷啟動成本。
- **建議修法：** 先解決 2.2 的口徑選擇。若保留完整冷啟動定義，斷言 browser network inventory 至 readiness 的全部 response 與總 gzip；三個 JSON 另作「資料子集合必須恰好相等」的斷言。

## 4. 更簡單的替代方案

### 4.1 比較鍵：封閉狀態表取代「flags exhaustiveness」

- **嚴重度：High**
- **問題：** 現行方案同時維護欄位型別、flags 封閉集合、比較鍵表與 exhaustiveness，卻沒有定義它們之間的多對多關係。
- **為什麼現在不修之後會更貴：** 每新增一個輔助 flag，都可能被誤認為新的互斥狀態，再次產生 GAP-8 類型差集。
- **建議修法：** 保留既有 artifact flags，不新增欄位；只在 normative spec 中建立一張「合法 typed/flags 組合 → semantic comparison key」決策表。C5 直接以該表作唯一 oracle。

### 4.2 不變量：必要前置條件取代全域七步流水號

- **嚴重度：Medium**
- **問題：** 全域線性順序為了隔離一個排序案例，犧牲了其他獨立檢查的可評估性。
- **為什麼現在不修之後會更貴：** report 會反覆只揭露第一層缺陷，降低 fixture 與正式 CI 的診斷價值。
- **建議修法：** 每條不變量只列自己的必要前置條件；「無法評估」依輸入缺失決定。這比維護全域順序更少耦合。

### 4.3 Stats：資料 facet 與呈現 surface 分離

- **嚴重度：Medium**
- **問題：** 一個三項 facet 清單同時承擔 stats schema、filter 值域與所有統計卡 oracle，職責過多。
- **為什麼現在不修之後會更貴：** provenance 或單值 metadata 的 UI 變更會被迫修改 facet 資料契約。
- **建議修法：** `stats.json.facets` 仍恰為三項；E2 只驗 facet widgets。`sourceUpdatedAt` 沿用 manifest 與 E3，不納入 facet oracle。

### 4.4 F1：改成單一、可量測的資料預算

- **嚴重度：Medium**
- **問題：** 目前將「完整冷啟動」與「三個資料檔 gzip」疊成同一指標，複雜且無唯一答案。
- **為什麼現在不修之後會更貴：** 首份正式 artifact 即使量完，也只能回答資料大小，不能解決整站 response 是否計入的爭議。
- **建議修法：** 最簡單且最符合現有 1,236 KiB 基線的方案，是將 1.5 MB 明確定義為 Tier 0 data payload，封閉為三個檔；完整頁面載入不宣稱受此門檻約束。若產品真正要限制完整冷啟動，則必須另立清楚的全 response 指標，不能共用這個基線。
