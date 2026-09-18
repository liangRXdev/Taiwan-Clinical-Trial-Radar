"""驗收 B8：`datasetVersion` 的可計算性與敏感性，以及 `artifactDigest` 的獨立性。

B8 的四條（§11）：
1. 同一輸入兩次 build 得到相同 `datasetVersion`（**證明無循環定義**）
2. 任一欄位值改變一個字元 → `datasetVersion` 改變
3. 兩個檔案內容互換 → `datasetVersion` 改變（證明邏輯檔名已納入）
4. `artifactDigest` 與 `datasetVersion` 為不同值且各自依 §9.3.2 可重算

另加 §9.3.6 的部分不變量與 §9.2.2／B7 的檔名規則抽查——樣本既然產出來了，順手證明
這些不變量對一份真的 artifact 是可檢查的（而不是只寫在規格裡）。

跑法：`python tests/fixtures/artifact_sample/check_b8.py`
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sample import (  # noqa: E402
    artifact_digest, build, canonical_json_bytes, dataset_version, load_rows, sha256hex,
)

failures = []


def check(cond, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        failures.append(msg)


def main():
    rows = load_rows()

    print("\n[B8-1] 兩次 build 相同 → datasetVersion 相同（無循環定義）")
    l1, p1, m1 = build(rows)
    l2, p2, m2 = build(rows)
    check(m1["datasetVersion"] == m2["datasetVersion"],
          f"datasetVersion 一致：{m1['datasetVersion']}")
    check(p1 == p2, "兩次 build 的全部檔案位元組逐一相同")
    check(m1["artifactDigest"] == m2["artifactDigest"], "artifactDigest 一致")

    print("\n[B8-1b] 固定點：從**已寫入版本欄位的最終檔案**反算 datasetVersion 須得同值")
    recomputed = {}
    for path, data in p1.items():
        obj = json.loads(data.decode("utf-8"))
        check(obj.pop("datasetVersion", None) == m1["datasetVersion"],
              f"{path} 內含正確的 datasetVersion（§9.2.2 跨檔綁定）")
        # 由發布路徑還原邏輯檔名：去掉中間的 <h>
        stem, h, ext = path.rsplit(".", 2)
        recomputed[f"{stem}.{ext}"] = obj
        check(re.fullmatch(r"[0-9a-f]{16}", h) is not None,
              f"{path} 的檔名帶 16 hex 內容雜湊（B7）")
    check(dataset_version(recomputed) == m1["datasetVersion"],
          "由最終檔案移除 datasetVersion 後重算，得到同一個 datasetVersion"
          "——這就是循環定義被解開的證據")

    print("\n[B8-2] 改一個字元 → datasetVersion 改變")
    # ws003-a 的台灣預計受試者人數 "10" → "11"
    mutated = build(rows, overrides={"ws003-a": {"台灣預計受試者人數": "11"}})[2]
    check(mutated["datasetVersion"] != m1["datasetVersion"],
          f"單一欄位改一字元後 datasetVersion 由 {m1['datasetVersion']} 變為 "
          f"{mutated['datasetVersion']}")
    # 改到不入 displayFields 的欄位（收文號）也必須改變——它仍在 shard 的 raw 裡
    mutated2 = build(rows, overrides={"ws003-b": {"TFDA收文號": "1130003X"}})[2]
    check(mutated2["datasetVersion"] != m1["datasetVersion"],
          "改動不入卡片的欄位（TFDA收文號）同樣改變 datasetVersion")

    print("\n[B8-3] 兩個檔案內容互換 → datasetVersion 改變（邏輯檔名已納入）")
    swapped = build(rows, swap=("stats.json", "search-short-all.json"))[2]
    check(swapped["datasetVersion"] != m1["datasetVersion"],
          "stats.json 與 search-short-all.json 內容互換後 datasetVersion 改變")
    # 反向哨兵：若 §9.3.2 步驟 3 漏掉邏輯檔名，互換後的 digest 會與原本相同
    payload_hashes = sorted(sha256hex(canonical_json_bytes(p)) for p in l1.values())
    swapped_logical = build(rows, swap=("stats.json", "search-short-all.json"))[0]
    swapped_hashes = sorted(sha256hex(canonical_json_bytes(p)) for p in swapped_logical.values())
    check(payload_hashes == swapped_hashes,
          "互換前後的 payload hash **多重集合相同**——故本條若通過，必然是靠邏輯檔名而非內容差異")

    print("\n[B8-4] artifactDigest 與 datasetVersion 各自可重算且不同")
    check(m1["artifactDigest"] != m1["datasetVersion"], "兩者為不同值")
    check(len(m1["datasetVersion"]) == 16 and len(m1["artifactDigest"]) == 64,
          "長度分別為 16 hex 與 64 hex（§9.3.2 封存）")
    check(artifact_digest(p1) == m1["artifactDigest"],
          "artifactDigest 由最終檔案位元組可重算")
    check("manifest.json" not in p1,
          "artifactDigest 的輸入不含 manifest.json（否則又是循環）")

    print("\n[§9.3.6] 不變量抽查")
    index = json.loads(p1[m1["files"]["trialsIndex"]["path"]].decode("utf-8"))
    shards = {s: json.loads(p1[meta["path"]].decode("utf-8"))
              for s, meta in m1["files"]["recordShards"].items()}

    check([t["id"] for t in index["trials"]] == sorted(t["id"] for t in index["trials"]),
          "trials 依 trialId 昇序")

    owner = {}
    ok_counts, ok_shard, ok_subset = True, True, True
    for t in index["trials"]:
        sh = shards[t["shard"]]["trials"][t["id"]]
        ok_counts &= (t["recordCount"] == len(sh["recordIds"])
                      and t["latestCohortCount"] == len(sh["latestCohort"]))
        ok_subset &= set(sh["latestCohort"]) <= set(sh["recordIds"])
        for rid in sh["recordIds"]:
            ok_shard &= rid in shards[t["shard"]]["records"]
            owner.setdefault(rid, []).append(t["id"])
    check(ok_counts, "recordCount／latestCohortCount 等於 shard 內對應清單長度（方案 B 防漂移）")
    check(ok_subset, "latestCohort ⊆ recordIds")
    check(ok_shard, "每個 recordId 存在於 trial.shard 指定的 shard")
    check(all(len(v) == 1 for v in owner.values()), "每個 record 恰好被一個 Trial 引用")
    check(all(rid.startswith(t) for rid, (t,) in
              ((rid, tuple(v)) for rid, v in owner.items())),
          "recordId 以 trialId 為前綴（shard 可自我描述）")

    declared = {m1["files"][k]["path"] for k in
                ("trialsIndex", "stats", "searchShortAll", "searchLongLatest", "searchLongAll")}
    declared |= {v["path"] for v in m1["files"]["recordShards"].values()}
    check(declared == set(p1), "manifest.files 的路徑集合 == 除 manifest.json 外的全部檔案")

    stats = json.loads(p1[m1["files"]["stats"]["path"]].decode("utf-8"))
    for name, facet in stats["facets"].items():
        total = sum(b["count"] for b in facet["buckets"]) + facet["unprovided"] + facet["conflicted"]
        check(total == stats["denominators"]["trials"],
              f"facet {name} 的 buckets+unprovided+conflicted == denominators.trials")

    print("\n[§6.4.5／§6.4.3] 衝突欄位省略與 rawVariants 的層級")
    by_protocol = {t["protocolRaw"][0]: t for t in index["trials"]}
    conflicting = [t for t in index["trials"] if t["conflictFields"]]
    check(len(conflicting) == 2, f"樣本含 2 個有衝突的 Trial（實際 {len(conflicting)}）")
    for t in conflicting:
        check(all(f not in t["displayFields"] for f in t["conflictFields"]),
              f"{t['protocolRaw'][0]} 的衝突欄位 {t['conflictFields']} 不在 displayFields 中"
              f"（不是 {{typed:null}}）")

    ws = by_protocol["WS-003"]
    for field in ("臨床試驗計畫中文名稱", "納入條件"):
        check("rawVariants" in ws["displayFields"][field]["flags"],
              f"WS-003 的 {field} 帶 rawVariants，且落在**該欄位的 flags**（§6.4.3 欄位層級）")
    check(not any(k.lower().startswith("rawvariant") for k in ws),
          "Trial 層級不存在等義的 rawVariants 旗標（兩種表示並存會分歧）")
    # 反向哨兵：沒有 raw 差異的 Trial 不得被標上 rawVariants
    nr = by_protocol["NR-028"]
    check(not any("rawVariants" in v["flags"] for v in nr["displayFields"].values()),
          "NR-028（單筆 record，無 raw 變體）沒有任何欄位帶 rawVariants")

    print("\n[§6.6] 樣本涵蓋的數值語意狀態")
    ind = by_protocol["IND-005"]
    check(ind["displayFields"]["全球預計受試者人數"]["typed"] is None
          and "numericMissing" in ind["displayFields"]["全球預計受試者人數"]["flags"],
          "IND-005 的空數值為 numericMissing 且 typed 為 null")
    check(nr["displayFields"]["台灣預計受試者人數"]["typed"] is None
          and nr["displayFields"]["台灣預計受試者人數"]["raw"] == "約400",
          "NR-028 的 約400 typed 為 null 且 raw 原文保留（不得推論為 400）")

    print(f"\n{'='*60}")
    if failures:
        print(f"FAIL：{len(failures)} 項不符")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
