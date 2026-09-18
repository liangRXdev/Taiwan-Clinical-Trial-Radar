"""§6.4.2 semantic comparison key。

**索引鍵是「合法的 `(typed 形狀, flags 組合)`」，不是單一旗標。** 旗標不互斥：
`numericRange + numericOutOfRange` 是複合（超界的區間），`sourceZero` 是合法整數的附加
旗標而非另一種比較狀態。照旗標逐一對應時，實作遇到複合組合沒有唯一答案。

**遇到表外組合必須硬失敗**，不得 fallback 到「比 raw」或「視為相等」。以單一旗標做窮盡
檢查時，一個「合法 range 對、scalar 超界對、複合的超界 range 壞掉」的實作會通過——
那正是本規格最怕的「測試全綠但功能是壞的」。
"""
from __future__ import annotations

from .fields import (
    CATEGORICAL_FIELDS,
    NUMERIC_FIELDS,
    PERIOD_FIELDS,
    TEXT_FIELDS,
)
from .normalize import conflict_text
from .parsing import FieldValue


class ComparisonKeyError(AssertionError):
    """§6.4.2 的組合表未涵蓋該組合。**這是規格缺口，不是可以 fallback 的情形。**"""


# 參與索引的旗標。`rawVariants` 不在其中——它是比較的**結果**不是輸入（§6.4.3）。
_INDEXED_FLAGS = frozenset(
    {
        "sourceZero",
        "numericMissing",
        "numericRange",
        "numericRangeInvalid",
        "numericImplausible",
        "numericUnparsed",
        "numericOutOfRange",
        "categoricalUnprovided",
        "categoricalUnknown",
        "periodStartMissing",
        "periodStartUnparsed",
        "periodEndMissing",
        "periodEndUnparsed",
    }
)

_PERIOD_FLAGS = frozenset(
    {"periodStartMissing", "periodStartUnparsed", "periodEndMissing", "periodEndUnparsed"}
)


def comparison_key(field: str, value: FieldValue) -> tuple:
    """回傳該欄位值的比較鍵。**比較鍵相同即不衝突**，即使 raw 不同。"""
    flags = tuple(f for f in value.flags if f in _INDEXED_FLAGS)

    # 第 1 列：文字欄位
    if field in TEXT_FIELDS:
        if flags:
            raise ComparisonKeyError(f"文字欄位不應帶旗標：{field} {flags}")
        return ("text", conflict_text(value.raw))

    if field in NUMERIC_FIELDS:
        # 第 2／3 列：合法整數。sourceZero 是附加旗標，**不影響比較**
        if flags in ((), ("sourceZero",)) and isinstance(value.typed, int):
            return ("int", value.typed)
        # 第 4 列：合法範圍
        if flags == ("numericRange",) and isinstance(value.typed, dict):
            return ("range", value.typed["min"], value.typed["max"])
        # 第 5 列：缺值。只有同為缺值才相等
        if flags == ("numericMissing",):
            return ("numericMissing",)
        # 第 6–8 列：typed 為 None 的單旗標異常
        if flags in (("numericUnparsed",), ("numericImplausible",), ("numericRangeInvalid",)):
            return (flags[0], conflict_text(value.raw))
        # 第 9 列：序 2 超界　第 10 列：序 3 超界（複合）
        # 兩列**同鍵**：都是「超出可表示範圍」，比較時只看 raw 原文。
        # numericRange 不進比較鍵——它只供 UI 說明來源形狀，多一個維度只是把同一件事判兩次。
        if flags in (("numericOutOfRange",), ("numericOutOfRange", "numericRange")):
            return ("numericOutOfRange", conflict_text(value.raw))
        raise ComparisonKeyError(f"§6.4.2 未涵蓋的數值組合：{field} typed={value.typed!r} flags={flags}")

    if field in CATEGORICAL_FIELDS:
        # 第 11 列：sentinel　第 12 列：非合法值　第 13 列：合法值
        if flags == ("categoricalUnprovided",):
            return ("unprovided",)
        if flags == ("categoricalUnknown",):
            return ("categoricalUnknown", conflict_text(value.raw))
        if flags == () and isinstance(value.typed, str):
            return ("cat", value.typed)
        raise ComparisonKeyError(f"§6.4.2 未涵蓋的分類組合：{field} typed={value.typed!r} flags={flags}")

    if field in PERIOD_FIELDS:
        # 第 14 列：可解析　第 15 列：不可解析／缺值
        if flags == () and isinstance(value.typed, str):
            return ("date", value.typed)
        if len(flags) == 1 and flags[0] in _PERIOD_FLAGS:
            return (flags[0], conflict_text(value.raw))
        raise ComparisonKeyError(f"§6.4.2 未涵蓋的期間組合：{field} typed={value.typed!r} flags={flags}")

    raise ComparisonKeyError(f"未知欄位：{field}")
