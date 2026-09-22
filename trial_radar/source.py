"""§9.1 管線的取得與驗證段：transport → archive → decode → schema → content。

**失敗絕不回空陣列。** 抓取失敗與「官方回覆空集」必須分辨：目前 205 無 sentinel 列，
0 資料列一律走 `ZERO_ROWS` 硬失敗。
"""
from __future__ import annotations

import csv
import io
import zipfile
import zlib
from dataclasses import dataclass
from fractions import Fraction

from .errors import ErrorCode, PipelineError
from .fields import COLUMNS
from .identity import sha256hex

DATASET_URL = "https://data.fda.gov.tw/data/opendata/export/205/csv"

# §9.6 驟降門檻。**以有理數表示**：便宜，且資料規模改變時不需重新評估。
# 規格的可驗證要求是「**不得先四捨五入或截斷到固定小數位再比較**」——
# drop = 0.2001 四捨五入到兩位會得 0.20 而照樣發布，上游掉了 20.01% 卻沒硬失敗。
WARN_THRESHOLD = Fraction(1, 10)
FAIL_THRESHOLD = Fraction(1, 5)


@dataclass
class FetchResult:
    body: bytes
    sha256: str


def validate_response(status: int, content_type: str, declared_length: int | None,
                      body: bytes) -> FetchResult:
    """§9.5 transport 層。**只接受最終 HTTP 狀態 200。**"""
    if status != 200:
        raise PipelineError(ErrorCode.HTTP_STATUS, f"最終狀態 {status}", {"status": status})

    # content-type 以 `;` 前的 MIME 比對**等於** application/zip（允許參數）。
    # 不得用 startswith——application/zip-compressed 會被誤放行。
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime != "application/zip":
        raise PipelineError(
            ErrorCode.UPSTREAM_ERROR_PAGE,
            f"MIME 非 zip：{content_type!r}",
            {"contentType": content_type, "mime": mime},
        )

    if declared_length is not None and len(body) != declared_length:
        raise PipelineError(
            ErrorCode.HTTP_TRUNCATED,
            f"實收 {len(body)} 位元組，Content-Length 宣告 {declared_length}",
            {"received": len(body), "declared": declared_length},
        )
    return FetchResult(body, sha256hex(body))


def extract_csv(zip_bytes: bytes) -> bytes:
    """§9.5 archive 層。**必須完整讀取**——只檢查「開得起來」會放過 CRC 壞掉的檔案。"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise PipelineError(ErrorCode.ZIP_CORRUPT, f"ZIP 結構失敗：{e}") from e

    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not names:
        raise PipelineError(
            ErrorCode.ZIP_NO_CSV, "ZIP 內無 .csv", {"members": zf.namelist()}
        )

    # `testzip()` 不只回傳壞掉的成員名，也可能直接拋——壓縮資料本身損毀時是
    # `zlib.error`（不是 `BadZipFile`），只接 `BadZipFile` 會讓它逸出成 traceback
    # 而非 structured error code。B 群的 zip_corrupt fixture 就是踩到這個。
    try:
        bad = zf.testzip()
        if bad is not None:
            raise PipelineError(ErrorCode.ZIP_CORRUPT, f"CRC 失敗：{bad}", {"member": bad})
        return zf.read(sorted(names)[0])
    except PipelineError:
        raise
    except (zipfile.BadZipFile, EOFError, zlib.error, ValueError) as e:
        raise PipelineError(
            ErrorCode.ZIP_CORRUPT, f"讀取失敗：{type(e).__name__}: {e}"
        ) from e


def decode_csv(data: bytes) -> str:
    """§9.5 decode 層。UTF-8 with BOM。

    **不得使用 errors='replace'／'ignore'**：那會靜默產出 U+FFFD 並繼續——
    資料變了但沒有任何訊號，是最糟的一種失敗。
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise PipelineError(
            ErrorCode.CSV_DECODE,
            f"UTF-8 解碼失敗於位元組 {e.start}",
            {"position": e.start, "reason": e.reason},
        ) from e


def parse_csv(text: str) -> list[dict[str, str]]:
    """§9.5 schema 層：釘住 16 欄的**欄名與順序**，並檢查列寬。

    以欄名集合（set）比對的實作會放過「兩個數值欄位對調」——而 §6.3 的 canonical
    serialization 依 canonical 欄位順序輸出，順序錯了 ID 全錯，且對調在數值上完全合理、
    不會有任何下游訊號。
    """
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise PipelineError(
            ErrorCode.SCHEMA_MISMATCH,
            "空檔，連欄名列都沒有",
            {"missing": list(COLUMNS), "extra": [], "order": False},
        ) from None

    expected = list(COLUMNS)
    if header != expected:
        missing = [c for c in expected if c not in header]
        extra = [c for c in header if c not in expected]
        # rename 同時滿足 missing 與 extra，無客觀判定方式——§9.5 因此只有單一 code 攜帶 detail
        order_only = not missing and not extra and header != expected
        raise PipelineError(
            ErrorCode.SCHEMA_MISMATCH,
            "16 欄欄名或順序不符",
            {"missing": missing, "extra": extra, "order": order_only,
             "actual": header},
        )

    rows: list[dict[str, str]] = []
    for lineno, values in enumerate(reader, start=2):
        if not values:
            continue
        if len(values) != len(expected):
            raise PipelineError(
                ErrorCode.ROW_WIDTH,
                f"第 {lineno} 列寬度 {len(values)}，應為 {len(expected)}",
                {"line": lineno, "width": len(values), "expected": len(expected)},
            )
        rows.append(dict(zip(expected, values, strict=True)))
    return rows


@dataclass
class DropVerdict:
    drop: Fraction | None
    warning: bool
    bootstrap: bool


def check_row_count(cur: int, prev: int | None) -> DropVerdict:
    """§9.6。回傳判定；硬失敗時拋 `ROWCOUNT_DROP`。

    **schema 通過後才因零列失敗**（B3）：呼叫端須在 `parse_csv` 之後才呼叫本函式，
    否則 `ZERO_ROWS` 與 `SCHEMA_MISMATCH` 會分不開，而兩者的處置不同
    （前者是上游出事，後者是上游改格式）。
    """
    if cur == 0:
        # bootstrap 仍要求列數 ≥1；不得因為「沒有 baseline 可比」而放行
        raise PipelineError(ErrorCode.ZERO_ROWS, "schema 通過但 0 資料列")

    if prev is None:
        # 首次無 baseline → bootstrap：不做驟降比較，**不假裝完成比較**
        return DropVerdict(None, False, True)

    drop = Fraction(prev - cur, prev)
    if drop > FAIL_THRESHOLD:
        raise PipelineError(
            ErrorCode.ROWCOUNT_DROP,
            f"驟降 {float(drop):.6f} 超過門檻",
            {"prev": prev, "cur": cur, "drop": str(drop)},
        )
    return DropVerdict(drop, drop > WARN_THRESHOLD, False)


def fetch_dataset(url: str = DATASET_URL, *,
                  connect_timeout: float = 10.0,
                  read_timeout: float = 120.0) -> FetchResult:
    """transport 層唯一的連網進入點（§9.1）。

    `requests` 在函式內載入，讓不連網的測試與 `validate_schema.py` 不必把它拉進來。

    **例外一律轉成 `PipelineError`**：B2 要求呼叫端以 structured code 判定，
    而一個逸出的 `requests` traceback 連 code 都沒有。逾時與連線中斷是不同的 code
    （`HTTP_TIMEOUT` vs `HTTP_TRUNCATED`），因為處置不同——前者重試合理，後者要查上游。
    """
    import requests

    try:
        resp = requests.get(url, timeout=(connect_timeout, read_timeout))
    except requests.Timeout as e:
        raise PipelineError(ErrorCode.HTTP_TIMEOUT, str(e), {"url": url}) from e
    except requests.RequestException as e:
        raise PipelineError(ErrorCode.HTTP_TRUNCATED, str(e), {"url": url}) from e

    declared = resp.headers.get("Content-Length")
    return validate_response(
        resp.status_code,
        resp.headers.get("Content-Type", ""),
        int(declared) if declared and declared.isdigit() else None,
        resp.content,
    )
