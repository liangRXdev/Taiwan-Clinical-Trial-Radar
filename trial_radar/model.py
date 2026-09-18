"""§6.2–§6.5 的資料模型：SourceRecord → Trial。

來源列稱 **SourceRecord（審查紀錄）**。「一列 = 某一版試驗計畫書」是推論不是事實；
資料只證明同 protocol 有多筆審查紀錄。模型與 UI 一律用「審查紀錄」，**不稱「第 N 版」**。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field as _dc_field

from .comparison import comparison_key
from .fields import (
    COLUMNS,
    PERIOD_END,
    PERIOD_START,
    PRESENTATION_FIELDS,
    PROTOCOL,
    UPDATED_AT,
)
from .identity import (
    IdentityKey,
    assign_identity_keys,
    canonical_serialization,
    detect_identity_collision,
    detect_truncation_collisions,
    near_duplicate_groups,
    record_id,
    shard_key,
    trial_id,
)
from .normalize import identity_normalize, loose_key
from .parsing import (
    FieldValue,
    ParsedDate,
    parse_field,
    parse_updated_at,
    period_order_anomaly,
    suspected_test_row,
)


@dataclass
class SourceRecord:
    rid: str
    raw: dict[str, str]
    fields: dict[str, FieldValue]
    updated: ParsedDate
    record_flags: tuple[str, ...]

    @property
    def sort_date(self) -> _dt.date | None:
        """排序與 cohort 用的**可採計**日期；不可採計者為 None。"""
        return self.updated.date if self.updated.usable else None


@dataclass
class Trial:
    id: str
    identity_key: IdentityKey
    protocol_raw: list[str]
    protocol_non_identifier: bool
    suspected_test_row: bool
    near_duplicate_group: str | None
    records: list[SourceRecord]
    latest_source_date: str | None
    date_unknown: bool
    latest_cohort: list[str]
    latest_ambiguous: bool
    conflict_fields: list[str]
    display_fields: dict[str, FieldValue]
    shard: str

    @property
    def record_ids(self) -> list[str]:
        """§9.3.6 排序：可採計日期降序、不可採計者置末、recordId 昇序。"""
        return [r.rid for r in sorted(
            self.records,
            key=lambda r: (r.sort_date is None,
                           _neg_date(r.sort_date),
                           r.rid),
        )]


def _neg_date(d: _dt.date | None) -> tuple:
    """讓日期降序可以與其他鍵一起放進 tuple（不可採計者的值不影響，已由前一個鍵分開）。"""
    if d is None:
        return (0, 0, 0)
    return (-d.year, -d.month, -d.day)


def build_records(
    rows: list[dict[str, str]], build_date: _dt.date
) -> tuple[list[SourceRecord], list[IdentityKey], dict[str, bytes]]:
    """解析每一列並配出 recordId。回傳 (records, identity keys, rid → canonical)。"""
    keys = assign_identity_keys(rows)
    detect_identity_collision(rows, keys)

    canon = [canonical_serialization(r) for r in rows]
    tids = [trial_id(k.render()) for k in keys]

    # §6.3.2：recordId 的 duplicate ordinal 一律存在且從 #0 起。
    # 同 Trial 內相同 canonical serialization 的列彼此逐位元相同，序號依內容排序配置。
    groups: dict[tuple[str, bytes], list[int]] = {}
    for i, (tid, c) in enumerate(zip(tids, canon)):
        groups.setdefault((tid, c), []).append(i)
    ordinal_of: dict[int, int] = {}
    for idxs in groups.values():
        for k, i in enumerate(idxs):
            ordinal_of[i] = k

    records: list[SourceRecord] = []
    record_canon: dict[str, bytes] = {}
    for i, row in enumerate(rows):
        rid = record_id(tids[i], canon[i], ordinal_of[i])
        fields = {f: parse_field(f, row[f]) for f in PRESENTATION_FIELDS}
        updated = parse_updated_at(row[UPDATED_AT], build_date)

        flags: list[str] = []
        if period_order_anomaly(fields[PERIOD_START], fields[PERIOD_END]):
            flags.append("periodEndBeforeStart")
        if suspected_test_row(row):
            flags.append("suspectedTestRow")

        records.append(
            SourceRecord(rid, dict(row), fields, updated, tuple(sorted(flags)))
        )
        record_canon[rid] = canon[i]
    return records, keys, record_canon


def build_trials(
    rows: list[dict[str, str]], build_date: _dt.date
) -> list[Trial]:
    """把 SourceRecord 收斂為 Trial（§6.2–§6.4）。"""
    records, keys, record_canon = build_records(rows, build_date)

    key_to_tid = {k.render(): trial_id(k.render()) for k in keys}
    detect_truncation_collisions(key_to_tid, record_canon)

    # §6.2.1：nearDuplicateGroup 以 looseKey 分組，只有含 ≥2 個不同 identity key 者成群。
    # loose key **不影響任何收斂結果**——它只用來產生提示。
    all_protocols = {r[PROTOCOL] for r in rows if identity_normalize(r[PROTOCOL])}
    near = near_duplicate_groups(all_protocols)
    ident_to_group = {
        ident: lk for lk, idents in near.items() for ident in idents
    }

    by_key: dict[str, list[SourceRecord]] = {}
    key_obj: dict[str, IdentityKey] = {}
    for rec, key in zip(records, keys):
        rendered = key.render()
        by_key.setdefault(rendered, []).append(rec)
        key_obj[rendered] = key

    trials: list[Trial] = []
    for rendered, recs in by_key.items():
        trials.append(_build_trial(rendered, key_obj[rendered], recs, ident_to_group))
    trials.sort(key=lambda t: t.id)  # §9.3.6：trials 依 trialId 昇序
    return trials


def _build_trial(
    rendered: str,
    key: IdentityKey,
    recs: list[SourceRecord],
    ident_to_group: dict[str, str],
) -> Trial:
    tid = trial_id(rendered)
    protocols = sorted({r.raw[PROTOCOL] for r in recs})

    # §6.2.2：looseKey 為空（含 raw 空字串與空白-only）即 protocolNonIdentifier
    non_identifier = all(loose_key(p) == "" for p in protocols)

    usable = [r for r in recs if r.updated.usable]
    if usable:
        latest = max(r.updated.date for r in usable)
        cohort = [r for r in usable if r.updated.date == latest]
        latest_source_date: str | None = latest.isoformat()
        date_unknown = False
    else:
        # §6.5.2：某 Trial 無任何可採計日期 → latestSourceDate=null、dateUnknown、
        # latestCohort = 全部 recordId
        cohort = list(recs)
        latest_source_date = None
        date_unknown = True

    conflict_fields, display = _resolve_cohort(cohort)

    return Trial(
        id=tid,
        identity_key=key,
        protocol_raw=protocols,
        protocol_non_identifier=non_identifier,
        suspected_test_row=any("suspectedTestRow" in r.record_flags for r in recs),
        near_duplicate_group=ident_to_group.get(identity_normalize(protocols[0]))
        if key.kind == "P"
        else None,
        records=recs,
        latest_source_date=latest_source_date,
        date_unknown=date_unknown,
        latest_cohort=sorted(r.rid for r in cohort),  # §9.3.6：latestCohort 依 rid 昇序
        latest_ambiguous=len(cohort) > 1 and bool(conflict_fields),
        conflict_fields=conflict_fields,
        display_fields=display,
        shard=shard_key(tid),
    )


def _resolve_cohort(
    cohort: list[SourceRecord],
) -> tuple[list[str], dict[str, FieldValue]]:
    """依 §6.4.2 判定衝突、依 §6.4.3 標 rawVariants、依 §6.4.5 組 displayFields。

    - **衝突欄位在 displayFields 中完全省略**，不是給 `{typed: null}`——後者會與「未提供」
      混淆，而混淆正是本專案最怕的誤導。
    - 代表值取 `latestCohort` 中 **recordId 字典序最小者**的 raw。
    """
    representative = min(cohort, key=lambda r: r.rid)
    conflict_fields: list[str] = []
    display: dict[str, FieldValue] = {}

    for f in PRESENTATION_FIELDS:  # 依 canonical 欄位順序
        keys = {comparison_key(f, r.fields[f]) for r in cohort}
        if len(keys) > 1:
            conflict_fields.append(f)
            continue
        value = representative.fields[f]
        if len({r.fields[f].raw for r in cohort}) > 1:
            # 比較鍵相同但 distinct raw > 1 → 該**欄位**的 flags 加 rawVariants。
            # rawVariants = true **不代表衝突**，只表示多個 raw 映射到同一比較鍵。
            value = value.with_flag("rawVariants")
        display[f] = value
    return conflict_fields, display
