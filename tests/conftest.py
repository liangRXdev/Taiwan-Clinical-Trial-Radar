"""共用 fixture 載入器。

**測試一律不連網**（§11）。來源資料是 `tests/fixtures/` 下的凍結 CSV 與手寫 oracle。
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# 與 a_core/oracle.json 的 harness.buildDate 一致。**測試一律注入固定值**——
# §6.5 的「不晚於 build 當日」依賴當日日期，浮動的 build 當日與凍結 fixture 矛盾。
BUILD_DATE = datetime.date(2026, 9, 18)


def _read_rows_json(name: str) -> dict[str, dict[str, str]]:
    path = FIXTURES / name / "rows.json"
    return json.loads(path.read_text(encoding="utf-8"))["rows"]


def _read_input_csv(name: str) -> list[dict[str, str]]:
    path = FIXTURES / name / "input.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def a_core_rows() -> dict[str, dict[str, str]]:
    """`rowKey → 16 欄值`。**oracle 一律用 rowKey 指涉列，不用 CSV 列序**（A3 要打亂列序）。"""
    return _read_rows_json("a_core")


@pytest.fixture(scope="session")
def a_core_csv() -> list[dict[str, str]]:
    return _read_input_csv("a_core")


@pytest.fixture(scope="session")
def a_core_oracle() -> dict:
    return json.loads((FIXTURES / "a_core" / "oracle.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def a7_rows() -> dict[str, dict[str, str]]:
    return _read_rows_json("a7_identity_collision")


@pytest.fixture(scope="session")
def a7_oracle() -> dict:
    return json.loads(
        (FIXTURES / "a7_identity_collision" / "oracle.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def b_failures_oracle() -> dict:
    return json.loads((FIXTURES / "b_failures" / "oracle.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def build_date() -> datetime.date:
    return BUILD_DATE
