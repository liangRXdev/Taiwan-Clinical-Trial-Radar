"""16 欄的 canonical 順序與欄位分類（§3、§6.4.1、§6.6、§8.5、§9.3.4）。

**欄位順序是規範的**：§6.3 的 canonical serialization 依此順序輸出，順序錯了 ID 全錯，
而兩個數值欄位對調在數值上完全合理、不會有任何下游訊號（B 群 `schema_order` fixture
就是為此而設）。
"""
from __future__ import annotations

# §3：來源 16 欄，此順序即 canonical 欄位順序
COLUMNS: tuple[str, ...] = (
    "臨床試驗申請者",
    "臨床試驗計畫書編號",
    "臨床試驗計畫中文名稱",
    "臨床試驗期別",
    "本臨床試驗規模",
    "試驗目的",
    "試驗預計執行期間起",
    "試驗預計執行期間迄",
    "全球預計受試者人數",
    "台灣預計受試者人數",
    "適應症中文",
    "主要評估指標",
    "納入條件",
    "排除條件",
    "TFDA收文號",
    "資料更新時間",
)

PROTOCOL = "臨床試驗計畫書編號"
RECEIPT_NO = "TFDA收文號"
UPDATED_AT = "資料更新時間"

# §6.4.1：呈現欄位（封閉集合，13 欄）= 16 欄扣除 protocol、收文號、資料更新時間
PRESENTATION_FIELDS: tuple[str, ...] = tuple(
    c for c in COLUMNS if c not in (PROTOCOL, RECEIPT_NO, UPDATED_AT)
)

# §6.6.1 分類欄位與其合法值
CATEGORICAL_FIELDS: tuple[str, ...] = ("臨床試驗期別", "本臨床試驗規模")
LEGAL_CATEGORICAL: dict[str, frozenset[str]] = {
    "臨床試驗期別": frozenset(
        {"Phase Ⅰ", "Phase Ⅱ", "Phase Ⅲ", "Phase Ⅳ",
         "Phase Ⅰ,Phase Ⅱ", "Phase Ⅱ,Phase Ⅲ", "其他"}
    ),
    "本臨床試驗規模": frozenset({"多國多中心", "台灣單中心", "台灣多中心"}),
}

# §6.6.3 數值欄位
NUMERIC_FIELDS: tuple[str, ...] = ("全球預計受試者人數", "台灣預計受試者人數")

# §6.5.3 試驗預計執行期間（**不**套用 buildDate 上限——試驗預計執行到未來是正常的）
PERIOD_START = "試驗預計執行期間起"
PERIOD_END = "試驗預計執行期間迄"
PERIOD_FIELDS: tuple[str, ...] = (PERIOD_START, PERIOD_END)

# §6.6.2 文字欄位：呈現欄位扣除分類、數值、期間
TEXT_FIELDS: tuple[str, ...] = tuple(
    c for c in PRESENTATION_FIELDS
    if c not in CATEGORICAL_FIELDS and c not in NUMERIC_FIELDS and c not in PERIOD_FIELDS
)

# §8.5 搜尋 scope 的欄位分層
SHORT_SEARCH_FIELDS: tuple[str, ...] = (
    PROTOCOL, "臨床試驗計畫中文名稱", "臨床試驗申請者", "適應症中文", RECEIPT_NO,
)
LONG_SEARCH_FIELDS: tuple[str, ...] = ("試驗目的", "主要評估指標")

assert len(COLUMNS) == 16
assert len(PRESENTATION_FIELDS) == 13
assert len(TEXT_FIELDS) == 7
# §9.3.4：searchShortLatest 的 `f` 順序固定為 SHORT_SEARCH_FIELDS
assert len(SHORT_SEARCH_FIELDS) == 5
