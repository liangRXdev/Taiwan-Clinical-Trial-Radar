"""驗收 B6：§9.3.6 的每一條不變量各有**獨立**反例，全部須硬失敗 `INTEGRITY_DIGEST`。

作法：以最小 artifact 樣本為基底，對 **logical payload** 注入單一缺陷後**照常算 digest**，
再用一支只實作 §9.3.6 的驗證器去檢。

**為什麼要在算 digest 之前注入**：真實的威脅模型是「有 bug 的 ETL 產出內部自洽但違反不變量的
artifact」——它會把自己算出來的 digest 一併寫進去。若改完最終位元組就放著不重算，
測到的只是 digest 本身，referential integrity 那幾條永遠不會被執行到。

**每個反例都斷言違反集合 exactly equals 預期**，不是「包含」。B6 要的是**獨立**反例：
若某個缺陷必然連帶觸發另一條，那麼只實作其中一條的驗證器也會通過測試，這條驗收就是假的。

跑法：`python tests/fixtures/artifact_sample/check_b6.py`
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sample import (  # noqa: E402
    artifact_digest, build, dataset_version, load_rows,
)

failures = []

# 編號**對齊 §9.3.6 的 I1–I7**，子編號用於區分同一條不變量的不同違反形狀。
# （v0.7 前本檔用自訂的 I1–I11，結果 latestCohort⊆recordIds 與 stats 一致性撞了同一個 id——
#  兩條不同的不變量共用編號時，B6 的「各自獨立反例」就驗不到其中一條。）
I = {
    "I1": "inventory：manifest.files 路徑集合 == 除 manifest.json 外的全部檔案",
    "I2": "跨檔版本綁定：每個非 manifest 檔案的 datasetVersion == manifest 的值",
    "I3.shard": "referential integrity：每個 recordId 存在於 trial.shard 指定的 shard",
    "I3.owner": "referential integrity：每個 record 恰好被一個 Trial 引用一次",
    "I3.orphan": "referential integrity：shard 內不得有零 Trial 引用的 record",
    "I3.subset": "referential integrity：latestCohort ⊆ recordIds",
    "I4.records": "計數一致：trial.recordCount == shard 內 recordIds 長度",
    "I4.cohort": "計數一致：trial.latestCohortCount == latestCohort 長度",
    "I5.trials": "排序：trials 依 trialId 昇序",
    "I5.records": "排序：recordIds 依（可採計日期降序、不可採計者置末、recordId 昇序）",
    "I5.cohort": "排序：latestCohort 依 recordId 昇序",
    "I6": "stats 一致性：facet bucket 計數 == 依 trials-index 重算的結果",
    "I7.datasetVersion": "datasetVersion 可由 logical payload 重算",
    "I7.artifactDigest": "artifactDigest 可由 manifest.files 的最終位元組重算",
}

# §9.3.6 的七條與本檔子編號的對照，供雙向對帳（r4 B6(d)）
SPEC_INVARIANTS = {
    "I1": ["I1"], "I2": ["I2"],
    "I3": ["I3.shard", "I3.owner", "I3.orphan", "I3.subset"],
    "I4": ["I4.records", "I4.cohort"],
    "I5": ["I5.trials", "I5.records", "I5.cohort"],
    "I6": ["I6"],
    "I7": ["I7.datasetVersion", "I7.artifactDigest"],
}


def check(cond, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        failures.append(msg)


def logical_name(path):
    stem, _h, ext = path.rsplit(".", 2)
    return f"{stem}.{ext}"


def validate(on_disk, manifest):
    """只實作 §9.3.6。回傳被違反的不變量 id 集合。

    這是**驗證器**不是 ETL：它只讀 artifact，不知道來源資料長什麼樣。
    """
    bad = set()

    declared = {manifest["files"][k]["path"] for k in
                ("trialsIndex", "stats", "searchShortAll", "searchLongLatest", "searchLongAll")}
    declared |= {v["path"] for v in manifest["files"]["recordShards"].values()}
    if declared != set(on_disk):
        bad.add("I1")

    missing = declared - set(on_disk)
    readable = {p: on_disk[p] for p in declared if p in on_disk}

    # I2／I7.datasetVersion：由最終檔案移除 top-level datasetVersion 後重算
    logical, embedded_ok = {}, True
    for path, data in readable.items():
        obj = json.loads(data.decode("utf-8"))
        if obj.pop("datasetVersion", None) != manifest["datasetVersion"]:
            embedded_ok = False
        logical[logical_name(path)] = obj
    if missing:
        # 宣告的檔案不在磁碟上時 I2／I7 無從重算——記為「無法評估」，不假裝驗過
        pass
    else:
        if not embedded_ok:
            bad.add("I2")
        if dataset_version(logical) != manifest["datasetVersion"]:
            bad.add("I7.datasetVersion")

    if not missing and artifact_digest(readable) != manifest["artifactDigest"]:
        bad.add("I7.artifactDigest")

    index_path = manifest["files"]["trialsIndex"]["path"]
    if index_path not in readable:
        return bad
    trials = json.loads(readable[index_path].decode("utf-8"))["trials"]
    shards = {s: json.loads(readable[m["path"]].decode("utf-8"))
              for s, m in manifest["files"]["recordShards"].items()
              if m["path"] in readable}

    if [t["id"] for t in trials] != sorted(t["id"] for t in trials):
        bad.add("I5.trials")

    owners = {}
    for t in trials:
        shard = shards.get(t["shard"])
        if shard is None or t["id"] not in shard["trials"]:
            bad.add("I3.shard")
            continue
        entry = shard["trials"][t["id"]]
        rids, cohort = entry["recordIds"], entry["latestCohort"]

        def sort_key(rid):
            rec = shard["records"].get(rid)
            d = (rec or {}).get("typed", {}).get("資料更新時間")
            # 可採計日期降序、不可採計者置末 → 以 (無日期?, 反轉日期, rid) 排序
            return (d is None, "" if d is None else "".join(chr(0x10FFFD - ord(c)) for c in d), rid)

        # **I3.shard 必須先於 I5.records 評估。** 排序鍵取自該 record 的 `資料更新時間`，
        # 而那筆資料在 shard 裡；record 放錯 shard 時排序鍵根本取不到，
        # 硬算會把「查不到日期」當成「不可採計日期→置末」而誤報 I5.records。
        # v0.7 §9.3.6 已把它寫成 I5 的必要前置條件（GAP-11）。
        resolvable = all(rid in shard["records"] for rid in rids)
        if not resolvable:
            bad.add("I3.shard")
        elif rids != sorted(rids, key=sort_key):
            bad.add("I5.records")
        if cohort != sorted(cohort):
            bad.add("I5.cohort")
        if not set(cohort) <= set(rids):
            bad.add("I3.subset")
        if t["recordCount"] != len(rids):
            bad.add("I4.records")
        if t["latestCohortCount"] != len(cohort):
            bad.add("I4.cohort")
        for rid in rids:
            owners[rid] = owners.get(rid, 0) + 1

    # **零 Trial 引用的 record 也是 referential integrity 的違規**——只數「已被引用者的 owner count」會漏掉，
    # 那正是 Codex 第四輪 B6 指出的弱化驗證器。
    for sh in shards.values():
        if any(rid not in owners for rid in sh["records"]):
            bad.add("I3.orphan")
    if any(n != 1 for n in owners.values()):
        bad.add("I3.owner")

    # I6 stats 一致性。**前置條件只有「兩個檔可讀」**，不依賴 I3／I4／I5——
    # v0.6 曾用全域七步順序，一個 shard 錯誤會遮蔽同時存在的 stats 錯誤（r4 1.2）。
    stats_path = manifest["files"]["stats"]["path"]
    if stats_path in readable:
        stats = json.loads(readable[stats_path].decode("utf-8"))
        FACET_FIELD = {"phase": "臨床試驗期別", "scale": "本臨床試驗規模",
                       "applicant": "臨床試驗申請者"}
        for name, facet in stats["facets"].items():
            counts = {}
            unprovided = conflicted = 0
            field = FACET_FIELD[name]
            for t in trials:
                if field in t["conflictFields"]:
                    conflicted += 1
                    continue
                df = t["displayFields"].get(field)
                if df is None or df["typed"] is None:
                    unprovided += 1
                else:
                    counts[df["typed"]] = counts.get(df["typed"], 0) + 1
            declared_counts = {b["value"]: b["count"] for b in facet["buckets"]}
            if (declared_counts != counts or facet["unprovided"] != unprovided
                    or facet["conflicted"] != conflicted):
                bad.add("I6")
            if (sum(b["count"] for b in facet["buckets"]) + facet["unprovided"]
                    + facet["conflicted"] != stats["denominators"]["trials"]):
                bad.add("I6")

    return bad


# ---------- mutation 們 ----------

def _index(logical):
    return logical["trials-index.json"]["trials"]


def _trial(logical, protocol):
    return next(t for t in _index(logical) if t["protocolRaw"][0] == protocol)


def _shard_entry(logical, protocol):
    t = _trial(logical, protocol)
    return logical[f"records/{t['shard']}.json"]["trials"][t["id"]], t


def m_dup_owner_cross_trial(logical):
    """IND-005 的一筆 record 同時被 NR-028 引用。兩者**同 shard（c4）**，故不連帶違反 I4。"""
    ind, _ = _shard_entry(logical, "IND-005")
    nr_entry, nr = _shard_entry(logical, "NR-028")
    borrowed = ind["recordIds"][0]
    shard = logical[f"records/{nr['shard']}.json"]
    recs = shard["records"]

    def key(rid):
        d = recs[rid]["typed"]["資料更新時間"]
        return (d is None, "" if d is None else "".join(chr(0x10FFFD - ord(c)) for c in d), rid)

    nr_entry["recordIds"] = sorted(nr_entry["recordIds"] + [borrowed], key=key)
    nr["recordCount"] = len(nr_entry["recordIds"])


def m_dup_within_trial(logical):
    """同一 Trial 的 recordIds 重複引用同一筆 record。"""
    entry, t = _shard_entry(logical, "IND-005")
    entry["recordIds"] = sorted(entry["recordIds"] + [entry["recordIds"][0]])
    t["recordCount"] = len(entry["recordIds"])


def m_wrong_shard(logical):
    """把 WS-003 的一筆 record 物件搬到別的 shard（recordIds 不動）。"""
    t = _trial(logical, "WS-003")
    src = logical[f"records/{t['shard']}.json"]
    dst_key = next(k for k in logical
                   if k.startswith("records/") and k != f"records/{t['shard']}.json")
    rid = sorted(src["records"])[0]
    logical[dst_key]["records"][rid] = src["records"].pop(rid)


def m_cohort_not_subset(logical):
    entry, t = _shard_entry(logical, "IND-005")
    fake = "t" + "f" * 16 + "r" + "f" * 16 + "#0"
    entry["latestCohort"] = sorted(entry["latestCohort"] + [fake])
    t["latestCohortCount"] = len(entry["latestCohort"])


def m_recordcount_mismatch(logical):
    _trial(logical, "WS-003")["recordCount"] = 99


def m_cohortcount_mismatch(logical):
    _trial(logical, "PH-004")["latestCohortCount"] = 5


def m_trials_unsorted(logical):
    _index(logical).reverse()


def m_recordids_unsorted(logical):
    entry, _ = _shard_entry(logical, "WS-003")
    entry["recordIds"] = list(reversed(entry["recordIds"]))


def m_cohort_unsorted(logical):
    entry, _ = _shard_entry(logical, "PH-004")
    entry["latestCohort"] = list(reversed(entry["latestCohort"]))


def m_orphan_record(logical):
    """shard 的 records 裡多一筆沒有任何 Trial 引用的 record。"""
    t = _trial(logical, "WS-003")
    shard = logical[f"records/{t['shard']}.json"]
    rid = sorted(shard["records"])[0]
    orphan = json.loads(json.dumps(shard["records"][rid]))
    shard["records"][t["id"] + "r" + "0" * 16 + "#0"] = orphan


def _facet_mutator(name):
    def m(logical):
        f = logical["stats.json"]["facets"][name]
        # 總和維持不變，只把計數挪到錯的 bucket——§9.3.5 的和仍成立，只有 I6 抓得到
        f["buckets"] = [dict(b) for b in f["buckets"]]
        f["buckets"][0]["count"] += 1
        f["unprovided"] = max(0, f["unprovided"] - 1) if f["unprovided"] else f["unprovided"]
        if not f["unprovided"] and f["conflicted"]:
            f["conflicted"] -= 1
        elif not f["unprovided"] and not f["conflicted"]:
            f["buckets"][-1]["count"] -= 1
    return m


MUTATIONS = [
    ("record 被兩個 Trial 引用（同 shard，故可隔離）", m_dup_owner_cross_trial, {"I3.owner"}),
    ("同一 Trial 重複引用同一筆 record", m_dup_within_trial, {"I3.owner"}),
    ("record 放錯 shard", m_wrong_shard, {"I3.shard"}),
    ("latestCohort ⊄ recordIds", m_cohort_not_subset, {"I3.subset"}),
    ("recordCount 與 shard 清單長度不符", m_recordcount_mismatch, {"I4.records"}),
    ("latestCohortCount 與 latestCohort 長度不符", m_cohortcount_mismatch, {"I4.cohort"}),
    ("trials 未依 trialId 昇序", m_trials_unsorted, {"I5.trials"}),
    ("recordIds 未依規定排序", m_recordids_unsorted, {"I5.records"}),
    ("latestCohort 未依 recordId 昇序", m_cohort_unsorted, {"I5.cohort"}),
    ("shard 內有零 Trial 引用的 orphan record", m_orphan_record, {"I3.orphan"}),
    ("facet phase 的 bucket 計數錯置", _facet_mutator("phase"), {"I6"}),
    ("facet scale 的 bucket 計數錯置", _facet_mutator("scale"), {"I6"}),
    ("facet applicant 的 bucket 計數錯置", _facet_mutator("applicant"), {"I6"}),
]


def main():
    rows = load_rows()
    _, published, manifest = build(rows)

    print("\n[反向哨兵] 未變造的樣本必須零違規")
    base = validate(published, manifest)
    check(base == set(), f"未變造樣本的違規集合為空（實際 {sorted(base)}）"
          + ("" if base == set() else "——驗證器若在這裡就紅，下面每一條都不算數"))

    print("\n[B6] 每條不變量的獨立反例（斷言違規集合 exactly equals 預期）")
    for label, mutate, expected in MUTATIONS:
        _, pub, man = build(rows, mutate=mutate)
        got = validate(pub, man)
        check(got == expected,
              f"{label} → {sorted(expected)}"
              + ("" if got == expected else f"（實際 {sorted(got)}）"))
        # digest 必須自洽——否則測到的是 digest 不是不變量
        check(not (got & {"I2", "I7.datasetVersion", "I7.artifactDigest"}),
              "  └ 該反例的 digest 與跨檔版本自洽，證明測到的是不變量本身")

    print("\n[B6] inventory 的兩種失敗形狀（§9.3.6 的 inventory 不變量）")
    orphan = dict(published)
    orphan["records/zz.deadbeefdeadbeef.json"] = b'{"datasetVersion":"x","trials":{},"records":{}}'
    got = validate(orphan, manifest)
    check(got == {"I1"}, f"磁碟上有 manifest 未列出的孤兒檔 → ['I1']（實際 {sorted(got)}）")
    check(artifact_digest({p: d for p, d in orphan.items()
                           if p != "records/zz.deadbeefdeadbeef.json"})
          == manifest["artifactDigest"],
          "  └ 孤兒檔**不會**改變 artifactDigest（§9.3.2 只走 manifest.files 的路徑）"
          "——故 inventory 不變量無可取代")

    dropped = {p: d for p, d in published.items()
               if p != manifest["files"]["stats"]["path"]}
    got = validate(dropped, manifest)
    check(got == {"I1"}, f"manifest 列出但檔案不存在 → ['I1']（實際 {sorted(got)}）")
    check("I7.datasetVersion" not in got and "I7.artifactDigest" not in got,
          "  └ 檔案缺席時 I2／I7 回報「無法評估」而非「違規」——"
          "把兩者混為一談的驗證器必須被殺死（v0.7 §9.3.6、B6(e)）")

    print("\n[B7] 跨版本綁定：某個 shard 帶舊的 datasetVersion")
    stale = dict(published)
    shard_path = next(iter(manifest["files"]["recordShards"].values()))["path"]
    obj = json.loads(stale[shard_path].decode("utf-8"))
    obj["datasetVersion"] = "0" * 16
    stale[shard_path] = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False).encode("utf-8")
    got = validate(stale, manifest)
    check(got == {"I2", "I7.artifactDigest"},
          f"shard 的 datasetVersion 與 manifest 不符 → I2 ＋ I7.artifactDigest"
          f"（實際 {sorted(got)}）")
    check("I7.datasetVersion" not in got,
          "  └ **I7.datasetVersion 不觸發**：移除版本欄位後的 logical payload 沒變，"
          "重算結果仍等於 manifest 的值。兩者是不同的不變量，把它們併成一條就驗不到這個區別")
    check("I2" in got,
          "  └ 前端據此 fail-closed 顯示「資料版本不一致，請重新載入」，不得混用渲染")

    print("\n[B6] 兩個 digest 各自的獨立反例")
    # I7.datasetVersion：logical payload 被動過，但版本欄位仍寫成舊值
    tampered = dict(published)
    idx_path = manifest["files"]["trialsIndex"]["path"]
    obj = json.loads(tampered[idx_path].decode("utf-8"))
    obj["trials"][0]["protocolRaw"] = ["TAMPERED"]
    tampered[idx_path] = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")
    got = validate(tampered, manifest)
    check(got == {"I7.datasetVersion", "I7.artifactDigest"},
          f"logical payload 被竄改但版本欄位不變 → 兩個 I7（實際 {sorted(got)}）")
    check("I2" not in got,
          "  └ I2 不觸發：檔案內的 datasetVersion 仍等於 manifest 的值。"
          "只做跨檔版本比對的驗證器抓不到內容竄改")

    # I7.artifactDigest：manifest 所載的 digest 本身是舊的
    stale_manifest = dict(manifest)
    stale_manifest["artifactDigest"] = "0" * 64
    got = validate(published, stale_manifest)
    check(got == {"I7.artifactDigest"},
          f"manifest.artifactDigest 為舊值 → 只有 I7.artifactDigest（實際 {sorted(got)}）")

    print("\n[B6(d)] mutation inventory 與 §9.3.6 的 I1–I7 雙向對帳")
    covered = set()
    for _, mutate, expected in MUTATIONS:
        covered |= expected
    covered |= {"I1", "I2", "I7.datasetVersion", "I7.artifactDigest"}  # 上面三段涵蓋
    for spec_id, subs in sorted(SPEC_INVARIANTS.items()):
        miss = [x for x in subs if x not in covered]
        check(not miss, f"§9.3.6 {spec_id} 的每個違反形狀都有反例"
              + ("" if not miss else f"（缺 {miss}）"))
    unknown = covered - set(I)
    check(not unknown, f"每個反例都對應到某條不變量{'' if not unknown else f'（多出 {unknown}）'}")

    print(f"\n{'='*60}")
    if failures:
        print(f"FAIL：{len(failures)} 項不符")
        for f in failures:
            print(f"  - {f.splitlines()[0]}")
        return 1
    print("全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
