"""F1／F3：初始 payload 的欄位邊界與 manifest 的大小欄位。

F3 要求「Tier 0 的全部 response 與 bundle 均不含長文字欄位**內容**，且**初始 payload 的
schema 不含這些欄位鍵**」。v0.7 的 §6.4.5 卻說 `displayFields` 涵蓋全部 13 個呈現欄位——
**兩條規範直接衝突，四輪覆審都沒抓到**，照 §6.4.5 寫就必然違反 F3。實測代價：照字面實作的
`trials-index` 是 15,621 KiB gzip，F1 門檻的 10.2 倍，長文字佔 raw 位元組 92.6%。

這裡是那條邊界的 M1 端守衛；M2 會在瀏覽器端以 canary 再驗一次（F3 的完整形式）。
"""
from __future__ import annotations

import json

from trial_radar.artifacts import build_artifacts
from trial_radar.fields import CARD_FIELDS, LONG_TEXT_FIELDS, PRESENTATION_FIELDS
from trial_radar.model import build_trials

BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


def _built(a_core_rows, build_date):
    trials = build_trials(list(a_core_rows.values()), build_date)
    return trials, build_artifacts(trials, **BUILD_KW)


def _index(out):
    return out.logical["trials-index.json"]


# ---------------------------------------------------------------- F3 schema

def test_card_fields_partition_presentation_fields():
    """9 個卡片欄位 ＋ 4 個長文字欄位 = 13 個呈現欄位，**無交集、無遺漏**。"""
    assert set(CARD_FIELDS) | set(LONG_TEXT_FIELDS) == set(PRESENTATION_FIELDS)
    assert not set(CARD_FIELDS) & set(LONG_TEXT_FIELDS)
    assert len(CARD_FIELDS) == 9 and len(LONG_TEXT_FIELDS) == 4


def test_index_display_fields_never_contain_long_text_keys(a_core_rows, build_date):
    """F3：初始 payload 的 schema **不含**長文字欄位鍵。"""
    _, out = _built(a_core_rows, build_date)
    for t in _index(out)["trials"]:
        keys = set(t["displayFields"])
        assert keys <= set(CARD_FIELDS), f"{t['id']} 的 displayFields 超出卡片欄位"
        assert not keys & set(LONG_TEXT_FIELDS)


def test_index_display_fields_are_not_silently_emptied(a_core_rows, build_date):
    """反向哨兵：卡片欄位**必須真的在**。

    沒有這條，把 `displayFields` 改成恆空的實作會讓上一條轉綠。
    """
    _, out = _built(a_core_rows, build_date)
    trials = _index(out)["trials"]
    # 至少一個 Trial 的 displayFields 覆蓋全部 9 個卡片欄位（無衝突者）
    assert any(set(t["displayFields"]) == set(CARD_FIELDS) for t in trials)


def test_long_text_content_absent_from_index_bytes(a_core_rows, build_date):
    """F3 的 canary 形式：長文字的**內容**不得出現在 index 的位元組裡。

    只檢查鍵名會放過「換個鍵名塞同樣的文字」。

    canary **取自 model 的 `display_fields`**，不是來源列——只有那些值在舊行為下真的會
    被序列化進 index。從來源列取會抽中衝突欄位的值，而衝突欄位本來就從 `displayFields`
    省略（§6.4.5），那樣這條在舊行為下照樣綠，等於什麼都沒守。
    """
    trials, out = _built(a_core_rows, build_date)
    blob = json.dumps(_index(out), ensure_ascii=False)

    canaries = [
        (field, value.raw)
        for t in trials
        for field in LONG_TEXT_FIELDS
        if (value := t.display_fields.get(field)) is not None and len(value.raw) >= 12
    ]
    assert canaries, "fixture 須有會被序列化的長文字值，否則這條測不到東西"

    for field, value in canaries:
        assert value not in blob, f"{field} 的內容洩進 trials-index"


def test_conflict_fields_may_still_include_long_text(a_core_rows, build_date):
    """長文字移出 `displayFields` **不得**連帶讓它退出衝突判定。

    §6.4.2 的收斂語意對全部 13 欄計算；卡片仍要顯示「同日多筆資料不一致」，
    只是不顯示候選值。把長文字整個排除在收斂之外會讓衝突被靜默吞掉。
    """
    trials, out = _built(a_core_rows, build_date)
    model_has = any(f in t.conflict_fields for t in trials for f in LONG_TEXT_FIELDS)
    assert model_has, "fixture 須有長文字欄位的同日衝突，否則這條測不到東西"

    serialized = any(
        f in t["conflictFields"] for t in _index(out)["trials"] for f in LONG_TEXT_FIELDS
    )
    assert serialized, "conflictFields 須保留長文字欄位名"


# ---------------------------------------------------------------- manifest 大小欄位

TOP_LEVEL = ("trialsIndex", "stats", "searchShortAll", "searchLongLatest", "searchLongAll")


def test_top_level_files_carry_brotli_bytes(a_core_rows, build_date):
    """§9.3.5：5 個 top-level 檔帶 `brotliBytes`，且它**小於** `gzipBytes`。

    相等代表退回了 gzip 卻仍叫 `brotliBytes`——那比缺欄位更難發現。
    """
    _, out = _built(a_core_rows, build_date)
    files = out.manifest["files"]
    for key in TOP_LEVEL:
        meta = files[key]
        assert "brotliBytes" in meta, key
        assert 0 < meta["brotliBytes"] < meta["gzipBytes"] < meta["bytes"], (key, meta)


def test_shards_do_not_carry_brotli_bytes(a_core_rows, build_date):
    """256 個 shard 不算 brotli：不在 §8.5 的切換器上、也不在 F1 的 Tier 0 內。

    對它們跑 quality 11 會讓月更新多花數分鐘卻沒有任何讀者。
    """
    _, out = _built(a_core_rows, build_date)
    shards = out.manifest["files"]["recordShards"]
    assert shards, "fixture 須產生至少一個 shard"
    for name, meta in shards.items():
        assert "brotliBytes" not in meta, name
        assert meta["gzipBytes"] > 0


def test_tier0_subset_is_exactly_three_files(a_core_rows, build_date):
    """F1 的資料層子集合**恰好等於** manifest ＋ trials-index ＋ stats。

    §9.3.5 的封閉清單；多一個或少一個都使 Tier 0 的量測與規格脫鉤。
    """
    _, out = _built(a_core_rows, build_date)
    files = out.manifest["files"]
    tier0 = {"manifest.json", files["trialsIndex"]["path"], files["stats"]["path"]}
    assert len(tier0) == 3
    assert files["searchShortAll"]["path"] not in tier0
    assert files["searchLongLatest"]["path"] not in tier0
    assert files["searchLongAll"]["path"] not in tier0


# ───────────────────────────────────────────────────────── F2

def test_f2_基線檔存在且以檔案為單位():
    """§11 F2：**以檔案為單位，不以 scope 為單位**。

    scope 的成本由 §8.5 的集合差導出，在基線裡再記一次 scope 數字必然產生
    「總量還是增量」的歧義——v0.8 就是這樣同時存在兩個口徑的。
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    baseline = json.loads((root / "payload-baseline.json").read_text(encoding="utf-8"))

    assert set(baseline["files"]) == {"searchShortAll", "searchLongLatest", "searchLongAll"}
    # 鍵是檔案名而不是 scope 名（`short|all` 之類）
    for key in baseline["files"]:
        assert "|" not in key, f"{key} 看起來是 scope 而不是檔案"
    assert baseline["warnRatio"] == 1.20


def test_f2_超出基線_20_百分比會告警而不是失敗():
    """**告警不是失敗**：上游資料長大是正常的，要的是有人看到並決定，不是擋住月更新。"""
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from scripts.measure_payload import check_on_demand  # noqa: PLC0415

    manifest = json.loads((root / "public" / "data" / "manifest.json").read_text(encoding="utf-8"))
    result = check_on_demand(manifest)
    assert result["status"] == "ok"
    assert len(result["files"]) == 3

    # 目前應無告警（基線就是現況）；ratio 全部在 1.0 附近
    for row in result["files"]:
        assert 0.9 <= row["ratio"] <= 1.1, row

    # **反向哨兵**：把基線壓到現況的一半，三個檔都必須告警
    shrunk = {r["file"]: r["brotliBytes"] // 2 for r in result["files"]}
    fired = [r["file"] for r in result["files"] if r["brotliBytes"] / shrunk[r["file"]] > 1.20]
    assert sorted(fired) == sorted(shrunk), "基線減半後三個檔都該告警"


# ───────────────────────────────────────────── schemaVersion 2 的稀疏 displayFields

def test_稀疏規則_typed_等於_raw_時省略(a_core_rows, build_date):
    """§9.3.3：**只省「可由 raw 無歧義還原」的資訊**。"""
    from trial_radar.artifacts import build_artifacts
    from trial_radar.model import build_trials

    out = build_artifacts(build_trials(list(a_core_rows.values()), build_date), **BUILD_KW)
    trials = out.logical["trials-index.json"]["trials"]

    omitted = kept_null = kept_diff = 0
    for t in trials:
        for field, v in t["displayFields"].items():
            assert "raw" in v, f"{t['id']}/{field} 缺 raw"
            if "typed" not in v:
                # 省略的前提：typed 恰等於 raw（同型別同值）
                omitted += 1
            elif v["typed"] is None:
                kept_null += 1
            else:
                kept_diff += 1
            # flags 為空時不得出現
            assert v.get("flags") != [], f"{t['id']}/{field} 的空 flags 未省略"

    # 三種情形都要在 fixture 裡真的出現，否則這條測不出差別
    assert omitted > 0, "沒有任何欄位被省略，規則等於沒生效"
    assert kept_null > 0, "沒有 typed=null 的欄位，最危險的那一格沒被涵蓋"
    assert kept_diff > 0, "沒有 typed≠raw 的欄位"


def test_稀疏還原_typed_為_null_不得代入_raw(a_core_rows, build_date):
    """**這是 `or` / `??` 會寫錯的那一格。**"""
    from trial_radar.artifacts import build_artifacts, field_typed
    from trial_radar.model import build_trials

    out = build_artifacts(build_trials(list(a_core_rows.values()), build_date), **BUILD_KW)
    trials = out.logical["trials-index.json"]["trials"]

    nulls = [
        (t["id"], f, v)
        for t in trials
        for f, v in t["displayFields"].items()
        if "typed" in v and v["typed"] is None
    ]
    assert nulls, "fixture 須有 typed=null 的欄位"
    for tid, field, v in nulls:
        assert field_typed(v) is None, f"{tid}/{field} 被代入了 raw"
        # 反向：天真的寫法會給出 raw
        assert (v.get("typed") or v["raw"]) == v["raw"], "這正是不能用 `or` 的理由"


def test_稀疏還原_與稠密結果等價(a_core_rows, build_date):
    """還原後的值必須與序列化前的 `FieldValue` 一致。"""
    from trial_radar.artifacts import build_artifacts, field_flags, field_typed
    from trial_radar.model import build_trials

    trials_model = build_trials(list(a_core_rows.values()), build_date)
    out = build_artifacts(trials_model, **BUILD_KW)
    by_id = {t.id: t for t in trials_model}

    for t in out.logical["trials-index.json"]["trials"]:
        model = by_id[t["id"]]
        for field, v in t["displayFields"].items():
            src = model.display_fields[field]
            assert field_typed(v) == src.typed, f"{t['id']}/{field} typed 還原不符"
            assert field_flags(v) == list(src.flags), f"{t['id']}/{field} flags 還原不符"
            assert v["raw"] == src.raw
