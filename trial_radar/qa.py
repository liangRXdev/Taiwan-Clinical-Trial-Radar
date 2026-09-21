"""QA report（`qa/quality-report.json`、`qa/schema-report.json`、`qa/collision-report.json`）。

**所有 warning 必須出現在結構化欄位中，不得只印在 log**（§9.6）。
只印 log 的實作在 CI 上看起來一模一樣，但沒有任何東西能斷言它。
"""
from __future__ import annotations

from dataclasses import dataclass

from .fields import (
    CATEGORICAL_FIELDS,
    NUMERIC_FIELDS,
    PERIOD_FIELDS,
    PRESENTATION_FIELDS,
    PROTOCOL,
    TEXT_FIELDS,
)
from .model import Trial
from .normalize import loose_key
from .source import DropVerdict

# §6.6.2 的字面 sentinel：三者**互相可區分，不得塌成同一值**
TEXT_SENTINELS = ("N/A", "NA", "")


def _count_field_flags(trials: list[Trial]) -> dict[str, dict[str, int]]:
    """每個欄位的旗標出現次數（**數全部 record，不是只數 cohort**）。"""
    out: dict[str, dict[str, int]] = {}
    for t in trials:
        for r in t.records:
            for field, value in r.fields.items():
                for flag in value.flags:
                    out.setdefault(field, {}).setdefault(flag, 0)
                    out[field][flag] += 1
            if r.updated.flag:
                out.setdefault("資料更新時間", {}).setdefault(r.updated.flag, 0)
                out["資料更新時間"][r.updated.flag] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def build_quality_report(
    trials: list[Trial],
    *,
    source_row_count: int,
    source_sha256: str,
    fetched_at: str,
    source_kind: str = "zip",
    drop: DropVerdict,
    near_duplicates: dict[str, list[str]],
    previous: dict | None = None,
    whitespace_variants: list[dict] | None = None,
) -> dict:
    """結構化 QA report。`warnings` 是**機器可讀**的清單，不是人看的字串拼接。"""
    warnings: list[dict] = []

    if drop.warning:
        warnings.append(
            {
                "code": "ROWCOUNT_DROP_WARNING",
                "drop": str(drop.drop),
                "prevRows": previous.get("recordCount") if previous else None,
                "curRows": source_row_count,
            }
        )
    if drop.bootstrap:
        warnings.append({"code": "BOOTSTRAP", "note": "首次無 baseline，未做驟降比較"})

    # §6.2：僅前後空白不同者靜默合併，**但揭露不是靜默的**。這些群不造成硬失敗，
    # 卻是上游輸入品質的訊號；只在程式裡合併而不寫進結構化報告，下個月多出一組時
    # 沒有任何東西會顯示出來。
    for group in whitespace_variants or []:
        warnings.append(
            {
                "code": "WHITESPACE_ONLY_PROTOCOL_VARIANT",
                "identityNormalized": group["identityNormalized"],
                "rawProtocols": group["rawProtocols"],
            }
        )

    flag_counts = _count_field_flags(trials)
    # 每一類 warning 級旗標都要進 warnings，並附**範例 recordId**（§9.6）
    warning_flags = {
        "numericRangeInvalid", "numericImplausible", "numericUnparsed", "numericOutOfRange",
        "categoricalUnknown", "dateUnparsed", "dateFuture",
    }
    examples: dict[str, list[str]] = {}
    for t in trials:
        for r in t.records:
            flags = {f for v in r.fields.values() for f in v.flags}
            if r.updated.flag:
                flags.add(r.updated.flag)
            flags |= set(r.record_flags)
            for f in flags & (warning_flags | {"periodEndBeforeStart"}):
                examples.setdefault(f, [])
                if len(examples[f]) < 5:
                    examples[f].append(r.rid)
    for flag in sorted(examples):
        total = sum(counts.get(flag, 0) for counts in flag_counts.values())
        if flag == "periodEndBeforeStart":
            total = sum(
                1 for t in trials for r in t.records if flag in r.record_flags
            )
        warnings.append(
            {"code": flag, "count": total, "exampleRecordIds": examples[flag]}
        )

    tie_groups = [t for t in trials if len(t.latest_cohort) > 1]
    conflicted = [t for t in trials if t.latest_ambiguous]

    text_sentinels = {
        field: {
            ("empty" if s == "" else s): sum(
                1 for t in trials for r in t.records if r.raw[field] == s
            )
            for s in TEXT_SENTINELS
        }
        for field in TEXT_FIELDS
    }

    nullness = {
        field: sum(1 for t in trials for r in t.records if r.raw[field].strip() == "")
        for field in PRESENTATION_FIELDS
    }

    non_identifier = [
        {"trialId": t.id, "protocolRaw": t.protocol_raw, "recordCount": len(t.records)}
        for t in trials
        if t.protocol_non_identifier
    ]
    test_rows = [
        {"trialId": t.id, "protocolRaw": t.protocol_raw,
         "recordIds": [r.rid for r in t.records if "suspectedTestRow" in r.record_flags]}
        for t in trials
        if t.suspected_test_row
    ]

    return {
        "counts": {
            "sourceRows": source_row_count,
            "records": sum(len(t.records) for t in trials),
            "trials": len(trials),
            "tieGroups": len(tie_groups),
            "conflictedTrials": len(conflicted),
            "dateUnknownTrials": sum(1 for t in trials if t.date_unknown),
        },
        # `sourceKind` 標明 `sourceSha256` 雜湊的是哪一層位元組：`zip`（連網取得，
        # §9.6 排除它的論據就是針對 ZIP metadata）或 `csv`（`--source` 本機檔，沒有
        # ZIP 可雜湊）。少了這個標記，換執行模式造成的 SHA 改變會被誤讀成上游換了內容。
        "provenance": {
            "sourceSha256": source_sha256,
            "sourceKind": source_kind,
            "fetchedAt": fetched_at,
        },
        "dropComparison": {
            "drop": str(drop.drop) if drop.drop is not None else None,
            "warning": drop.warning,
            "bootstrap": drop.bootstrap,
        },
        "fieldFlagCounts": flag_counts,
        "textSentinelCounts": text_sentinels,
        "nullness": nullness,
        "conflictFieldDistribution": _conflict_distribution(conflicted),
        # §6.2.1 第 3 點：QA report 列出每個 group 的**全部 raw protocol 與 trialId**
        "nearDuplicateGroups": [
            {
                "looseKey": lk,
                "identityKeys": idents,
                "trials": sorted(
                    {t.id for t in trials
                     if t.near_duplicate_group == lk},
                ),
                "rawProtocols": sorted(
                    {p for t in trials if t.near_duplicate_group == lk for p in t.protocol_raw}
                ),
            }
            for lk, idents in sorted(near_duplicates.items())
        ],
        "protocolNonIdentifier": non_identifier,
        "suspectedTestRows": test_rows,
        "warnings": warnings,
    }


def _conflict_distribution(conflicted: list[Trial]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for t in conflicted:
        for f in t.conflict_fields:
            dist[f] = dist.get(f, 0) + 1
    return dict(sorted(dist.items(), key=lambda kv: (-kv[1], kv[0])))


def build_schema_report(header: list[str], row_count: int) -> dict:
    return {"columns": header, "columnCount": len(header), "rowCount": row_count}


def build_collision_report(detail: dict) -> dict:
    """§9.8：須能**唯一定位**每個 collision group。

    **空 report 或只含 error code 者視為不合規**——那種 report 在事故當下毫無用處。
    """
    groups = detail.get("groups") or []
    if not groups:
        raise ValueError("collision report 不得為空（§9.8）")
    return {"groups": groups, "groupCount": len(groups)}
