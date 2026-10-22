# Plan verdict r6 — v0.10 修訂的逐項判定

- 日期：2026-10-22
- 對象：`plan-review-r6.md`（Codex `gpt-6-astra`，只審 v0.10 修訂本身）
- 基準：`.ai-review/plan.md` v0.10 @ `c7357df`

**統計：接受 7／部分接受 5／拒絕 0（範圍蔓延 0）。Blocker 0／High 0。**

判定前查過實資料（2026-10-22 live dry-run，5,928 Trial）：純空白申請者 0、U+001C–U+001F／U+0085 0、零寬字元 0、`N/A` 申請者 1 個 Trial。所以 R6-1／R6-2 在**現行快照**上不改變任何輸出，屬於「規格沒定義、資料剛好沒踩到」——那正是 v0.8 首次實跑的教訓，照樣修。

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|------|--------|------|------|
| R6-1 | facetNormalize 內部空白未封閉 | Medium | **接受** | 屬實。實作用 Python `\s`（含 U+001C–U+001F，不含部分 `White_Space`），與 §6.0 封閉集合不同。改為明定壓縮與 strip 都用 §6.0 的 `White_Space=Yes` 集合、輸出 U+0020；零寬與集合外控制字元不動。實作改用顯式字元類別 |
| R6-2 | 非空 typed 正規化後成空鍵 | Medium | **接受** | 屬實：`parse_text` 只把 `""` 視為 null，`" \t"` 的 typed 非空，v0.10 實作會產生 `""` bucket。定案：衝突 → typed null → 鍵為空，依序判；空鍵歸「未提供」、禁止 `""` bucket；`facetKeys` 帶 `""` 表示（鍵 ≠ typed 的一般規則自然成立），前端讀到 `""` 即「未提供」 |
| R6-3 | §7.1 仍寫 typed 篩選；facetKeys 鍵集合未封閉 | Low | **接受**（併 R6-12） | §7.1 第 443 行改引 §9.3.5；`facetKeys` 允許鍵封閉為 `臨床試驗申請者`，不得有額外鍵、不得為空物件 |
| R6-4 | 舊 URL 延期不得被讀成允許靜默零結果 | Medium | **部分接受** | 規格層接受：明定「格式合法但不在 bucket 的 applicant 值」屬 §7.4 無效值路徑，§15 的延期不豁免。**實作仍延到 review #3**——現行前端對任何不在 facet 的值都靜默零結果（v0.9 就已違反 §7.4），v0.10 只是多一類來源。§15 改寫成「已知違反，追蹤於 #3」，不再寫成「未涵蓋」 |
| R6-5 | §9.3.5 manifest 範例 `schemaVersion: 1` | Low | **接受** | 範例改 3，版本 1 的豁免說明標為歷史 |
| R6-6 | 稀疏性不能由 F1 代驗 | Medium | **部分接受** | 問題屬實，但修法併入 R6-8：稀疏性的必要與充分條件已在 I6，缺的是 B6 反例，不另立條文 |
| R6-7 | D4／E2 未鎖住「勾一個選項取回整組」 | Medium | **接受** | 新增 **D9**：跨不同 Trial、≥3 變體（尾隨 TAB、CRLF、前導 U+3000、內部 NBSP、U+F9B3），斷言唯一 bucket 的精確值與計數、選取後 trialId 集合完全相等且數量 == bucket 計數、canonical URL 與 reload |
| R6-8 | B6 對 I6 的新約束無獨立反例 | Medium | **接受** | B6 對 I6 明列：鍵值錯、冗餘鍵、必要鍵缺失、衝突者帶鍵、未提供者帶鍵、額外鍵、空物件，以及「stats 與 facetKeys 同步改成同一錯誤分組、typed 不變」（殺讀 facetKeys 自證的驗證器） |
| R6-9 | C1／C3／D6／E7 對 facet 路徑的邊界 | Medium | **部分接受** | 接受兩點並入 D9：phase／scale 合法值（含 `Phase Ⅱ`）不經 facetNormalize；applicant 的 `N/A`／`NA` 是**文字**，各自成 bucket，不歸「未提供」（不得套 C1 的分類 sentinel 政策）。D6／E7 的「衝突者不帶 facetKeys」已由 I6 定義、由 R6-8 的反例承擔，不另改 D6／E7 |
| R6-10 | 四套正規化獨立性未被證明 | Medium | **接受** | 並入 D9：`甲 乙`／`甲乙` 分屬兩個 bucket（conflictText 會合併）；`ABC`／`abc` 分屬兩個 bucket（search 會合併）；尾綴 U+200B 不合併。facet 鍵由 §6.4.3 代表值的 typed 導出，不引入多 bucket membership |
| R6-11 | NFKC 後才形成的特殊字元；卡片仍顯示 raw | Medium | **部分接受** | 接受案例、降為 D9 的子項而非改寫 E4：申請者含 U+FE64／U+FE65（NFKC → `<`／`>`）時，篩選選項以文字呈現；同一變體 Trial 的卡片顯示 raw。E4 原條文的 surface 盤點已涵蓋篩選選項，缺的只是會被 NFKC 製造出來的輸入 |
| R6-12 | facetKeys 看似通用機制 | Low | **部分接受**（併 R6-3） | 不改架構，只封閉鍵集合。Codex 自己的結論也是「不構成 over-engineering」 |

## 未接受為新範圍的事

無。R6-4 的實作屬既有 review #3，不是本輪新增需求。

## 送審前自查（本輪未由 Codex 提出）

- **S1**：v0.10 的 §15 寫「已知未涵蓋」，實際是對 §7.4 的已知違反——用詞會讓人以為規格允許。R6-4 一併改正。
