# Fixtures

凍結測試資料與手寫 oracle。對應 `.ai-review/plan.md` v0.7 §11 的驗收編號。

**這裡沒有 ETL 實作。** `build_*.py` 只把字面值寫成 CSV 或注入輸入；`check_*.py` 只檢查
fixture 資料本身的性質，不計算 Trial 模型。唯一的例外是 `artifact_sample/`，見下。

## 目前有什麼

| 目錄 | 對應驗收 | 規模 | 用途 |
|---|---|---:|---|
| `a_core/` | A1–A6、A9、A10（兼 C1–C3、C5 的資料面） | 77 列 | 正常路徑的全部 A 群案例 |
| `a7_identity_collision/` | A7 | 5 列 | identity 正規化碰撞 → 硬失敗 |
| `b_failures/` | B1／B2／B3／B4／B5 | 12 個輸入 | §9.5 每個 error code 的注入 |
| `artifact_sample/` | **B6／B8**、C1／C3／C4 | 8 Trial | 最小合規 artifact 樣本 ＋ 反例 |

`run_all.py` 一次跑完五支自檢（目前 **289 條斷言**）。

A8（ID 截短碰撞）**沒有 fixture**：真實的 64 位元 SHA-256 碰撞需約 `2^32` 次雜湊，
不適合放進單元測試。改以注入的雜湊替身驅動，詳見 `.ai-review/fixture-findings-a.md` 的 GAP-6。

## 檔案角色

- `build_*.py` — 產生 `input.csv`（UTF-8 with BOM、CRLF，比照來源 `205_2.csv`）與 `rows.json`。
  16 欄值全部是字面值，不從活資料抽樣。
- `rows.json` — `rowKey → 16 欄值`。**oracle 一律用 `rowKey` 指涉列，不用 CSV 列序**，
  因為 A3 要打亂列序重跑。
- `oracle.json` — **手寫**。刻意不由 `build_*.py` 計算：A5 要求 oracle 的 row identity
  獨立於 §6.3 的 canonical serialization，若兩邊共用推導就會一致地錯而通過。
- `check_*.py` — 驗證 fixture **真的含有** oracle 宣稱的案例。fixture 最常見的失效
  方式是「宣稱含某案例但其實沒有」，而那在實作寫出來以前不會被發現。

## `artifact_sample/` 的特殊地位

它是唯一會「算東西」的目錄，因為 B8 要證明的正是「照 §9.3.2 的文字算得出來」。
但它**仍然不是 ETL**：兩個 Trial（`WS-003`／`PH-004`）的模型內容是手寫的，
只有 canonical serialization、`trialId`／`recordId`、`datasetVersion`、`artifactDigest`
是照規格算的。

**M1 不得沿用 `build_sample.py` 的函式當實作。** 規格要能被兩份獨立的程式碼各自寫出來
才算寫清楚；本目錄提供的是「可實作」的證據，不是答案。

## 跑法

```bash
python tests/fixtures/run_all.py                 # 全部自檢，exit 0 為通過

# 個別重建（改了 build_*.py 才需要）
python tests/fixtures/build_a_core.py                   # a_core（77 列）
python tests/fixtures/build_a7.py                       # a7
python tests/fixtures/b_failures/build_b_failures.py    # b_failures 的 12 個注入輸入
python tests/fixtures/artifact_sample/build_sample.py   # artifact 樣本 → out/
```

Windows 主控台預設 Big5，看中文輸出要加 `PYTHONIOENCODING=utf-8` 並重導向到檔案再讀。

## oracle 的約定

- **不寫 `trialId`／`recordId` 的字面值**（雜湊輸出手寫不可能）。ID 只檢查格式、唯一性
  與跨排列穩定性；語意用 `rowKey` 群組表達。
- **規格未定義之處填 `"__SPEC_GAP__"`**，並在 `specGaps`／`specGapStates` 說明，
  不猜一個值填進去。**GAP-1～GAP-12 已全部結案**（v0.6／v0.7），目前沒有 open 的 gap。
  `CMP-035`～`CMP-039` 是它們留下的回歸案例：前三組釘住 v0.6 新增的三個語意狀態，
  後兩組釘住 v0.7 的**複合狀態**（`numericRange + numericOutOfRange`）——
  那是第四輪覆審指出「以單一旗標做窮盡檢查不夠」的具體反例。
- **計數要數全部列，不是「為該案例設計的列」**。踩過兩次：初版把 `排除條件="N/A"` 寫成 1 筆
  （實際 3 筆）；本輪 `periodEndMissing` 差點只寫 `pd031-missing`，實際還有 `nonid-test`
  （上游測試列的期間兩端本來就是空的）。`numericStateCounts` 因此改為八類互斥且加總
  必須等於 `列數 × 2` 的形式，讓漏數直接失敗。

## artifact 樣本為什麼收了 8 個 Trial

每一個都是為了讓某條驗收**做得出反例**，不是為了「多一點資料」：

| Trial | 在樣本裡的職責 |
|---|---|
| `WS-003` | `rawVariants` 的代表值規則（recordId 字典序最小者）必須真的算得出來 |
| `PH-004` | 衝突欄位在 `displayFields` 中**完全省略**的形狀 |
| `IND-005`／`NR-028` | **同屬 shard `c4`**——B6 的「record 被兩個 Trial 引用」若跨 shard 會連帶違反 shard 歸屬而無法隔離 |
| `未列編號` | 兩個分類欄位的 `"0"` sentinel（C1 的五處斷言、C4 的前兩個 mutation） |
| `TXT-021A/B/C` | `N/A`／`NA`／空 三型文字 sentinel（C3、C4 的第三個 mutation） |

## 尚未建立

- D／E／F／G／H 群（前端與 CI，需先有實作）
- 長文字 fixture（E6／F3 的 22,490 字元案例與多筆分散 canary）
- `numericRange` 單端超界的案例（等 GAP-9 定案才知道 oracle 該寫什麼）
