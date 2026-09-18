"""驗證 a_core fixture 真的含有 oracle 宣稱的案例。

**這不是 ETL 實作，也不是 oracle 的替代品。** 它只檢查 fixture **資料本身**的性質
（哪些列逐位元相同、哪些列依比較鍵相同、各類異常的列數），不計算 Trial 模型、
不做 identity 收斂、不產出 artifact——那些是 oracle 手寫、將來由實作去對的。

存在的理由：fixture 最常見的失效方式是「宣稱含某案例但其實沒有」，
而那種失效在實作寫出來以前不會被發現。A2 要求每個案例都附 oracle，
這支腳本確保 oracle 指的案例在資料裡真的存在。

v0.6 對齊：
- [2] 的同日分類改用 §6.4.2 的 **semantic comparison key**（依欄位型別與語意狀態），
  取代 v0.4 的「比正規化 raw」。
- [4] 的數值分類改用 §6.6.3 的**完整 lexical grammar 與解析順序**
  （含 numericRange／numericRangeInvalid／numericOutOfRange）。
- v0.6 §6.4.2 補上三個原本未涵蓋的語意狀態（GAP-8 結案）。比較鍵的 dispatch 為**窮盡**，
  表外狀態一律 `raise`——**不得 fallback 到「比 raw」或「視為相等」**，
  那會把規格缺口變成一個看不見的行為。

跑法：`python tests/fixtures/check_a_core.py`
"""
import datetime
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "a_core")

DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
BUILD_DATE = datetime.date(2026, 9, 18)  # 與 oracle.harness.buildDate 一致
MAX_SAFE_INT = 2 ** 53 - 1  # §6.6.3 可表示範圍上限

# §6.4.1 的封閉呈現欄位集合（16 欄扣除 protocol、收文號、資料更新時間）
TEXT_FIELDS = [
    "臨床試驗申請者", "臨床試驗計畫中文名稱", "試驗目的",
    "適應症中文", "主要評估指標", "納入條件", "排除條件",
]
CATEGORICAL_FIELDS = ["臨床試驗期別", "本臨床試驗規模"]
NUMERIC_FIELDS = ["全球預計受試者人數", "台灣預計受試者人數"]
PERIOD_FIELDS = ["試驗預計執行期間起", "試驗預計執行期間迄"]
PRESENTATION_FIELDS = (
    TEXT_FIELDS + CATEGORICAL_FIELDS + NUMERIC_FIELDS + PERIOD_FIELDS
)
assert len(PRESENTATION_FIELDS) == 13

# §6.6.1 合法值
LEGAL_CATEGORICAL = {
    "臨床試驗期別": {
        "Phase Ⅰ", "Phase Ⅱ", "Phase Ⅲ", "Phase Ⅳ",
        "Phase Ⅰ,Phase Ⅱ", "Phase Ⅱ,Phase Ⅲ", "其他",
    },
    "本臨床試驗規模": {"多國多中心", "台灣單中心", "台灣多中心"},
}

# §6.6.3 序 3／4 的範圍文法（比對對象為 nfkc(strip(raw))）
RANGE_RE = re.compile(r"^(\d+)\s*(?:[-~～〜–—]|至)\s*(\d+)$")

failures = []
notes = []
spec_gaps = []


def check(cond, msg):
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        failures.append(msg)


# ---------- §6.0 基礎定義 ----------

def nfkc(s):
    return unicodedata.normalize("NFKC", s or "")


def identity_normalize(s):
    return nfkc((s or "").strip()).upper()


def loose_key(s):
    return re.sub(r"[^0-9A-Za-z]", "", nfkc(s)).upper()


def conflict_text(s):
    """§6.0 conflictText：nfkc 後移除全部空白（含全形空白）。"""
    return re.sub(r"\s+", "", nfkc(s))


def parse_date(s):
    m = DATE_RE.match(nfkc(s or "").strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def date_class(s):
    """§6.5.2 的 `資料更新時間` 分級。"""
    if (s or "").strip() == "":
        return "dateMissing"
    d = parse_date(s)
    if d is None:
        return "dateUnparsed"
    if d > BUILD_DATE:
        return "dateFuture"
    return "ok"


# ---------- §6.6.3 數值 lexical grammar ----------

def numeric_state(raw):
    """回傳 (state, payload, flags)。state 為 §6.6.3 的解析結果分類。

    v0.6 §6.6.3 分兩階段：階段一為序 1–6，階段二為後置的可表示範圍檢查（只在序 2／3
    命中時套用）。單端超界時**整個** typed 為 null，旗標為 numericRange ＋ numericOutOfRange。
    """
    v = nfkc((raw or "").strip())
    if v == "":
        return ("numericMissing", None, ["numericMissing"])
    if re.fullmatch(r"\d+", v):
        n = int(v)
        if n > MAX_SAFE_INT:
            return ("numericOutOfRange", None, ["numericOutOfRange"])
        return ("int", n, ["sourceZero"] if n == 0 else [])
    m = RANGE_RE.match(v)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= hi:
            if hi > MAX_SAFE_INT or lo > MAX_SAFE_INT:
                # v0.6 §6.6.3 階段二：任一端超界 → 整個 typed 為 null（不留半個區間）
                return ("numericOutOfRange", None, ["numericRange", "numericOutOfRange"])
            return ("range", (lo, hi), ["numericRange"])
        return ("numericRangeInvalid", None, ["numericRangeInvalid"])
    if re.fullmatch(r"-\d+", v):
        return ("numericImplausible", None, ["numericImplausible"])
    return ("numericUnparsed", None, ["numericUnparsed"])


def categorical_state(field, raw):
    v = (raw or "").strip()
    if v == "0":
        return ("categoricalUnprovided", None)
    if v in LEGAL_CATEGORICAL[field]:
        return ("cat", v)
    return ("categoricalUnknown", v)


# ---------- §6.4.2 semantic comparison key ----------

SPEC_GAP = "__SPEC_GAP__"

# v0.6 §6.4.2 須涵蓋 §9.3.3 旗標封閉集合的每一個狀態（rawVariants 除外——它是比較的
# **結果**不是輸入）。四個 typed 為 null 的數值異常狀態皆採 (旗標名, conflictText(raw))。
NULL_TYPED_NUMERIC_STATES = (
    "numericUnparsed", "numericImplausible", "numericRangeInvalid", "numericOutOfRange",
)


def comparison_key(field, raw):
    """§6.4.2 的比較鍵。**窮盡 dispatch**：表外狀態一律 raise，不 fallback。"""
    if field in TEXT_FIELDS:
        return ("text", conflict_text(raw))

    if field in CATEGORICAL_FIELDS:
        st, val = categorical_state(field, raw)
        if st == "categoricalUnprovided":
            return ("unprovided",)
        if st == "cat":
            return ("cat", val)
        if st == "categoricalUnknown":
            return ("categoricalUnknown", conflict_text(raw))
        raise AssertionError(f"§6.4.2 未涵蓋的分類狀態：{st}")

    if field in NUMERIC_FIELDS:
        st, payload, _ = numeric_state(raw)
        if st == "int":
            return ("int", payload)
        if st == "range":
            return ("range", payload[0], payload[1])
        if st == "numericMissing":
            return ("numericMissing",)
        if st in NULL_TYPED_NUMERIC_STATES:
            return (st, conflict_text(raw))
        raise AssertionError(f"§6.4.2 未涵蓋的數值狀態：{st}")

    # PERIOD_FIELDS
    d = parse_date(raw)
    if d is not None:
        return ("date", d.isoformat())
    flag = ("periodStart" if field.endswith("起") else "periodEnd") + (
        "Missing" if (raw or "").strip() == "" else "Unparsed"
    )
    return (flag, conflict_text(raw))


def main():
    rows = json.load(open(os.path.join(CORE, "rows.json"), encoding="utf-8"))["rows"]
    oracle = json.load(open(os.path.join(CORE, "oracle.json"), encoding="utf-8"))

    print("\n[0] 基本盤")
    check(len(rows) == oracle["totals"]["recordCount"],
          f"列數 {len(rows)} == oracle recordCount {oracle['totals']['recordCount']}")

    claimed = set()
    for t in oracle["trials"]:
        claimed.update(t["rowKeys"])
    check(claimed == set(rows), f"oracle 涵蓋全部 {len(rows)} 個 rowKey，無遺漏無多餘"
          + ("" if claimed == set(rows)
             else f"（缺 {sorted(set(rows)-claimed)}，多 {sorted(claimed-set(rows))}）"))

    seen, dup = {}, []
    for t in oracle["trials"]:
        for k in t["rowKeys"]:
            if k in seen:
                dup.append(k)
            seen[k] = t["label"]
    check(not dup, f"每個 rowKey 只屬於一個 trial{'' if not dup else f'（重複：{dup}）'}")
    # EMPTY-DUP 一個 oracle 條目展開為 2 個 Trial（兩列逐位元相同、序號 #0／#1）
    expanded = sum(t.get("expandsToTrialCount", 1) for t in oracle["trials"])
    check(expanded == oracle["totals"]["trialCount"],
          f"oracle trials 展開後 {expanded} == totals.trialCount "
          f"{oracle['totals']['trialCount']}")

    print("\n[1] A2 必含案例")

    def sig(k):
        return tuple(rows[k].values())

    big = [t for t in oracle["trials"] if t.get("recordCount", 0) >= 10]
    check(len(big) >= 1,
          f"≥1 個 10 列以上的 protocol（實際 {[(t['label'], t['recordCount']) for t in big]}）")

    byte_groups = []
    for t in oracle["trials"]:
        for g in t.get("byteIdenticalRowGroups", []) or []:
            byte_groups.append(g)
    ok_byte = all(len({sig(k) for k in g}) == 1 for g in byte_groups)
    check(byte_groups and ok_byte,
          f"oracle 宣稱的 {len(byte_groups)} 組逐位元相同，資料確實相同")

    empties = [k for k in rows if rows[k]["臨床試驗計畫書編號"] == ""]
    empty_sigs = {}
    for k in empties:
        empty_sigs.setdefault(sig(k), []).append(k)
    identical_empty = [g for g in empty_sigs.values() if len(g) >= 2]
    check(identical_empty, f"≥2 筆完全相同的空 protocol 列（實際 {identical_empty}）")
    check(len(empties) == 3, f"空 protocol 列共 3 筆（2 相同 + 1 獨特），實際 {len(empties)}")

    # v0.5 §6.3.1：空白-only protocol 走 H: 分支（identityNormalize 後為空，但 raw 非空）
    ws_only = [k for k in rows
               if rows[k]["臨床試驗計畫書編號"] != ""
               and identity_normalize(rows[k]["臨床試驗計畫書編號"]) == ""]
    check(len(ws_only) >= 1,
          f"≥1 筆空白-only protocol（raw 非空但 identityNormalize 後為空）：{sorted(ws_only)}")
    check(all(loose_key(rows[k]["臨床試驗計畫書編號"]) == "" for k in ws_only),
          "空白-only protocol 的 looseKey 亦為空（§6.2.2 須標 protocolNonIdentifier）")
    raws = {rows[k]["臨床試驗計畫書編號"] for k in ws_only}
    check(len(raws) == len(ws_only),
          f"空白-only 各列的 raw 互不相同（證明 raw 完整保留供稽核）：{sorted(map(repr, raws))}")

    print("\n[2] 同日 cohort 分類（§6.4.2 semantic comparison key）")
    # 只把 identityNormalize 後非空的 protocol 成組；空與空白-only 走 §6.3.1 的 H: 分支，
    # 各自依內容雜湊成 Trial，不能用 raw protocol 當分組鍵。
    by_proto = {}
    for k, r in rows.items():
        p = r["臨床試驗計畫書編號"]
        if identity_normalize(p):
            by_proto.setdefault(p, []).append(k)

    def cohort_of(ks):
        """回傳 (cohort rowKeys, dateUnknown)。僅供 fixture 分類，非實作。"""
        usable = [(parse_date(rows[k]["資料更新時間"]), k) for k in ks
                  if date_class(rows[k]["資料更新時間"]) == "ok"]
        if not usable:
            return ks, True
        mx = max(d for d, _ in usable)
        return [k for d, k in usable if d == mx], False

    conflict_groups, identical_groups, key_same_raw_diff = [], [], []
    gap_dependent_groups = []
    for p, ks in by_proto.items():
        cohort, unknown = cohort_of(ks)
        if len(cohort) < 2:
            continue
        conflicted, raw_variant_fields, gap_fields = [], [], []
        for f in PRESENTATION_FIELDS:
            keys = {comparison_key(f, rows[k][f]) for k in cohort}
            if len(keys) > 1:
                conflicted.append(f)
            elif len({rows[k][f] for k in cohort}) > 1:
                raw_variant_fields.append(f)
        if gap_fields:
            gap_dependent_groups.append((p, gap_fields))
        elif conflicted:
            conflict_groups.append((p, conflicted))
        elif raw_variant_fields:
            key_same_raw_diff.append((p, raw_variant_fields))
        else:
            identical_groups.append(p)

    check(len(conflict_groups) >= 3,
          f"≥3 組同日且比較鍵不同（衝突）：{sorted(p for p, _ in conflict_groups)}")
    check(len(identical_groups) >= 1,
          f"≥1 組同日且比較鍵全同且 raw 亦全同：{sorted(identical_groups)}")
    check(len(key_same_raw_diff) >= 1,
          f"≥1 組同日比較鍵相同但 raw 不同（須不衝突且帶 rawVariants）："
          f"{sorted((p, fs) for p, fs in key_same_raw_diff)}")

    exp_conf = {p: sorted(fs) for p, fs in
                oracle["cohortClassification"]["conflicting"].items()}
    act_conf = {p: sorted(fs) for p, fs in conflict_groups}
    check(act_conf == exp_conf, "衝突組與衝突欄位與 oracle 完全相符"
          + ("" if act_conf == exp_conf else f"\n         實際 {json.dumps(act_conf, ensure_ascii=False)}"
                                             f"\n         oracle {json.dumps(exp_conf, ensure_ascii=False)}"))

    exp_rv = {p: sorted(fs) for p, fs in
              oracle["cohortClassification"]["rawVariantsOnly"].items()}
    act_rv = {p: sorted(fs) for p, fs in key_same_raw_diff}
    check(act_rv == exp_rv, "rawVariants 組與欄位與 oracle 完全相符"
          + ("" if act_rv == exp_rv else f"\n         實際 {json.dumps(act_rv, ensure_ascii=False)}"
                                         f"\n         oracle {json.dumps(exp_rv, ensure_ascii=False)}"))

    exp_ident = sorted(oracle["cohortClassification"]["allIdentical"])
    check(sorted(identical_groups) == exp_ident,
          f"比較鍵與 raw 全同的組與 oracle 相符（實際 {sorted(identical_groups)}）")

    # C5 的四個逐型別案例
    print("\n[2b] C5 semantic comparison key 逐型別")
    c5 = oracle["comparisonKeyCases"]
    for case in c5:
        f = case["field"]
        ka = comparison_key(f, case["a"])
        kb = comparison_key(f, case["b"])
        if case["expect"] == "conflict":
            check(ka != kb, f"{case['label']}：{case['a']!r} vs {case['b']!r} → 比較鍵不同（衝突）")
        elif case["expect"] == "same":
            check(ka == kb and case["a"] != case["b"],
                  f"{case['label']}：{case['a']!r} vs {case['b']!r} → 比較鍵相同且 raw 不同"
                  f"（不衝突 + rawVariants）")
        else:
            raise AssertionError(f"未知的 expect：{case['expect']}")

    print("\n[3] §6.5 日期異常")
    counts = {"dateMissing": 0, "dateUnparsed": 0, "dateFuture": 0, "ok": 0}
    for r in rows.values():
        counts[date_class(r["資料更新時間"])] += 1
    exp = oracle["qualityReportExpectations"]["dateAnomalyCounts"]
    for cls in ("dateUnparsed", "dateMissing", "dateFuture"):
        check(counts[cls] == exp[cls], f"{cls} 列數 {counts[cls]} == oracle {exp[cls]}")

    # buildDate 邊界（§6.5.2）
    on_build = [k for k, r in rows.items()
                if parse_date(r["資料更新時間"]) == BUILD_DATE]
    plus_one = [k for k, r in rows.items()
                if parse_date(r["資料更新時間"]) == BUILD_DATE + datetime.timedelta(days=1)]
    check(on_build, f"≥1 筆 資料更新時間 == buildDate（須可採計）：{sorted(on_build)}")
    check(all(date_class(rows[k]["資料更新時間"]) == "ok" for k in on_build),
          "buildDate 當日判為可採計（非 dateFuture）")
    check(plus_one, f"≥1 筆 資料更新時間 == buildDate+1（須 dateFuture）：{sorted(plus_one)}")
    check(all(date_class(rows[k]["資料更新時間"]) == "dateFuture" for k in plus_one),
          "buildDate+1 判為 dateFuture")
    # 該 Trial 的 cohort 不得含 +1 日那列
    for k in plus_one:
        p = rows[k]["臨床試驗計畫書編號"]
        if p and len(by_proto.get(p, [])) > 1:
            cohort, _ = cohort_of(by_proto[p])
            check(k not in cohort,
                  f"{p} 的 latest cohort 不含 dateFuture 列 {k}（未來日期不得支配卡片）")

    # 期間欄位（§6.5.3）
    end_lt, period_flags = [], {}
    for k, r in rows.items():
        a, b = parse_date(r["試驗預計執行期間起"]), parse_date(r["試驗預計執行期間迄"])
        if a and b and b < a:
            end_lt.append(k)
        for f in PERIOD_FIELDS:
            key = comparison_key(f, r[f])
            if key[0] != "date":
                period_flags.setdefault(key[0], []).append(k)
    check(len(end_lt) == exp["periodEndBeforeStart"],
          f"end<start 列數 {len(end_lt)} == oracle {exp['periodEndBeforeStart']}（{end_lt}）")
    pexp = exp["periodFieldAnomalies"]
    for flag in ("periodStartUnparsed", "periodEndMissing"):
        got = sorted(period_flags.get(flag, []))
        check(got == sorted(pexp[flag]), f"{flag} 列 {got} == oracle {sorted(pexp[flag])}")
    check(not any(k in end_lt for k in
                  period_flags.get("periodStartUnparsed", []) + period_flags.get("periodEndMissing", [])),
          "任一端不可解析／缺值者不得同時判為 end<start（§6.5.3 只在兩端皆可解析時比較）")

    all_bad = [p for p, ks in by_proto.items()
               if all(date_class(rows[k]["資料更新時間"]) != "ok" for k in ks)]
    check(len(all_bad) >= 2, f"≥2 個 protocol 全部日期不可採計（dateUnknown）：{sorted(all_bad)}")

    print("\n[4] §6.6.3 數值 lexical grammar 與解析順序")
    nexp = oracle["qualityReportExpectations"]["numericStateCounts"]
    ncnt = {}
    by_state = {}
    for k, r in rows.items():
        for f in NUMERIC_FIELDS:
            st, payload, flags = numeric_state(r[f])
            for fl in flags:
                ncnt[fl] = ncnt.get(fl, 0) + 1
            if st == "int" and payload == 0:
                st = "sourceZero"
            by_state.setdefault(st, []).append((k, f, r[f]))
            ncnt.setdefault("_state_" + st, 0)
            ncnt["_state_" + st] += 1
    for state, want in nexp.items():
        if state.startswith("_"):
            continue
        got = ncnt.get("_state_" + state, 0)
        check(got == want, f"numeric state {state} 欄位出現次數 {got} == oracle {want}")
    total_fields = len(rows) * len(NUMERIC_FIELDS)
    check(sum(v for k, v in nexp.items() if not k.startswith("_")) == total_fields,
          f"oracle 的八類數值狀態總和 == 欄位出現次數 {total_fields}（互斥且窮盡）")

    # C2 要求的每一型至少各一
    for state in ("numericMissing", "int", "sourceZero", "range", "numericRangeInvalid",
                  "numericImplausible", "numericUnparsed", "numericOutOfRange"):
        check(state in by_state, f"C2 必含數值型別 {state} 至少一筆"
              + (f"（{by_state[state][0][2]!r}）" if state in by_state else ""))

    # 前導零：typed 為 26 但 raw 須保留 026
    lead_zero = [(k, f, v) for k, f, v in
                 [(k, f, r[f]) for k, r in rows.items() for f in NUMERIC_FIELDS]
                 if re.fullmatch(r"0\d+", v)]
    check(lead_zero, f"≥1 筆前導零（C2 要求 raw 顯示 026 而非 26）：{lead_zero}")
    for k, f, v in lead_zero:
        st, payload, _ = numeric_state(v)
        check(st == "int" and payload == int(v) and rows[k][f] == v,
              f"前導零 {v!r} → typed {payload}，raw 在 rows.json 中仍為 {v!r}")

    # 約略值不得被讀成數字（§6.6.3 的紀律）
    approx = [(k, f, r[f]) for k, r in rows.items() for f in NUMERIC_FIELDS
              if re.search(r"約|至少", nfkc(r[f]))]
    check(approx, f"≥1 筆約略值：{approx}")
    for k, f, v in approx:
        st, _, _ = numeric_state(v)
        check(st == "numericUnparsed", f"約略值 {v!r} 維持 numericUnparsed（不推論為數字）")

    # 超界值
    over = [(k, f, r[f]) for k, r in rows.items() for f in NUMERIC_FIELDS
            if numeric_state(r[f])[0] == "numericOutOfRange"]
    for k, f, v in over:
        check(numeric_state(v)[1] is None,
              f"超界值 {v!r} 的 typed 為 null（不得輸出失真數字）")

    print("\n[5] §6.6.1 分類 sentinel 與非合法值")
    cexp = oracle["qualityReportExpectations"]["categoricalStateCounts"]
    for f in CATEGORICAL_FIELDS:
        st_count = {}
        for r in rows.values():
            st, _ = categorical_state(f, r[f])
            st_count[st] = st_count.get(st, 0) + 1
        for st, want in cexp[f].items():
            check(st_count.get(st, 0) == want,
                  f"{f} 的 {st} 列數 {st_count.get(st, 0)} == oracle {want}")
    for f in CATEGORICAL_FIELDS:
        zeros = [k for k, r in rows.items() if r[f].strip() == "0"]
        for k in zeros:
            check(rows[k][f] == "0", f"{f} 的 sentinel raw 在 rows.json 中仍為 \"0\"（C1）")

    print("\n[6] 文字 sentinel 三型可區分（C3）")
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
    check(len({comparison_key("排除條件", v) for v in ("N/A", "NA", "")}) == 3,
          "N/A／NA／空 的比較鍵互不相同（不得塌成同一值）")

    print("\n[7] §6.2.1 nearDuplicateGroup 與 §6.2.2 protocolNonIdentifier")
    groups = {}
    for p in by_proto:
        lk = loose_key(p)
        if lk:
            groups.setdefault(lk, set()).add(p)
    near = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    exp_near = {k: sorted(v) for k, v in oracle["nearDuplicateGroups"].items()
                if not k.startswith("_")}
    check(near == exp_near, "nearDuplicateGroup 與 oracle 完全相符"
          + ("" if near == exp_near else f"（實際 {json.dumps(near, ensure_ascii=False)}）"))

    for lk, ps in near.items():
        idents = {identity_normalize(p) for p in ps}
        check(len(idents) == len(ps),
              f"loose key {lk} 的 {len(ps)} 個 protocol 在 identity 正規化後仍相異（不得合併）")

    id_map = {}
    for p in by_proto:
        id_map.setdefault(identity_normalize(p), []).append(p)
    coll = {k: v for k, v in id_map.items() if len(v) > 1}
    check(not coll, f"a_core 無 identity 碰撞（碰撞案例歸 a7 fixture）{'' if not coll else coll}")

    # §6.2.2：looseKey 為空即 protocolNonIdentifier（含空字串與空白-only）
    nonid_rows = [k for k, r in rows.items()
                  if loose_key(r["臨床試驗計畫書編號"]) == ""]
    pcount = oracle["qualityReportExpectations"]["protocolNonIdentifierRowCount"]
    check(len(nonid_rows) == pcount,
          f"protocolNonIdentifier 列數 {len(nonid_rows)} == oracle {pcount}（{sorted(nonid_rows)}）")
    notes.append(f"A10 觸發確認：{len(nonid_rows)} 列中 {len(empties)} 列空字串、"
                 f"{len(ws_only)} 列空白-only、"
                 f"{len(nonid_rows)-len(empties)-len(ws_only)} 列非空但無 ASCII 英數字元"
                 f"（含 '系統測試'，isalnum() 為 True，以 Unicode alphanumeric 實作會全部漏標）")

    empty_loose = [p for p in by_proto if not loose_key(p)]
    check(all(loose_key(p) not in near for p in empty_loose),
          f"loose key 為空的 protocol 不成群（{sorted(empty_loose)}）")

    # §6.2.2 疑似上游測試列
    def suspected_test(r):
        if r["臨床試驗申請者"].strip() == "" and r["臨床試驗計畫中文名稱"].strip() == "":
            return True
        if any(nfkc(r[f]).strip().casefold() == "test" for f in PRESENTATION_FIELDS):
            return True
        p = r["臨床試驗計畫書編號"]
        return "系統測試" in p or "計畫書編號" in p
    test_rows = [k for k, r in rows.items() if suspected_test(r)]
    texp2 = oracle["qualityReportExpectations"]["suspectedUpstreamTestRowCount"]
    check(len(test_rows) == texp2,
          f"suspectedTestRow 列數 {len(test_rows)} == oracle {texp2}（{sorted(test_rows)}）")
    by_rule_b = [k for k, r in rows.items()
                 if any(nfkc(r[f]).strip().casefold() == "test" for f in PRESENTATION_FIELDS)]
    check(by_rule_b, f"≥1 筆僅以 TEST 值型觸發（§6.2.2 (b)）：{sorted(by_rule_b)}")

    print("\n[8] §6.4.2 的比較鍵 dispatch 為窮盡（GAP-8 已於 v0.6 結案）")
    check(not spec_gaps and not gap_dependent_groups,
          f"不存在未定義比較鍵的狀態（實際 {sorted({g[0] for g in spec_gaps})}）")

    # 窮盡性：§9.3.3 的 field-scoped 旗標封閉集合（rawVariants 除外），每一個都要取得比較鍵
    covered = {
        "categoricalUnprovided": ("臨床試驗期別", "0"),
        "categoricalUnknown": ("臨床試驗期別", "第三期"),
        "numericMissing": ("台灣預計受試者人數", ""),
        "sourceZero": ("台灣預計受試者人數", "0"),
        "numericRange": ("台灣預計受試者人數", "20-40"),
        "numericRangeInvalid": ("台灣預計受試者人數", "40-20"),
        "numericImplausible": ("台灣預計受試者人數", "-5"),
        "numericUnparsed": ("台灣預計受試者人數", "約400"),
        "numericOutOfRange": ("台灣預計受試者人數", str(2 ** 53)),
        "periodStartMissing": ("試驗預計執行期間起", ""),
        "periodStartUnparsed": ("試驗預計執行期間起", "2025/13/01"),
        "periodEndMissing": ("試驗預計執行期間迄", ""),
        "periodEndUnparsed": ("試驗預計執行期間迄", "2025/13/01"),
    }
    missing_key = []
    for flag, (field, sample) in sorted(covered.items()):
        try:
            key = comparison_key(field, sample)
            if not (isinstance(key, tuple) and key[0] != SPEC_GAP):
                missing_key.append(flag)
        except AssertionError:
            missing_key.append(flag)
    check(not missing_key,
          f"§9.3.3 旗標封閉集合的 {len(covered)} 個狀態全部取得比較鍵"
          + ("" if not missing_key else f"（缺 {missing_key}）"))

    # 反向哨兵：表外狀態必須硬失敗，不得 fallback
    orig = globals()["numeric_state"]
    globals()["numeric_state"] = lambda raw: ("someUnlistedState", None, [])
    try:
        comparison_key("台灣預計受試者人數", "x")
        raised = False
    except AssertionError:
        raised = True
    finally:
        globals()["numeric_state"] = orig
    check(raised, "表外狀態使 dispatch 硬失敗，**不得** fallback 到比 raw 或視為相等")

    for p_ in ("CMP-035", "CMP-036", "CMP-037"):
        fields = oracle["cohortClassification"]["conflicting"].get(p_)
        check(bool(fields),
              f"{p_} 依 v0.6 §6.4.2 判為衝突，衝突欄位 {fields}（v0.5 時為 __SPEC_GAP__）")

    print()
    for n in notes:
        print(f"  NOTE  {n}")

    print(f"\n{'='*60}")
    if failures:
        print(f"FAIL：{len(failures)} 項不符")
        for f in failures:
            if f:
                print(f"  - {f.splitlines()[0]}")
        return 1
    print("全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
