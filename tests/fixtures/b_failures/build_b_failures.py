"""產生 §9.5 失敗分類的注入 fixture（驗收 B1／B2／B3）。

每個可用位元組表達的 error code 各一個檔案；transport 與 publish 層的 code 不是檔案而是
**注入點**，列在 `oracle.json` 的 `injectionOnly` 區塊，由將來的測試以 mock／monkeypatch 驅動。

**這不是 ETL 實作。** 本檔只造出「有缺陷的輸入」；`check_b_failures.py` 驗證這些輸入
**真的有它宣稱的缺陷**（例如 corrupt ZIP 真的解不開、schema fixture 真的少一欄），
不判斷管線會不會回對的 code——那是 M1 的測試。

跑法：`python tests/fixtures/b_failures/build_b_failures.py`
"""
import io
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "inputs")

COLUMNS = [
    "臨床試驗申請者", "臨床試驗計畫書編號", "臨床試驗計畫中文名稱", "臨床試驗期別",
    "本臨床試驗規模", "試驗目的", "試驗預計執行期間起", "試驗預計執行期間迄",
    "全球預計受試者人數", "台灣預計受試者人數", "適應症中文", "主要評估指標",
    "納入條件", "排除條件", "TFDA收文號", "資料更新時間",
]

GOOD_ROW = [
    "測試甲藥廠股份有限公司", "OK-001", "合法列", "Phase Ⅲ", "多國多中心", "評估療效",
    "2025/01/01", "2027/01/01", "100", "10", "氣喘", "FEV1", "年齡 18 歲以上", "無",
    "1130001", "2026/02/01",
]

BOM = b"\xef\xbb\xbf"


def csv_bytes(header, rows):
    """以最單純的方式組 CSV：本 fixture 的每個值都不含逗號、引號或換行。"""
    for r in rows:
        for v in r:
            assert not any(c in v for c in ',"\r\n'), v
    lines = [",".join(header)] + [",".join(r) for r in rows]
    return BOM + ("\r\n".join(lines) + "\r\n").encode("utf-8")


def zip_bytes(name, payload):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, payload)
    return buf.getvalue()


def write(rel, data):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return rel, len(data)


def main():
    made = []

    # ---- transport：200 但 MIME 非 zip（實務上是上游的錯誤頁）----
    made.append(write("upstream_error_page.html",
                      "<!DOCTYPE html><html><head><title>系統忙碌中</title></head>"
                      "<body><h1>服務暫時無法使用</h1></body></html>".encode()))

    # ---- archive：ZIP 結構／CRC 失敗 ----
    good = zip_bytes("205_2.csv", csv_bytes(COLUMNS, [GOOD_ROW]))
    corrupt = bytearray(good)
    # 破壞壓縮資料區（local file header 之後），使 CRC 校驗失敗而非結構失敗
    corrupt[40] ^= 0xFF
    corrupt[41] ^= 0xFF
    made.append(write("zip_corrupt.zip", bytes(corrupt)))

    made.append(write("zip_no_csv.zip",
                      zip_bytes("readme.txt", "本壓縮檔沒有 CSV。".encode())))

    # ---- decode：UTF-8 解碼失敗（Big5 的「臨床」＋ 單獨的 0x80 續位元組）----
    bad_utf8 = BOM + b"\xc5\x53\xa7\xc9," + b"\x80\x80" + b"\r\n"
    made.append(write("csv_decode.zip", zip_bytes("205_2.csv", bad_utf8)))

    # ---- decode：欄位含 U+001F（§6.3 的硬性檢查）----
    ctrl_row = list(GOOD_ROW)
    ctrl_row[2] = "含控制字元\x1f的名稱"
    made.append(write("source_control_char.zip",
                      zip_bytes("205_2.csv", csv_bytes(COLUMNS, [ctrl_row]))))

    # ---- schema：missing／extra／order 三類差異各一 ----
    made.append(write("schema_missing.zip",
                      zip_bytes("205_2.csv",
                                csv_bytes([c for c in COLUMNS if c != "適應症中文"],
                                          [[v for c, v in zip(COLUMNS, GOOD_ROW)
                                            if c != "適應症中文"]]))))
    made.append(write("schema_extra.zip",
                      zip_bytes("205_2.csv",
                                csv_bytes(COLUMNS + ["執行狀態"], [GOOD_ROW + ["執行中"]]))))
    swapped = list(COLUMNS)
    swapped[8], swapped[9] = swapped[9], swapped[8]  # 兩個數值欄位對調
    made.append(write("schema_order.zip",
                      zip_bytes("205_2.csv", csv_bytes(swapped, [GOOD_ROW]))))
    # rename：同時滿足 missing 與 extra，故 §9.5 已合併為單一 SCHEMA_MISMATCH + detail
    renamed = list(COLUMNS)
    renamed[10] = "適應症"
    made.append(write("schema_renamed.zip",
                      zip_bytes("205_2.csv", csv_bytes(renamed, [GOOD_ROW]))))

    # ---- schema：列寬不符 ----
    short_line = BOM + (",".join(COLUMNS) + "\r\n"
                        + ",".join(GOOD_ROW) + "\r\n"
                        + ",".join(GOOD_ROW[:10]) + "\r\n").encode("utf-8")
    made.append(write("row_width.zip", zip_bytes("205_2.csv", short_line)))

    # ---- content：schema 通過但 0 資料列 ----
    made.append(write("zero_rows.zip", zip_bytes("205_2.csv", csv_bytes(COLUMNS, []))))

    # ---- 多重異常：驗 §9.5 的 precedence（transport → archive → decode → schema）----
    # 這個 ZIP 同時是「內容為壞 UTF-8」與「欄名缺一欄」；再由 oracle 指定它以 text/html 回應，
    # 三層同時異常，期望 transport 勝出。
    both = BOM + ("," .join([c for c in COLUMNS if c != "適應症中文"])).encode("utf-8") \
        + b"\r\n" + b"\x80\x80\r\n"
    made.append(write("multi_anomaly.zip", zip_bytes("205_2.csv", both)))

    for rel, n in made:
        print(f"{rel:32} {n:>7} bytes")
    print(f"\n共 {len(made)} 個注入輸入")


if __name__ == "__main__":
    main()
