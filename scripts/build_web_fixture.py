"""由 `tests/fixtures/a_core/` 產生前端測試用的 artifact（`tests/fixtures/web_artifact/`）。

**與 `tests/fixtures/artifact_sample/` 是兩回事**：那一份是 B8 的證據，位元組被
`.gitattributes` 釘住、由 `build_sample.py` 以另一套獨立程式碼產生（規格要能被兩份程式碼
各自寫出來）。這一份相反——它**刻意就是現行 ETL 的輸出**，前端測試才會在資料契約改變時
立刻轉紅，而不是等到 M2 做完才發現前端讀的是想像中的形狀。

`tests/test_web_fixture.py` 會斷言本目錄的內容與現行 `build_artifacts` 逐位元相同。

用法：
    uv run python scripts/build_web_fixture.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trial_radar.artifacts import build_artifacts  # noqa: E402
from trial_radar.model import build_trials  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "web_artifact"

# 與 tests/conftest.py 的 BUILD_DATE 一致。**浮動的 build 當日與凍結 fixture 矛盾**
# ——§6.5 的「不晚於 build 當日」依賴當日日期。
BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


PROTOCOL = "臨床試驗計畫書編號"
#: 衍生列的 donor。固定挑明就不會因 a_core 補案例而悄悄換人。
WS_DONOR = "SAME-010"


def _whitespace_variant(rows: list[dict]) -> list[dict]:
    """加一列「僅尾隨空白」的衍生資料（§6.2 的合併案例）。

    **a_core 本身沒有空白變體**（`whitespace_only_variants` 對它回傳空清單），
    但前端詳情頁必須顯示合併後 Trial 的**全部** `protocolRaw`。fixture 少了這一類，
    對應的前端測試會退化成「沒有資料所以沒有反例」而靜默全綠。

    衍生而非改動 a_core：那份 fixture 的位元組被 `.gitattributes` 釘住，且 A 群的
    oracle 逐列對應，動它會連帶打翻 ETL 那一側的斷言。
    """
    donor = next(r for r in rows if r[PROTOCOL] == WS_DONOR)
    variant = dict(donor)
    variant[PROTOCOL] = donor[PROTOCOL] + " "
    # 收文號換掉，否則兩列逐位元相同，測到的是重複列而不是空白變體
    variant["TFDA收文號"] = "WEB-FIXTURE-WS"
    return [variant]


def build() -> tuple[dict[str, bytes], dict]:
    import datetime

    rows_path = ROOT / "tests" / "fixtures" / "a_core" / "rows.json"
    rows = list(json.loads(rows_path.read_text(encoding="utf-8"))["rows"].values())
    trials = build_trials(rows + _whitespace_variant(rows), datetime.date(2026, 9, 18))
    out = build_artifacts(trials, **BUILD_KW)
    return out.published, out.manifest


def main() -> int:
    published, manifest = build()

    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    FIXTURE.mkdir(parents=True)

    for path, data in published.items():
        target = FIXTURE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    # manifest 最後寫：它是唯一固定 URL，也是前端的入口
    (FIXTURE / "manifest.json").write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    )

    print(f"{len(published) + 1} 個檔案 → {FIXTURE.relative_to(ROOT)}")
    print(f"datasetVersion={manifest['datasetVersion']} "
          f"trialCount={manifest['trialCount']} recordCount={manifest['recordCount']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
