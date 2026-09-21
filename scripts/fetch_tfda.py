"""取得 TFDA dataset 205 並做 transport／archive／decode 驗證（§9.1 前三層）。

**fail-closed**：任一層不符即以 §9.5 的相異非零 exit code 結束，**絕不回空 CSV**。
抓取失敗與「官方回覆空集」必須分辨——本腳本不做列數判定（那是 content 層，
在 `validate_schema.py` 與 `build_data.py`），它只保證「拿到的確實是那包 ZIP 裡的 CSV」。

用法：
    uv run python scripts/fetch_tfda.py --out .cache/205.csv
    uv run python scripts/fetch_tfda.py --from-zip local.zip --out out.csv   # 不連網
    uv run python scripts/fetch_tfda.py --out x.csv --report qa/fetch.json

stdout（未指定 `--report` 時）為 JSON 報告，含 `sourceSha256`——那是 §9.4 比較時
被排除的欄位之一，但也是「上游是否真的換了內容」的唯一憑據，每次抓取都要留存。
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trial_radar.cli import EXIT_CODE_EPILOG, emit, run  # noqa: E402
from trial_radar.identity import sha256hex  # noqa: E402
from trial_radar.source import (  # noqa: E402
    DATASET_URL,
    FetchResult,
    decode_csv,
    extract_csv,
    fetch_dataset,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODE_EPILOG,
    )
    ap.add_argument("--url", default=DATASET_URL, help=f"預設 {DATASET_URL}")
    ap.add_argument("--from-zip", type=Path,
                    help="改讀本機 ZIP（跳過 transport 層；離線重現用）")
    ap.add_argument("--out", type=Path, help="寫出 CSV（UTF-8 with BOM 原樣位元組）")
    ap.add_argument("--zip-out", type=Path, help="一併留存原始 ZIP")
    ap.add_argument("--report", type=Path, help="JSON 報告輸出路徑（預設印到 stdout）")
    args = ap.parse_args(argv)

    def body() -> int:
        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        if args.from_zip:
            raw = args.from_zip.read_bytes()
            result = FetchResult(raw, sha256hex(raw))
            origin = str(args.from_zip)
        else:
            result = fetch_dataset(args.url)
            origin = args.url

        csv_bytes = extract_csv(result.body)
        # decode 層在此就跑：拿到一包解不開的 UTF-8 要當場失敗，
        # **不要**把壞位元組寫進 --out 讓下游去踩。
        text = decode_csv(csv_bytes)

        if args.zip_out:
            args.zip_out.parent.mkdir(parents=True, exist_ok=True)
            args.zip_out.write_bytes(result.body)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(csv_bytes)

        emit(
            {
                "origin": origin,
                "fetchedAt": fetched_at,
                "zipBytes": len(result.body),
                "zipSha256": result.sha256,
                "csvBytes": len(csv_bytes),
                "csvSha256": sha256hex(csv_bytes),
                # §9.6 排除 `sourceSha256` 的論據明寫「ZIP metadata 或列序變動會改變
                # source SHA」——所以**有 ZIP 時 sourceSha256 就是 ZIP 的雜湊**。
                # `sourceKind` 一併寫出：`--source` 路徑沒有 ZIP 可雜湊，值域不同，
                # 不標明型別的話兩次執行的 SHA 不同會被誤讀成上游換了內容。
                "sourceKind": "zip",
                "sourceSha256": result.sha256,
                "lines": text.count("\n"),
                "csvOut": str(args.out) if args.out else None,
                "zipOut": str(args.zip_out) if args.zip_out else None,
            },
            str(args.report) if args.report else None,
        )
        return 0

    return run(body)


if __name__ == "__main__":
    sys.exit(main())
