"""三個 CLI（`fetch_tfda.py`／`validate_schema.py`／`build_data.py`）共用的收尾。

存在的理由只有一個：**exit code 與 stderr 格式必須三支一致**。
B2 明文要求呼叫端（CI）以 structured code 判定，各自複製一份 try/except 遲早會漂移成
「其中一支把某個 code 印成 exit 1」——而那在 CI 上看起來和成功以外的任何失敗一樣。
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable

from .errors import EXIT_CODE_OF, ErrorCode, PipelineError

#: `argparse` 的 epilog：把 §9.5 的對照表直接印在 `--help`，省得去翻規格
EXIT_CODE_EPILOG = "exit code 對照（§9.5，每個 code 相異且非零）：\n" + "\n".join(
    f"  {c.value:<26} {EXIT_CODE_OF[c]}" for c in ErrorCode
)


def report(error: PipelineError, *, detail_limit: int = 2000) -> int:
    """把 `PipelineError` 印成人看的 stderr，回傳 exit code。

    stderr 只是輔助說明；**判定依據是回傳值**。
    """
    print(f"[{error.code.value}] layer={error.layer.value} {error.message}", file=sys.stderr)
    if error.detail:
        print(
            json.dumps(error.detail, ensure_ascii=False, indent=1)[:detail_limit],
            file=sys.stderr,
        )
    return error.exit_code


def run(fn: Callable[[], int]) -> int:
    """執行 `fn`，把 `PipelineError` 轉成對應的 exit code。

    **只接 `PipelineError`**：其他例外是實作 bug，應該以 traceback 曝光而不是被吞成
    某個看起來像資料問題的 exit code。
    """
    try:
        return fn()
    except PipelineError as e:
        return report(e)


def emit(payload: dict, out: str | None) -> None:
    """報告輸出：`out` 為 None 印到 stdout，否則寫檔。

    兩者都用同一份 JSON（`ensure_ascii=False`、`indent=1`），使「CI 存檔的」與
    「人在終端看到的」是同一份位元組。
    """
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if out is None:
        print(text)
    else:
        from pathlib import Path

        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
