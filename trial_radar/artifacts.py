"""§9.3 輸出契約：各檔 schema、`datasetVersion`／`artifactDigest`、內容雜湊檔名。

**`datasetVersion` 與 `artifactDigest` 是兩個概念**（§9.3.2）：前者由**不含版本欄位本身**的
logical payload 計算，後者待版本寫入最終檔案後對**最終位元組**計算。v0.4 曾把兩者寫成同一個
東西——檔案位元組包含 `datasetVersion` 而 `datasetVersion` 又由那些位元組導出，**無固定點，
照文字寫不出合規 artifact**。分離後可由最終檔案反算回同一個版本號，那就是循環被解開的證據。
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass

from .comparison import comparison_key  # noqa: F401  (供 stats 一致性引用者取得同一實作)
from .fields import (
    CARD_FIELDS,
    CATEGORICAL_FIELDS,
    LONG_SEARCH_FIELDS,
    PROTOCOL,
    SHORT_SEARCH_FIELDS,
)
from .identity import sha256hex
from .model import Trial
from .normalize import search_normalize

SCHEMA_VERSION = 1
SOURCE_DATASET_ID = 205

# §9.3.5：facet 名單為封閉集合，恰為三個。E2 以本清單為 facet widget 的唯一 oracle 來源。
FACETS: dict[str, str] = {
    "phase": "臨床試驗期別",
    "scale": "本臨床試驗規模",
    "applicant": "臨床試驗申請者",
}


#: §9.3.5：brotli 品質。**必須與 Cloudflare Pages 實際使用的設定一致**，否則 §8.5 顯示的
#: 下載大小會系統性偏離使用者真正付的位元組——而那個數字存在的唯一目的就是告訴使用者成本。
BROTLI_QUALITY = 11


def brotli_size(data: bytes) -> int:
    """壓縮後位元組數。

    `brotli` 不在標準庫，**缺套件時直接拋**，不退回 gzip：退回會讓 manifest 悄悄改報
    一個大 43% 的數字，而欄位名仍叫 `brotliBytes`——那比缺欄位更難發現。
    """
    import brotli

    return len(brotli.compress(data, quality=BROTLI_QUALITY))


def canonical_json_bytes(obj) -> bytes:
    """鍵依字典序、無多餘空白、UTF-8、不轉義非 ASCII（§9.3.2 步驟 1）。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def dataset_version(logical: dict[str, object]) -> str:
    """§9.3.2：logical payload（**已移除 top-level `datasetVersion`**）的 digest 前 16 hex。

    串接的是 **hex 字串**並納入**邏輯檔名**（不含 `<h>`），故兩個檔案內容互換時會改變。
    **不納入 `<h>`**——它由 payload 導出，納入會再度形成循環。
    """
    lines = [
        f"{name}:{sha256hex(canonical_json_bytes(payload))}"
        for name, payload in sorted(logical.items())
    ]
    return sha256hex("\n".join(lines).encode("utf-8"))[:16]


def artifact_digest(published: dict[str, bytes]) -> str:
    """§9.3.2：對**最終檔案位元組**計算，依實際發布路徑排序，**不含 `manifest.json` 自身**。

    輸入是 `manifest.files` 列出的路徑，**不是目錄列表**——因此磁碟上的孤兒檔不會改變本值，
    §9.3.6 的 inventory 不變量無可取代。
    """
    lines = [f"{path}:{sha256hex(data)}" for path, data in sorted(published.items())]
    return sha256hex("\n".join(lines).encode("utf-8"))


def _field_json(value) -> object:
    """FieldValue → §9.3.3 的 `{raw, typed, flags}` 三元組。"""
    return {"raw": value.raw, "typed": value.typed, "flags": list(value.flags)}


def _trial_json(t: Trial) -> dict:
    """§6.4.4 的 Trial（方案 B：`recordIds`／`latestCohort` **不**在 index 內）。"""
    return {
        "id": t.id,
        "protocolRaw": t.protocol_raw,
        "protocolNonIdentifier": t.protocol_non_identifier,
        "suspectedTestRow": t.suspected_test_row,
        "nearDuplicateGroup": t.near_duplicate_group,
        "latestSourceDate": t.latest_source_date,
        "dateUnknown": t.date_unknown,
        "latestCohortCount": len(t.latest_cohort),
        "recordCount": len(t.records),
        "latestAmbiguous": t.latest_ambiguous,
        # §6.4.4：`conflictFields` 涵蓋**全部 13 個**呈現欄位，長文字欄位也可入列——
        # 卡片仍要顯示「同日多筆資料不一致」，只是不顯示候選值。
        "conflictFields": t.conflict_fields,
        # §6.4.5／F3：**只序列化 9 個卡片欄位**。四個長文字欄位不在 Trial 層級輸出，
        # 詳情頁逐 record 從 shard 取原文。照 v0.7 把 13 欄全放時 index 是
        # 15,621 KiB gzip（F1 門檻的 10.2 倍），長文字佔 raw 位元組 92.6%。
        "displayFields": {
            k: _field_json(v) for k, v in t.display_fields.items() if k in CARD_FIELDS
        },
        "searchShortLatest": [
            {
                "r": r.rid,
                "f": [search_normalize(r.raw[f]) for f in SHORT_SEARCH_FIELDS],
            }
            # §9.3.4：**每一筆 latest-cohort record 保留獨立 recordId 與五欄陣列**，
            # 不得跨 record 合併文字——合併後兩個 term 可能分別命中不同 record，
            # 違反 §8.3 的 record 層 AND，且違反方式是靜默多報。
            for r in sorted(
                (r for r in t.records if r.rid in set(t.latest_cohort)),
                key=lambda r: r.rid,
            )
        ],
        "shard": t.shard,
    }


def _stats(trials: list[Trial], record_count: int) -> dict:
    """§9.3.5。每個 facet 的 `buckets + unprovided + conflicted` 須等於 `denominators.trials`。"""
    facets = {}
    for name, field in FACETS.items():
        buckets: dict[str, int] = {}
        unprovided = conflicted = 0
        for t in trials:
            if field in t.conflict_fields:
                conflicted += 1
                continue
            value = t.display_fields.get(field)
            if value is None or value.typed is None:
                unprovided += 1
            else:
                buckets[value.typed] = buckets.get(value.typed, 0) + 1
        facets[name] = {
            "denominatorKind": "trials",
            "buckets": [{"value": v, "count": c} for v, c in sorted(buckets.items())],
            "unprovided": unprovided,
            "conflicted": conflicted,
        }
    return {
        "denominators": {"trials": len(trials), "records": record_count},
        "facets": facets,
    }


def _search_file(trials: list[Trial], fields: tuple[str, ...], latest_only: bool) -> dict:
    records = []
    for t in trials:
        cohort = set(t.latest_cohort)
        for r in t.records:
            if latest_only and r.rid not in cohort:
                continue
            records.append(
                {
                    "r": r.rid,
                    "t": t.id,
                    # `d` 為 null 表示該 record 無可採計日期（供 §7.2 標示「資料日期不明」）
                    "d": r.sort_date.isoformat() if r.sort_date else None,
                    "f": [search_normalize(r.raw[f]) for f in fields],
                }
            )
    records.sort(key=lambda x: x["r"])
    return {"fields": list(fields), "records": records}


@dataclass
class BuildOutput:
    logical: dict[str, object]
    published: dict[str, bytes]
    manifest: dict


def build_artifacts(
    trials: list[Trial],
    *,
    build_date: str,
    fetched_at: str,
    built_at: str,
    source_sha256: str,
    bootstrap: bool = False,
    source_updated_at: str | None = None,
) -> BuildOutput:
    """產出 §9.3.1 的全部檔案。回傳 logical payload、最終位元組與 manifest。"""
    record_count = sum(len(t.records) for t in trials)

    shards: dict[str, dict] = {}
    for t in trials:
        s = shards.setdefault(t.shard, {"trials": {}, "records": {}})
        s["trials"][t.id] = {
            "latestCohort": list(t.latest_cohort),
            "recordIds": t.record_ids,
        }
        for r in t.records:
            s["records"][r.rid] = {
                "raw": dict(r.raw),
                "typed": {
                    **{k: v.typed for k, v in r.fields.items()},
                    PROTOCOL: r.raw[PROTOCOL] or None,
                    "TFDA收文號": r.raw["TFDA收文號"] or None,
                    "資料更新時間": r.updated.date.isoformat() if r.updated.date else None,
                },
                # `資料更新時間` 的旗標**必須**寫進 artifact：dateMissing／dateUnparsed／
                # dateFuture 都在 §9.3.3 的封閉集合內，而下游（§9.3.6 驗證器、§7.2 的
                # 「資料日期不明」標示）光看 typed 分不出「有日期」與「可採計」——
                # dateFuture 的 typed 是一個合法 ISO 日期，卻不得參與 latest 選擇。
                "fieldFlags": {
                    **{k: list(v.flags) for k, v in r.fields.items() if v.flags},
                    **({"資料更新時間": [r.updated.flag]} if r.updated.flag else {}),
                },
                # record-level 旗標與 field-scoped **分開，不得混在同一陣列**（§9.3.3）
                "recordFlags": list(r.record_flags),
            }

    logical: dict[str, object] = {
        "trials-index.json": {"trials": [_trial_json(t) for t in trials]},
        "stats.json": _stats(trials, record_count),
        "search-short-all.json": _search_file(trials, SHORT_SEARCH_FIELDS, False),
        "search-long-latest.json": _search_file(trials, LONG_SEARCH_FIELDS, True),
        "search-long-all.json": _search_file(trials, LONG_SEARCH_FIELDS, False),
    }
    # §9.3.1：records/ **只輸出非空 shard**（不固定產生 256 個）
    for s in sorted(shards):
        logical[f"records/{s}.json"] = shards[s]

    dv = dataset_version(logical)

    published: dict[str, bytes] = {}
    meta: dict[str, dict] = {}
    for name, payload in logical.items():
        h = sha256hex(canonical_json_bytes(payload))[:16]
        stem, ext = name.rsplit(".", 1)
        path = f"{stem}.{h}.{ext}"
        data = canonical_json_bytes({**payload, "datasetVersion": dv})
        published[path] = data
        meta[name] = {
            "path": path,
            "bytes": len(data),
            # gzipBytes 保留供 CI 對照與無 brotli 的部署環境 fallback
            "gzipBytes": len(gzip.compress(data, mtime=0)),
        }
        # §9.3.5：**brotliBytes 才是 §8.5 的 UI 顯示下載大小來源**——Cloudflare Pages
        # 對 JSON 實際送 brotli，顯示 gzip 等於對使用者高報約 43%。
        # **只算 5 個 top-level 檔**：256 個 shard 不在 scope 切換器上、也不在 F1 的
        # Tier 0 內，對它們跑 quality 11 會讓月更新多花數分鐘卻沒有任何讀者。
        if not name.startswith("records/"):
            meta[name]["brotliBytes"] = brotli_size(data)

    if source_updated_at is None:
        dates = [t.latest_source_date for t in trials if t.latest_source_date]
        source_updated_at = max(dates) if dates else None

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "datasetVersion": dv,
        "artifactDigest": artifact_digest(published),
        "sourceDatasetId": SOURCE_DATASET_ID,
        "sourceUpdatedAt": source_updated_at,
        "fetchedAt": fetched_at,
        "builtAt": built_at,
        "buildDate": build_date,
        "sourceSha256": source_sha256,
        "trialCount": len(trials),
        "recordCount": record_count,
        "bootstrap": bootstrap,
        "files": {
            "trialsIndex": meta["trials-index.json"],
            "stats": meta["stats.json"],
            "searchShortAll": meta["search-short-all.json"],
            "searchLongLatest": meta["search-long-latest.json"],
            "searchLongAll": meta["search-long-all.json"],
            "recordShards": {s: meta[f"records/{s}.json"] for s in sorted(shards)},
        },
    }
    return BuildOutput(logical, published, manifest)


def manifest_paths(manifest: dict) -> set[str]:
    """`manifest.files` 列出的全部發布路徑。"""
    files = manifest["files"]
    paths = {
        files[k]["path"]
        for k in ("trialsIndex", "stats", "searchShortAll", "searchLongLatest", "searchLongAll")
    }
    paths |= {v["path"] for v in files["recordShards"].values()}
    return paths
