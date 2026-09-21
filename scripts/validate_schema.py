"""釘住 16 欄的欄名與順序、列寬與 U+001F（§9.1 的 decode／schema 層 ＋ §6.3 的硬性檢查）。

**以欄名集合比對的實作會放過「兩個數值欄位對調」**——§6.3 的 canonical serialization
依 canonical 欄位順序輸出，順序錯了 ID 全錯，而對調在數值上完全合理、下游不會有任何訊號。
本腳本因此比對的是 list 相等，不是 set。

列數判定（`ZERO_ROWS`／`ROWCOUNT_DROP`）屬 content 層，**只在給定 `--prev-rows` 時才做**：
沒有 baseline 就不做驟降比較，也不假裝做過（§9.6 的 bootstrap）。`ZERO_ROWS` 則一律檢查，
且必然在 schema 通過之後才可能觸發（B3）。

用法：
    uv run python scripts/validate_schema.py --source .cache/205.csv
    uv run python scripts/validate_schema.py --source x.csv --prev-rows 8974
    uv run python scripts/validate_schema.py --source x.csv --report qa/schema-report.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trial_radar.cli import EXIT_CODE_EPILOG, emit, run  # noqa: E402
from trial_radar.fields import COLUMNS  # noqa: E402
from trial_radar.identity import canonical_serialization, sha256hex  # noqa: E402
from trial_radar.qa import build_schema_report  # noqa: E402
from trial_radar.source import check_row_count, decode_csv, parse_csv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODE_EPILOG,
    )
    ap.add_argument("--source", type=Path, required=True, help="CSV（UTF-8 with BOM）")
    ap.add_argument("--prev-rows", type=int,
                    help="上一次成功快照的列數；給了才做 §9.6 驟降比較")
    ap.add_argument("--report", type=Path, help="JSON 報告輸出路徑（預設印到 stdout）")
    args = ap.parse_args(argv)

    def body() -> int:
        raw = args.source.read_bytes()
        text = decode_csv(raw)
        rows = parse_csv(text)

        # §6.3 的 U+001F 檢查。此處不需要 serialization 的結果，只需要它會拋的那個錯——
        # **不得另寫一份掃描**：兩份檢查遲早會對「哪些字元算控制字元」給出不同答案，
        # 而真正決定 identity 是否可能把兩列併成一列的是 serialization 裡的那一份。
        for row in rows:
            canonical_serialization(row)

        drop = check_row_count(len(rows), args.prev_rows)

        report = build_schema_report(list(COLUMNS), len(rows))
        report["sourceBytes"] = len(raw)
        report["csvSha256"] = sha256hex(raw)
        report["rowCount"] = len(rows)
        report["prevRowCount"] = args.prev_rows
        report["bootstrap"] = drop.bootstrap
        report["drop"] = str(drop.drop) if drop.drop is not None else None
        report["dropWarning"] = drop.warning

        emit(report, str(args.report) if args.report else None)
        return 0

    return run(body)


if __name__ == "__main__":
    sys.exit(main())
