"""管線進入點：抓取 → 驗證 → 收斂 → 產出 artifact → promotion（§9.1）。

**exit code 依 §9.5，每個 error code 相異且非零**；`--help` 會列出對照表。
stderr 只是輔助說明，呼叫端（CI）一律看 exit code。

用法：
    uv run python scripts/build_data.py --source 205_2.csv        # 用本機 CSV
    uv run python scripts/build_data.py --fetch                    # 連網抓取
    uv run python scripts/build_data.py --source x.csv --dry-run   # 只驗證不發布
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import zoneinfo
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trial_radar.artifacts import build_artifacts  # noqa: E402
from trial_radar.cli import EXIT_CODE_EPILOG, report  # noqa: E402
from trial_radar.errors import ErrorCode, PipelineError  # noqa: E402
from trial_radar.identity import (  # noqa: E402
    near_duplicate_groups,
    sha256hex,
    whitespace_only_variants,
)
from trial_radar.model import build_trials  # noqa: E402
from trial_radar.normalize import identity_normalize  # noqa: E402
from trial_radar.promotion import (  # noqa: E402
    promote,
    read_published_manifest,
    stage,
    verify_published,
)
from trial_radar.qa import (  # noqa: E402
    build_collision_report,
    build_quality_report,
    build_schema_report,
)
from trial_radar.source import (  # noqa: E402
    DATASET_URL,
    check_row_count,
    decode_csv,
    extract_csv,
    fetch_dataset,
    parse_csv,
)

TAIPEI = zoneinfo.ZoneInfo("Asia/Taipei")


def taipei_build_date(now: datetime.datetime | None = None) -> datetime.date:
    """§6.5.1：production 的 `buildDate` 以 **Asia/Taipei 日曆日**產生。

    **不得取決於 runner 的 UTC 日期**——runner 是 UTC，台灣時間 08:00 前 UTC 仍是前一天，
    「未來日期」判定會差一天（H5）。
    """
    now = now or datetime.datetime.now(datetime.UTC)
    return now.astimezone(TAIPEI).date()


class RealGit:
    def __init__(self, cwd: Path):
        self.cwd = cwd

    def _run(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.cwd, check=True, capture_output=True)

    def add_all(self) -> None:
        self._run("add", "-A")

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def push(self) -> None:
        self._run("push")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODE_EPILOG,
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--source", type=Path, help="本機 CSV（UTF-8 with BOM）")
    src.add_argument("--fetch", action="store_true", help=f"連網抓取 {DATASET_URL}")
    ap.add_argument("--public", type=Path, default=Path("public/data"))
    ap.add_argument("--qa", type=Path, default=Path("qa"))
    ap.add_argument("--staging", type=Path, default=Path(".staging"))
    ap.add_argument("--build-date", type=datetime.date.fromisoformat,
                    help="覆寫 buildDate（測試用；production 依 Asia/Taipei）")
    ap.add_argument("--dry-run", action="store_true", help="只驗證與產出，不 promotion")
    args = ap.parse_args(argv)

    build_date = args.build_date or taipei_build_date()
    fetched_at = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    try:
        if args.fetch:
            fetched = fetch_dataset(DATASET_URL)
            # §9.6 排除 `sourceSha256` 的論據明寫「ZIP metadata 或列序變動會改變
            # source SHA」——有 ZIP 時它就是 ZIP 的雜湊。`--source` 沒有 ZIP 可雜湊，
            # 退回 CSV 雜湊；兩者值域不同，QA report 因此一併記 `sourceKind`，
            # 否則換執行模式造成的 SHA 改變會被誤讀成上游換了內容。
            source_sha, source_kind = fetched.sha256, "zip"
            csv_bytes = extract_csv(fetched.body)
        else:
            csv_bytes = args.source.read_bytes()
            source_sha, source_kind = sha256hex(csv_bytes), "csv"

        text = decode_csv(csv_bytes)
        rows = parse_csv(text)

        prev = read_published_manifest(args.public)
        prev_rows = prev.get("recordCount") if prev else None
        drop = check_row_count(len(rows), prev_rows)

        try:
            trials = build_trials(rows, build_date)
        except PipelineError as e:
            if e.code is ErrorCode.IDENTITY_COLLISION:
                args.qa.mkdir(parents=True, exist_ok=True)
                (args.qa / "collision-report.json").write_text(
                    json.dumps(build_collision_report(e.detail), ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
            raise

        # §9.4：`builtAt` 是**這份發布物**的建置時間。無變動時根本不會發布
        # （promotion 以 `datasetVersion` 判定），所以這裡一律取「現在」；
        # 沿用 prev 的值反而會讓真的有變動的那次標上舊時間。
        out = build_artifacts(
            trials,
            build_date=build_date.isoformat(),
            fetched_at=fetched_at,
            built_at=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            source_sha256=source_sha,
            bootstrap=drop.bootstrap,
        )

        args.qa.mkdir(parents=True, exist_ok=True)
        near = near_duplicate_groups({r["臨床試驗計畫書編號"] for r in rows
                                      if identity_normalize(r["臨床試驗計畫書編號"])})
        (args.qa / "schema-report.json").write_text(
            json.dumps(build_schema_report(list(rows[0]), len(rows)),
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        (args.qa / "quality-report.json").write_text(
            json.dumps(
                build_quality_report(
                    trials,
                    source_row_count=len(rows),
                    source_sha256=source_sha,
                    source_kind=source_kind,
                    fetched_at=fetched_at,
                    drop=drop,
                    near_duplicates=near,
                    previous=prev,
                    whitespace_variants=whitespace_only_variants(rows),
                ),
                ensure_ascii=False, indent=1,
            ),
            encoding="utf-8",
        )

        stage(out, args.staging)
        if args.dry_run:
            print(f"dry-run：datasetVersion={out.manifest['datasetVersion']}"
                  f"，{len(trials)} Trial／{len(rows)} 列，未發布")
            return 0

        result = promote(out, args.public, args.staging, RealGit(Path.cwd()),
                         message=f"data: update TFDA clinical trial dataset {build_date}")
        if result.published:
            verify_published(args.public)
            print(f"已發布 datasetVersion={result.dataset_version}")
        else:
            print(f"無變動（{result.reason}），未發布")
        return 0

    except PipelineError as e:
        return report(e)


if __name__ == "__main__":
    sys.exit(main())
