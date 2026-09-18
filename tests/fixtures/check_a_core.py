"""驗證 a_core fixture 真的含有 oracle 宣稱的案例。

**這不是 ETL 實作，也不是 oracle 的替代品。** 它只檢查 fixture **資料本身**的性質
（哪些列逐位元相同、哪些列正規化後相同、各類異常的列數），不計算 Trial 模型、
不做 identity 收斂、不算 cohort——那些是 oracle 手寫、將來由實作去對的。

存在的理由：fixture 最常見的失效方式是「宣稱含某案例但其實沒有」，
而那種失效在實作寫出來以前不會被發現。A2 要求每個案例都附 oracle，
這支腳本確保 oracle 指的案例在資料裡真的存在。

跑法：`python tests/fixtures/check_a_core.py`

註：本檔 [2] 的分類仍以「比較正規化 raw」實作，那是 v0.4 的規則。v0.5 §6.4.2 已改為
semantic comparison key（依欄位型別與語意狀態）。兩者對本 fixture 的分類結果相同
（NUM-022 兩種規則下都是衝突），故暫不改；待 M0.5 補 numericRange 案例時一併改為比較鍵。
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "a_core")

DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
BUILD_DATE = (2026, 9, 18)  # 與 oracle.harness.buildDate 一致

# §6.4 的封閉呈現欄位集合（16 欄扣除 protocol、收文號、資料更新時間）
PRESENTATION_FIELDS = [
    "臨床試驗申請者", "臨床試驗計畫中文名稱", "臨床試驗期別", "本臨床試驗規模",
    "試驗目的", "試驗預計執行期間起", "試驗預計執行期間迄", "全球預計受試者人數",
    "台灣預計受試者人數", "適應症中文", "主要評估指標", "納入條件", "排除條件",
]

failures = []
notes = []


def check(cond, msg):
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        failures.append(msg)


def norm_conflict(s):
    """§6.4 的衝突比較：NFKC + 移除全部空白。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def parse_date(s):
    m = DATE_RE.match(s or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        import datetime
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def date_class(s):
    """回傳 §6.5 的日期分級。"""
    if (s or "").strip() == "":
        return "dateMissing"
    d = parse_date(s)
    if d is None:
        return "dateUnparsed"
    import datetime
    if d > datetime.date(*BUILD_DATE):
        return "dateFuture"
    return "ok"


def main():
    rows = json.load(open(os.path.join(CORE, "rows.json"), encoding="utf-8"))["rows"]
    oracle = json.load(open(os.path.join(CORE, "oracle.json"), encoding="utf-8"))

    print(f"\n[0] 基本盤")
    check(len(rows) == oracle["totals"]["recordCount"],
          f"列數 {len(rows)} == oracle recordCount {oracle['totals']['recordCount']}")

    # oracle 宣稱的 rowKey 全部存在，且沒有列被遺漏
    claimed = set()
    for t in oracle["trials"]:
        claimed.update(t["rowKeys"])
    check(claimed == set(rows), f"oracle 涵蓋全部 {len(rows)} 個 rowKey，無遺漏無多餘"
          + ("" if claimed == set(rows) else f"（缺 {sorted(set(rows)-claimed)}，多 {sorted(claimed-set(rows))}）"))

    # 每列只屬於一個 trial（A5：multiset 不得錯置）
    seen = {}
    dup = []
    for t in oracle["trials"]:
        for k in t["rowKeys"]:
            if k in seen:
                dup.append(k)
            seen[k] = t["label"]
    check(not dup, f"每個 rowKey 只屬於一個 trial{'' if not dup else f'（重複：{dup}）'}")

    print(f"\n[1] A2 必含案例")

    # ≥1 個 10 列以上的 protocol
    big = [t for t in oracle["trials"] if t.get("recordCount", 0) >= 10]
    check(len(big) >= 1, f"≥1 個 10 列以上的 protocol（實際 {[ (t['label'], t['recordCount']) for t in big ]}）")

    # ≥1 組 16 欄全同的純重複
    def sig(k):
        return tuple(rows[k].values())
    byte_groups = []
    for t in oracle["trials"]:
        for g in t.get("byteIdenticalRowGroups", []) or []:
            byte_groups.append(g)
        if t.get("label") == "EMPTY-DUP":
            byte_groups.append(t["rowKeys"])
    ok_byte = all(len({sig(k) for k in g}) == 1 for g in byte_groups)
    check(byte_groups and ok_byte,
          f"oracle 宣稱的 {len(byte_groups)} 組逐位元相同，資料確實相同")

    # ≥2 筆完全相同的空 protocol 列
    empties = [k for k in rows if rows[k]["臨床試驗計畫書編號"] == ""]
    empty_sigs = {}
    for k in empties:
        empty_sigs.setdefault(sig(k), []).append(k)
    identical_empty = [g for g in empty_sigs.values() if len(g) >= 2]
    check(identical_empty, f"≥2 筆完全相同的空 protocol 列（實際 {identical_empty}）")
    check(len(empties) == 3, f"空 protocol 列共 3 筆（2 相同 + 1 獨特），實際 {len(empties)}")

    # 同日 cohort 的衝突／不衝突分類
    print(f"\n[2] 同日 cohort 分類（§6.4 的正規化比較）")
    by_proto = {}
    for k, r in rows.items():
        p = r["臨床試驗計畫書編號"]
        if p:
            by_proto.setdefault(p, []).append(k)

    conflict_groups, identical_groups, ws_only_groups = [], [], []
    for p, ks in by_proto.items():
        # 取可採計日期最大者（僅為分類 fixture 用，非實作）
        usable = [(parse_date(rows[k]["資料更新時間"]), k) for k in ks
                  if date_class(rows[k]["資料更新時間"]) == "ok"]
        if not usable:
            continue
        mx = max(d for d, _ in usable)
        cohort = [k for d, k in usable if d == mx]
        if len(cohort) < 2:
            continue
        raw_diff = any(len({rows[k][f] for k in cohort}) > 1 for f in PRESENTATION_FIELDS)
        nrm_diff = any(len({norm_conflict(rows[k][f]) for k in cohort}) > 1 for f in PRESENTATION_FIELDS)
        if nrm_diff:
            conflict_groups.append(p)
        elif raw_diff:
            ws_only_groups.append(p)
        else:
            identical_groups.append(p)

    check(len(conflict_groups) >= 3,
          f"≥3 組同日且正規化後仍衝突（實際 {sorted(conflict_groups)}）")
    check(len(identical_groups) >= 1,
          f"≥1 組同日且正規化後全同（實際 {sorted(identical_groups)}）")
    check(len(ws_only_groups) >= 1,
          f"≥1 組同日僅空白／全半形差異，須判為不衝突（實際 {sorted(ws_only_groups)}）")

    # WS-003 的 GAP-1：不衝突但 raw 不同
    if "WS-003" in ws_only_groups:
        ks = [k for k in by_proto["WS-003"]]
        diff_fields = [f for f in PRESENTATION_FIELDS if len({rows[k][f] for k in ks}) > 1]
        notes.append(f"GAP-1（已修）觸發確認：WS-003 比較鍵相同但 raw 在 {diff_fields} 上不同"
                     f"——v0.5 §6.4.3 規定該欄位加 rawVariants、代表值取 recordId 字典序最小者")

    print(f"\n[3] §6.5 日期異常四類")
    counts = {"dateMissing": 0, "dateUnparsed": 0, "dateFuture": 0}
    for k, r in rows.items():
        c = date_class(r["資料更新時間"])
        if c in counts:
            counts[c] += 1
    exp = oracle["qualityReportExpectations"]["dateAnomalyCounts"]
    for cls in ("dateUnparsed", "dateMissing", "dateFuture"):
        check(counts[cls] == exp[cls], f"{cls} 列數 {counts[cls]} == oracle {exp[cls]}")

    # end < start
    end_lt = []
    for k, r in rows.items():
        a, b = parse_date(r["試驗預計執行期間起"]), parse_date(r["試驗預計執行期間迄"])
        if a and b and b < a:
            end_lt.append(k)
    check(len(end_lt) == exp["periodEndBeforeStart"],
          f"end<start 列數 {len(end_lt)} == oracle {exp['periodEndBeforeStart']}（{end_lt}）")

    # 全部日期不可採計的 protocol
    all_bad = [p for p, ks in by_proto.items()
               if all(date_class(rows[k]["資料更新時間"]) != "ok" for k in ks)]
    check(len(all_bad) >= 2, f"≥2 個 protocol 全部日期不可採計（dateUnknown，實際 {sorted(all_bad)}）")

    print(f"\n[4] §6.6 數值與分類 sentinel")
    nexp = oracle["qualityReportExpectations"]["numericAnomalyCounts"]
    NUM = ["全球預計受試者人數", "台灣預計受試者人數"]
    ncnt = {"sourceZero": 0, "numericMissing": 0, "numericUnparsed": 0, "numericImplausible": 0}
    for k, r in rows.items():
        for f in NUM:
            v = (r[f] or "").strip()
            if v == "":
                ncnt["numericMissing"] += 1
            elif re.fullmatch(r"\d+", v):
                if int(v) == 0:
                    ncnt["sourceZero"] += 1
            elif re.fullmatch(r"-\d+", v):
                ncnt["numericImplausible"] += 1
            else:
                ncnt["numericUnparsed"] += 1
    for cls in ncnt:
        check(ncnt[cls] == nexp[cls], f"{cls} 欄位數 {ncnt[cls]} == oracle {nexp[cls]}")

    cexp = oracle["qualityReportExpectations"]["categoricalSentinelCounts"]
    for f in ("臨床試驗期別", "本臨床試驗規模"):
        c = sum(1 for r in rows.values() if (r[f] or "").strip() == "0")
        check(c == cexp[f], f"{f} 的 \"0\" sentinel 列數 {c} == oracle {cexp[f]}")

    print(f"\n[5] 文字 sentinel 三型可區分（C3）")
    texp = oracle["qualityReportExpectations"]["textSentinelCounts"]["排除條件"]
    tcnt = {"N/A": 0, "NA": 0, "empty": 0}
    for r in rows.values():
        v = r["排除條件"]
        if v == "N/A":
            tcnt["N/A"] += 1
        elif v == "NA":
            tcnt["NA"] += 1
        elif v == "":
            tcnt["empty"] += 1
    for cls in tcnt:
        check(tcnt[cls] == texp[cls], f"排除條件 {cls!r} 列數 {tcnt[cls]} == oracle {texp[cls]}")

    print(f"\n[6] §6.2.1 nearDuplicateGroup 與 §6.2.2 protocolNonIdentifier")

    def loose(p):
        return re.sub(r"[^0-9A-Za-z]", "", p).upper()

    def ident(p):
        return unicodedata.normalize("NFKC", (p or "").strip()).upper()

    groups = {}
    for p in by_proto:
        lk = loose(p)
        if lk:
            groups.setdefault(lk, set()).add(p)
    near = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    print(f"        實際 nearDuplicateGroup: {json.dumps(near, ensure_ascii=False)}")
    exp_near = {k: sorted(v) for k, v in oracle["nearDuplicateGroups"].items()
                if not k.startswith("_")}
    check(near == exp_near, "nearDuplicateGroup 與 oracle 完全相符"
          + ("" if near == exp_near else f"（oracle {exp_near}）"))

    # identity 不折疊近似寫法（A1 的「不應合併」）
    for lk, ps in near.items():
        idents = {ident(p) for p in ps}
        check(len(idents) == len(ps),
              f"loose key {lk} 的 {len(ps)} 個 protocol 在 identity 正規化後仍相異（不得合併）")

    # 沒有任何 identity 碰撞（a_core 是正常路徑，碰撞歸 a7）
    id_map = {}
    for p in by_proto:
        id_map.setdefault(ident(p), []).append(p)
    coll = {k: v for k, v in id_map.items() if len(v) > 1}
    check(not coll, f"a_core 無 identity 碰撞（碰撞案例歸 a7 fixture）{'' if not coll else coll}")

    nonid_rows = [k for k, r in rows.items()
                  if not re.search(r"[0-9A-Za-z]", r["臨床試驗計畫書編號"] or "")]
    pexp = oracle["qualityReportExpectations"]["protocolNonIdentifierRowCount"]
    check(len(nonid_rows) == pexp,
          f"protocolNonIdentifier 列數 {len(nonid_rows)} == oracle {pexp}（{sorted(nonid_rows)}）")
    notes.append(f"GAP-4（已修）觸發確認：{len(nonid_rows)} 列中 {len(empties)} 列是空 protocol、"
                 f"{len(nonid_rows)-len(empties)} 列是非空但無 ASCII 英數字元。"
                 f"v0.5 §6.2.2 定案兩者皆算，故計數為 {pexp}")

    # loose key 為空者不得成群（§6.2.1 第 4 點）
    empty_loose = [p for p in by_proto if not loose(p)]
    check(all(loose(p) not in near for p in empty_loose),
          f"loose key 為空的 protocol 不成群（{sorted(empty_loose)}）")

    print(f"\n[7] GAP-5 觸發確認（衝突比較套用於數值欄位）")
    gap5 = []
    for p, ks in by_proto.items():
        usable = [(parse_date(rows[k]["資料更新時間"]), k) for k in ks
                  if date_class(rows[k]["資料更新時間"]) == "ok"]
        cohort = [k for d, k in usable if usable and d == max(x for x, _ in usable)] if usable else []
        if len(cohort) < 2:
            # dateUnknown 的 trial 用全部列
            if all(date_class(rows[k]["資料更新時間"]) != "ok" for k in ks) and len(ks) >= 2:
                cohort = ks
            else:
                continue
        for f in NUM:
            vals = {rows[k][f] for k in cohort}
            if len(vals) > 1:
                def typed(v):
                    v = (v or "").strip()
                    return int(v) if re.fullmatch(r"\d+", v) else None
                if len({typed(v) for v in vals}) == 1:
                    gap5.append((p, f, sorted(vals)))
    if gap5:
        notes.append(f"GAP-5（建議被否決）觸發：{gap5} —— typed 皆 null 但語意狀態不同"
                     f"（numericMissing vs numericImplausible）。v0.5 §6.4.2 的 semantic comparison key "
                     f"使其**維持衝突**；原提議「typed 皆 null 即不衝突」會隱藏異常，比假警報更糟")
    else:
        notes.append("GAP-5 的案例不在本 fixture 中：需一組「同日兩列、同一數值欄位 raw 不同"
                     "但 typed 皆為 null」的案例（例如一列 \"\" 一列 \"-5\"）")

    print()
    for n in notes:
        print(f"  NOTE  {n}")

    print(f"\n{'='*60}")
    if failures:
        print(f"FAIL：{len(failures)} 項不符")
        for f in failures:
            if f:
                print(f"  - {f}")
        return 1
    print("全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
