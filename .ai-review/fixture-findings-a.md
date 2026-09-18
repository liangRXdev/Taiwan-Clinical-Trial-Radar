# A 群 fixture 反驗規格的結果

- **日期**：2026-09-18
- **受驗規格**：`.ai-review/plan.md` v0.4 §11 A1–A9（及其依賴的 §6.2–§6.6）
- **產出**：`tests/fixtures/a_core/`（50 列／29 Trial）、`tests/fixtures/a7_identity_collision/`（5 列）
- **方法**：先照 A1–A9 的要求手寫 fixture 與 oracle，**寫不出來或寫出來自相矛盾的地方就是規格的洞**
- **狀態**：`check_a_core.py` 全部通過（fixture 確實含有 oracle 宣稱的每個案例）

**尚無 ETL 實作程式碼。** 本輪只做凍結測試資料、手寫 oracle，以及一支只檢查「fixture 資料性質」的自檢腳本。

---

## 結論

A 群共 9 條驗收條件，**8 條可寫出 fixture，1 條（A8）不可**。另在寫 oracle 的過程中發現 **7 個規格洞**，其中 3 個是 High。

| 條件 | 可否落實 | 備註 |
|---|---|---|
| A1 group membership | 可 | 「不應合併」反例已改用 §6.2 不折疊的差異（連字號／空白／括號），與 A7 的 collision 案例分家 |
| A2 必含案例 + oracle | 可 | 12 類必含案例全部到位，見下表 |
| A3 排列決定性 | 可 | 5 種排列（asIs／reversed／3 seeds） |
| A4 反向哨兵 | 可 | 指定 tie group = BIG-001，指定斷言 = `latestAmbiguous` 翻轉 |
| A5 multiset multiplicity | 可 | oracle 的 row identity 用 `rows.json` 的 16 欄字面 tuple，與 §6.3 的 serialization 獨立 |
| A6 相同空 protocol | 可 | 但暴露 GAP-2、GAP-4 |
| A7 identity 碰撞 | 可 | 獨立 fixture，含兩組碰撞（大小寫、全半形）＋一列無碰撞對照 |
| **A8 截短碰撞** | **不可** | **GAP-6**，見下 |
| A9 nearDuplicateGroup | 可 | 3 組，且已驗 loose key 不影響收斂 |

fixture 覆蓋的 A2 必含案例：

| 要求 | 實現 |
|---|---|
| ≥1 個 10 列以上 protocol | `BIG-001`（11 列） |
| ≥1 組 16 欄全同純重複 | `DUP-002`；另 `BIG-001` cohort 內含一對 |
| ≥2 筆完全相同的空 protocol 列 | `empty-dup-a`／`empty-dup-b` |
| ≥3 組同日衝突 | `BIG-001`、`PH-004`、`IND-005`（另 `NUM-022` 見 GAP-5） |
| ≥1 組同日但正規化後全同 | `DUP-002` |
| ≥1 組同日僅空白／全半形差異（須判不衝突） | `WS-003` |
| ≥1 筆 `TFDA收文號="移案BPA"` | `RCP-014A`／`RCP-014B`（兼收文號跨 Trial 重複） |
| ≥1 個 `nearDuplicateGroup` | 3 組 |
| ≥1 筆 `protocolNonIdentifier` | `系統測試`（疑似測試列）、`未列編號`（真實試驗） |
| 四類日期異常各 ≥1 | `DT-015` 不可解析／`DT-016` 空值／`DT-017` 未來日期／`PD-020` end<start |
| （額外）`dateUnknown` 與 `latestAmbiguous` 獨立 | `DT-018`（兩者皆 true）／`DT-019`（前 true 後 false） |
| （額外）§6.6 數值四型 | `PH-004` 0／`IND-005` 空／`DT-015` 千分位／`DT-016` 負數 |

---

## 七個規格洞

### GAP-1（High）§6.4 的 `displayFields` 在「正規化後相同、raw 不同」時無定義

**觸發**：`WS-003` 兩列同日，名稱差半形／全形括號，納入條件多一個空格。

§6.4 規定衝突判定用正規化值、顯示用 raw 值。此組正規化後不衝突，於是該欄位要進 `displayFields`——但 `displayFields` 定義為「latestCohort 內無衝突呈現欄位的**共同 raw 值**」，而這裡**沒有共同 raw 值**。

oracle 只能填 `__SPEC_GAP__`。實測母體有 **14 組**屬此類，不是邊緣情形。

**建議**：正規化後相同而 raw 不同時，取 `latestCohort` 中 `recordId` 字典序最小者的 raw 值，並在該欄位加 `rawVariants: true`，詳情頁列出全部變體。

### GAP-3（High）`displayFields` 存 raw、typed 還是三元組未定義

**觸發**：`未列編號` 的 `臨床試驗期別="0"`、`本臨床試驗規模="0"`。

§6.6 要求分類 sentinel 的 typed value 為 `null`、UI 顯示「未提供」、raw 保留。但 §6.4／§9.3 的 `displayFields` 只寫「共同 raw 值」。raw（`"0"`）、typed（`null`）、UI 文字（「未提供」）三者不同，而 §9.3 的 Trial schema 沒說前端從哪裡取 typed。

**後果**：C1 要求「卡片顯示未提供」，若 `displayFields` 只有 raw，前端得自己再做一次 sentinel 判定——判定邏輯出現在兩處，且會分歧。

**建議**：`displayFields` 每個欄位存 `{raw, typed, flags}`，前端不重做判定；§9.3 明寫此形狀。

### GAP-6（High）A8 無法以凍結 fixture 滿足

A8 要求「注入不同 identity key 但 `trialId` 前 16 hex 相同的 fixture」。找出 SHA-256 的 **64 位元**截短碰撞需約 `2^32` 次雜湊（Pollard-rho 類方法為 O(2^32) 時間、O(1) 記憶體；生日表法另需數十 GB 記憶體）。這在單元測試中不實際，產物也只會是一對無意義的不透明字串。

而且它與 §11 開頭的「全部 fixture 為凍結資料」相牴觸——真實碰撞不是「凍結的來源資料」，是刻意搜出來的人工構造。

**後果**：照原文寫下去，實作者只會跳過 A8 或偽造一個假案例，`ID_TRUNCATION_COLLISION` 的偵測分支永遠沒有測試守著。

**建議**：A8 改為「以注入的雜湊函式（測試替身，刻意截短為極少位元）驅動碰撞偵測分支，斷言回傳 `ID_TRUNCATION_COLLISION` 且不發布」，並在 §11 開頭的凍結原則加上這個例外與理由。

### GAP-5（Medium）衝突比較模式套用於數值／分類欄位會產生假警報

**觸發**：`NUM-022` 兩列同日，唯一差異是 `全球預計受試者人數` `""` vs `"-5"`。兩者 typed 皆為 `null`（都是「未提供」），raw 卻不同 → 依 §6.4 判為衝突 → 該欄位被從卡片抽掉，使用者看到「同日多筆資料不一致」。

但兩筆其實都只是沒有有效數值。這是假警報，而 §6.4 引入正規化比較的目的**正是**要避免假警報（那 14 組空白差異就是為此排除的）。

**建議**：衝突判定分型——文字欄位比正規化 raw；數值與分類欄位比 typed value（兩者皆 `null` 即不衝突），raw 不同時加 `rawVariants` 標記。

### GAP-2（Medium）單一空 protocol 列是否帶 `#0` 後綴未定義

§6.3 寫「若多列 content hash 相同時附加出現序號 `#k`」。單列時是否帶 `#0` 沒寫。

**後果**：若單列不帶後綴，未來出現一筆內容相同的新列時，原本的 `H:x` 會變成 `H:x#0`，URL 失效。這與 §6.3 的「只保證對相同快照穩定」相容，但屬**可避免**的不穩定。

**建議**：一律帶序號（單列即 `#0`），使 ID 形狀不隨鄰居增減而改變。

### GAP-4（Medium）空 protocol 算不算 `protocolNonIdentifier`

§6.2.2 說「protocol 值不含任何英數字元時標記 `protocolNonIdentifier`」。空字串是這條的退化情形，但 §6.3 已對空 protocol 走另一條 `H:` 分支。兩節關係未寫明。

**後果**：本 fixture 的 `protocolNonIdentifier` 列數是 **5 還是 2** 取決於此（3 列空 protocol）。影響統計「未提供編號」的分母與 E8 的 UI 斷言對象。

**建議**：明寫空 protocol 也算（兩者是同一個「來源未提供編號」概念的兩種表現），或明確排除並說明理由。

### GAP-7（Medium）「不晚於 build 當日」與凍結 fixture 相牴觸，且邊界無法測

§6.5 的可採計日期依賴 build 當日，但 §11 要求 fixture 凍結。若不注入固定的 build 當日，未來日期的判定會隨真實時間漂移。

本 fixture 用 `2099/01/01` 迴避，並在 oracle 的 `harness.buildDate` 注入 `2026-09-18`。但這也意味著**「剛好晚一天」的邊界目前無法測試**。

**建議**：規格明定 build 當日為可注入參數，且驗收須含 build 當日（可採計）與當日+1（不可採計）兩個邊界案例。

---

## 寫 fixture 過程中的兩個方法論收穫

### 1. oracle 的計數要數「全部列」，不是「為該案例設計的列」

初版 oracle 我把 `排除條件="N/A"` 寫成 1 筆、`numericMissing` 寫成 2 筆——因為我只數了刻意為那個案例設計的列，忘了其他列的**附帶出現**。實際是 3 筆與 5 筆。

`check_a_core.py` 一跑就抓到三項。若沒有這支自檢，這些錯會等到實作寫完、測試轉紅時才被發現，而那時第一反應會是「實作錯了」而不是「oracle 錯了」。

**這也回頭驗證了 C3 的寫法是對的**：C3 要求「精確計數與對應 recordId」，正是這種錯的剋星。

### 2. 宣稱一個規格洞之前，要先讓資料真的觸發它

我最初寫下 GAP-5 時，fixture 裡**沒有**任何一組能觸發它——self-check 的 `[7]` 直接印出「未被觸發，需補一組…」。我補了 `NUM-022` 才讓它成為可證明的發現。

沒補的話，GAP-5 就只是一個看規格推想出來的擔憂，與「實測發現」是兩回事。

---

## 對規格的處置建議

7 個洞全部落在 M1 前須封存的範圍內（§6.3／§6.4／§6.5／§6.6／§9.3 與 §11 A8），與第二輪判定要求第三輪限縮審查的範圍**完全重疊**。

因此建議：**把這 7 項併入第三輪的送審材料**，一起審。理由是 GAP-1／GAP-3／GAP-5 都在動 `displayFields` 的形狀與衝突判定規則，而那正是第三輪要審的 §6.4；分兩次審會讓同一段被改兩輪，重演「修訂自造新洞」的模式。
