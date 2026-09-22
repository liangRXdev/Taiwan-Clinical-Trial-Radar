"""§9.5 失敗分類：error code、層、exit code。

三條硬性紀律：

1. **每個 code 對應相異的非零 exit code。** §9.5 只要求「相異」，沒有指定號碼；
   本檔選定並釘住，測試斷言的是「非零且兩兩相異」，不是特定數字。
2. **stderr 訊息只作輔助，不得作為判定依據**（B2）。呼叫端一律看 `PipelineError.code`。
3. **多重異常的 precedence 由外而內**：transport → archive → decode → schema → content → publish。
   沒有 precedence 的實作會回傳「先被程式碼碰到的那一個」，而那取決於函式呼叫順序不是規格。
"""
from __future__ import annotations

from enum import Enum


class Layer(str, Enum):
    """§9.5 的層。順序即 precedence（由外而內，先觸發者勝）。"""

    TRANSPORT = "transport"
    ARCHIVE = "archive"
    DECODE = "decode"
    SCHEMA = "schema"
    CONTENT = "content"
    PUBLISH = "publish"


# precedence：index 越小越外層、越優先
LAYER_ORDER = [
    Layer.TRANSPORT,
    Layer.ARCHIVE,
    Layer.DECODE,
    Layer.SCHEMA,
    Layer.CONTENT,
    Layer.PUBLISH,
]


class ErrorCode(str, Enum):
    HTTP_STATUS = "HTTP_STATUS"
    HTTP_TIMEOUT = "HTTP_TIMEOUT"
    HTTP_TRUNCATED = "HTTP_TRUNCATED"
    UPSTREAM_ERROR_PAGE = "UPSTREAM_ERROR_PAGE"
    ZIP_CORRUPT = "ZIP_CORRUPT"
    ZIP_NO_CSV = "ZIP_NO_CSV"
    CSV_DECODE = "CSV_DECODE"
    SOURCE_CONTROL_CHAR = "SOURCE_CONTROL_CHAR"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    ROW_WIDTH = "ROW_WIDTH"
    ZERO_ROWS = "ZERO_ROWS"
    ROWCOUNT_DROP = "ROWCOUNT_DROP"
    IDENTITY_COLLISION = "IDENTITY_COLLISION"
    ID_TRUNCATION_COLLISION = "ID_TRUNCATION_COLLISION"
    INTEGRITY_DIGEST = "INTEGRITY_DIGEST"
    PROMOTION_FAILED = "PROMOTION_FAILED"
    BASELINE_MOVED = "BASELINE_MOVED"


LAYER_OF: dict[ErrorCode, Layer] = {
    ErrorCode.HTTP_STATUS: Layer.TRANSPORT,
    ErrorCode.HTTP_TIMEOUT: Layer.TRANSPORT,
    ErrorCode.HTTP_TRUNCATED: Layer.TRANSPORT,
    ErrorCode.UPSTREAM_ERROR_PAGE: Layer.TRANSPORT,
    ErrorCode.ZIP_CORRUPT: Layer.ARCHIVE,
    ErrorCode.ZIP_NO_CSV: Layer.ARCHIVE,
    ErrorCode.CSV_DECODE: Layer.DECODE,
    ErrorCode.SOURCE_CONTROL_CHAR: Layer.DECODE,
    ErrorCode.SCHEMA_MISMATCH: Layer.SCHEMA,
    ErrorCode.ROW_WIDTH: Layer.SCHEMA,
    ErrorCode.ZERO_ROWS: Layer.CONTENT,
    ErrorCode.ROWCOUNT_DROP: Layer.CONTENT,
    ErrorCode.IDENTITY_COLLISION: Layer.CONTENT,
    ErrorCode.ID_TRUNCATION_COLLISION: Layer.CONTENT,
    ErrorCode.INTEGRITY_DIGEST: Layer.PUBLISH,
    ErrorCode.PROMOTION_FAILED: Layer.PUBLISH,
    ErrorCode.BASELINE_MOVED: Layer.PUBLISH,
}

# 相異的非零 exit code。數字本身不具規範意義，只有「非零且兩兩相異」是契約。
# 從 10 起跳，避開 shell 慣用的 1（一般錯誤）與 2（誤用）。
EXIT_CODE_OF: dict[ErrorCode, int] = {
    ErrorCode.HTTP_STATUS: 10,
    ErrorCode.HTTP_TIMEOUT: 11,
    ErrorCode.HTTP_TRUNCATED: 12,
    ErrorCode.UPSTREAM_ERROR_PAGE: 13,
    ErrorCode.ZIP_CORRUPT: 14,
    ErrorCode.ZIP_NO_CSV: 15,
    ErrorCode.CSV_DECODE: 16,
    ErrorCode.SOURCE_CONTROL_CHAR: 17,
    ErrorCode.SCHEMA_MISMATCH: 18,
    ErrorCode.ROW_WIDTH: 19,
    ErrorCode.ZERO_ROWS: 20,
    ErrorCode.ROWCOUNT_DROP: 21,
    ErrorCode.IDENTITY_COLLISION: 22,
    ErrorCode.ID_TRUNCATION_COLLISION: 23,
    ErrorCode.INTEGRITY_DIGEST: 24,
    ErrorCode.PROMOTION_FAILED: 25,
    ErrorCode.BASELINE_MOVED: 26,
}


class PipelineError(Exception):
    """結構化失敗。**判定一律看 `code`／`layer`，不看訊息字串**（B2）。

    `detail` 供 QA report 與測試使用；`SCHEMA_MISMATCH` 須載明 missing／extra／order
    三類差異（§9.5）。
    """

    def __init__(self, code: ErrorCode, message: str = "", detail: dict | None = None):
        super().__init__(message or code.value)
        self.code = code
        self.layer = LAYER_OF[code]
        self.message = message
        self.detail = detail or {}

    @property
    def exit_code(self) -> int:
        return EXIT_CODE_OF[self.code]

    def __repr__(self) -> str:  # pragma: no cover - 偵錯用
        return f"PipelineError({self.code.value}, layer={self.layer.value}, detail={self.detail})"


def precedence_winner(errors: list[PipelineError]) -> PipelineError:
    """§9.5 的多重失敗 precedence：由外而內，先觸發者勝。

    同層多個時取傳入順序的第一個——同層內的順序不是規格，呼叫端不得依賴。
    """
    if not errors:
        raise ValueError("precedence_winner 需要至少一個錯誤")
    return min(errors, key=lambda e: LAYER_ORDER.index(e.layer))
