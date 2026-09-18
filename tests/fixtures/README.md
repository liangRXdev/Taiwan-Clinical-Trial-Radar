# Fixtures

凍結測試資料與手寫 oracle。對應 `.ai-review/plan.md` v0.4 §11 的驗收編號。

**這裡沒有 ETL 實作。** `build_*.py` 只把字面值寫成 CSV；`check_*.py` 只檢查 fixture
資料本身的性質，不計算 Trial 模型。

## 目前有什麼

| 目錄 | 對應驗收 | 列數 | 用途 |
|---|---|---:|---|
| `a_core/` | A1–A6、A9（兼 C1–C3 的資料面） | 50 | 正常路徑的全部 A 群案例 |
| `a7_identity_collision/` | A7 | 5 | identity 正規化碰撞 → 硬失敗 |

A8（ID 截短碰撞）**沒有 fixture**：真實的 64 位元 SHA-256 碰撞需約 `2^32` 次雜湊，
不適合放進單元測試。詳見 `.ai-review/fixture-findings-a.md` 的 GAP-6。

## 檔案角色

- `build_*.py` — 產生 `input.csv`（UTF-8 with BOM、CRLF，比照來源 `205_2.csv`）與 `rows.json`。
  16 欄值全部是字面值，不從活資料抽樣。
- `rows.json` — `rowKey → 16 欄值`。**oracle 一律用 `rowKey` 指涉列，不用 CSV 列序**，
  因為 A3 要打亂列序重跑。
- `oracle.json` — **手寫**。刻意不由 `build_*.py` 計算：A5 要求 oracle 的 row identity
  獨立於 §6.3 的 canonical serialization，若兩邊共用推導就會一致地錯而通過。
- `check_*.py` — 驗證 fixture **真的含有** oracle 宣稱的案例。fixture 最常見的失效
  方式是「宣稱含某案例但其實沒有」，而那在實作寫出來以前不會被發現。

## 跑法

```bash
python tests/fixtures/build_a_core.py     # 重新產生 a_core
python tests/fixtures/build_a7.py         # 重新產生 a7
python tests/fixtures/check_a_core.py     # 自檢，exit 0 為通過
```

Windows 主控台預設 Big5，看中文輸出要加 `PYTHONIOENCODING=utf-8` 並重導向到檔案再讀。

## oracle 的約定

- **不寫 `trialId`／`recordId` 的字面值**（雜湊輸出手寫不可能）。ID 只檢查格式、唯一性
  與跨排列穩定性；語意用 `rowKey` 群組表達。
- **規格未定義之處填 `"__SPEC_GAP__"`**，並在 `specGaps` 區塊說明，不猜一個值填進去。
  目前 `a_core/oracle.json` 有 7 個 gap，全部在 `.ai-review/fixture-findings-a.md` 展開。
- **計數要數全部列，不是「為該案例設計的列」**。初版 oracle 把 `排除條件="N/A"` 寫成 1 筆
  （實際 3 筆），因為漏了其他列的附帶出現——`check_a_core.py` 抓到的就是這個。

## 尚未建立

- B 群（ETL 失敗注入、promotion 邊界）
- C 群的 mutation（C4 的三個獨立 mutation）
- D／E／F／G／H 群（前端與 CI，需先有實作）
- 長文字 fixture（E6／F3 的 22,490 字元案例與多筆分散 canary）
