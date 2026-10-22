"""applicant facet 的分組鍵（schemaVersion 3，2026-10-22 review #2）。

v2 以 raw typed 分 bucket：同一申請者只差尾隨空白／`\t`／`\r\n`／CJK 相容字就拆成
多個 bucket。實資料 370 bucket 中 7 組、124 個 Trial 落在旁支，最大一組勾主選項
漏 116/278（42%）。
"""
from __future__ import annotations

import pytest

from trial_radar.artifacts import build_artifacts, facet_key
from trial_radar.invariants import check_invariants
from trial_radar.model import build_trials
from trial_radar.normalize import facet_normalize

APPLICANT = "臨床試驗申請者"
BASE = "測試丙藥廠股份有限公司"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (BASE + " \t", BASE),                      # 實資料最大一組的形狀
        (BASE + "\r\n", BASE),
        (" " + BASE + " ", BASE),
        ("　" + BASE, BASE),                    # 全形空白
        ("甲  乙", "甲 乙"),               # 內部 NBSP 連續 → 單一空格
        ("ABC Co", "ABC Co"),                       # 不 casefold：鍵原樣當選項標籤顯示
    ],
)
def test_facet_normalize(raw, expected):
    assert facet_normalize(raw) == expected


def test_compat_ideograph_folds():
    # U+F9B3 是 CJK 相容字（NFKC → U+9748 靈）。實資料「台灣百靈佳」那組就是這種
    raw = "台灣百靈佳殷格翰股份有限公司"
    assert facet_normalize(raw) == "台灣百靈佳殷格翰股份有限公司"


def test_zero_width_not_folded():
    # §6.0：零寬字元不是空白。不可見差異不靜默合併，與 identity 的立場一致
    assert facet_normalize(BASE + "​") != BASE


def test_phase_scale_keys_untouched():
    # 合法值常數不得被 NFKC 改寫（`Phase Ⅱ` → `Phase II` 會讓 bucket 對不上 §6.6.1）
    assert facet_key("臨床試驗期別", "Phase Ⅱ") == "Phase Ⅱ"


@pytest.fixture(scope="module")
def variant_out(a_core_rows, build_date):
    donor = next(r for r in a_core_rows.values() if r[APPLICANT].strip())
    rows = [dict(r) for r in a_core_rows.values()]
    for n, applicant in enumerate((BASE, BASE + " \t", BASE + "\r\n"), start=1):
        row = dict(donor)
        row["臨床試驗計畫書編號"] = f"APPL-WS-{n:02d}"
        row["TFDA收文號"] = f"AW{n:02d}"
        row[APPLICANT] = applicant
        rows.append(row)
    trials = build_trials(rows, build_date)
    return build_artifacts(
        trials, build_date=build_date.isoformat(), fetched_at="2026-09-18T01:00:00Z",
        built_at="2026-09-18T01:02:03Z", source_sha256="0" * 64,
    )


def _logical(out, name):
    import json
    path = out.manifest["files"][name]["path"]
    return json.loads(out.published[path])


def test_variants_share_one_bucket(variant_out):
    buckets = _logical(variant_out, "stats")["facets"]["applicant"]["buckets"]
    assert [b for b in buckets if b["value"].startswith(BASE)] == [{"value": BASE, "count": 3}]


def test_facet_keys_sparse(variant_out):
    trials = _logical(variant_out, "trialsIndex")["trials"]
    keyed = {t["protocolRaw"][0]: t.get("facetKeys") for t in trials
             if t["protocolRaw"][0].startswith("APPL-WS-")}
    assert keyed == {
        "APPL-WS-01": None,                    # 鍵 == typed → 不帶
        "APPL-WS-02": {APPLICANT: BASE},
        "APPL-WS-03": {APPLICANT: BASE},
    }
    # raw 不被改寫：卡片仍顯示原文
    raw = {t["protocolRaw"][0]: t["displayFields"][APPLICANT]["raw"] for t in trials
           if t["protocolRaw"][0].startswith("APPL-WS-")}
    assert raw["APPL-WS-02"] == BASE + " \t"


def test_variant_artifact_passes_invariants(variant_out):
    rep = check_invariants(variant_out.published, variant_out.manifest)
    assert rep.ok, rep.violated
