"""B1／B2 的 CLI 層：`fetch_tfda.py` 與 `validate_schema.py` 的 exit code 契約。

`test_b_failures.py` 驗的是函式拋出的 code；這裡驗的是**呼叫端（CI）真正看得到的東西**
——process 的 exit code。兩者不可互相取代：把 code 對到 exit code 的那張表在 CLI 裡，
函式層測試再綠也不會發現某支 CLI 把所有失敗都回成 1。

**一律不連網**（§11）：`fetch_tfda.py` 走 `--from-zip`，transport 層以
`upstream_error_page.html` 在函式層另測（CLI 無法在不連網下觸發 HTTP 狀態）。
"""
from __future__ import annotations

import json
import pathlib
import sys
from fractions import Fraction

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import fetch_tfda  # noqa: E402
import validate_schema  # noqa: E402

from trial_radar.errors import EXIT_CODE_OF, ErrorCode  # noqa: E402
from trial_radar.source import FAIL_THRESHOLD, WARN_THRESHOLD  # noqa: E402

INPUTS = pathlib.Path(__file__).parent / "fixtures" / "b_failures" / "inputs"
A_CORE = pathlib.Path(__file__).parent / "fixtures" / "a_core"
A_CORE_CSV = A_CORE / "input.csv"

#: **從 fixture 自己數**，不寫死。fixture 補案例時列數會變，寫死的數字會讓這些測試
#: 在「CLI 完全正常、只是 fixture 長大了」時轉紅，而那是假訊號。
A_CORE_ROWS = len(json.loads((A_CORE / "rows.json").read_text(encoding="utf-8"))["rows"])


def _fetch_cli(tmp_path: pathlib.Path, zip_name: str, *extra: str) -> tuple[int, dict | None]:
    out = tmp_path / "out.csv"
    report = tmp_path / "fetch.json"
    code = fetch_tfda.main(
        ["--from-zip", str(INPUTS / zip_name), "--out", str(out),
         "--report", str(report), *extra]
    )
    payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
    return code, payload


def _validate_cli(tmp_path: pathlib.Path, csv_path: pathlib.Path,
                  *extra: str) -> tuple[int, dict | None]:
    report = tmp_path / "schema.json"
    code = validate_schema.main(["--source", str(csv_path), "--report", str(report), *extra])
    payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
    return code, payload


# ---------------------------------------------------------------- fetch_tfda

def test_fetch_cli_happy_path_writes_csv_and_report(tmp_path):
    """成功時 exit 0，CSV 寫出，報告含 provenance。"""
    code, payload = _fetch_cli(tmp_path, "zero_rows.zip")
    assert code == 0
    assert (tmp_path / "out.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert payload["sourceKind"] == "zip"
    assert len(payload["sourceSha256"]) == 64
    assert len(payload["csvSha256"]) == 64
    # sourceSha256 雜湊的是 ZIP 不是 CSV——兩者相等代表 sourceKind 的標示是空話
    assert payload["sourceSha256"] != payload["csvSha256"]


@pytest.mark.parametrize(
    ("zip_name", "code"),
    [
        ("zip_corrupt.zip", ErrorCode.ZIP_CORRUPT),
        ("zip_no_csv.zip", ErrorCode.ZIP_NO_CSV),
        ("csv_decode.zip", ErrorCode.CSV_DECODE),
    ],
)
def test_fetch_cli_exits_with_the_error_code(tmp_path, zip_name, code):
    """archive／decode 層失敗 → 該 code 的相異非零 exit code。"""
    exit_code, payload = _fetch_cli(tmp_path, zip_name)
    assert exit_code == EXIT_CODE_OF[code]
    assert exit_code != 0
    assert payload is None, "失敗不得留下報告，否則下游會把它當成功的產物"


def test_fetch_cli_writes_nothing_on_failure(tmp_path):
    """**fail-closed**：解不開的 UTF-8 不得寫進 `--out` 讓下游去踩。"""
    exit_code, _ = _fetch_cli(tmp_path, "csv_decode.zip")
    assert exit_code == EXIT_CODE_OF[ErrorCode.CSV_DECODE]
    assert not (tmp_path / "out.csv").exists()


# ---------------------------------------------------------------- validate_schema

def test_validate_cli_happy_path(tmp_path):
    code, payload = _validate_cli(tmp_path, A_CORE_CSV)
    assert code == 0
    assert payload["columnCount"] == 16
    assert payload["rowCount"] == A_CORE_ROWS
    assert payload["bootstrap"] is True, "未給 --prev-rows 就是 bootstrap，不假裝比較過"
    assert payload["drop"] is None


@pytest.mark.parametrize(
    ("zip_name", "code"),
    [
        ("schema_missing.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_extra.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_order.zip", ErrorCode.SCHEMA_MISMATCH),
        ("schema_renamed.zip", ErrorCode.SCHEMA_MISMATCH),
        ("row_width.zip", ErrorCode.ROW_WIDTH),
        ("zero_rows.zip", ErrorCode.ZERO_ROWS),
        ("source_control_char.zip", ErrorCode.SOURCE_CONTROL_CHAR),
    ],
)
def test_validate_cli_exits_with_the_error_code(tmp_path, zip_name, code):
    """schema／content／U+001F 的 exit code 契約。

    `schema_order.zip` 是關鍵案例：欄名集合相同、只有順序不同。以 set 比對的實作
    會在這裡回 0，而 §6.3 的 canonical serialization 依欄位順序輸出，ID 會全錯。
    """
    ok, csv_path = _extract_to(tmp_path, zip_name)
    assert ok
    exit_code, payload = _validate_cli(tmp_path, csv_path)
    assert exit_code == EXIT_CODE_OF[code]
    assert exit_code != 0
    assert payload is None


def test_validate_cli_rowcount_drop_hard_fail(tmp_path):
    """§9.6：驟降超過 1/5 → `ROWCOUNT_DROP`。"""
    prev = A_CORE_ROWS * 2  # drop = 1/2，遠超門檻
    assert Fraction(prev - A_CORE_ROWS, prev) > FAIL_THRESHOLD
    exit_code, _ = _validate_cli(tmp_path, A_CORE_CSV, "--prev-rows", str(prev))
    assert exit_code == EXIT_CODE_OF[ErrorCode.ROWCOUNT_DROP]


def test_validate_cli_rowcount_drop_warning_is_structured(tmp_path):
    """warning 級驟降**不得只印 log**：須落在報告的結構化欄位（§9.6）。"""
    prev = A_CORE_ROWS + 10
    drop = Fraction(prev - A_CORE_ROWS, prev)
    # 先證明這組數字確實落在警告帶——否則測試可能在「什麼都沒警告」時照樣綠
    assert WARN_THRESHOLD < drop <= FAIL_THRESHOLD, drop

    exit_code, payload = _validate_cli(tmp_path, A_CORE_CSV, "--prev-rows", str(prev))
    assert exit_code == 0
    assert payload["dropWarning"] is True
    assert payload["drop"] == str(drop), "以有理數保存，不得先四捨五入到固定小數位"
    assert payload["bootstrap"] is False


def test_validate_cli_exit_codes_are_pairwise_distinct(tmp_path):
    """同一支 CLI 對不同 code 必須給出不同 exit code（B1）。

    只斷言「非零」會放過「全部回 1」的實作——那在 CI 上分不出上游改格式與上游掛掉。
    """
    seen = {}
    for zip_name in ("schema_missing.zip", "row_width.zip", "zero_rows.zip",
                     "source_control_char.zip"):
        _, csv_path = _extract_to(tmp_path / zip_name, zip_name)
        seen[zip_name] = _validate_cli(tmp_path / zip_name, csv_path)[0]
    assert len(set(seen.values())) == len(seen), seen


# ---------------------------------------------------------------- helper

def _extract_to(tmp_path: pathlib.Path, zip_name: str) -> tuple[bool, pathlib.Path]:
    """用 `fetch_tfda.py` 自己把 fixture ZIP 解成 CSV——注入輸入只有 ZIP 形式。

    `zero_rows.zip` 與 `source_control_char.zip` 在 fetch 階段是合法的
    （B3：schema 通過後才因零列失敗），所以這一步必然 exit 0。
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "extracted.csv"
    code = fetch_tfda.main(["--from-zip", str(INPUTS / zip_name), "--out", str(csv_path),
                            "--report", str(tmp_path / "f.json")])
    return code == 0, csv_path
