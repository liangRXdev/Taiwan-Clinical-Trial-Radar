"""前端測試 fixture 的漂移守門（`tests/fixtures/web_artifact/`）。

前端讀的是 JSON 形狀，而那個形狀由 Python 這一側決定。沒有這條，M2 可以照著
**想像中的**資料契約寫完整套 UI，等到接上真實 artifact 才發現欄位不存在——
而那時前端測試全綠、ETL 測試也全綠，兩邊各自對自己的假設自洽。

**與 `tests/fixtures/artifact_sample/` 相反**：那一份是 B8 的證據，位元組被釘住且由
另一套獨立程式碼產生（規格要能被兩份程式碼各自寫出來）；這一份**刻意就是現行 ETL 的
輸出**，契約一改就要重新產生並 commit，讓改動在 diff 上看得見。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import build_web_fixture  # noqa: E402

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "web_artifact"
REGEN = "uv run python scripts/build_web_fixture.py"


@pytest.fixture(scope="module")
def built():
    return build_web_fixture.build()


def test_web_fixture_matches_current_etl_output(built):
    """committed 的 fixture 須與現行 `build_artifacts` **逐位元相同**。"""
    published, _ = built

    on_disk = {
        p.relative_to(FIXTURE).as_posix(): p.read_bytes()
        for p in FIXTURE.rglob("*.json")
        if p.name != "manifest.json"
    }
    assert set(on_disk) == set(published), (
        f"檔案清單與現行 ETL 不符，請重新產生：{REGEN}"
    )
    for path in sorted(published):
        assert on_disk[path] == published[path], f"{path} 內容已漂移，請重新產生：{REGEN}"


def test_web_fixture_manifest_matches(built):
    _, manifest = built
    on_disk = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest, f"manifest 已漂移，請重新產生：{REGEN}"


def test_web_fixture_covers_the_cases_the_frontend_must_handle(built):
    """**保護 fixture 本身**：前端驗收需要的每一類案例都要在這份資料裡。

    少了任何一類，對應的前端測試會退化成「沒有資料所以沒有反例」而靜默全綠——
    這正是 A2 對 ETL fixture 做的同一件事。
    """
    published, manifest = built
    index = json.loads(
        published[manifest["files"]["trialsIndex"]["path"]].decode("utf-8")
    )
    trials = index["trials"]

    assert any(t["latestAmbiguous"] for t in trials), "須有同日衝突（E7）"
    assert any(t["dateUnknown"] for t in trials), "須有無可採計日期者（E8）"
    assert any(t["protocolNonIdentifier"] for t in trials), "須有無編號者（E8）"
    assert any(t["nearDuplicateGroup"] for t in trials), "須有近似編號群（E8）"
    assert any(len(t["protocolRaw"]) > 1 for t in trials), "須有合併後多寫法者（§6.2）"
    assert any(t["latestCohortCount"] > 1 for t in trials), "須有同日多筆（§7.3）"
    assert any(t["recordCount"] > 1 for t in trials), "須有多筆審查紀錄（§7.3）"

    # 搜尋：latest 與 all 的 record 數必須不同，否則 history scope 切換測不出差異
    short_all = json.loads(
        published[manifest["files"]["searchShortAll"]["path"]].decode("utf-8")
    )
    latest_records = sum(len(t["searchShortLatest"]) for t in trials)
    assert len(short_all["records"]) > latest_records, (
        "全部紀錄須多於最新 cohort，否則 §8.5 的 history 切換沒有可觀察差異"
    )

    # 統計：三個 facet 都要有 ≥2 個 bucket，否則篩選多選（OR）測不到
    stats = json.loads(published[manifest["files"]["stats"]["path"]].decode("utf-8"))
    for name, facet in stats["facets"].items():
        assert len(facet["buckets"]) >= 2, f"facet {name} 須有 ≥2 個 bucket"
