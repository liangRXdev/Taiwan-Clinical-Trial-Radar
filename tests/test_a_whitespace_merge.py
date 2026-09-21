"""§6.2（v0.8）：僅前後空白不同的 protocol 合併，不是碰撞。

這條規則是 2026-09-21 首次連網實跑逼出來的——v0.7 照字面把 `identityNormalize` 自己的
`strip()` 也算成碰撞，實資料 4 組僅尾隨一個空白的 protocol 使管線 exit 22，一次都跑不完。

輸入以 `a_core` 的凍結列**程式化衍生**（附加一個尾隨空白），與 A8 的注入替身同一手法：
凍結 fixture 證明不了「規格符合現實」，而這條規則的來源正是現實。
"""
from __future__ import annotations

import pytest

from trial_radar.errors import ErrorCode, PipelineError
from trial_radar.identity import (
    assign_identity_keys,
    detect_identity_collision,
    whitespace_only_variants,
)
from trial_radar.model import build_trials
from trial_radar.normalize import identity_normalize

PROTOCOL = "臨床試驗計畫書編號"


def _rows_with_trailing_space(a_core_rows) -> tuple[list[dict], str]:
    """複製一列真實資料，protocol 尾隨一個空白。回傳 (rows, 被複製的 protocol)。"""
    rows = [dict(r) for r in a_core_rows.values()]
    donor = next(
        r for r in rows
        if identity_normalize(r[PROTOCOL]) and r[PROTOCOL] == r[PROTOCOL].strip()
    )
    variant = dict(donor)
    variant[PROTOCOL] = donor[PROTOCOL] + " "
    # 讓兩列不是逐位元相同，否則測的會是重複列而不是空白變體
    variant["TFDA收文號"] = "WS-TRAILING-SPACE"
    rows.append(variant)
    return rows, donor[PROTOCOL]


def test_trailing_space_is_not_a_collision(a_core_rows, build_date):
    """僅尾隨空白不同 → **不得**硬失敗。"""
    rows, _ = _rows_with_trailing_space(a_core_rows)
    build_trials(rows, build_date)  # 不拋即通過


def test_trailing_space_variants_merge_into_one_trial(a_core_rows, build_date):
    """兩個寫法合併為同一個 Trial，且**兩個 raw 值都保留在 `protocolRaw`**。

    只合併卻丟掉其中一個 raw 值，等於讓使用者查得到的那個寫法在詳情頁上消失。
    """
    rows, protocol = _rows_with_trailing_space(a_core_rows)
    trials = build_trials(rows, build_date)

    matched = [t for t in trials if identity_normalize(protocol) in
               {identity_normalize(p) for p in t.protocol_raw}]
    assert len(matched) == 1, "應合併為一個 Trial"
    assert set(matched[0].protocol_raw) >= {protocol, protocol + " "}


def test_case_fold_collision_still_hard_fails(a_core_rows, build_date):
    """反向哨兵：大小寫折疊**仍然**是碰撞。

    界線畫在 `strip` 而非「全部折疊」——若把整條規則關掉而不是限縮，這條會轉綠。
    """
    rows = [dict(r) for r in a_core_rows.values()]
    donor = next(
        r for r in rows
        if identity_normalize(r[PROTOCOL]) and r[PROTOCOL] != r[PROTOCOL].lower()
    )
    variant = dict(donor)
    variant[PROTOCOL] = donor[PROTOCOL].lower()
    variant["TFDA收文號"] = "WS-CASEFOLD"
    rows.append(variant)

    with pytest.raises(PipelineError) as exc:
        build_trials(rows, build_date)
    assert exc.value.code is ErrorCode.IDENTITY_COLLISION


def test_collision_grouping_key_is_stripped_raw(a_core_rows):
    """直接釘住分組鍵：以 `raw` 分組會讓尾隨空白轉成碰撞。

    這條不經 `build_trials`，是為了在規則本身而非其呼叫端上留一道斷言——
    `detect_identity_collision` 未來被換掉時，上面三條可能一起沉默。
    """
    rows, _ = _rows_with_trailing_space(a_core_rows)
    keys = assign_identity_keys(rows)
    detect_identity_collision(rows, keys)  # 不拋

    # 反向：把 strip 拿掉（模擬 v0.7 的寫法）必須拋
    by_key: dict[str, set[str]] = {}
    for row, key in zip(rows, keys):
        if key.kind == "P":
            by_key.setdefault(key.value, set()).add(row[PROTOCOL])
    assert any(len(v) > 1 for v in by_key.values()), (
        "以 raw 分組必須看得到這組差異，否則這個 fixture 根本沒注入到東西"
    )


def test_whitespace_variants_are_disclosed(a_core_rows):
    """合併是靜默的，**揭露不是**——QA report 須列出該群與兩個 raw 值。"""
    rows, protocol = _rows_with_trailing_space(a_core_rows)
    groups = whitespace_only_variants(rows)
    assert len(groups) == 1
    assert groups[0]["identityNormalized"] == identity_normalize(protocol)
    assert groups[0]["rawProtocols"] == sorted({protocol, protocol + " "})


def test_no_whitespace_variants_in_unmodified_fixture(a_core_rows):
    """反向哨兵：未變造的 fixture 不得有任何空白變體群。

    沒有這條，上一條在「函式恆回傳非空」時照樣綠。
    """
    rows = [dict(r) for r in a_core_rows.values()]
    assert whitespace_only_variants(rows) == []


# ---------------------------------------------------------------- QA report 形狀

def test_whitespace_warning_shape(a_core_rows, build_date):
    """§6.2：**以 Trial 為單位，一個 Trial 最多一則**，且須帶 `trialId`。

    少了 `trialId`，看 QA report 的人要自己從 `identityNormalized` 反推 Trial——
    而那正是這則 warning 想省掉的事。
    """
    from trial_radar.identity import trial_id
    from trial_radar.qa import build_quality_report
    from trial_radar.source import DropVerdict

    rows, protocol = _rows_with_trailing_space(a_core_rows)
    trials = build_trials(rows, build_date)
    report = build_quality_report(
        trials,
        source_row_count=len(rows),
        source_sha256="0" * 64,
        fetched_at="2026-09-21T00:00:00Z",
        drop=DropVerdict(None, False, True),
        near_duplicates={},
        whitespace_variants=whitespace_only_variants(rows),
    )

    ws = [w for w in report["warnings"] if w["code"] == "WHITESPACE_ONLY_PROTOCOL_VARIANT"]
    assert len(ws) == 1, "一個 Trial 一則，不得展開成 pair"
    assert ws[0]["trialId"] == trial_id(f"P:{identity_normalize(protocol)}")
    assert ws[0]["identityNormalized"] == identity_normalize(protocol)
    assert ws[0]["rawProtocols"] == sorted({protocol, protocol + " "})


def test_three_variants_still_one_warning(a_core_rows, build_date):
    """三個以上變體仍是**一則**，全部列在同一個 `rawProtocols`（§6.2 基數封存）。"""
    rows = [dict(r) for r in a_core_rows.values()]
    donor = next(
        r for r in rows
        if identity_normalize(r[PROTOCOL]) and r[PROTOCOL] == r[PROTOCOL].strip()
    )
    expected = {donor[PROTOCOL]}
    for i, suffix in enumerate((" ", "　", " ")):
        v = dict(donor)
        v[PROTOCOL] = donor[PROTOCOL] + suffix
        v["TFDA收文號"] = f"WS-MULTI-{i}"
        rows.append(v)
        expected.add(v[PROTOCOL])

    groups = whitespace_only_variants(rows)
    assert len(groups) == 1
    assert set(groups[0]["rawProtocols"]) == expected
    # 四個寫法收斂成一個 Trial
    trials = build_trials(rows, build_date)
    merged = [t for t in trials if identity_normalize(donor[PROTOCOL])
              in {identity_normalize(p) for p in t.protocol_raw}]
    assert len(merged) == 1
    assert set(merged[0].protocol_raw) == expected


def test_collision_report_rejects_v08_flat_shape():
    """`build_collision_report` 主動檢查 §9.8 的結構，不只是轉手。

    這份 report 只在事故當下被讀，那時沒有人有餘裕發現它少了一個欄位——
    **形狀錯誤要在產生的當下就爆**。
    """
    import pytest as _pytest

    from trial_radar.qa import build_collision_report

    with _pytest.raises(ValueError):
        build_collision_report({"groups": []})
    # v0.8 的扁平形狀
    with _pytest.raises(ValueError):
        build_collision_report(
            {"groups": [{"identityNormalized": "ABC", "rawProtocols": ["abc", "ABC"]}]}
        )
    # member 只有一個 → 不成群
    with _pytest.raises(ValueError):
        build_collision_report({"groups": [{
            "identityNormalized": "ABC", "trialId": "t0",
            "members": [{"raws": ["abc"], "strippedRaw": "abc", "fingerprints": ["f"]}],
        }]})
    # 群內 strippedRaw 相同 → 那是 §6.2 的合併案例，不是碰撞
    with _pytest.raises(ValueError):
        build_collision_report({"groups": [{
            "identityNormalized": "ABC", "trialId": "t0",
            "members": [
                {"raws": ["abc"], "strippedRaw": "abc", "fingerprints": ["f"]},
                {"raws": ["abc "], "strippedRaw": "abc", "fingerprints": ["g"]},
            ],
        }]})

    ok = build_collision_report({"groups": [{
        "identityNormalized": "ABC", "trialId": "t0",
        "members": [
            {"raws": ["abc"], "strippedRaw": "abc", "fingerprints": ["f"]},
            {"raws": ["ABC"], "strippedRaw": "ABC", "fingerprints": ["g"]},
        ],
    }]})
    assert ok["groupCount"] == 1
