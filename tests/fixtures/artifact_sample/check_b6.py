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

# §9.3.6 的不變量編號（本檔自訂，供反例對位）
I = {
    "I1": "trials 依 trialId 昇序",
    "I2": "recordIds 依（可採計日期降序、不可採計者置末、recordId 昇序）",
    "I3": "latestCohort 依 recordId 昇序",
    "I4": "每個 recordId 存在於 trial.shard 指定的 shard",
    "I5": "每個 record 恰好被一個 Trial 引用一次",
    "I6": "latestCohort ⊆ recordIds",
    "I7": "trial.recordCount == shard 內 recordIds 長度",
    "I8": "trial.latestCohortCount == latestCohort 長度",
    "I9": "manifest.files 路徑集合 == 除 manifest.json 外的全部檔案",
    "I10": "datasetVersion 可由 logical payload 重算，且每個檔案內含同值",
    "I11": "artifactDigest 可由 manifest.files 的最終位元組重算",
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
        bad.add("I9")

    missing = declared - set(on_disk)
    readable = {p: on_disk[p] for p in declared if p in on_disk}

    # I10：由最終檔案移除 top-level datasetVersion 後重算
    logical, embedded_ok = {}, True
    for path, data in readable.items():
        obj = json.loads(data.decode("utf-8"))
        if obj.pop("datasetVersion", None) != manifest["datasetVersion"]:
            embedded_ok = False
        logical[logical_name(path)] = obj
    if missing:
        # 宣告的檔案不在磁碟上時 I10／I11 無從重算——記為 I9 已足夠，不假裝驗過
        pass
    elif not embedded_ok or dataset_version(logical) != manifest["datasetVersion"]:
        bad.add("I10")

    if not missing and artifact_digest(readable) != manifest["artifactDigest"]:
        bad.add("I11")

    index_path = manifest["files"]["trialsIndex"]["path"]
    if index_path not in readable:
        return bad
    trials = json.loads(readable[index_path].decode("utf-8"))["trials"]
    shards = {s: json.loads(readable[m["path"]].decode("utf-8"))
              for s, m in manifest["files"]["recordShards"].items()
              if m["path"] in readable}

    if [t["id"] for t in trials] != sorted(t["id"] for t in trials):
        bad.add("I1")

    owners = {}
    for t in trials:
        shard = shards.get(t["shard"])
        if shard is None or t["id"] not in shard["trials"]:
            bad.add("I4")
            continue
        entry = shard["trials"][t["id"]]
        rids, cohort = entry["recordIds"], entry["latestCohort"]

        def sort_key(rid):
            rec = shard["records"].get(rid)
            d = (rec or {}).get("typed", {}).get("資料更新時間")
            # 可採計日期降序、不可採計者置末 → 以 (無日期?, 反轉日期, rid) 排序
            return (d is None, "" if d is None else "".join(chr(0x10FFFD - ord(c)) for c in d), rid)

        # **I4 必須先於 I2 評估。** I2 的排序鍵取自該 record 的 `資料更新時間`，
        # 而那筆資料在 shard 裡；record 放錯 shard 時排序鍵根本取不到，
        # 硬算會把「查不到日期」當成「不可採計日期→置末」而誤報 I2。
        # §9.3.6 是一串平鋪的 bullet，沒有寫評估順序——見 fixture-findings-m05.md GAP-11。
        resolvable = all(rid in shard["records"] for rid in rids)
        if not resolvable:
            bad.add("I4")
        elif rids != sorted(rids, key=sort_key):
            bad.add("I2")
        if cohort != sorted(cohort):
            bad.add("I3")
        if not set(cohort) <= set(rids):
            bad.add("I6")
        if t["recordCount"] != len(rids):
            bad.add("I7")
        if t["latestCohortCount"] != len(cohort):
            bad.add("I8")
        for rid in rids:
            owners[rid] = owners.get(rid, 0) + 1

    if any(n != 1 for n in owners.values()):
        bad.add("I5")

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


MUTATIONS = [
    ("record 被兩個 Trial 引用（同 shard，故可隔離）", m_dup_owner_cross_trial, {"I5"}),
    ("同一 Trial 重複引用同一筆 record", m_dup_within_trial, {"I5"}),
    ("record 放錯 shard", m_wrong_shard, {"I4"}),
    ("latestCohort ⊄ recordIds", m_cohort_not_subset, {"I6"}),
    ("recordCount 與 shard 清單長度不符", m_recordcount_mismatch, {"I7"}),
    ("latestCohortCount 與 latestCohort 長度不符", m_cohortcount_mismatch, {"I8"}),
    ("trials 未依 trialId 昇序", m_trials_unsorted, {"I1"}),
    ("recordIds 未依規定排序", m_recordids_unsorted, {"I2"}),
    ("latestCohort 未依 recordId 昇序", m_cohort_unsorted, {"I3"}),
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
        check("I10" not in got and "I11" not in got,
              f"  └ 該反例的 digest 自洽（I10／I11 未觸發），證明測到的是不變量本身")

    print("\n[B6] inventory 的兩種失敗形狀（§9.3.6 的 inventory 不變量）")
    orphan = dict(published)
    orphan["records/zz.deadbeefdeadbeef.json"] = b'{"datasetVersion":"x","trials":{},"records":{}}'
    got = validate(orphan, manifest)
    check(got == {"I9"}, f"磁碟上有 manifest 未列出的孤兒檔 → ['I9']（實際 {sorted(got)}）")
    check(artifact_digest({p: d for p, d in orphan.items()
                           if p != "records/zz.deadbeefdeadbeef.json"})
          == manifest["artifactDigest"],
          "  └ 孤兒檔**不會**改變 artifactDigest（§9.3.2 只走 manifest.files 的路徑）"
          "——故 inventory 不變量無可取代")

    dropped = {p: d for p, d in published.items()
               if p != manifest["files"]["stats"]["path"]}
    got = validate(dropped, manifest)
    check(got == {"I9"}, f"manifest 列出但檔案不存在 → ['I9']（實際 {sorted(got)}）")

    print("\n[B7] 跨版本綁定：某個 shard 帶舊的 datasetVersion")
    stale = dict(published)
    shard_path = next(iter(manifest["files"]["recordShards"].values()))["path"]
    obj = json.loads(stale[shard_path].decode("utf-8"))
    obj["datasetVersion"] = "0" * 16
    stale[shard_path] = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False).encode("utf-8")
    got = validate(stale, manifest)
    check(got == {"I10", "I11"},
          f"shard 的 datasetVersion 與 manifest 不符 → ['I10', 'I11']（實際 {sorted(got)}）")
    check("I10" in got,
          "  └ 前端據此 fail-closed 顯示「資料版本不一致，請重新載入」，不得混用渲染")

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
