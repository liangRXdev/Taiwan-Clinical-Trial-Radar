"""產出**最小 artifact 樣本**，實證 §9.3.2 的 `datasetVersion`／`artifactDigest` 可實作且無循環。

對應驗收 **B8**，並附帶示範 §9.3.5 各檔 schema 與 §9.3.6 的部分不變量。

---

**這不是 ETL 實作。** 本檔**沒有** identity 收斂、cohort 判定、sentinel 分型或日期規則；
兩個 Trial 的內容是**手寫**的（取自 a_core fixture 的 WS-003 與 PH-004 兩列組），
只有三樣東西是照規格算出來的，因為那正是 B8 要證明可實作的部分：

1. §6.3 canonical serialization 與 §6.3.3 的 `trialId`／`recordId`／shard key
2. §9.3.2 的 `datasetVersion`（logical payload，不含版本欄位本身）
3. §9.3.2 的 `artifactDigest`（最終檔案位元組）

**M1 不得直接沿用本檔的函式當實作。** 規格要能被兩份獨立的程式碼各自寫出來才算寫清楚；
本檔存在的意義是「照 v0.5 的文字能不能做出一份合規 artifact」，不是提供答案。

跑法：`python tests/fixtures/artifact_sample/build_sample.py`（輸出到 `out/`）
"""
import gzip
import hashlib
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS_JSON = os.path.join(HERE, os.pardir, "a_core", "rows.json")
OUT = os.path.join(HERE, "out")

US = "\x1f"  # U+001F，§6.3 的欄位分隔符與長度前綴分隔符

BUILD_DATE = "2026-09-18"          # §6.5.1 可注入
FETCHED_AT = "2026-09-18T01:00:00Z"
BUILT_AT = "2026-09-18T01:02:03Z"
SOURCE_SHA256 = "0" * 64           # 樣本用固定值；真實管線填來源 ZIP 的 sha256

COLUMNS = [
    "臨床試驗申請者", "臨床試驗計畫書編號", "臨床試驗計畫中文名稱", "臨床試驗期別",
    "本臨床試驗規模", "試驗目的", "試驗預計執行期間起", "試驗預計執行期間迄",
    "全球預計受試者人數", "台灣預計受試者人數", "適應症中文", "主要評估指標",
    "納入條件", "排除條件", "TFDA收文號", "資料更新時間",
]

SHORT_FIELDS = ["臨床試驗計畫書編號", "臨床試驗計畫中文名稱", "臨床試驗申請者",
                "適應症中文", "TFDA收文號"]
LONG_FIELDS = ["試驗目的", "主要評估指標"]

# 本樣本收錄的兩個 Trial（手寫選定），以及各自的 rowKey → 這是全部的「模型決策」
SAMPLE = {
    "WS-003": {
        "rowKeys": ["ws003-a", "ws003-b"],
        "latestSourceDate": "2026-04-01",
        "latestCohortRowKeys": ["ws003-a", "ws003-b"],
        "latestAmbiguous": False,
        "conflictFields": [],
        # §6.4.3：比較鍵相同但 distinct raw > 1 的欄位
        "rawVariantFields": ["臨床試驗計畫中文名稱", "納入條件"],
        "_why": "rawVariants 的代表值規則（recordId 字典序最小者）必須真的算得出來",
    },
    "PH-004": {
        "rowKeys": ["ph004-a", "ph004-b"],
        "latestSourceDate": "2026-05-01",
        "latestCohortRowKeys": ["ph004-a", "ph004-b"],
        "latestAmbiguous": True,
        "conflictFields": ["臨床試驗期別"],
        "rawVariantFields": [],
        "_why": "衝突欄位須在 displayFields 中**完全省略**（§6.4.5），樣本要證明 schema 容得下這個形狀",
    },
}


# ---------- §6.0 / §8.1 正規化 ----------

def search_normalize(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", (s or "").strip()).casefold())


# ---------- §6.3 canonical serialization 與 ID ----------

def canonical_serialization(row):
    """§6.3：逐欄 `<UTF-8 位元組長度>` + US + `<欄位位元組>`，欄位之間再以 US 分隔。"""
    parts = []
    for col in COLUMNS:
        v = row[col]
        if US in v:
            raise ValueError("SOURCE_CONTROL_CHAR")  # §6.3 的硬性檢查
        parts.append(f"{len(v.encode('utf-8'))}{US}{v}")
    return US.join(parts).encode("utf-8")


def sha256hex(b):
    return hashlib.sha256(b).hexdigest()


def trial_id(identity_key):
    return "t" + sha256hex(identity_key.encode("utf-8"))[:16]


def record_id(tid, canonical, k):
    return f"{tid}r{sha256hex(canonical)[:16]}#{k}"


# ---------- §9.3.2 ----------

def canonical_json_bytes(obj):
    """鍵依字典序、無多餘空白、UTF-8、不轉義非 ASCII。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def dataset_version(logical_payloads):
    """§9.3.2：logical payload（已移除 top-level datasetVersion）的 digest。

    串接的是 **hex 字串** 並納入**邏輯檔名**（不含 <h>），故兩個檔案內容互換時會改變。
    """
    lines = [f"{name}:{sha256hex(canonical_json_bytes(payload))}"
             for name, payload in sorted(logical_payloads.items())]
    return sha256hex("\n".join(lines).encode("utf-8"))[:16]


def artifact_digest(published):
    """§9.3.2：對**最終檔案位元組**計算，依實際發布路徑排序，**不含 manifest.json**。"""
    lines = [f"{path}:{sha256hex(data)}" for path, data in sorted(published.items())]
    return sha256hex("\n".join(lines).encode("utf-8"))


# ---------- 手寫的 typed 值（§9.3.3）----------

def typed_and_flags(field, raw):
    """只涵蓋本樣本用得到的情形。完整規則是 §6.6，由 M1 實作。"""
    if field in ("試驗預計執行期間起", "試驗預計執行期間迄"):
        m = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", raw)
        return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}", []) if m else (None, [])
    if field in ("全球預計受試者人數", "台灣預計受試者人數"):
        if re.fullmatch(r"\d+", raw):
            n = int(raw)
            return n, (["sourceZero"] if n == 0 else [])
        return None, ["numericUnparsed"]
    return (raw if raw != "" else None), []


def build(rows, overrides=None, swap=None):
    """回傳 (logical_payloads, published_bytes, manifest)。

    overrides: {rowKey: {欄位: 新值}}，供 B8 的敏感度測試改一個字元。
    swap: (邏輯檔名A, 邏輯檔名B)，供 B8 證明邏輯檔名已納入 datasetVersion。
    """
    rows = {k: dict(v) for k, v in rows.items()}
    for rk, patch in (overrides or {}).items():
        rows[rk].update(patch)

    trials, shard_map, search_records = [], {}, []

    for protocol, spec in SAMPLE.items():
        ident = "P:" + unicodedata.normalize("NFKC", protocol.strip()).upper()
        tid = trial_id(ident)
        shard = tid[1:3]

        # recordId：§6.3.2 的 ordinal 一律從 #0 起，依 canonical serialization 排序配置
        by_canon = {}
        for rk in spec["rowKeys"]:
            by_canon.setdefault(canonical_serialization(rows[rk]), []).append(rk)
        rid_of = {}
        for canon in sorted(by_canon):
            for k, rk in enumerate(by_canon[canon]):
                rid_of[rk] = record_id(tid, canon, k)

        cohort_rids = sorted(rid_of[rk] for rk in spec["latestCohortRowKeys"])
        # §9.3.6：recordIds 依（可採計日期降序、不可採計者置末、recordId 昇序）
        all_rids = sorted(rid_of.values())

        display = {}
        for field in COLUMNS:
            if field in ("臨床試驗計畫書編號", "TFDA收文號", "資料更新時間"):
                continue
            if field in spec["conflictFields"]:
                continue  # §6.4.5：衝突欄位完全省略
            # 代表值：latestCohort 中 recordId 字典序最小者的 raw
            rep_rk = min(spec["latestCohortRowKeys"], key=lambda rk: rid_of[rk])
            raw = rows[rep_rk][field]
            typed, flags = typed_and_flags(field, raw)
            if field in spec["rawVariantFields"]:
                flags = flags + ["rawVariants"]
            display[field] = {"raw": raw, "typed": typed, "flags": flags}

        trials.append({
            "id": tid,
            "protocolRaw": sorted({rows[rk]["臨床試驗計畫書編號"] for rk in spec["rowKeys"]}),
            "protocolNonIdentifier": False,
            "suspectedTestRow": False,
            "nearDuplicateGroup": None,
            "latestSourceDate": spec["latestSourceDate"],
            "dateUnknown": False,
            "latestCohortCount": len(cohort_rids),
            "recordCount": len(all_rids),
            "latestAmbiguous": spec["latestAmbiguous"],
            "conflictFields": spec["conflictFields"],
            "displayFields": display,
            "searchShortLatest": [
                {"r": rid_of[rk], "f": [search_normalize(rows[rk][f]) for f in SHORT_FIELDS]}
                for rk in sorted(spec["latestCohortRowKeys"], key=lambda rk: rid_of[rk])
            ],
            "shard": shard,
        })

        s = shard_map.setdefault(shard, {"trials": {}, "records": {}})
        s["trials"][tid] = {"latestCohort": cohort_rids, "recordIds": all_rids}
        for rk in spec["rowKeys"]:
            raw_obj = {c: rows[rk][c] for c in COLUMNS}
            typed_obj, field_flags = {}, {}
            for c in COLUMNS:
                t, fl = typed_and_flags(c, rows[rk][c])
                typed_obj[c] = t
                if fl:
                    field_flags[c] = fl
            s["records"][rid_of[rk]] = {
                "raw": raw_obj, "typed": typed_obj,
                "fieldFlags": field_flags, "recordFlags": [],
            }
            search_records.append({
                "r": rid_of[rk], "t": tid,
                "d": spec["latestSourceDate"] if rk in spec["latestCohortRowKeys"] else None,
                "row": rows[rk],
                "latest": rk in spec["latestCohortRowKeys"],
            })

    trials.sort(key=lambda t: t["id"])

    def search_file(fields, latest_only):
        return {
            "fields": fields,
            "records": [
                {"r": r["r"], "t": r["t"], "d": r["d"],
                 "f": [search_normalize(r["row"][f]) for f in fields]}
                for r in sorted(search_records, key=lambda r: r["r"])
                if (r["latest"] or not latest_only)
            ],
        }

    # ---- logical payloads（**不含** datasetVersion 欄位本身）----
    logical = {
        "trials-index.json": {"trials": trials},
        "stats.json": {
            "denominators": {"trials": len(trials), "records": len(search_records)},
            "facets": {
                "phase": {"denominatorKind": "trials",
                          "buckets": [{"value": "Phase Ⅲ", "count": 1}],
                          "unprovided": 0, "conflicted": 1},
                "scale": {"denominatorKind": "trials",
                          "buckets": [{"value": "多國多中心", "count": 2}],
                          "unprovided": 0, "conflicted": 0},
                "applicant": {"denominatorKind": "trials",
                              "buckets": [{"value": "測試乙生技股份有限公司", "count": 1},
                                          {"value": "測試甲藥廠股份有限公司", "count": 1}],
                              "unprovided": 0, "conflicted": 0},
            },
        },
        "search-short-all.json": search_file(SHORT_FIELDS, latest_only=False),
        "search-long-latest.json": search_file(LONG_FIELDS, latest_only=True),
        "search-long-all.json": search_file(LONG_FIELDS, latest_only=False),
    }
    for shard, payload in shard_map.items():
        logical[f"records/{shard}.json"] = payload

    if swap:
        a, b = swap
        logical[a], logical[b] = logical[b], logical[a]

    dv = dataset_version(logical)

    # ---- 最終檔案位元組：把 datasetVersion 寫回去 ----
    published, file_meta = {}, {}
    for name, payload in logical.items():
        h = sha256hex(canonical_json_bytes(payload))[:16]
        stem, ext = name.rsplit(".", 1)
        path = f"{stem}.{h}.{ext}"
        final = dict(payload)
        final["datasetVersion"] = dv
        data = canonical_json_bytes(final)
        published[path] = data
        file_meta[name] = {"path": path, "bytes": len(data),
                           "gzipBytes": len(gzip.compress(data, mtime=0))}

    manifest = {
        "schemaVersion": 1,
        "datasetVersion": dv,
        "artifactDigest": artifact_digest(published),
        "sourceDatasetId": 205,
        "sourceUpdatedAt": max(t["latestSourceDate"] for t in trials),
        "fetchedAt": FETCHED_AT,
        "builtAt": BUILT_AT,
        "buildDate": BUILD_DATE,
        "sourceSha256": SOURCE_SHA256,
        "trialCount": len(trials),
        "recordCount": len(search_records),
        "bootstrap": False,
        "files": {
            "trialsIndex": file_meta["trials-index.json"],
            "stats": file_meta["stats.json"],
            "searchShortAll": file_meta["search-short-all.json"],
            "searchLongLatest": file_meta["search-long-latest.json"],
            "searchLongAll": file_meta["search-long-all.json"],
            "recordShards": {s: file_meta[f"records/{s}.json"] for s in sorted(shard_map)},
        },
    }
    return logical, published, manifest


def load_rows():
    return json.load(open(ROWS_JSON, encoding="utf-8"))["rows"]


def main():
    rows = load_rows()
    logical, published, manifest = build(rows)

    for rel in list(published) + ["manifest.json"]:
        p = os.path.join(OUT, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
    for rel, data in published.items():
        with open(os.path.join(OUT, rel.replace("/", os.sep)), "wb") as f:
            f.write(data)
    with open(os.path.join(OUT, "manifest.json"), "wb") as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))

    print(f"datasetVersion  {manifest['datasetVersion']}")
    print(f"artifactDigest  {manifest['artifactDigest']}")
    print(f"檔案 {len(published)} 個（不含 manifest.json）：")
    for path in sorted(published):
        print(f"  {path}  {len(published[path])} bytes")


if __name__ == "__main__":
    main()
