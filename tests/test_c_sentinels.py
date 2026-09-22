"""C 群驗收：sentinel、分類與數值（C1–C6）。"""
from __future__ import annotations

import pytest

from trial_radar.artifacts import FACETS, build_artifacts
from trial_radar.comparison import ComparisonKeyError, comparison_key
from trial_radar.fields import CATEGORICAL_FIELDS, NUMERIC_FIELDS
from trial_radar.model import build_trials
from trial_radar.parsing import (
    MAX_SAFE_INT,
    FieldValue,
    parse_categorical,
    parse_numeric,
    parse_text,
)

BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


@pytest.fixture(scope="module")
def trials(a_core_rows, build_date):
    return build_trials(list(a_core_rows.values()), build_date)


# ---------------------------------------------------------------- C1

@pytest.mark.parametrize("field", CATEGORICAL_FIELDS)
def test_c1_categorical_sentinel_five_assertions(trials, a_core_rows, build_date, field):
    """C1：**兩個**分類欄位**各自**通過五處斷言。

    第 4／5 處（filter DOM、卡片文字）需要前端，M1 先驗其資料層等價條件：
    篩選選項的唯一來源是 facet buckets、`displayFields` 帶 `categoricalUnprovided`
    供前端直接取用（§6.4.5 要求前端不得重做判定）。DOM 斷言在 M2 補。
    """
    t = next(t for t in trials if "未列編號" in t.protocol_raw)
    value = t.display_fields[field]

    # (1) typed 為 null
    assert value.typed is None
    # (2) raw 仍等於 "0"
    assert value.raw == "0"
    assert t.records[0].raw[field] == "0"
    # (5-資料層) 旗標供 UI 顯示「未提供」，前端不重做判定
    assert "categoricalUnprovided" in value.flags

    out = build_artifacts(trials, **BUILD_KW)
    import json

    stats = json.loads(out.published[out.manifest["files"]["stats"]["path"]].decode())
    facet_name = next(k for k, v in FACETS.items() if v == field)
    options = [b["value"] for b in stats["facets"][facet_name]["buckets"]]
    # (3) stats facet 不含 "0"
    assert "0" not in options
    # (4-資料層) 篩選選項的唯一來源是 buckets，故也不含 "0"；該 Trial 計入 unprovided
    assert stats["facets"][facet_name]["unprovided"] >= 1


def test_c1_categorical_unknown_warns(trials):
    """C1 另測非合法值 → `categoricalUnknown`（warning 分級）。"""
    t = next(t for t in trials if "CMP-036" in t.protocol_raw)
    # 該欄位在 cohort 內衝突，故從 displayFields 省略；改看 record 層
    values = [r.fields["臨床試驗期別"] for r in t.records]
    assert all(v.typed is None for v in values)
    assert all("categoricalUnknown" in v.flags for v in values)
    assert {v.raw for v in values} == {"第三期", "Phase III"}


# ---------------------------------------------------------------- C2

# §6.6.3 兩階段的完整矩陣。**兩個數值欄位各跑一次**——否則另一欄可以走一套完全不同的
# 錯誤邏輯而通過。flags 以**完全相等**比對，不是「包含」：用「包含」時實作可以額外附加
# numericUnparsed 等錯誤旗標而通過，錯誤會經 §6.4.2 的組合表擴散到衝突判定與 UI。
NUMERIC_MATRIX = [
    # (raw, typed, flags, grade)
    ("", None, ("numericMissing",), "normal"),
    ("42", 42, (), "normal"),
    ("0", 0, ("sourceZero",), "normal"),
    ("026", 26, (), "normal"),
    ("20-40", {"min": 20, "max": 40}, ("numericRange",), "normal"),
    ("100至200", {"min": 100, "max": 200}, ("numericRange",), "normal"),
    ("40-20", None, ("numericRangeInvalid",), "warning"),
    ("-5", None, ("numericImplausible",), "warning"),
    ("約400", None, ("numericUnparsed",), "warning"),
    ("1,200", None, ("numericUnparsed",), "warning"),
    # 階段二：序 2 命中後超界
    (str(MAX_SAFE_INT + 1), None, ("numericOutOfRange",), "warning"),
    # 階段二：序 3 命中且**單端**超界 → typed 整個為 None
    (f"1-{MAX_SAFE_INT + 1}", None, ("numericOutOfRange", "numericRange"), "warning"),
]

WARNING_FLAGS = {
    "numericRangeInvalid", "numericImplausible", "numericUnparsed", "numericOutOfRange",
}


@pytest.mark.parametrize("field", NUMERIC_FIELDS)
@pytest.mark.parametrize("raw,typed,flags,grade", NUMERIC_MATRIX)
def test_c2_numeric_matrix(field, raw, typed, flags, grade):
    """C2：每欄位、每列逐筆斷言 typed、**旗標集合完全相等**、warning 分級。"""
    v = parse_numeric(raw)
    assert v.typed == typed, f"{field} {raw!r}"
    assert v.flags == tuple(sorted(flags)), f"{field} {raw!r} 旗標須完全相等"
    actual_grade = "warning" if set(v.flags) & WARNING_FLAGS else "normal"
    assert actual_grade == grade
    # raw 一律原樣保留——顯示 typed 就是改寫來源
    assert v.raw == raw


def test_c2_leading_zero_displays_raw():
    """C2：前導零須斷言 raw 顯示為 `026` 而非 `26`。"""
    v = parse_numeric("026")
    assert v.typed == 26
    assert v.raw == "026"


def test_c2_source_zero_only_when_zero():
    """`sourceZero` 只在值為 0 時為 true（對所有數字都設 sourceZero 的實作要被殺死）。"""
    assert parse_numeric("0").flags == ("sourceZero",)
    assert parse_numeric("00").flags == ("sourceZero",)
    for raw in ("1", "42", "026", "100"):
        assert "sourceZero" not in parse_numeric(raw).flags, raw


def test_c2_single_endpoint_out_of_range_has_no_partial_typed():
    """單端超界時 typed 為**整個 None**，不得留 `{min: 1, max: None}`。

    半個區間無法參與 §8.4 的重疊判定，「有 min 沒有 max」會讓前端與篩選各自猜邊界。
    """
    v = parse_numeric(f"1-{MAX_SAFE_INT + 1}")
    assert v.typed is None
    assert v.flags == ("numericOutOfRange", "numericRange")


def test_c2_approximate_values_are_not_inferred():
    """**反向哨兵**：任何「抽出字串中的數字」的實作都會把 typed 填成 400／480。"""
    for raw in ("約400", "至少480", "148(最多266)", "240=90+150"):
        v = parse_numeric(raw)
        assert v.typed is None, f"{raw} 不得被推論為數字"
        assert v.flags == ("numericUnparsed",)


# ---------------------------------------------------------------- C3

def test_c3_text_sentinels_exact_counts(trials, a_core_oracle):
    """C3：`N/A`／`NA`／`""` 的**精確計數與對應 recordId**。計數須**數全部列**。"""
    exp = a_core_oracle["qualityReportExpectations"]["textSentinelCounts"]["排除條件"]
    seen: dict[str, list[str]] = {"N/A": [], "NA": [], "empty": []}
    for t in trials:
        for r in t.records:
            v = r.raw["排除條件"]
            key = "empty" if v == "" else v
            if key in seen:
                seen[key].append(r.rid)
    assert {k: len(v) for k, v in seen.items()} == exp
    for k, rids in seen.items():
        assert len(set(rids)) == len(rids), f"{k} 的 recordId 須互異"


def test_c3_three_sentinels_distinguishable():
    """三型**不得塌成同一值**：raw 與比較鍵都要能分。"""
    values = [parse_text("N/A"), parse_text("NA"), parse_text("")]
    assert len({v.raw for v in values}) == 3
    keys = {comparison_key("排除條件", v) for v in values}
    assert len(keys) == 3


# ---------------------------------------------------------------- C5

def test_c5_every_combination_row_has_a_case():
    """C5：§6.4.2 組合表的**每一列**各有一組正例，含複合狀態。"""
    F = "台灣預計受試者人數"
    P = "臨床試驗期別"
    D = "試驗預計執行期間起"
    T = "臨床試驗計畫中文名稱"
    huge = str(MAX_SAFE_INT + 1)

    rows = [
        (1, T, parse_text("abc")),
        (2, F, parse_numeric("42")),
        (3, F, parse_numeric("0")),
        (4, F, parse_numeric("20-40")),
        (5, F, parse_numeric("")),
        (6, F, parse_numeric("約400")),
        (7, F, parse_numeric("-5")),
        (8, F, parse_numeric("40-20")),
        (9, F, parse_numeric(huge)),
        (10, F, parse_numeric(f"1-{huge}")),
        (11, P, parse_categorical(P, "0")),
        (12, P, parse_categorical(P, "第三期")),
        (13, P, parse_categorical(P, "Phase Ⅲ")),
        (14, D, FieldValue("2025/01/01", "2025-01-01", ())),
        (15, D, FieldValue("", None, ("periodStartMissing",))),
    ]
    assert len(rows) == 15
    for num, field, value in rows:
        key = comparison_key(field, value)
        assert isinstance(key, tuple) and key, f"第 {num} 列取不到比較鍵"


@pytest.mark.parametrize(
    "field,a,b,expect",
    [
        # typed 皆 null 但語意狀態不同 → 衝突（GAP-5 的原建議被否決之處）
        ("全球預計受試者人數", "", "-5", "conflict"),
        # NFKC 後等價 → 不衝突
        ("台灣預計受試者人數", "20", "２０", "same"),
        ("台灣預計受試者人數", "20-40", "20～40", "same"),
        # 端點不同 → 衝突（與上一列成對，證明比的是端點值不是字面）
        ("台灣預計受試者人數", "20-40", "20-41", "conflict"),
        # v0.6 新增的三個語意狀態
        ("台灣預計受試者人數", "40-20", "50-30", "conflict"),
        ("臨床試驗期別", "第三期", "Phase III", "conflict"),
        ("全球預計受試者人數", str(MAX_SAFE_INT + 1), str(MAX_SAFE_INT + 2), "conflict"),
        # v0.7 新增的**複合**狀態：numericRange + numericOutOfRange
        (
            "台灣預計受試者人數",
            f"1-{MAX_SAFE_INT + 1}",
            f"2-{MAX_SAFE_INT + 1}",
            "conflict",
        ),
        (
            "台灣預計受試者人數",
            f"1-{MAX_SAFE_INT + 1}",
            "１-９００７１９９２５４７４０９９２",
            "same",
        ),
    ],
)
def test_c5_comparison_key_by_type(field, a, b, expect):
    """C5 逐型別。**複合狀態的兩組是關鍵**：只驗原子狀態的實作抓不到它們。"""
    from trial_radar.parsing import parse_field

    ka = comparison_key(field, parse_field(field, a))
    kb = comparison_key(field, parse_field(field, b))
    if expect == "conflict":
        assert ka != kb
    else:
        assert ka == kb and a != b


def test_c5_exhaustiveness_hard_fails_outside_table():
    """C5：遇到表外組合須**硬失敗而非 fallback**。

    fallback 到「比 raw」或「視為相等」會把規格缺口變成一個看不見的行為。
    """
    with pytest.raises(ComparisonKeyError):
        comparison_key("台灣預計受試者人數", FieldValue("x", None, ("someUnlistedFlag",)))
    with pytest.raises(ComparisonKeyError):
        comparison_key("臨床試驗期別", FieldValue("x", None, ()))


def test_c5_source_zero_does_not_affect_comparison():
    """第 2／3 列同鍵：`sourceZero` 只影響 UI 文案，不影響「兩筆是不是同一個值」。"""
    F = "台灣預計受試者人數"
    assert comparison_key(F, parse_numeric("0")) == comparison_key(F, parse_numeric("00"))
    assert comparison_key(F, parse_numeric("0")) == ("int", 0)


def test_c5_out_of_range_rows_share_key_prefix():
    """第 9／10 列同鍵：超界只看 raw，`numericRange` 不進比較鍵。"""
    F = "台灣預計受試者人數"
    huge = str(MAX_SAFE_INT + 1)
    k9 = comparison_key(F, parse_numeric(huge))
    k10 = comparison_key(F, parse_numeric(f"1-{huge}"))
    assert k9[0] == k10[0] == "numericOutOfRange"
    assert k9 != k10  # raw 不同


# ---------------------------------------------------------------- C6

def test_c6_raw_variants_is_field_scoped(trials):
    """C6：`rawVariants` 出現在**該欄位的 flags**，且 Trial 層級**不存在**等義旗標。"""
    t = next(t for t in trials if "WS-003" in t.protocol_raw)
    for field in ("臨床試驗計畫中文名稱", "納入條件"):
        assert "rawVariants" in t.display_fields[field].flags
    assert not any(
        attr.lower().startswith("rawvariant") for attr in vars(t)
    ), "Trial 層級不得有等義旗標（兩種表示並存會分歧）"


def test_c6_representative_is_lexicographically_smallest_record_id(trials):
    """C6：代表值為 `recordId` 字典序最小者的 raw。"""
    t = next(t for t in trials if "WS-003" in t.protocol_raw)
    smallest = min(t.records, key=lambda r: r.rid)
    for field in ("臨床試驗計畫中文名稱", "納入條件"):
        assert t.display_fields[field].raw == smallest.raw[field]


def test_c6_detail_keeps_every_record(trials):
    """C6：詳情頁須列出 cohort 中**每一筆** record 的原始值，不得只列去重文字。"""
    t = next(t for t in trials if "WS-003" in t.protocol_raw)
    cohort = [r for r in t.records if r.rid in set(t.latest_cohort)]
    assert len(cohort) == 2
    raws = [r.raw["納入條件"] for r in cohort]
    assert len(raws) == 2 and len(set(raws)) == 2, "兩筆原始值都要在，且確實不同"


def test_c6_no_raw_variants_without_difference(trials):
    """**反向哨兵**：沒有 raw 差異的 Trial 不得被標上 `rawVariants`。"""
    t = next(t for t in trials if "NR-028" in t.protocol_raw)
    assert len(t.records) == 1
    assert not any("rawVariants" in v.flags for v in t.display_fields.values())


# ---------------------------------------------------------------- C6（v0.9 補）

def test_c6_long_text_raw_variants_absent_from_every_output(a_core_rows, build_date):
    """C6（v0.9）：四個長文字欄位的 `rawVariants` **不出現在任何輸出**。

    §6.4.3 定案長文字仍**計算**比較鍵與衝突，但**不輸出 `rawVariants`**——
    它們不在 `displayFields` 內，而 §6.4.5 明定該旗標只放那裡、不另設 Trial 層級表示。

    這條堵的是「實作私自擴充 schema 替它找個位置」：丟棄、複製到 record、
    自創一個新鍵，三種都可能通過其餘的 C6 斷言。
    """
    from trial_radar.fields import LONG_TEXT_FIELDS

    trials = build_trials(list(a_core_rows.values()), build_date)

    # 前提：fixture 確實有長文字欄位帶 rawVariants，否則這條測不到東西
    carriers = [
        t for t in trials
        if any("rawVariants" in t.display_fields[f].flags
               for f in LONG_TEXT_FIELDS if f in t.display_fields)
    ]
    assert carriers, "fixture 須有長文字欄位的 rawVariants，否則這條是空轉的"

    out = build_artifacts(trials, **BUILD_KW)

    # (1) trials-index 的 displayFields 完全不含這四欄，遑論其旗標
    for entry in out.logical["trials-index.json"]["trials"]:
        assert not set(entry["displayFields"]) & set(LONG_TEXT_FIELDS)

    # (2) shard 的 record-level fieldFlags 不得被塞進 rawVariants。
    #     rawVariants 是 cohort 層級的結論，複製到每一筆 record 會讓它看起來
    #     像是該筆紀錄自己的性質——那是另一個意思。
    for name, payload in out.logical.items():
        if not name.startswith("records/"):
            continue
        for rec in payload["records"].values():
            for field, flags in rec.get("fieldFlags", {}).items():
                assert "rawVariants" not in flags, f"{name} {field}"

    # (3) 全域字串掃描：任何新鍵下夾帶都會被抓到
    import json

    for name, payload in out.logical.items():
        blob = json.dumps(payload, ensure_ascii=False)
        if "rawVariants" not in blob:
            continue
        # 只有 9 個卡片欄位的 flags 可以帶它
        for entry in payload.get("trials", []):
            for field, value in entry["displayFields"].items():
                # schemaVersion 2：`flags` 為空時被省略（§9.3.3）
                if "rawVariants" in value.get("flags", []):
                    assert field not in LONG_TEXT_FIELDS


def test_c6_short_field_raw_variants_still_present(a_core_rows, build_date):
    """**反向哨兵**：卡片欄位的 `rawVariants` 必須照樣輸出。

    沒有這條，一個「把 rawVariants 整個拿掉」的實作會讓上一條轉綠。
    """
    out = build_artifacts(build_trials(list(a_core_rows.values()), build_date), **BUILD_KW)
    found = [
        (t["id"], f)
        for t in out.logical["trials-index.json"]["trials"]
        for f, v in t["displayFields"].items()
        if "rawVariants" in v.get("flags", [])
    ]
    assert found, "卡片欄位的 rawVariants 不得一併消失"
