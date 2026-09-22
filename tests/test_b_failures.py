"""B 群驗收：ETL 與發布可靠性（B1–B4、B6–B9）。

**判定一律看 structured error code 與 layer，不以 stderr 字串判定**（B2）。
注入輸入在 `tests/fixtures/b_failures/inputs/`，其缺陷由該目錄的 self-check 保證存在。
"""
from __future__ import annotations

import pathlib
from fractions import Fraction

import pytest

from trial_radar.errors import EXIT_CODE_OF, LAYER_OF, ErrorCode, PipelineError, precedence_winner
from trial_radar.source import (
    check_row_count,
    decode_csv,
    extract_csv,
    parse_csv,
    validate_response,
)

INPUTS = pathlib.Path(__file__).parent / "fixtures" / "b_failures" / "inputs"


def _read(name: str) -> bytes:
    return (INPUTS / name).read_bytes()


def _run_pipeline(name: str, status: int = 200, content_type: str = "application/zip"):
    """把注入輸入跑過 transport → archive → decode → schema 全段。"""
    body = _read(name)
    fetched = validate_response(status, content_type, None, body)
    csv_bytes = extract_csv(fetched.body)
    text = decode_csv(csv_bytes)
    return parse_csv(text)


# ---------------------------------------------------------------- B1／B2

def test_b1_every_error_code_has_distinct_nonzero_exit_code():
    """B1(a)：每個 code 的 exit code **非零且兩兩相異**。

    斷言的是這個性質，不是特定號碼——寫死號碼等於自己發明規格。
    """
    codes = list(ErrorCode)
    assert len(codes) == 16
    exits = [EXIT_CODE_OF[c] for c in codes]
    assert all(e != 0 for e in exits)
    assert len(set(exits)) == len(exits)
    assert set(EXIT_CODE_OF) == set(codes), "每個 code 都要有 exit code"
    assert set(LAYER_OF) == set(codes), "每個 code 都要有 layer"


def test_b1_oracle_covers_every_error_code(b_failures_oracle):
    """§9.5 的 16 個 code 全部有 fixture 或注入點。"""
    declared = set(b_failures_oracle["allErrorCodes"])
    assert declared == {c.value for c in ErrorCode}
    covered = {c["errorCode"] for c in b_failures_oracle["fileCases"]} | {
        c["errorCode"] for c in b_failures_oracle["injectionOnly"]
    }
    assert declared - covered == set()


@pytest.mark.parametrize(
    "name,code",
    [
        ("zip_corrupt.zip", ErrorCode.ZIP_CORRUPT),
        ("zip_no_csv.zip", ErrorCode.ZIP_NO_CSV),
        ("csv_decode.zip", ErrorCode.CSV_DECODE),
        ("schema_missing.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_extra.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_order.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_renamed.zip", ErrorCode.SCHEMA_MISMATCH),
        ("row_width.zip", ErrorCode.ROW_WIDTH),
    ],
)
def test_b2_structured_code_and_layer(name, code, b_failures_oracle):
    """B2：每個案例寫死 structured code 與 layer。"""
    with pytest.raises(PipelineError) as exc:
        _run_pipeline(name)
    err = exc.value
    assert err.code is code
    case = next(c for c in b_failures_oracle["fileCases"] if c["file"] == name)
    assert err.layer.value == case["layer"]


def test_b2_upstream_error_page_beats_inner_layers():
    """B2：**多重異常驗 precedence**。三層同時異常時 transport 勝出。

    沒有 precedence 的實作會回傳「先被程式碼碰到的那一個」，而那取決於函式呼叫順序。
    """
    with pytest.raises(PipelineError) as exc:
        _run_pipeline("multi_anomaly.zip", content_type="text/html")
    assert exc.value.code is ErrorCode.UPSTREAM_ERROR_PAGE
    assert exc.value.layer.value == "transport"

    # 同一個檔案若 MIME 正確，才會暴露內層（decode）的缺陷——證明上面那條不是碰巧
    with pytest.raises(PipelineError) as exc2:
        _run_pipeline("multi_anomaly.zip")
    assert exc2.value.code is ErrorCode.CSV_DECODE


def test_b2_precedence_helper_orders_by_layer():
    errors = [
        PipelineError(ErrorCode.INTEGRITY_DIGEST),
        PipelineError(ErrorCode.SCHEMA_MISMATCH),
        PipelineError(ErrorCode.ZIP_CORRUPT),
    ]
    assert precedence_winner(errors).code is ErrorCode.ZIP_CORRUPT


def test_b2_schema_mismatch_detail_has_three_kinds(b_failures_oracle):
    """§9.5：`SCHEMA_MISMATCH` 的 detail 須載明 missing／extra／order 三類差異。"""
    for name in ("schema_missing.zip", "schema_extra.zip", "schema_order.zip",
                 "schema_renamed.zip"):
        with pytest.raises(PipelineError) as exc:
            _run_pipeline(name)
        detail = exc.value.detail
        assert {"missing", "extra", "order"} <= set(detail)
        case = next(c for c in b_failures_oracle["fileCases"] if c["file"] == name)
        assert detail["missing"] == case["detail"]["missing"]
        assert detail["extra"] == case["detail"]["extra"]
        assert detail["order"] == case["detail"]["order"]


def test_b2_column_order_matters():
    """以欄名**集合**比對的實作會通過 `schema_order` —— 這條把它殺掉。"""
    from trial_radar.fields import COLUMNS

    with pytest.raises(PipelineError) as exc:
        _run_pipeline("schema_order.zip")
    actual = exc.value.detail["actual"]
    assert set(actual) == set(COLUMNS), "前提：欄名集合相同"
    assert actual != list(COLUMNS), "前提：順序不同"
    assert exc.value.detail["order"] is True


def test_b1_upstream_error_page_is_transport():
    with pytest.raises(PipelineError) as exc:
        validate_response(200, "text/html; charset=utf-8", None,
                          _read("upstream_error_page.html"))
    assert exc.value.code is ErrorCode.UPSTREAM_ERROR_PAGE


def test_b1_http_status_and_truncation():
    with pytest.raises(PipelineError) as exc:
        validate_response(500, "application/zip", None, b"x")
    assert exc.value.code is ErrorCode.HTTP_STATUS

    with pytest.raises(PipelineError) as exc2:
        validate_response(200, "application/zip", 100, b"x" * 99)
    assert exc2.value.code is ErrorCode.HTTP_TRUNCATED


def test_b1_content_type_cases(b_failures_oracle):
    """B1：content-type 逐例。`application/zip;charset=utf-8` 通過、`text/html` 失敗。"""
    for case in b_failures_oracle["contentTypeCases"]:
        if case["expect"] == "pass":
            validate_response(200, case["value"], None, b"PK\x03\x04")
        else:
            with pytest.raises(PipelineError) as exc:
                validate_response(200, case["value"], None, b"PK\x03\x04")
            assert exc.value.code is ErrorCode.UPSTREAM_ERROR_PAGE, case["value"]


def test_b1_decode_must_not_silently_replace():
    """`errors='replace'` 會靜默產出 U+FFFD——資料變了但沒有訊號。"""
    data = extract_csv(_read("csv_decode.zip"))
    assert data.decode("utf-8-sig", errors="replace").count("�") > 0
    with pytest.raises(PipelineError) as exc:
        decode_csv(data)
    assert exc.value.code is ErrorCode.CSV_DECODE


def test_b1_source_control_char_hard_fails():
    """§6.3 的硬性檢查：欄位含 U+001F → `SOURCE_CONTROL_CHAR`。"""
    from trial_radar.identity import canonical_serialization

    rows = _run_pipeline("source_control_char.zip")
    assert rows, "schema 須先通過"
    with pytest.raises(PipelineError) as exc:
        canonical_serialization(rows[0])
    assert exc.value.code is ErrorCode.SOURCE_CONTROL_CHAR
    assert exc.value.layer.value == "decode"


# ---------------------------------------------------------------- B3

def test_b3_zero_rows_after_schema_passes():
    """B3：斷言 CSV schema **已通過後**才因零列失敗。"""
    rows = _run_pipeline("zero_rows.zip")  # schema 不得拋
    assert rows == []
    with pytest.raises(PipelineError) as exc:
        check_row_count(len(rows), prev=18736)
    assert exc.value.code is ErrorCode.ZERO_ROWS
    assert exc.value.layer.value == "content"


def test_b3_zero_rows_even_without_baseline():
    """bootstrap 也要求列數 ≥1——不得因「沒有 baseline 可比」而放行。"""
    with pytest.raises(PipelineError) as exc:
        check_row_count(0, prev=None)
    assert exc.value.code is ErrorCode.ZERO_ROWS


# ---------------------------------------------------------------- B4

def test_b4_threshold_cases(b_failures_oracle):
    """B4：逐案例斷言 warning／publish／hard-failure，並比對精確有理數。"""
    for case in b_failures_oracle["rowcountDropCases"]:
        prev, cur = case["prev"], case["cur"]
        if case["expect"] == "hard-fail":
            with pytest.raises(PipelineError) as exc:
                check_row_count(cur, prev)
            assert exc.value.code is ErrorCode[case["errorCode"]]
            continue
        verdict = check_row_count(cur, prev)
        assert verdict.warning == case["warning"], (prev, cur)
        assert verdict.bootstrap == case.get("bootstrap", False)
        if prev is not None:
            assert str(verdict.drop) == case["drop"]


@pytest.mark.parametrize("digits", [2, 3, 4])
def test_b4_kills_rounding_implementation(b_failures_oracle, digits):
    """B4 的作用是殺死「先四捨五入再比較」的實作。

    固定小數例（0.1001／0.2001）只殺得死 2 位；**真實基線例**（prev=18736 時
    cur=16862／14988）殺得死 3／4 位——那兩個 cur 恰是各自門檻「最接近且嚴格超過」的整數。
    """
    killed = 0
    for case in b_failures_oracle["rowcountDropCases"]:
        prev, cur = case["prev"], case["cur"]
        if prev is None:
            continue
        drop = Fraction(prev - cur, prev)
        correct = ("hard-fail" if drop > Fraction(1, 5) else "publish",
                   drop > Fraction(1, 10))
        r = round(float(drop), digits)
        rounded = ("hard-fail" if r > 0.20 else "publish", r > 0.10)
        if rounded != correct:
            killed += 1
    assert killed >= 2, f"四捨五入到 {digits} 位的實作必須被至少 2 個案例殺死"


def test_b4_threshold_boundaries_are_strict():
    """邊界為**嚴格大於**：drop 恰等於 0.10 屬正常、恰等於 0.20 屬 warning。"""
    assert check_row_count(9000, 10000).warning is False   # drop == 0.10
    v = check_row_count(8000, 10000)                        # drop == 0.20
    assert v.warning is True
    with pytest.raises(PipelineError):
        check_row_count(7999, 10000)                        # drop == 0.2001


def test_b4_bootstrap_does_not_fake_a_comparison():
    v = check_row_count(18736, None)
    assert v.bootstrap is True
    assert v.drop is None, "bootstrap 不得假裝完成比較"
