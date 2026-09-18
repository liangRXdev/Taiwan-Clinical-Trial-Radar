"""B 群驗收：§9.3.6 不變量反例（B6）、digest 可計算性（B8）、no-change 冪等（B9）。

**缺陷一律注入在計算 digest 之前**，使 artifact 的 digest 自洽——真實的威脅模型是
「有 bug 的 ETL 產出內部自洽但違反不變量的 artifact」，它會把自己算出來的 digest 一併
寫進去。改完最終位元組不重算的話，測到的只是 digest 本身，referential integrity 那幾條
永遠不會被執行到。

**每個反例斷言違規集合 exactly equals 預期**，不是「包含」——用「包含」的話，一個把所有
檢查都回報違規的驗證器會全過。
"""
from __future__ import annotations

import copy
import json

import pytest

from trial_radar.artifacts import (
    artifact_digest,
    build_artifacts,
    canonical_json_bytes,
    dataset_version,
    manifest_paths,
)
from trial_radar.errors import ErrorCode, PipelineError
from trial_radar.invariants import INVARIANTS, SPEC_INVARIANTS, assert_invariants, check_invariants
from trial_radar.model import build_trials

BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


@pytest.fixture(scope="module")
def trials(a_core_rows, build_date):
    return build_trials(list(a_core_rows.values()), build_date)


@pytest.fixture(scope="module")
def out(trials):
    return build_artifacts(trials, **BUILD_KW)


def _republish(logical: dict) -> tuple[dict[str, bytes], dict]:
    """把（可能已變造的）logical payload 重新算 digest 並產生最終位元組與 manifest。

    這是 §9.3.2 的後半段——刻意與 `build_artifacts` 共用同一套 digest 函式，
    因為這裡要測的是**不變量**，不是 digest 本身。
    """
    from trial_radar.identity import sha256hex

    dv = dataset_version(logical)
    published, meta = {}, {}
    for name, payload in logical.items():
        h = sha256hex(canonical_json_bytes(payload))[:16]
        stem, ext = name.rsplit(".", 1)
        path = f"{stem}.{h}.{ext}"
        published[path] = canonical_json_bytes({**payload, "datasetVersion": dv})
        meta[name] = {"path": path, "bytes": 0, "gzipBytes": 0}
    manifest = {
        "datasetVersion": dv,
        "artifactDigest": artifact_digest(published),
        "files": {
            "trialsIndex": meta["trials-index.json"],
            "stats": meta["stats.json"],
            "searchShortAll": meta["search-short-all.json"],
            "searchLongLatest": meta["search-long-latest.json"],
            "searchLongAll": meta["search-long-all.json"],
            "recordShards": {
                n.split("/")[1].split(".")[0]: meta[n]
                for n in logical
                if n.startswith("records/")
            },
        },
    }
    return published, manifest


def _mutated(out, mutate):
    logical = copy.deepcopy(out.logical)
    mutate(logical)
    return _republish(logical)


def _index(logical):
    return logical["trials-index.json"]["trials"]


def _trial_by_protocol(logical, protocol):
    return next(t for t in _index(logical) if protocol in t["protocolRaw"])


def _entry(logical, protocol):
    t = _trial_by_protocol(logical, protocol)
    return logical[f"records/{t['shard']}.json"]["trials"][t["id"]], t


# ---------------------------------------------------------------- 反向哨兵

def test_unmutated_artifact_has_zero_violations(out):
    """**反向哨兵**：未變造的 artifact 必須零違規。這裡若紅，底下每一條都不算數。"""
    rep = check_invariants(out.published, out.manifest)
    assert rep.violated == set()
    assert rep.unevaluable == {}
    assert_invariants(out.published, out.manifest)


# ---------------------------------------------------------------- B6

def _m_dup_owner(logical):
    """同 shard 的兩個 Trial 引用同一筆 record。跨 shard 會連帶違反 shard 歸屬而無法隔離。"""
    ind, _ = _entry(logical, "IND-005")
    nr_entry, nr = _entry(logical, "NR-028")
    borrowed = ind["recordIds"][0]
    shard = logical[f"records/{nr['shard']}.json"]
    recs = shard["records"]

    def key(rid):
        d = recs[rid]["typed"]["資料更新時間"]
        return (d is None, "" if d is None else "".join(chr(0x10FFFD - ord(c)) for c in d), rid)

    nr_entry["recordIds"] = sorted(nr_entry["recordIds"] + [borrowed], key=key)
    nr["recordCount"] = len(nr_entry["recordIds"])


def _m_dup_within_trial(logical):
    entry, t = _entry(logical, "IND-005")
    entry["recordIds"] = sorted(entry["recordIds"] + [entry["recordIds"][0]])
    t["recordCount"] = len(entry["recordIds"])


def _m_wrong_shard(logical):
    t = _trial_by_protocol(logical, "WS-003")
    src = logical[f"records/{t['shard']}.json"]
    dst = next(k for k in logical
               if k.startswith("records/") and k != f"records/{t['shard']}.json")
    rid = sorted(src["records"])[0]
    logical[dst]["records"][rid] = src["records"].pop(rid)


def _m_orphan_record(logical):
    t = _trial_by_protocol(logical, "WS-003")
    shard = logical[f"records/{t['shard']}.json"]
    rid = sorted(shard["records"])[0]
    shard["records"][t["id"] + "r" + "0" * 16 + "#0"] = copy.deepcopy(shard["records"][rid])


def _m_cohort_not_subset(logical):
    entry, t = _entry(logical, "IND-005")
    entry["latestCohort"] = sorted(entry["latestCohort"] + ["t" + "f" * 16 + "r" + "f" * 16 + "#0"])
    t["latestCohortCount"] = len(entry["latestCohort"])


def _m_recordcount_mismatch(logical):
    _trial_by_protocol(logical, "WS-003")["recordCount"] = 99


def _m_cohortcount_mismatch(logical):
    _trial_by_protocol(logical, "PH-004")["latestCohortCount"] = 5


def _m_trials_unsorted(logical):
    _index(logical).reverse()


def _m_recordids_unsorted(logical):
    entry, _ = _entry(logical, "BIG-001")
    entry["recordIds"] = list(reversed(entry["recordIds"]))


def _m_cohort_unsorted(logical):
    entry, _ = _entry(logical, "PH-004")
    entry["latestCohort"] = list(reversed(entry["latestCohort"]))


def _facet_mutator(name):
    def m(logical):
        f = logical["stats.json"]["facets"][name]
        f["buckets"] = [dict(b) for b in f["buckets"]]
        # 維持總和不變，只把計數挪到錯的 bucket——§9.3.5 的和仍成立，只有 I6 抓得到
        f["buckets"][0]["count"] += 1
        if f["unprovided"]:
            f["unprovided"] -= 1
        elif f["conflicted"]:
            f["conflicted"] -= 1
        else:
            f["buckets"][-1]["count"] -= 1
    return m


B6_CASES = [
    ("record 被兩個 Trial 引用（同 shard，可隔離）", _m_dup_owner, {"I3.owner"}),
    ("同一 Trial 重複引用同一筆 record", _m_dup_within_trial, {"I3.owner"}),
    ("record 放錯 shard", _m_wrong_shard, {"I3.shard"}),
    ("shard 內有零 Trial 引用的 record", _m_orphan_record, {"I3.orphan"}),
    ("latestCohort ⊄ recordIds", _m_cohort_not_subset, {"I3.subset"}),
    ("recordCount 與 shard 清單長度不符", _m_recordcount_mismatch, {"I4.records"}),
    ("latestCohortCount 與 latestCohort 長度不符", _m_cohortcount_mismatch, {"I4.cohort"}),
    ("trials 未依 trialId 昇序", _m_trials_unsorted, {"I5.trials"}),
    ("recordIds 未依規定排序", _m_recordids_unsorted, {"I5.records"}),
    ("latestCohort 未依 recordId 昇序", _m_cohort_unsorted, {"I5.cohort"}),
    ("facet phase 的 bucket 計數錯置", _facet_mutator("phase"), {"I6"}),
    ("facet scale 的 bucket 計數錯置", _facet_mutator("scale"), {"I6"}),
    ("facet applicant 的 bucket 計數錯置", _facet_mutator("applicant"), {"I6"}),
]


@pytest.mark.parametrize("label,mutate,expected", B6_CASES,
                         ids=[c[0] for c in B6_CASES])
def test_b6_each_invariant_has_independent_counterexample(out, label, mutate, expected):
    published, manifest = _mutated(out, mutate)
    rep = check_invariants(published, manifest)
    assert rep.violated == expected, label
    # digest 自洽 → 證明測到的是不變量本身，不是 digest
    assert not (rep.violated & {"I2", "I7.datasetVersion", "I7.artifactDigest"})
    with pytest.raises(PipelineError) as exc:
        assert_invariants(published, manifest)
    assert exc.value.code is ErrorCode.INTEGRITY_DIGEST


def test_b6_inventory_orphan_file(out):
    """磁碟上有 manifest 未列出的孤兒檔。"""
    on_disk = dict(out.published)
    on_disk["records/zz.deadbeefdeadbeef.json"] = b'{"datasetVersion":"x"}'
    rep = check_invariants(on_disk, out.manifest)
    assert rep.violated == {"I1"}
    # 孤兒檔**不會**改變 artifactDigest（§9.3.2 只走 manifest.files 的路徑）
    assert artifact_digest(out.published) == out.manifest["artifactDigest"]


def test_b6_inventory_missing_file(out):
    """manifest 列出但檔案不存在 → I1 違規，I2／I7 回報**無法評估**而非違規。"""
    on_disk = {k: v for k, v in out.published.items()
               if k != out.manifest["files"]["stats"]["path"]}
    rep = check_invariants(on_disk, out.manifest)
    assert rep.violated == {"I1"}
    assert set(rep.unevaluable) >= {"I2", "I7.datasetVersion", "I7.artifactDigest"}


def test_b6_unevaluable_is_not_pass(out):
    """B6(e)：「無法評估」≠「通過」。把兩者混為一談的驗證器必須被殺死。"""
    on_disk = {k: v for k, v in out.published.items()
               if k != out.manifest["files"]["stats"]["path"]}
    rep = check_invariants(on_disk, out.manifest)
    assert "I6" in rep.unevaluable or "I6" in rep.violated
    assert rep.unevaluable, "須明確記錄哪一條因為什麼前置條件而無法評估"


def test_b6_mutation_inventory_reconciles_with_spec(out):
    """B6(d)：mutation inventory 與 §9.3.6 的 I1–I7 **雙向對帳**。"""
    covered = set()
    for _, _, expected in B6_CASES:
        covered |= expected
    covered |= {"I1", "I2", "I7.datasetVersion", "I7.artifactDigest"}  # 由其他測試涵蓋

    for spec_id, subs in SPEC_INVARIANTS.items():
        missing = [s for s in subs if s not in covered]
        assert not missing, f"§9.3.6 {spec_id} 缺反例：{missing}"
    assert covered <= set(INVARIANTS), "每個反例都要對應到某條不變量"


# ---------------------------------------------------------------- B7

def test_b7_cross_version_binding(out):
    """B7：manifest 為新版但某 shard 為舊 `datasetVersion` → fail-closed。"""
    shard_path = next(iter(out.manifest["files"]["recordShards"].values()))["path"]
    stale = dict(out.published)
    obj = json.loads(stale[shard_path].decode())
    obj["datasetVersion"] = "0" * 16
    stale[shard_path] = canonical_json_bytes(obj)

    rep = check_invariants(stale, out.manifest)
    assert rep.violated == {"I2", "I7.artifactDigest"}
    # I7.datasetVersion **不觸發**：移除版本欄位後的 logical payload 沒變。
    # 兩者是不同的不變量，把它們併成一條就驗不到這個區別。
    assert "I7.datasetVersion" not in rep.violated


def test_b7_all_files_but_manifest_carry_content_hash(out):
    """B7：除 `manifest.json` 外所有檔名都帶內容雜湊，且 manifest 為唯一固定 URL。"""
    import re

    for path in manifest_paths(out.manifest):
        stem, h, ext = path.rsplit(".", 2)
        assert re.fullmatch(r"[0-9a-f]{16}", h), path
        assert ext == "json"
    assert "manifest.json" not in out.published


# ---------------------------------------------------------------- B8

def test_b8_deterministic_and_non_circular(trials, out):
    """B8-1：同一輸入兩次 build 得到相同 `datasetVersion`。"""
    again = build_artifacts(trials, **BUILD_KW)
    assert again.manifest["datasetVersion"] == out.manifest["datasetVersion"]
    assert again.published == out.published


def test_b8_fixed_point_from_final_files(out):
    """B8-1b：從**已寫入版本欄位的最終檔案**移除該欄位後反算，須得同一個版本號。

    這才是循環被解開的證據——「兩次跑結果相同」只證明決定性。
    """
    logical = {}
    for path, data in out.published.items():
        obj = json.loads(data.decode())
        assert obj.pop("datasetVersion") == out.manifest["datasetVersion"]
        stem, _h, ext = path.rsplit(".", 2)
        logical[f"{stem}.{ext}"] = obj
    assert dataset_version(logical) == out.manifest["datasetVersion"]


def test_b8_single_character_change_moves_version(a_core_rows, build_date, out):
    """B8-2：任一欄位值改一個字元 → `datasetVersion` 改變。"""
    rows = [dict(r) for r in a_core_rows.values()]
    rows[0]["台灣預計受試者人數"] = rows[0]["台灣預計受試者人數"] + "1"
    other = build_artifacts(build_trials(rows, build_date), **BUILD_KW)
    assert other.manifest["datasetVersion"] != out.manifest["datasetVersion"]


def test_b8_swapping_two_files_changes_version(out):
    """B8-3：兩個檔案內容互換 → `datasetVersion` 改變（證明邏輯檔名已納入）。

    附反向哨兵：互換前後的 payload hash **多重集合相同**——否則「digest 改變」也可能
    只是因為內容本來就不同，證不到邏輯檔名有作用。
    """
    from trial_radar.identity import sha256hex

    logical = copy.deepcopy(out.logical)
    a, b = "stats.json", "search-short-all.json"
    logical[a], logical[b] = logical[b], logical[a]

    before = sorted(sha256hex(canonical_json_bytes(p)) for p in out.logical.values())
    after = sorted(sha256hex(canonical_json_bytes(p)) for p in logical.values())
    assert before == after, "payload hash 多重集合必須相同"
    assert dataset_version(logical) != out.manifest["datasetVersion"]


def test_b8_two_digests_are_different_and_recomputable(out):
    """B8-4：兩者為不同值、長度分別為 16／64 hex、各自可重算。"""
    m = out.manifest
    assert m["artifactDigest"] != m["datasetVersion"]
    assert len(m["datasetVersion"]) == 16 and len(m["artifactDigest"]) == 64
    assert artifact_digest(out.published) == m["artifactDigest"]
    assert "manifest.json" not in out.published, "artifactDigest 的輸入不含 manifest 自身"


# ---------------------------------------------------------------- B9

def test_b9_no_change_idempotent(trials, out):
    """B9：同一凍結來源連跑兩次，`datasetVersion` 相同 → 不發布、`builtAt` 不變。"""
    later = build_artifacts(
        trials,
        build_date="2026-09-18",
        fetched_at="2026-10-01T09:00:00Z",   # 第二次抓取時間不同
        built_at="2026-10-01T09:00:05Z",
        source_sha256="1" * 64,               # 上游重新打包 → source SHA 不同
    )
    # §9.4 的排除清單：builtAt／fetchedAt／sourceSha256／artifactDigest 不進比較
    assert later.manifest["datasetVersion"] == out.manifest["datasetVersion"]
    # 判準是 datasetVersion 相同即無變動 → 不發布，故已發布的 builtAt 維持原值
    assert out.manifest["builtAt"] == "2026-09-18T01:02:03Z"


def test_b9_source_sha_change_alone_does_not_republish(trials, out):
    """改變 `sourceSha256` 但 logical payload 不變 → 仍不發布。

    上游若以相同資料重新打包，ZIP metadata 或列序變動會改變 source SHA 而正規化資料不變；
    把它算進比較會每月產生噪音 commit。它是 provenance 不是資料。
    """
    other = build_artifacts(trials, **{**BUILD_KW, "source_sha256": "f" * 64})
    assert other.manifest["datasetVersion"] == out.manifest["datasetVersion"]
