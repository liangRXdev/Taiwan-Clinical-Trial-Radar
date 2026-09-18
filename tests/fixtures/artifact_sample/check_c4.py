"""驗收 C1／C3 的資料層斷言，以及 C4 的三個**獨立**反向哨兵。

C4 要求三個 mutation 各自**確為違規**，且**不得**使用「分類 typed value 轉 null」——
那是 §6.6.1 規定的**正確行為**，拿它當 mutation 等於測試在要求實作違反規格。
（第一輪覆審就是在這裡踩過：v0.3 的 C4 第一個 mutation 是合規行為。）

三個 mutation：
1. 分類 sentinel 的 **raw 值遺失** → C1 的 raw 斷言須失敗
2. `stats.json` 的 facet **保留 `"0"`** → C1 的 facet 與 filter 選項斷言須失敗
3. 文字 sentinel 三型**塌成同一值** → C3 須失敗

每個 mutation 都斷言「只有目標那組斷言變紅、其餘仍綠」。否則三個 mutation 不是獨立的，
只實作其中一條檢查的測試也會全過。

**範圍限制**：C1 的第 4／5 處斷言（filter DOM 不含該選項、卡片顯示「未提供」）需要前端，
目前只驗到資料層的等價條件——選項清單的**唯一來源**是 facet buckets、
`displayFields` 帶 `categoricalUnprovided` 旗標供前端直接取用（§6.4.5 要求前端不得重做判定）。
UI 斷言待 M2，這裡不假裝驗過。

跑法：`python tests/fixtures/artifact_sample/check_c4.py`
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sample import build, load_rows  # noqa: E402

CATEGORICAL = ["臨床試驗期別", "本臨床試驗規模"]
FACET_OF = {"臨床試驗期別": "phase", "本臨床試驗規模": "scale"}

failures = []


def check(cond, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        failures.append(msg)


def load(published, manifest):
    index = json.loads(published[manifest["files"]["trialsIndex"]["path"]].decode("utf-8"))
    stats = json.loads(published[manifest["files"]["stats"]["path"]].decode("utf-8"))
    shards = {s: json.loads(published[m["path"]].decode("utf-8"))
              for s, m in manifest["files"]["recordShards"].items()}
    trials = {t["protocolRaw"][0]: t for t in index["trials"]}
    records = {}
    for sh in shards.values():
        records.update(sh["records"])
    return trials, stats, records


def c1_assertions(trials, stats, records):
    """回傳 {斷言 id: bool}。分類欄位各自一組。"""
    out = {}
    t = trials["未列編號"]
    for field in CATEGORICAL:
        df = t["displayFields"][field]
        rid = next(r for r in records if r.startswith(t["id"]))
        facet = stats["facets"][FACET_OF[field]]
        options = [b["value"] for b in facet["buckets"]]  # filter 選項的唯一來源
        out[f"{field}/typed-null"] = df["typed"] is None
        out[f"{field}/raw-preserved"] = (df["raw"] == "0"
                                         and records[rid]["raw"][field] == "0")
        out[f"{field}/facet-excludes-0"] = "0" not in options
        out[f"{field}/filter-options-exclude-0"] = "0" not in options and facet["unprovided"] >= 1
        out[f"{field}/flag-for-ui"] = "categoricalUnprovided" in df["flags"]
    return out


def c3_assertions(trials, records):
    """N/A／NA／空 三型必須互相可區分，且精確對應到 recordId。"""
    want = {"TXT-021A": "N/A", "TXT-021B": "NA", "TXT-021C": ""}
    seen = {}
    for protocol, expected in want.items():
        t = trials[protocol]
        rid = next(r for r in records if r.startswith(t["id"]))
        seen[protocol] = records[rid]["raw"]["排除條件"]
    return {
        "c3/exact-values": seen == want,
        "c3/three-distinct": len(set(seen.values())) == 3,
        "c3/display-raw": all(trials[p]["displayFields"]["排除條件"]["raw"] == v
                              for p, v in want.items()),
    }


def all_assertions(published, manifest):
    trials, stats, records = load(published, manifest)
    a = c1_assertions(trials, stats, records)
    a.update(c3_assertions(trials, records))
    return a


# ---------- C4 的三個 mutation ----------

def _trial(logical, protocol):
    return next(t for t in logical["trials-index.json"]["trials"]
                if t["protocolRaw"][0] == protocol)


def m1_categorical_raw_lost(logical):
    """分類 sentinel 的 raw 值遺失（typed 仍為 null——那部分是合規的）。"""
    t = _trial(logical, "未列編號")
    for field in CATEGORICAL:
        t["displayFields"][field]["raw"] = ""
    shard = logical[f"records/{t['shard']}.json"]
    for rid, rec in shard["records"].items():
        if rid.startswith(t["id"]):
            for field in CATEGORICAL:
                rec["raw"][field] = ""


def m2_facet_keeps_zero(logical):
    """stats.json 的 facet 把 "0" 當成一個正常值留在 buckets 裡。"""
    for facet_name in ("phase", "scale"):
        f = logical["stats.json"]["facets"][facet_name]
        f["buckets"] = f["buckets"] + [{"value": "0", "count": 1}]
        f["unprovided"] = 0  # 維持總和 == denominators.trials，故 §9.3.5 的和仍成立


def m3_text_sentinels_collapsed(logical):
    """N/A／NA／空 三型塌成同一值。"""
    for protocol in ("TXT-021A", "TXT-021B", "TXT-021C"):
        t = _trial(logical, protocol)
        t["displayFields"]["排除條件"]["raw"] = ""
        shard = logical[f"records/{t['shard']}.json"]
        for rid, rec in shard["records"].items():
            if rid.startswith(t["id"]):
                rec["raw"]["排除條件"] = ""


MUTATIONS = [
    ("C4-1 分類 sentinel 的 raw 值遺失", m1_categorical_raw_lost,
     {"臨床試驗期別/raw-preserved", "本臨床試驗規模/raw-preserved"}),
    ("C4-2 stats.json 的 facet 保留 \"0\"", m2_facet_keeps_zero,
     {"臨床試驗期別/facet-excludes-0", "臨床試驗期別/filter-options-exclude-0",
      "本臨床試驗規模/facet-excludes-0", "本臨床試驗規模/filter-options-exclude-0"}),
    ("C4-3 文字 sentinel 三型塌成同一值", m3_text_sentinels_collapsed,
     {"c3/exact-values", "c3/three-distinct", "c3/display-raw"}),
]


def main():
    rows = load_rows()
    _, published, manifest = build(rows)

    print("\n[C1／C3] 未變造的樣本：全部斷言須為真")
    base = all_assertions(published, manifest)
    for k, v in sorted(base.items()):
        check(v, k)

    trials, stats, _ = load(published, manifest)
    for field in CATEGORICAL:
        facet = stats["facets"][FACET_OF[field]]
        total = sum(b["count"] for b in facet["buckets"]) + facet["unprovided"] + facet["conflicted"]
        check(total == stats["denominators"]["trials"],
              f"{field} 的 facet 總和 == denominators.trials（§9.3.5）")

    print("\n[C4] 三個 mutation 各自**確為違規**且**互相獨立**")
    for label, mutate, expected_failing in MUTATIONS:
        _, pub, man = build(rows, mutate=mutate)
        after = all_assertions(pub, man)
        broke = {k for k, v in after.items() if not v}
        check(broke == expected_failing,
              f"{label} → 轉紅的斷言恰為 {sorted(expected_failing)}"
              + ("" if broke == expected_failing else f"（實際 {sorted(broke)}）"))

    print("\n[C4] 反向查核：規格規定的**正確行為**不得被當成 mutation")
    _, pub, man = build(rows)
    trials2, _, _ = load(pub, man)
    check(all(trials2["未列編號"]["displayFields"][f]["typed"] is None for f in CATEGORICAL),
          "分類 sentinel 的 typed 本來就是 null（§6.6.1）"
          "——把它「轉成 null」當 mutation 會是測試在要求實作違反規格")

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
