"""§9.3.6 不變量驗證器。違反一律硬失敗 `INTEGRITY_DIGEST`。

**每條只宣告自己的必要前置條件，不設全域順序。** 前置條件不成立時回報「**無法評估**」
而非「違規」——對外行為不變（仍 fail-closed），變的是 report 的歸因。

為什麼需要前置條件：`recordIds` 的排序鍵取自該 record 的 `資料更新時間`，而那筆資料在
shard 裡。record 放錯 shard 時排序鍵**取不到**，硬算會把「查不到」當成「不可採計日期→置末」
而同時誤報排序違規——B6 要求的「各自獨立反例」就寫不出來。

但前置條件是**逐條**的：stats 一致性不依賴 record 歸屬，digest 在檔案可讀時不依賴 stats。
全域流水號會讓一個 shard 錯誤遮蔽同時存在的 stats 或 digest 錯誤。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as _dc_field

from .artifacts import (
    FACETS,
    TOP_LEVEL_FILE_KEYS,
    artifact_digest,
    brotli_size,
    canonical_json_bytes,
    dataset_version,
    manifest_paths,
)
from .errors import ErrorCode, PipelineError

# 子編號用於區分同一條不變量的不同違反形狀。
# **兩條不同的不變量不可共用編號**——共用時「各自獨立反例」會有一條永遠驗不到。
INVARIANTS: dict[str, str] = {
    "I1": "inventory：manifest.files 路徑集合 == 除 manifest.json 外的全部檔案",
    "I2": "跨檔版本綁定：每個非 manifest 檔案的 datasetVersion == manifest 的值",
    "I3.shard": "每個 recordId 存在於 trial.shard 指定的 shard",
    "I3.owner": "每個 record 恰好被一個 Trial 引用一次",
    "I3.orphan": "shard 內不得有零 Trial 引用的 record",
    "I3.subset": "latestCohort ⊆ recordIds",
    "I4.records": "trial.recordCount == shard 內 recordIds 長度",
    "I4.cohort": "trial.latestCohortCount == latestCohort 長度",
    "I5.trials": "trials 依 trialId 昇序",
    "I5.records": "recordIds 依（可採計日期降序、不可採計者置末、recordId 昇序）",
    "I5.cohort": "latestCohort 依 recordId 昇序",
    "I6": "stats 的 facet bucket 計數 == 依 trials-index 重算的結果",
    "I7.datasetVersion": "datasetVersion 可由 logical payload 重算",
    "I7.artifactDigest": "artifactDigest 可由 manifest.files 的最終位元組重算",
    "I8.bytes": "每個 files 條目的 bytes == 該檔實際位元組長度",
    "I8.gzipBytes": "每個 files 條目的 gzipBytes == 對該位元組的 gzip 長度",
    "I8.brotliBytes": "五個具名 top-level 條目的 brotliBytes == 對該位元組的 brotli q11 長度",
    "I8.shardNoBrotli": "recordShards 條目不得有 brotliBytes",
}

SPEC_INVARIANTS: dict[str, list[str]] = {
    "I1": ["I1"],
    "I2": ["I2"],
    "I3": ["I3.shard", "I3.owner", "I3.orphan", "I3.subset"],
    "I4": ["I4.records", "I4.cohort"],
    "I5": ["I5.trials", "I5.records", "I5.cohort"],
    "I6": ["I6"],
    "I7": ["I7.datasetVersion", "I7.artifactDigest"],
    "I8": ["I8.bytes", "I8.gzipBytes", "I8.brotliBytes", "I8.shardNoBrotli"],
}


@dataclass
class InvariantReport:
    violated: set[str] = _dc_field(default_factory=set)
    unevaluable: dict[str, str] = _dc_field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.violated


def _logical_name(path: str) -> str:
    stem, _h, ext = path.rsplit(".", 2)
    return f"{stem}.{ext}"


# §6.5.2 的不可採計旗標。**有 typed 日期 ≠ 可採計**——dateFuture 的 typed 是一個合法
# ISO 日期，卻必須置末；只看 typed 的驗證器會與 §9.3.6 的排序規則不一致。
_UNUSABLE_DATE_FLAGS = frozenset({"dateMissing", "dateUnparsed", "dateFuture"})


def _sort_key(rid: str, records: dict) -> tuple:
    rec = records.get(rid, {})
    flags = set(rec.get("fieldFlags", {}).get("資料更新時間", []))
    d = rec.get("typed", {}).get("資料更新時間")
    if flags & _UNUSABLE_DATE_FLAGS:
        d = None
    # 可採計日期降序、不可採計者置末
    return (d is None, "" if d is None else "".join(chr(0x10FFFD - ord(c)) for c in d), rid)


def check_invariants(on_disk: dict[str, bytes], manifest: dict) -> InvariantReport:
    """`on_disk` 是 `public/data/` 中除 `manifest.json` 外的全部檔案（路徑 → 位元組）。"""
    rep = InvariantReport()
    declared = manifest_paths(manifest)

    # I1 inventory：無前置條件
    if declared != set(on_disk):
        rep.violated.add("I1")

    missing = declared - set(on_disk)
    readable = {p: on_disk[p] for p in declared if p in on_disk}

    parsed: dict[str, dict] = {}
    unparsable: list[str] = []
    for path, data in readable.items():
        try:
            parsed[path] = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            unparsable.append(path)

    # I2 跨檔版本綁定：前置＝該檔可讀且為合法 JSON
    if unparsable or missing:
        rep.unevaluable["I2"] = f"檔案缺席或無法解析：{sorted(missing) + sorted(unparsable)}"
    else:
        if any(o.get("datasetVersion") != manifest["datasetVersion"] for o in parsed.values()):
            rep.violated.add("I2")

    # I7：前置＝manifest.files 列出的檔案全部可讀
    if missing or unparsable:
        rep.unevaluable["I7.datasetVersion"] = "manifest 列出的檔案並非全部可讀"
        rep.unevaluable["I7.artifactDigest"] = "manifest 列出的檔案並非全部可讀"
    else:
        logical = {}
        for path, obj in parsed.items():
            payload = {k: v for k, v in obj.items() if k != "datasetVersion"}
            logical[_logical_name(path)] = payload
        if dataset_version(logical) != manifest["datasetVersion"]:
            rep.violated.add("I7.datasetVersion")
        if artifact_digest(readable) != manifest["artifactDigest"]:
            rep.violated.add("I7.artifactDigest")

    index_path = manifest["files"]["trialsIndex"]["path"]
    if index_path not in parsed:
        for key in ("I3.shard", "I3.owner", "I3.orphan", "I3.subset",
                    "I4.records", "I4.cohort", "I5.trials", "I5.records", "I5.cohort", "I6"):
            rep.unevaluable[key] = "trials-index 不可讀"
        return rep

    trials = parsed[index_path]["trials"]
    shards = {
        s: parsed[m["path"]]
        for s, m in manifest["files"]["recordShards"].items()
        if m["path"] in parsed
    }

    # I5.trials：無前置（只看 index 自己）
    if [t["id"] for t in trials] != sorted(t["id"] for t in trials):
        rep.violated.add("I5.trials")

    owners: dict[str, int] = {}
    for t in trials:
        shard = shards.get(t["shard"])
        if shard is None or t["id"] not in shard.get("trials", {}):
            rep.violated.add("I3.shard")
            continue
        entry = shard["trials"][t["id"]]
        rids, cohort = entry["recordIds"], entry["latestCohort"]

        resolvable = all(rid in shard["records"] for rid in rids)
        if not resolvable:
            rep.violated.add("I3.shard")
            # I5.records 的排序鍵取不到 → 對這個 Trial 無法評估，**不報違規**
            rep.unevaluable.setdefault("I5.records", f"{t['id']} 的 record 不在指定 shard")
        elif rids != sorted(rids, key=lambda r: _sort_key(r, shard["records"])):
            rep.violated.add("I5.records")

        if cohort != sorted(cohort):
            rep.violated.add("I5.cohort")
        if not set(cohort) <= set(rids):
            rep.violated.add("I3.subset")
        if t["recordCount"] != len(rids):
            rep.violated.add("I4.records")
        if t["latestCohortCount"] != len(cohort):
            rep.violated.add("I4.cohort")
        for rid in rids:
            owners[rid] = owners.get(rid, 0) + 1

    # I3.orphan：shard 內存在但沒有任何 Trial 引用的 record。
    # 只數「已被引用者的 owner count」會漏掉這一類。
    for shard in shards.values():
        if any(rid not in owners for rid in shard.get("records", {})):
            rep.violated.add("I3.orphan")
    if any(n != 1 for n in owners.values()):
        rep.violated.add("I3.owner")

    # I6 stats 一致性：前置只有「index 與 stats 皆可讀」，**不依賴 I3／I4／I5**
    stats_path = manifest["files"]["stats"]["path"]
    if stats_path not in parsed:
        rep.unevaluable["I6"] = "stats.json 不可讀"
    else:
        stats = parsed[stats_path]
        for name, field in FACETS.items():
            facet = stats["facets"].get(name)
            if facet is None:
                rep.violated.add("I6")
                continue
            buckets: dict[str, int] = {}
            unprovided = conflicted = 0
            for t in trials:
                if field in t["conflictFields"]:
                    conflicted += 1
                    continue
                value = t["displayFields"].get(field)
                if value is None or value["typed"] is None:
                    unprovided += 1
                else:
                    buckets[value["typed"]] = buckets.get(value["typed"], 0) + 1
            declared_counts = {b["value"]: b["count"] for b in facet["buckets"]}
            if (
                declared_counts != buckets
                or facet["unprovided"] != unprovided
                or facet["conflicted"] != conflicted
                or sum(declared_counts.values()) + facet["unprovided"] + facet["conflicted"]
                != stats["denominators"]["trials"]
            ):
                rep.violated.add("I6")

    _check_size_metadata(on_disk, manifest, rep)
    return rep


def _check_size_metadata(on_disk: dict[str, bytes], manifest: dict,
                        rep: InvariantReport) -> None:
    """I8：大小 metadata 可獨立重算（§9.3.6）。

    **這是唯一打斷循環自證的地方。** `datasetVersion` 與 `artifactDigest` 都**不含
    `manifest.json` 自身**（§9.3.2），所以把 `brotliBytes` 改成任意數字不會讓 I7、
    H2、H3 轉紅；而 §8.5 的 UI 與 F2 的基線都讀這個值——manifest 說多少，兩邊就都
    相信多少。前置條件因此刻意只有「該檔可讀」，不依賴 I1～I7。
    """
    import gzip

    files = manifest["files"]
    named = {k: files[k] for k in TOP_LEVEL_FILE_KEYS if k in files}

    for key, meta in named.items():
        data = on_disk.get(meta["path"])
        if data is None:
            rep.unevaluable.setdefault("I8.bytes", f"{key} 的檔案不可讀")
            continue
        if meta.get("bytes") != len(data):
            rep.violated.add("I8.bytes")
        if meta.get("gzipBytes") != len(gzip.compress(data, mtime=0)):
            rep.violated.add("I8.gzipBytes")
        if meta.get("brotliBytes") != brotli_size(data):
            rep.violated.add("I8.brotliBytes")

    for name, meta in files.get("recordShards", {}).items():
        data = on_disk.get(meta["path"])
        # **shard 不得有 brotliBytes**：多出這個欄位代表實作偷偷對 256 個 shard 跑了
        # quality 11（月更新多花數分鐘卻沒有讀者），或把某個別處的數字複製了過來。
        if "brotliBytes" in meta:
            rep.violated.add("I8.shardNoBrotli")
        if data is None:
            rep.unevaluable.setdefault("I8.bytes", f"shard {name} 不可讀")
            continue
        if meta.get("bytes") != len(data):
            rep.violated.add("I8.bytes")
        if meta.get("gzipBytes") != len(gzip.compress(data, mtime=0)):
            rep.violated.add("I8.gzipBytes")


def assert_invariants(on_disk: dict[str, bytes], manifest: dict) -> InvariantReport:
    """違反時拋 `INTEGRITY_DIGEST`；`detail` 帶違反與無法評估兩份清單。"""
    rep = check_invariants(on_disk, manifest)
    if not rep.ok:
        raise PipelineError(
            ErrorCode.INTEGRITY_DIGEST,
            f"{len(rep.violated)} 條不變量違反",
            {
                "violated": sorted(rep.violated),
                "unevaluable": dict(sorted(rep.unevaluable.items())),
            },
        )
    return rep
