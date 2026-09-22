"""§6.5 日期規則與 §6.6 sentinel／分類／數值解析。

每個欄位解析成一個 `FieldValue`：`raw`（永不為 None）、`typed`（§9.3.3 的封閉型別）、
`flags`（§9.3.3 的 field-scoped 旗標，**排序後的 tuple**）。

**旗標是排序後的 tuple 而非 set**，因為 §6.4.2 的比較鍵以 `(typed 形狀, flags 組合)`
索引——組合必須有穩定表示才做得出窮盡 match。
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

from .fields import (
    CATEGORICAL_FIELDS,
    LEGAL_CATEGORICAL,
    NUMERIC_FIELDS,
    PERIOD_FIELDS,
    PERIOD_START,
    UPDATED_AT,
)
from .normalize import nfkc

# §6.6.3 可表示範圍：JSON number 可精確表示的整數上限
MAX_SAFE_INT = 2**53 - 1

_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
_INT_RE = re.compile(r"^\d+$")
_NEG_INT_RE = re.compile(r"^-\d+$")
# §6.6.3 序 3／4：嚴格範圍。分隔符為連字號類或「至」。
_RANGE_RE = re.compile(r"^(\d+)\s*(?:[-~～〜–—]|至)\s*(\d+)$")


@dataclass(frozen=True)
class FieldValue:
    raw: str
    typed: object = None
    flags: tuple[str, ...] = ()

    def with_flag(self, flag: str) -> FieldValue:
        """加一個旗標並維持排序（`rawVariants` 由 §6.4.3 在 cohort 層加上）。"""
        if flag in self.flags:
            return self
        return FieldValue(self.raw, self.typed, tuple(sorted(self.flags + (flag,))))


@dataclass
class ParsedDate:
    """§6.5.2 `資料更新時間` 的解析結果。"""

    raw: str
    date: _dt.date | None = None
    flag: str | None = None  # dateMissing／dateUnparsed／dateFuture；None 表示可採計

    @property
    def usable(self) -> bool:
        """**可採計**：格式正確、是實際日曆日、且不晚於 buildDate。"""
        return self.date is not None and self.flag is None


def _calendar_date(text: str) -> _dt.date | None:
    """`^\\d{4}/\\d{2}/\\d{2}$` 且可解析為**實際日曆日**（2026/13/45 不是）。"""
    s = nfkc(text or "").strip()
    if not _DATE_RE.match(s):
        return None
    y, m, d = (int(p) for p in s.split("/"))
    try:
        return _dt.date(y, m, d)
    except ValueError:
        return None


def parse_updated_at(raw: str, build_date: _dt.date) -> ParsedDate:
    """§6.5.2。**未來日期不得支配卡片**：晚於 `build_date` 者不可採計。

    邊界：等於 `build_date` **可採計**；`build_date + 1 日` 為 `dateFuture`。
    """
    if (raw or "").strip() == "":
        return ParsedDate(raw, None, "dateMissing")
    d = _calendar_date(raw)
    if d is None:
        return ParsedDate(raw, None, "dateUnparsed")
    if d > build_date:
        # 原值仍照顯示、仍出現在歷史，只是排除於 latestSourceDate 與全站 sourceUpdatedAt
        return ParsedDate(raw, d, "dateFuture")
    return ParsedDate(raw, d, None)


def parse_period(field: str, raw: str) -> FieldValue:
    """§6.5.3 試驗預計執行期間起／迄。**不**套用 buildDate 上限。"""
    assert field in PERIOD_FIELDS, field
    which = "periodStart" if field == PERIOD_START else "periodEnd"
    if (raw or "").strip() == "":
        return FieldValue(raw, None, (which + "Missing",))
    d = _calendar_date(raw)
    if d is None:
        return FieldValue(raw, None, (which + "Unparsed",))
    return FieldValue(raw, d.isoformat(), ())


def period_order_anomaly(start: FieldValue, end: FieldValue) -> bool:
    """§6.5.3：**只有兩端皆可解析時才比較順序**。end < start → periodEndBeforeStart。

    任一端不可解析或為空時回傳 False——硬比會把「取不到」誤報成「順序異常」。
    """
    if start.typed is None or end.typed is None:
        return False
    return end.typed < start.typed


def parse_numeric(raw: str) -> FieldValue:
    """§6.6.3，**兩階段**。

    階段一：對 `nfkc(strip(raw))` 依序 1–6 比對，第一個命中者決定分類。
    階段二：只在序 2／3 命中（產生了 typed 整數）時套用可表示範圍檢查。

    單端超界時 **typed 整個為 None**，不得留 `{min: 1, max: None}`——半個區間無法參與
    §8.4 的重疊判定，而「有 min 沒有 max」會讓前端與篩選各自猜邊界。
    保留 `numericRange` 旗標是為了讓 UI 說得出「來源是一個區間，但數值超出可表示範圍」。
    """
    v = nfkc((raw or "").strip())

    # 序 1：空字串
    if v == "":
        return FieldValue(raw, None, ("numericMissing",))

    # 序 2：純整數（不接受正負號、千分位、內部空白；接受前導零）
    if _INT_RE.match(v):
        n = int(v)
        if n > MAX_SAFE_INT:  # 階段二
            return FieldValue(raw, None, ("numericOutOfRange",))
        # 前導零：typed 為 26 但 raw 一律顯示 026——顯示 typed 就是改寫來源
        return FieldValue(raw, n, ("sourceZero",) if n == 0 else ())

    m = _RANGE_RE.match(v)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= hi:  # 序 3：嚴格範圍
            if hi > MAX_SAFE_INT:  # 階段二：任一端超界 → 整個 typed 為 None
                return FieldValue(raw, None, ("numericOutOfRange", "numericRange"))
            return FieldValue(raw, {"min": lo, "max": hi}, ("numericRange",))
        # 序 4：min > max。不自動交換、不隱藏
        return FieldValue(raw, None, ("numericRangeInvalid",))

    # 序 5：負數
    if _NEG_INT_RE.match(v):
        return FieldValue(raw, None, ("numericImplausible",))

    # 序 6：其他非空。**不從約略值推論**——把 20-40 讀成區間是結構解讀，
    # 把 約400 讀成 400 會丟掉「約」，那是推論。
    return FieldValue(raw, None, ("numericUnparsed",))


def parse_categorical(field: str, raw: str) -> FieldValue:
    """§6.6.1。`"0"` 是 sentinel：typed 為 None 但 **raw 必須保留**。"""
    assert field in CATEGORICAL_FIELDS, field
    v = (raw or "").strip()
    if v == "0":
        return FieldValue(raw, None, ("categoricalUnprovided",))
    if v in LEGAL_CATEGORICAL[field]:
        return FieldValue(raw, v, ())
    return FieldValue(raw, None, ("categoricalUnknown",))


def parse_text(raw: str) -> FieldValue:
    """§6.6.2。`N/A`／`NA`／`""` **互相可區分，不得塌成同一值**。

    空字串的 typed 為 None（§9.3.3「空字串視為 null typed」），但 raw 保留空字串，
    故三者在 raw 層仍然可分。
    """
    return FieldValue(raw, raw if raw != "" else None, ())


def parse_field(field: str, raw: str) -> FieldValue:
    """依欄位型別分派。`資料更新時間` 由 `parse_updated_at` 另外處理（需要 buildDate）。"""
    if field in NUMERIC_FIELDS:
        return parse_numeric(raw)
    if field in CATEGORICAL_FIELDS:
        return parse_categorical(field, raw)
    if field in PERIOD_FIELDS:
        return parse_period(field, raw)
    if field == UPDATED_AT:
        raise ValueError("資料更新時間 須以 parse_updated_at 解析（需要 buildDate）")
    return parse_text(raw)


def suspected_test_row(row: dict[str, str]) -> bool:
    """§6.2.2 疑似上游測試列。三條任一成立即是，**不自動刪除**，單獨計數警示。"""
    # (a) 申請者與中文名稱皆為空
    if row["臨床試驗申請者"].strip() == "" and row["臨床試驗計畫中文名稱"].strip() == "":
        return True
    # (b) 任一呈現欄位的 nfkc 後 casefold 值等於 test
    from .fields import PRESENTATION_FIELDS

    if any(nfkc(row[f]).strip().casefold() == "test" for f in PRESENTATION_FIELDS):
        return True
    # (c) protocol 含 系統測試 或 計畫書編號 字樣
    from .fields import PROTOCOL

    p = row[PROTOCOL]
    return "系統測試" in p or "計畫書編號" in p
