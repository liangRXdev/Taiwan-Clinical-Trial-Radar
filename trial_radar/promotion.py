"""§9.2 發布契約。

保證的是：**被 commit 並 push 出去的 tree 永遠是完整一致的；不存在部分發布的 commit。**

**不聲稱** working tree 在中途失敗後「整體等於舊版」——逐檔替換做不到，而 commit 的
原子性不回復 working tree。CI runner 的 working tree 是用後即棄、無任何讀者，去斷言它
會讓測試變成在測一個規格沒承諾的性質。

作法：全部 artifact 先寫進 staging 並通過整體驗證；**替換、`git add -A`、`git commit`
收攏為管線最後三個步驟**；任一步失敗即非零 exit，runner 隨即丟棄。
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .artifacts import BuildOutput, manifest_paths
from .errors import ErrorCode, PipelineError
from .invariants import assert_invariants

MANIFEST_NAME = "manifest.json"


class Git(Protocol):
    """只用到三個動作，方便注入假的 runner 做 B5 的失敗注入。"""

    def add_all(self) -> None: ...
    def commit(self, message: str) -> None: ...
    def push(self) -> None: ...


@dataclass
class PromotionResult:
    published: bool
    dataset_version: str
    reason: str = ""


def stage(out: BuildOutput, staging: Path) -> None:
    """把 artifact 寫進 staging 並**在那裡**通過 §9.3.6 的整體驗證。

    驗證在 staging 做，是為了讓「正式 artifact 不動」這件事在驗證失敗時自然成立。
    """
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for path, data in out.published.items():
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (staging / MANIFEST_NAME).write_bytes(
        json.dumps(out.manifest, ensure_ascii=False, indent=1).encode("utf-8")
    )
    assert_invariants(out.published, out.manifest)


def read_published_manifest(public_data: Path) -> dict | None:
    """讀目前**已發布**的 manifest；沒有就是首次發布（bootstrap）。"""
    p = public_data / MANIFEST_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def promote(
    out: BuildOutput,
    public_data: Path,
    staging: Path,
    git: Git,
    *,
    message: str,
    deploy: Callable[[], None] | None = None,
) -> PromotionResult:
    """§9.2.1 的最後三步（＋部署啟用）。任一步失敗即拋 `PROMOTION_FAILED`。

    §9.4 的 no-change 判準：**`datasetVersion` 相同即無變動** → 不發布、不 commit，
    `builtAt` 與 manifest 均不變。比較**排除** `builtAt`／`fetchedAt`／`sourceSha256`／
    `artifactDigest`——前三者是 provenance 不是資料，最後一個由其餘內容導出。
    """
    current = read_published_manifest(public_data)
    if current and current.get("datasetVersion") == out.manifest["datasetVersion"]:
        return PromotionResult(False, out.manifest["datasetVersion"], "no normalized change")

    try:
        _replace(out, public_data, staging)
        git.add_all()
        git.commit(message)
        git.push()
        if deploy is not None:
            deploy()
    except PipelineError:
        raise
    except BaseException as e:
        # **BaseException 不是筆誤**：SIGTERM／workflow 取消會以 KeyboardInterrupt 或
        # SystemExit 進來，只接 Exception 會讓那條路徑完全沒有處置。B5 明列這個注入點。
        raise PipelineError(
            ErrorCode.PROMOTION_FAILED,
            f"{type(e).__name__}: {e}",
            {"stage": "promotion"},
        ) from e
    return PromotionResult(True, out.manifest["datasetVersion"], "published")


def _replace(out: BuildOutput, public_data: Path, staging: Path) -> None:
    """以 staging 的內容替換 `public/data/`，並刪除不再被引用的 orphan 檔案。

    orphan 必須刪：§9.3.6 的 inventory 不變量要求 `manifest.files` 的路徑集合等於目錄內
    除 manifest 外的全部檔案，而**孤兒檔不會改變 `artifactDigest`**（§9.3.2 只走
    `manifest.files` 的路徑），沒有這條就完全靜默。
    """
    public_data.mkdir(parents=True, exist_ok=True)
    wanted = manifest_paths(out.manifest)

    for path, data in out.published.items():
        target = public_data / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    (public_data / MANIFEST_NAME).write_bytes(
        json.dumps(out.manifest, ensure_ascii=False, indent=1).encode("utf-8")
    )

    for existing in sorted(public_data.rglob("*.json")):
        rel = existing.relative_to(public_data).as_posix()
        if rel == MANIFEST_NAME or rel in wanted:
            continue
        existing.unlink()

    for d in sorted(public_data.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def verify_published(public_data: Path) -> None:
    """發布後從磁碟重讀並再驗一次 §9.3.6。

    這是「發布鏈三段一致」的最後一段——staging 驗過不代表落到磁碟上的也對。
    """
    manifest = read_published_manifest(public_data)
    if manifest is None:
        raise PipelineError(ErrorCode.INTEGRITY_DIGEST, "發布後讀不到 manifest")
    on_disk = {}
    for p in public_data.rglob("*.json"):
        rel = p.relative_to(public_data).as_posix()
        if rel != MANIFEST_NAME:
            on_disk[rel] = p.read_bytes()
    assert_invariants(on_disk, manifest)
