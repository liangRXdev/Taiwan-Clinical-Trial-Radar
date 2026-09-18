"""產生 A7（identity normalization 碰撞）的凍結 fixture。

預期結果是整個 build 硬失敗 `IDENTITY_COLLISION`，故列數刻意精簡。
oracle 見 a7_identity_collision/oracle.json（手寫）。

跑法：`python tests/fixtures/build_a7.py`
"""
import csv
import io
import json
import os

from build_a_core import COLUMNS

APP = "測試甲藥廠股份有限公司"
BASE = [APP, "", "碰撞測試", "Phase Ⅲ", "多國多中心", "評估療效",
        "2025/01/01", "2027/01/01", "100", "10", "測試適應症", "測試指標",
        "年齡 20 歲以上", "無", "1130901", "2026/05/01"]

# rowKey → protocol 字面值
PROTOCOLS = [
    ("coll-lower", "abc-1"),
    ("coll-upper", "ABC-1"),
    ("coll-width", "ＡＢＣ－２"),
    ("coll-ascii", "abc-2"),
    ("ok-control", "OK-9"),
]

PROTOCOL_IDX = COLUMNS.index("臨床試驗計畫書編號")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "a7_identity_collision")
    os.makedirs(out, exist_ok=True)

    rows = []
    for key, proto in PROTOCOLS:
        vals = list(BASE)
        vals[PROTOCOL_IDX] = proto
        # 讓每列的其餘內容互異，避免與 A6 的「逐位元相同」情形混在一起
        vals[COLUMNS.index("臨床試驗計畫中文名稱")] = f"碰撞測試 {key}"
        rows.append((key, vals))

    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(COLUMNS)
    for _, vals in rows:
        w.writerow(vals)
    with open(os.path.join(out, "input.csv"), "wb") as f:
        f.write(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))

    with open(os.path.join(out, "rows.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {"columns": COLUMNS, "rows": {k: dict(zip(COLUMNS, v)) for k, v in rows}},
            f, ensure_ascii=False, indent=1,
        )

    print(f"input.csv: {len(rows)} 列")


if __name__ == "__main__":
    main()
