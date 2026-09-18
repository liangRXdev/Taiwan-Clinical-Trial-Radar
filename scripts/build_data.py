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
from trial_radar.errors import EXIT_CODE_OF, ErrorCode, PipelineError  # noqa: E402
from trial_radar.identity import near_duplicate_groups, sha256hex  # noqa: E402
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
    parse_csv,
    validate_response,
)

TAIPEI = zoneinfo.ZoneInfo("Asia/Taipei")


def taipei_build_date(now: datetime.datetime | None = None) -> datetime.date:
    """§6.5.1：production 的 `buildDate` 以 **Asia/Taipei 日曆日**產生。

    **不得取決於 runner 的 UTC 日期**——runner 是 UTC，台灣時間 08:00 前 UTC 仍是前一天，
    「未來日期」判定會差一天（H5）。
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
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


def _fetch(url: str) -> tuple[bytes, str]:
    import requests

    try:
        resp = requests.get(url, timeout=(10, 120))
    except requests.Timeout as e:
        raise PipelineError(ErrorCode.HTTP_TIMEOUT, str(e)) from e
    except requests.RequestException as e:
        raise PipelineError(ErrorCode.HTTP_TRUNCATED, str(e)) from e

    declared = resp.headers.get("Content-Length")
    result = validate_response(
        resp.status_code,
        resp.headers.get("Content-Type", ""),
        int(declared) if declared and declared.isdigit() else None,
        resp.content,
    )
    return result.body, result.sha256


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exit code 對照：\n"
        + "\n".join(f"  {c.value:<26} {EXIT_CODE_OF[c]}" for c in ErrorCode),
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
    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    try:
        if args.fetch:
            zip_bytes, source_sha = _fetch(DATASET_URL)
            csv_bytes = extract_csv(zip_bytes)
        else:
            csv_bytes = args.source.read_bytes()
            source_sha = sha256hex(csv_bytes)

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

        built_at = (
            prev["builtAt"] if prev else
            datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        )
        out = build_artifacts(
            trials,
            build_date=build_date.isoformat(),
            fetched_at=fetched_at,
            built_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
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
                    fetched_at=fetched_at,
                    drop=drop,
                    near_duplicates=near,
                    previous=prev,
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
        print(f"[{e.code.value}] layer={e.layer.value} {e.message}", file=sys.stderr)
        if e.detail:
            print(json.dumps(e.detail, ensure_ascii=False, indent=1)[:2000], file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
