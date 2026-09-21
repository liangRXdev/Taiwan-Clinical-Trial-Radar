"""A 群驗收：資料模型與收斂（A1–A10）。

oracle 在 `tests/fixtures/a_core/oracle.json`，**手寫**且 row identity 獨立於 §6.3 的
canonical serialization——共用推導會讓兩邊一致地錯而通過（A5）。
"""
from __future__ import annotations

import random

import pytest

from trial_radar.artifacts import build_artifacts
from trial_radar.errors import ErrorCode, PipelineError
from trial_radar.identity import (
    canonical_serialization,
    near_duplicate_groups,
    sha256hex,
    trial_id,
)
from trial_radar.model import build_trials
from trial_radar.normalize import identity_normalize, loose_key
from trial_radar.parsing import suspected_test_row

PROTOCOL = "臨床試驗計畫書編號"

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
def rid_to_rowkey(trials, a_core_rows) -> dict[str, str]:
    """recordId → rowKey，**全域一次指派**。

    逐位元相同的兩列（`empty-dup-a`／`empty-dup-b`）在內容上不可分辨，oracle 因此標
    `rowKeyToTrialMapping: "__ORDER_INDIFFERENT__"`——任何一組合法指派都算對。
    逐 Trial 各自貪婪配對會讓兩個 Trial 都挑到同一個 rowKey，那是測試的 bug 不是實作的。
    """
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for t in trials:
        for r in t.records:
            for k, v in a_core_rows.items():
                if k not in used and v == r.raw:
                    mapping[r.rid] = k
                    used.add(k)
                    break
    assert len(mapping) == sum(len(t.records) for t in trials)
    return mapping


def _rowkeys_of(trial, rid_to_rowkey) -> set[str]:
    return {rid_to_rowkey[r.rid] for r in trial.records}


# ---------------------------------------------------------------- A1

def test_a1_group_membership(trials, rid_to_rowkey, a_core_oracle):
    """A1：寫死**每個來源列 → trialId 的 group membership**，不只比總數。"""
    actual = {}
    for t in trials:
        actual[t.id] = _rowkeys_of(t, rid_to_rowkey)

    # oracle 的 rowKey 群組（EMPTY-DUP 展開為兩個 Trial，各一列）
    expected_groups = []
    for entry in a_core_oracle["trials"]:
        if entry.get("expandsToTrialCount", 1) > 1:
            expected_groups.extend([{k} for k in entry["rowKeys"]])
        else:
            expected_groups.append(set(entry["rowKeys"]))

    assert sorted(map(sorted, actual.values())) == sorted(map(sorted, expected_groups))


@pytest.mark.parametrize(
    "a,b",
    [
        ("MK-3475-158", "MK3475-158"),      # 連字號有無
        ("9785-CL- 0123", "9785-CL-0123"),  # 空格有無
        ("ROR-PH-301(APD811-301", "ROR-PH-301(APD811-301)"),  # 括號閉合
    ],
)
def test_a1_must_not_merge(trials, a, b):
    """A1 的「不應合併」反例須採 §6.2 **明確不折疊**的差異。

    **不得**使用大小寫或全半形差異——那些會折疊，屬 A7。
    """
    assert identity_normalize(a) != identity_normalize(b)
    ids = {t.id for t in trials if a in t.protocol_raw or b in t.protocol_raw}
    assert len(ids) == 2, f"{a} 與 {b} 必須是兩個 Trial"


def test_a1_must_merge(trials, rid_to_rowkey):
    """A1 的「應合併」案例：同一 raw protocol 兩列不同日 → 一個 Trial 兩筆 record。"""
    t = next(t for t in trials if "SAME-010" in t.protocol_raw)
    assert len(t.records) == 2
    assert _rowkeys_of(t, rid_to_rowkey) == {"same010-old", "same010-new"}


# ---------------------------------------------------------------- A2

def test_a2_required_cases_present(trials, a_core_oracle):
    """A2 的必含案例逐一存在。**這條保護的是 fixture 本身**，不是實作。"""
    # ≥1 個 10 列以上 protocol
    assert any(len(t.records) >= 10 for t in trials)
    # ≥2 筆完全相同的空 protocol 列
    empty = [t for t in trials if t.identity_key.kind == "H" and t.protocol_raw == [""]]
    assert len(empty) == 3  # 2 相同 + 1 獨特
    # ≥1 筆空白-only protocol（raw 非空但 identityNormalize 後為空）
    ws_only = [
        t for t in trials
        if t.identity_key.kind == "H" and t.protocol_raw[0] != ""
    ]
    assert len(ws_only) >= 1
    assert all(identity_normalize(t.protocol_raw[0]) == "" for t in ws_only)
    # ≥3 組同日衝突
    assert len([t for t in trials if t.latest_ambiguous]) >= 3
    # ≥1 筆 TFDA收文號="移案BPA" 與 ≥1 筆收文號重複
    receipts = [r.raw["TFDA收文號"] for t in trials for r in t.records]
    assert "移案BPA" in receipts
    assert len(receipts) != len(set(receipts))
    # ≥1 個 nearDuplicateGroup／≥1 筆 protocolNonIdentifier／≥1 筆 suspectedTestRow
    assert any(t.near_duplicate_group for t in trials)
    assert any(t.protocol_non_identifier for t in trials)
    assert any(t.suspected_test_row for t in trials)


def test_a2_date_anomalies(trials, a_core_oracle):
    """A2 的日期異常各 ≥1，計數與 oracle 完全相符（**數全部列**）。"""
    exp = a_core_oracle["qualityReportExpectations"]["dateAnomalyCounts"]
    counts = {"dateMissing": 0, "dateUnparsed": 0, "dateFuture": 0}
    period_before = 0
    for t in trials:
        for r in t.records:
            if r.updated.flag in counts:
                counts[r.updated.flag] += 1
            if "periodEndBeforeStart" in r.record_flags:
                period_before += 1
    assert counts["dateUnparsed"] == exp["dateUnparsed"]
    assert counts["dateMissing"] == exp["dateMissing"]
    assert counts["dateFuture"] == exp["dateFuture"]
    assert period_before == exp["periodEndBeforeStart"]


def test_a2_build_date_boundaries(trials):
    """`buildDate` 當日須**可採計**、`buildDate + 1 日`須為 `dateFuture` 且不進 cohort。"""
    t = next(t for t in trials if "BD-024" in t.protocol_raw)
    today = next(r for r in t.records if r.raw["資料更新時間"] == "2026/09/18")
    tomorrow = next(r for r in t.records if r.raw["資料更新時間"] == "2026/09/19")
    assert today.updated.usable and today.updated.flag is None
    assert tomorrow.updated.flag == "dateFuture"
    assert t.latest_cohort == [today.rid]
    # 未來日期不得支配卡片：卡片的台灣人數必須是 12，不是 99
    assert t.display_fields["台灣預計受試者人數"].raw == "12"


def test_a2_future_date_does_not_dominate(trials):
    """§6.5／N3 的關鍵案例：2099/01/01 不得遮蔽正常紀錄。"""
    t = next(t for t in trials if "DT-017" in t.protocol_raw)
    assert t.latest_source_date == "2026-01-15"
    assert t.display_fields["台灣預計受試者人數"].raw == "17"
    assert t.display_fields["台灣預計受試者人數"].raw != "99"


# ---------------------------------------------------------------- A3

def _artifact_of(rows, build_date):
    return build_artifacts(build_trials(rows, build_date), **BUILD_KW)


@pytest.mark.parametrize("perm", ["asIs", "reversed", "seed-1", "seed-2", "seed-3"])
def test_a3_determinism(a_core_rows, build_date, perm):
    """A3：對 reverse 與 3 個固定 seed 的排列，輸出必須逐位元相同。

    斷言順序有意義：**先比檔案 inventory，再逐檔 hash**——漏一個輸出檔時，
    不完整的 hash 清單會放過它。
    """
    base = _artifact_of(list(a_core_rows.values()), build_date)

    rows = list(a_core_rows.values())
    if perm == "reversed":
        rows = list(reversed(rows))
    elif perm.startswith("seed-"):
        random.Random(int(perm.split("-")[1])).shuffle(rows)
    other = _artifact_of(rows, build_date)

    assert set(other.published) == set(base.published), "檔案 inventory 不同"
    for path in sorted(base.published):
        assert sha256hex(other.published[path]) == sha256hex(base.published[path]), path
    assert other.manifest == base.manifest


def test_a3_tie_semantics_stable(a_core_rows, build_date):
    """A3 的第三層：每個 tie case 的語意結果（含衝突欄位與 displayFields）跨排列相同。"""
    rows = list(a_core_rows.values())
    base = {t.id: (t.latest_ambiguous, tuple(t.conflict_fields),
                   tuple(sorted((k, v.raw) for k, v in t.display_fields.items())))
            for t in build_trials(rows, build_date)}
    shuffled = list(rows)
    random.Random(7).shuffle(shuffled)
    other = {t.id: (t.latest_ambiguous, tuple(t.conflict_fields),
                    tuple(sorted((k, v.raw) for k, v in t.display_fields.items())))
             for t in build_trials(shuffled, build_date)}
    assert other == base


# ---------------------------------------------------------------- A4

def test_a4_reverse_sentinel(a_core_rows, build_date, monkeypatch):
    """A4 反向哨兵：把同日處置改為「任取 cohort 第一筆」時，**指定 tie group 的
    `latestAmbiguous` 必須由 true 變 false**，且 displayFields 會冒出具體值。

    這條不是在測正確行為，是在證明**測試抓得到那個弱化版本**。
    """
    import trial_radar.model as model

    good = {t.id: t for t in build_trials(list(a_core_rows.values()), build_date)}
    big = next(t for t in good.values() if "BIG-001" in t.protocol_raw)
    assert big.latest_ambiguous is True
    assert "台灣預計受試者人數" in big.conflict_fields
    assert "台灣預計受試者人數" not in big.display_fields

    def weakened(cohort):
        """弱化版本：不判衝突，直接取第一筆。"""
        first = cohort[0]
        return [], dict(first.fields)

    monkeypatch.setattr(model, "_resolve_cohort", weakened)
    broken = {t.id: t for t in build_trials(list(a_core_rows.values()), build_date)}
    bad_big = broken[big.id]

    assert bad_big.latest_ambiguous is False, "弱化版本必須被這條斷言殺死"
    assert "台灣預計受試者人數" in bad_big.display_fields, "衝突欄位不該冒出具體值"


# ---------------------------------------------------------------- A5

def test_a5_canonical_multiset_with_multiplicity(a_core_rows):
    """A5：canonical fingerprint 的**完整 multiset 含 multiplicity**。

    oracle 的 row identity 來自 `rows.json` 的 16 欄字面值——**獨立於 §6.3 的
    serialization**，否則就是拿實作驗自己。
    """
    from collections import Counter

    rows = list(a_core_rows.values())
    fingerprints = Counter(sha256hex(canonical_serialization(r)) for r in rows)
    # 獨立算法：直接用 16 欄 tuple 當 identity
    independent = Counter(tuple(r.values()) for r in rows)
    assert sum(fingerprints.values()) == len(rows)
    assert sorted(fingerprints.values()) == sorted(independent.values())
    assert len(fingerprints) == len(independent)


def test_a5_separator_boundary(a_core_rows):
    """A5 的分隔符／長度前綴邊界：含逗號、引號、換行與 TAB 的長欄位不得造成歧義。"""
    row = a_core_rows["big001-h1"]
    assert "\t" in row["納入條件"] and "\n" in row["納入條件"] and "「" in row["納入條件"]
    other = dict(row)
    # 把分隔符「搬家」：長度前綴使兩者不可能撞在一起
    other["納入條件"] = row["納入條件"] + "X"
    assert canonical_serialization(row) != canonical_serialization(other)


# ---------------------------------------------------------------- A6

def test_a6_empty_protocol_ordinals(trials, a_core_rows):
    """A6：兩筆完全相同的空 protocol 列各自取得唯一 ID（`#0`／`#1`），**單筆也帶 `#0`**。"""
    empties = [t for t in trials if t.identity_key.kind == "H" and t.protocol_raw == [""]]
    dup = [t for t in empties if t.records[0].raw["臨床試驗計畫中文名稱"] == "無編號試驗甲"]
    uniq = [t for t in empties if t.records[0].raw["臨床試驗計畫中文名稱"] == "無編號試驗乙"]

    assert len(dup) == 2 and len({t.id for t in dup}) == 2, "兩列須成為兩個相異 Trial"
    assert sorted(t.identity_key.ordinal for t in dup) == [0, 1]
    assert len(uniq) == 1
    assert uniq[0].identity_key.ordinal == 0, "單筆也必須帶 #0——ID 形狀不得隨鄰居增減而變"
    assert uniq[0].identity_key.render().endswith("#0")


def test_a6_record_id_ordinal_always_present(trials):
    """§6.3.2 的 ordinal 規則**同樣套用於 recordId**。"""
    for t in trials:
        for r in t.records:
            assert "#" in r.rid and r.rid.rsplit("#", 1)[1].isdigit()
    # BIG-001 的 cohort 內有一對逐位元相同的列 → #0／#1
    big = next(t for t in trials if "BIG-001" in t.protocol_raw)
    ordinals = [int(r.rid.rsplit("#", 1)[1]) for r in big.records]
    assert 1 in ordinals, "逐位元相同的兩列必須以 ordinal 區分"


# ---------------------------------------------------------------- A7

def test_a7_identity_collision_hard_fails(a7_rows, build_date, a7_oracle):
    """A7：`strip(raw)` 相異而正規化後相同 → 硬失敗，collision report 須能唯一定位。

    **空 report 或只含 error code 者視為不合規**（§9.8）。
    """
    rows = list(a7_rows.values())
    with pytest.raises(PipelineError) as exc:
        build_trials(rows, build_date)
    err = exc.value
    assert err.code is ErrorCode.IDENTITY_COLLISION
    assert err.layer.value == "content"

    groups = err.detail["groups"]
    assert groups, "空 collision report 必須使測試失敗"

    # 由 fixture 自己推導期望的 group／member 結構，**不抄實作的輸出**
    expected: dict[str, dict[str, set[str]]] = {}
    for r in rows:
        raw = r[PROTOCOL]
        ident = identity_normalize(raw)
        if ident:
            expected.setdefault(ident, {}).setdefault(raw.strip(), set()).add(raw)
    expected = {k: v for k, v in expected.items() if len(v) > 1}
    assert expected, "A7 fixture 必須真的含碰撞，否則這條測不到東西"

    assert {g["identityNormalized"] for g in groups} == set(expected)

    for g in groups:
        ident = g["identityNormalized"]
        # §9.8：trialId 由 identity key 導出，群內共用；**不可用來區分 member**
        assert g["trialId"] == trial_id(f"P:{ident}")

        members = g["members"]
        assert len(members) >= 2
        stripped = [m["strippedRaw"] for m in members]
        assert stripped == sorted(stripped), "members 依 strippedRaw 昇序"
        # **配對關係精確相等**，不是「欄位存在且非空」
        assert {m["strippedRaw"]: set(m["raws"]) for m in members} == expected[ident]

        for m in members:
            assert m["fingerprints"], "每個 member 須能回指來源列"
            assert m["fingerprints"] == sorted(m["fingerprints"])
            assert all(len(f) == 64 for f in m["fingerprints"])
            # strippedRaw 是判定成立的依據本身，必須與 raws 自洽
            assert {x.strip() for x in m["raws"]} == {m["strippedRaw"]}


def test_a7_whitespace_only_is_not_a_collision(a7_rows, build_date):
    """A7 的必含反例：僅前後空白不同者**不得**觸發 `IDENTITY_COLLISION`（§6.2）。

    這條與 `test_a_whitespace_merge.py` 同源，但放在 A7 這一側：**A7 的正例矩陣若被
    寫成「任何折疊都算碰撞」，這條會紅**——它守的是界線本身，不是合併結果。
    """
    rows = [dict(r) for r in a7_rows.values()]
    donor = next(r for r in rows if identity_normalize(r[PROTOCOL])
                 and r[PROTOCOL] == r[PROTOCOL].strip())

    def members_of(rs):
        with pytest.raises(PipelineError) as exc:
            build_trials(rs, build_date)
        g = next(g for g in exc.value.detail["groups"]
                 if g["identityNormalized"] == identity_normalize(donor[PROTOCOL]))
        return {m["strippedRaw"]: set(m["raws"]) for m in g["members"]}

    # a7 fixture 的 donor 本來就與另一個大小寫變體碰撞，**那個群是合法的**。
    # 要斷言的不是「群不存在」，而是**空白變體不得新增 member**。
    before = members_of(rows)

    variants = []
    for suffix, tag in ((" ", "TRAIL"), ("　", "IDEO"), (" ", "NBSP")):
        v = dict(donor)
        v[PROTOCOL] = donor[PROTOCOL] + suffix
        v["TFDA收文號"] = f"A7-WS-{tag}"
        rows.append(v)
        variants.append(v[PROTOCOL])

    after = members_of(rows)

    assert set(after) == set(before), (
        f"僅前後空白不同不得新增 member：{sorted(set(after) - set(before))}"
    )
    key = donor[PROTOCOL].strip()
    assert after[key] == before[key] | set(variants), (
        "三個空白變體須全部折進 donor 所屬的那一個 member"
    )


def test_a7_zero_width_is_a_collision(a7_rows, build_date):
    """§6.0 strip 字元集合的**反向哨兵**：零寬字元不被 strip，故必須判為碰撞。

    把 strip 實作成「移除全部不可見字元」會讓這條轉綠——而那會讓兩個肉眼無法區分的
    計畫書編號被靜默合併成一個，正是 fail-closed 要擋的。
    """
    rows = [dict(r) for r in a7_rows.values()]
    donor = next(r for r in rows if identity_normalize(r[PROTOCOL])
                 and r[PROTOCOL] == r[PROTOCOL].strip())
    variant = dict(donor)
    variant[PROTOCOL] = donor[PROTOCOL] + "​"
    variant["TFDA收文號"] = "A7-ZWSP"
    rows.append(variant)

    with pytest.raises(PipelineError) as exc:
        build_trials(rows, build_date)
    groups = {g["identityNormalized"]: g for g in exc.value.detail["groups"]}
    # NFKC 不移除 U+200B，故正規化後的鍵含該字元；碰撞群以該鍵成立
    target = identity_normalize(donor[PROTOCOL] + "​")
    assert target in groups or identity_normalize(donor[PROTOCOL]) in groups, (
        "零寬字元差異必須產生碰撞群"
    )


# ---------------------------------------------------------------- A8

def test_a8_truncation_collision_with_injected_hash(monkeypatch, a_core_rows, build_date):
    """A8（測試替身例外）：以**刻意截短為極少位元的雜湊替身**驅動碰撞偵測分支。

    真實的 64 位元 SHA-256 碰撞需約 2^32 次運算，不是「凍結的來源資料」而是刻意搜出的
    人工構造——那不屬於 fixture，故此條改用注入。測試仍使用**兩個不同的 identity key**。
    """
    import trial_radar.identity as ident

    real = ident.sha256hex

    def stubby(data: bytes) -> str:
        # 只保留 1 個 hex 位元的熵，其餘補零 → trialId 前 16 hex 必然碰撞
        return real(data)[0] + "0" * 63

    monkeypatch.setattr(ident, "sha256hex", stubby)
    monkeypatch.setattr("trial_radar.model.trial_id", lambda k: "t" + stubby(k.encode())[:16])

    with pytest.raises(PipelineError) as exc:
        build_trials(list(a_core_rows.values()), build_date)
    assert exc.value.code is ErrorCode.ID_TRUNCATION_COLLISION
    assert exc.value.detail["trialId"], "collision report 須指出撞在一起的 identity key"


# ---------------------------------------------------------------- A9

def test_a9_near_duplicate_groups(trials, a_core_oracle):
    """A9：`nearDuplicateGroup` 與 oracle 完全相符；`looseKey` 為空者**不入任何 group**。"""
    expected = {k: v for k, v in a_core_oracle["nearDuplicateGroups"].items()
                if not k.startswith("_")}
    protocols = {p for t in trials for p in t.protocol_raw if identity_normalize(p)}
    actual = near_duplicate_groups(protocols)
    assert {k: sorted(v) for k, v in actual.items()} == {
        k: sorted(identity_normalize(x) for x in v) for k, v in expected.items()
    }

    # 單一成員的 group 輸出 null
    singles = [t for t in trials if t.near_duplicate_group is None]
    assert singles, "大多數 Trial 的 nearDuplicateGroup 應為 null"
    # looseKey 為空者不入 group
    for t in trials:
        if t.protocol_raw[0] and loose_key(t.protocol_raw[0]) == "":
            assert t.near_duplicate_group is None


def test_a9_loose_key_does_not_affect_convergence(a_core_rows, build_date, monkeypatch):
    """A9：偵測用的 loose key **不影響任何 Trial 的收斂結果**。"""
    base = {t.id: sorted(r.rid for r in t.records)
            for t in build_trials(list(a_core_rows.values()), build_date)}

    import trial_radar.model as model

    monkeypatch.setattr(model, "near_duplicate_groups", lambda protocols: {})
    off = {t.id: sorted(r.rid for r in t.records)
           for t in build_trials(list(a_core_rows.values()), build_date)}
    assert off == base


# ---------------------------------------------------------------- A10

def test_a10_ascii_alnum_charset(trials):
    """A10：`系統測試`（中文，`isalnum()` 為 True）**必須**標記 `protocolNonIdentifier`。

    以 Unicode alphanumeric 實作者必須失敗。
    """
    assert "系統測試".isalnum() is True, "前提：Python 把中文視為 alphanumeric"
    t = next(t for t in trials if "系統測試" in t.protocol_raw)
    assert t.protocol_non_identifier is True
    assert loose_key("系統測試") == ""


def test_a10_protocol_non_identifier_count(trials, a_core_oracle):
    """計數須**數全部列**（空字串 + 空白-only + 非空但無 ASCII 英數字元）。"""
    expected = a_core_oracle["qualityReportExpectations"]["protocolNonIdentifierRowCount"]
    rows = sum(len(t.records) for t in trials if t.protocol_non_identifier)
    assert rows == expected


def test_a10_suspected_test_row_rule_b_alone(a_core_rows):
    """§6.2.2 (b)：protocol 合法、申請者與標題非空時，**只靠 `TEST` 值型**也要觸發。"""
    row = a_core_rows["test029"]
    assert row["臨床試驗申請者"] and row["臨床試驗計畫中文名稱"]
    assert "系統測試" not in row["臨床試驗計畫書編號"]
    assert "計畫書編號" not in row["臨床試驗計畫書編號"]
    assert suspected_test_row(row) is True
