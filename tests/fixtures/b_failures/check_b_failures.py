"""驗證 b_failures 的每個注入輸入**真的有** oracle 宣稱的缺陷。

同 `check_a_core.py` 的理由：fixture 最常見的失效方式是「宣稱含某缺陷但其實沒有」。
一個其實開得起來的「corrupt ZIP」會讓 B1 的那條測試永遠綠，而沒有人會發現。

**這不是管線測試。** 它不判斷 ETL 會回哪個 error code——那是 M1 的事。
它只確認輸入的形狀符合 oracle，並檢查 oracle 自身的一致性（code 涵蓋 §9.5 全表、
precedence 層名合法、B4 的算術與判定相符）。

跑法：`python tests/fixtures/b_failures/check_b_failures.py`
"""
import io
import json
import os
import sys
import zipfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "inputs")

sys.path.insert(0, HERE)
from build_b_failures import COLUMNS  # noqa: E402

failures = []


def check(cond, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        failures.append(msg)


def read(name):
    with open(os.path.join(INPUTS, name), "rb") as f:
        return f.read()


def csv_of(zip_name):
    """回傳 ZIP 內第一個 .csv 成員的原始位元組。"""
    with zipfile.ZipFile(io.BytesIO(read(zip_name))) as z:
        member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        return z.read(member)


def header_of(zip_name):
    data = csv_of(zip_name)
    text = data.decode("utf-8-sig")
    return text.split("\r\n")[0].split(",")


def main():
    oracle = json.load(open(os.path.join(HERE, "oracle.json"), encoding="utf-8"))

    print("\n[0] oracle 自身的一致性")
    codes = oracle["allErrorCodes"]
    check(len(codes) == len(set(codes)) == 16,
          f"§9.5 的 error code 共 16 個且互異（實際 {len(set(codes))}）")
    covered = {c["errorCode"] for c in oracle["fileCases"]} \
        | {c["errorCode"] for c in oracle["injectionOnly"]}
    missing = set(codes) - covered
    check(not missing, f"每個 error code 都有 fixture 或注入點"
          + ("" if not missing else f"（未涵蓋：{sorted(missing)}）"))
    layers = set(oracle["precedence"])
    bad_layer = [c["layer"] for c in oracle["fileCases"] + oracle["injectionOnly"]
                 if c["layer"] not in layers]
    check(not bad_layer, f"每個 case 的 layer 都在 precedence 清單內{bad_layer or ''}")

    print("\n[1] 每個檔案真的有它宣稱的缺陷")
    for case in oracle["fileCases"]:
        name = case["file"]
        check(os.path.exists(os.path.join(INPUTS, name)), f"{name} 存在")

    # transport：HTML 不是 ZIP
    check(not read("upstream_error_page.html").startswith(b"PK"),
          "upstream_error_page.html 不是 ZIP（不以 PK 開頭）")

    # archive：CRC 真的壞了，但 central directory 完好（否則測不到「開得起來但壞了」）
    z = zipfile.ZipFile(io.BytesIO(read("zip_corrupt.zip")))
    check(z.namelist() == ["205_2.csv"],
          "zip_corrupt.zip 的 central directory 完好，成員清單讀得出來")
    bad_member = None
    try:
        bad_member = z.testzip()
    except Exception as e:  # noqa: BLE001 — 壞 ZIP 可能在讀取時就拋
        bad_member = type(e).__name__
    check(bad_member is not None,
          f"zip_corrupt.zip 的內容確實校驗失敗（testzip → {bad_member}）"
          "——只檢查『開得起來』的實作會漏掉")

    with zipfile.ZipFile(io.BytesIO(read("zip_no_csv.zip"))) as z2:
        check(not any(n.lower().endswith(".csv") for n in z2.namelist()),
              f"zip_no_csv.zip 內無 .csv（成員：{z2.namelist()}）")

    # decode
    raw = csv_of("csv_decode.zip")
    try:
        raw.decode("utf-8-sig")
        ok = False
    except UnicodeDecodeError:
        ok = True
    check(ok, "csv_decode.zip 的內容確實不是合法 UTF-8")
    check(raw.decode("utf-8-sig", errors="replace").count("�") > 0,
          "  └ 以 errors='replace' 解碼會產生 U+FFFD——這正是必須禁止的靜默改資料")

    ctrl = csv_of("source_control_char.zip")
    check(b"\x1f" in ctrl, "source_control_char.zip 的欄位內確實含 U+001F")

    # schema：三類差異各自成立
    for name, key in (("schema_missing.zip", "missing"), ("schema_extra.zip", "extra"),
                      ("schema_order.zip", "order"), ("schema_renamed.zip", "renamed")):
        hdr = header_of(name)
        case = next(c for c in oracle["fileCases"] if c["file"] == name)
        det = case["detail"]
        act_missing = [c for c in COLUMNS if c not in hdr]
        act_extra = [c for c in hdr if c not in COLUMNS]
        act_order = (act_missing == [] and act_extra == [] and hdr != COLUMNS)
        check(act_missing == det["missing"] and act_extra == det["extra"]
              and act_order == det["order"],
              f"{name} 的 detail 與 oracle 相符："
              f"missing={act_missing}／extra={act_extra}／order={act_order}")

    check(header_of("schema_order.zip") != COLUMNS
          and set(header_of("schema_order.zip")) == set(COLUMNS),
          "schema_order.zip 的欄名**集合相同、順序不同**（以 set 比對的實作會通過）")

    # row width
    lines = csv_of("row_width.zip").decode("utf-8-sig").rstrip("\r\n").split("\r\n")
    widths = [len(line.split(",")) for line in lines]
    check(widths[0] == 16 and any(w != 16 for w in widths[1:]),
          f"row_width.zip 欄名 16 欄、資料列有寬度不符者（各列寬度 {widths}）")

    # zero rows：欄名必須**完全正確**，否則測到的是 SCHEMA_MISMATCH
    zr = csv_of("zero_rows.zip").decode("utf-8-sig").rstrip("\r\n").split("\r\n")
    check(zr[0].split(",") == COLUMNS,
          "zero_rows.zip 的 16 欄欄名與順序完全正確（B3：須 schema 通過後才失敗）")
    check(len(zr) == 1, f"zero_rows.zip 沒有任何資料列（實際 {len(zr)-1} 列）")

    # multi anomaly：三層缺陷同時存在
    ma_case = next(c for c in oracle["fileCases"] if c["file"] == "multi_anomaly.zip")
    ma = csv_of("multi_anomaly.zip")
    try:
        ma.decode("utf-8-sig")
        decode_bad = False
    except UnicodeDecodeError:
        decode_bad = True
    ma_hdr = ma.split(b"\r\n")[0].decode("utf-8-sig").split(",")
    check(decode_bad and [c for c in COLUMNS if c not in ma_hdr]
          and ma_case["response"]["contentType"].startswith("text/html"),
          "multi_anomaly 同時具備 transport（MIME）＋ decode（UTF-8）＋ schema（缺欄）三層缺陷")
    check(ma_case["errorCode"] == "UPSTREAM_ERROR_PAGE"
          and oracle["precedence"].index("transport") == 0,
          "  └ oracle 期望 transport 勝出（precedence 由外而內）")

    print("\n[2] content-type 比對規則（B1）")
    for c in oracle["contentTypeCases"]:
        mime = c["value"].split(";")[0].strip().lower()
        passed = (mime == "application/zip")
        check(passed == (c["expect"] == "pass"),
              f"{c['value']!r} → {'通過' if passed else '失敗'}（oracle {c['expect']}）")

    print("\n[3] §9.6 驟降門檻（B4）")
    kills_rounding = 0
    for c in oracle["rowcountDropCases"]:
        if c["prev"] is None:
            check(c.get("bootstrap") is True,
                  f"prev=None 的案例標為 bootstrap（cur={c['cur']}，期望 {c['expect']}）")
            continue
        d = Fraction(c["prev"] - c["cur"], c["prev"])
        check(str(d) == c["drop"] or (d == 0 and c["drop"] == "0"),
              f"prev={c['prev']} cur={c['cur']} → drop {d}（oracle {c['drop']}）")
        verdict = "hard-fail" if d > Fraction(1, 5) else "publish"
        warning = d > Fraction(1, 10)
        check(verdict == c["expect"] and warning == c["warning"],
              f"  └ 判定 {verdict}／warning={warning}（oracle {c['expect']}／{c['warning']}）")
        r = round(float(d), 2)
        rv = "hard-fail" if r > 0.20 else "publish"
        rw = r > 0.10
        if (rv, rw) != (verdict, warning):
            kills_rounding += 1
    check(kills_rounding >= 2,
          f"本組有 {kills_rounding} 個案例能殺死「四捨五入到兩位小數」的實作（須 ≥2）")

    # 反向查核 oracle 的實測宣稱：float 與有理數在本規模下判定永遠相同
    diff = []
    for prev in range(3, 20001):
        for thr, tf in ((Fraction(1, 10), 0.10), (Fraction(1, 5), 0.20)):
            base = prev - int(prev * thr)
            for cur in range(max(0, base - 2), min(prev, base + 3)):
                if (Fraction(prev - cur, prev) > thr) != ((prev - cur) / prev > tf):
                    diff.append((prev, cur))
    check(not diff,
          f"prev ≤ 20,000 的門檻鄰域內，float 與有理數判定無差異（{len(diff)} 筆）"
          "——故『以有理數比較』在本專案規模下不可驗證（GAP-12）")

    print("\n[4] B5 注入點與發布狀態斷言的完整性")
    check(len(oracle["promotionFailurePoints"]) == 9,
          f"promotion 失敗注入點 9 個（B5 逐項列出，實際 {len(oracle['promotionFailurePoints'])}）")
    check(any("SIGTERM" in p or "取消" in p for p in oracle["promotionFailurePoints"]),
          "  └ 含非例外式終止（SIGTERM／取消）——只測 raise 的實作會漏掉這條路徑")
    check(any("無新增正式檔" in a for a in oracle["publishedStateAssertions"]),
          "發布狀態斷言含「無新增正式檔」（B1(c)）")

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
