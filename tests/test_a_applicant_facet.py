"""D9：applicant facet 的分組鍵（規格 v0.10，schemaVersion 3）。

v0.9 以 raw typed 分 bucket：同一申請者只差尾隨空白／`\\t`／`\\r\\n`／CJK 相容字就拆成
多個 bucket。實資料 370 bucket 中 7 組、124 個 Trial 落在旁支，最大一組勾主選項
漏 116/278（42%）。
"""
from __future__ import annotations

import json

import pytest

from trial_radar.artifacts import build_artifacts, facet_key
from trial_radar.invariants import check_invariants
from trial_radar.model import build_trials
from trial_radar.normalize import facet_normalize

APPLICANT = "臨床試驗申請者"
BASE = "測試丙藥廠股份有限公司"


# ───────────────────────────────────────────── facetNormalize 單元（§6.0）

@pytest.mark.parametrize(
    "raw,expected",
    [
        (BASE + " \t", BASE),                       # 實資料最大一組的形狀
        (BASE + "\r\n", BASE),
        (" " + BASE + " ", BASE),
        ("　" + BASE, BASE),                    # 全形空白
        ("甲  乙", "甲 乙"),               # 內部 NBSP 連續 → 單一 U+0020
        ("甲 　乙", "甲 乙"),               # 其他 White_Space 也算
        ("ABC Co", "ABC Co"),                       # 不 casefold：鍵原樣當選項標籤顯示
        ("台灣百靈佳", "台灣百靈佳"),             # CJK 相容字由 NFKC 折疊（實資料百靈佳那組）
        (" \t\r\n", ""),                            # 只有空白 → 空鍵（由呼叫端歸未提供）
    ],
)
def test_facet_normalize(raw, expected):
    assert facet_normalize(raw) == expected


@pytest.mark.parametrize("ch", ["​", "﻿", "‌", "‍", "\x1c", "\x1f"])
def test_non_white_space_untouched(ch):
    """§6.0：零寬字元與 White_Space 以外的控制字元不壓縮、不移除（r6 R6-1）。

    Python `\\s` 含 U+001C–U+001F，用它實作會讓這組失敗。
    """
    assert facet_normalize(f"甲{ch}乙") == f"甲{ch}乙"
    assert facet_normalize(BASE + ch) == BASE + ch


def test_phase_scale_keys_untouched():
    # 合法值常數不得被 NFKC 改寫（`Phase Ⅱ` → `Phase II` 會讓 bucket 對不上 §6.6.1）
    assert facet_key("臨床試驗期別", "Phase Ⅱ") == "Phase Ⅱ"
    assert facet_key("本臨床試驗規模", "多國多中心") == "多國多中心"


# ───────────────────────────────────────────── 端到端：artifact 的 bucket 與 facetKeys

#: protocol → applicant。每列一個**不同** Trial。
CASES = {
    # 同組：五種寫法 → 一個 bucket
    "AW-01": BASE,
    "AW-02": BASE + " \t",
    "AW-03": "　" + BASE + "\r\n",
    "AW-04": " " + BASE,
    "AW-05": BASE.replace("丙", "丙 "),       # 內部 NBSP：與 BASE 不同組，見下
    # 四套正規化的獨立性（R6-10）
    "AW-10": "甲 乙藥廠",                            # conflictText 會與 AW-11 合併，facet 不會
    "AW-11": "甲乙藥廠",
    "AW-12": "ABC Pharma",                          # search 會與 AW-13 合併，facet 不會
    "AW-13": "abc pharma",
    "AW-14": "丁藥廠​",                          # 零寬：與 AW-15 不合併
    "AW-15": "丁藥廠",
    # sentinel 與空鍵（R6-2、R6-9）
    "AW-20": " \t",                                 # 只有空白 → 未提供
    "AW-21": "N/A",                                 # 文字，不是分類 sentinel → 自成 bucket
    "AW-22": "NA",
}


@pytest.fixture(scope="module")
def variant_out(a_core_rows, build_date):
    donor = next(r for r in a_core_rows.values() if r[APPLICANT].strip())
    rows = [dict(r) for r in a_core_rows.values()]
    for protocol, applicant in CASES.items():
        row = dict(donor)
        row["臨床試驗計畫書編號"] = protocol
        row["TFDA收文號"] = protocol
        row[APPLICANT] = applicant
        rows.append(row)
    trials = build_trials(rows, build_date)
    return build_artifacts(
        trials, build_date=build_date.isoformat(), fetched_at="2026-09-18T01:00:00Z",
        built_at="2026-09-18T01:02:03Z", source_sha256="0" * 64,
    )


def _logical(out, name):
    return json.loads(out.published[out.manifest["files"][name]["path"]])


def _buckets(out):
    return {b["value"]: b["count"] for b in _logical(out, "stats")["facets"]["applicant"]["buckets"]}


def _trials(out):
    return {t["protocolRaw"][0]: t for t in _logical(out, "trialsIndex")["trials"]
            if t["protocolRaw"][0] in CASES}


def test_variants_share_one_bucket(variant_out):
    b = _buckets(variant_out)
    assert b[BASE] == 4                               # AW-01..04
    assert b[BASE.replace("丙", "丙 ")] == 1          # AW-05：內部空白壓成一格但不消失


def test_normalizations_stay_independent(variant_out):
    b = _buckets(variant_out)
    assert b["甲 乙藥廠"] == 1 and b["甲乙藥廠"] == 1
    assert b["ABC Pharma"] == 1 and b["abc pharma"] == 1
    assert b["丁藥廠​"] == 1 and b["丁藥廠"] == 1


def test_blank_is_unprovided_not_bucket(variant_out):
    b = _buckets(variant_out)
    assert "" not in b
    assert _trials(variant_out)["AW-20"]["facetKeys"] == {APPLICANT: ""}


def test_text_sentinels_are_values(variant_out):
    """applicant 是文字欄位：`N/A`／`NA` 保留原文各成 bucket，不套 C1 的分類 sentinel 政策。"""
    b = _buckets(variant_out)
    assert b["N/A"] >= 1 and b["NA"] >= 1


def test_facet_keys_sparse_and_exact(variant_out):
    keyed = {p: t.get("facetKeys") for p, t in _trials(variant_out).items()}
    assert keyed == {
        "AW-01": None, "AW-02": {APPLICANT: BASE}, "AW-03": {APPLICANT: BASE},
        "AW-04": {APPLICANT: BASE}, "AW-05": {APPLICANT: BASE.replace("丙", "丙 ")},
        "AW-10": None, "AW-11": None, "AW-12": None, "AW-13": None,
        "AW-14": None, "AW-15": None,
        "AW-20": {APPLICANT: ""}, "AW-21": None, "AW-22": None,
    }


def test_raw_preserved(variant_out):
    t = _trials(variant_out)
    assert t["AW-02"]["displayFields"][APPLICANT]["raw"] == BASE + " \t"
    assert t["AW-20"]["displayFields"][APPLICANT]["raw"] == " \t"


def test_variant_artifact_passes_invariants(variant_out):
    rep = check_invariants(variant_out.published, variant_out.manifest)
    assert rep.ok, rep.violated
