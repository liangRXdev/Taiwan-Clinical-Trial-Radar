"""B5 驗收：promotion 的失敗注入。

每個注入點斷言同一件事：**不存在部分發布的 commit**（§9.2.1）。

**刻意不斷言** working tree 在中途失敗後等於舊版——§9.2.1 明確不聲稱那件事
（逐檔替換做不到，而 commit 的原子性不回復 working tree）。去斷言它會讓測試變成在測
一個規格沒承諾的性質，之後任何合理的重構都會無故轉紅。
"""
from __future__ import annotations

import json

import pytest

from trial_radar.artifacts import build_artifacts
from trial_radar.errors import ErrorCode, PipelineError
from trial_radar.model import build_trials
from trial_radar.promotion import (
    MANIFEST_NAME,
    promote,
    read_published_manifest,
    stage,
    verify_published,
)

BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


class FakeGit:
    """可在任一動作注入失敗的假 git runner。"""

    def __init__(self, fail_at: str | None = None, exc: BaseException | None = None):
        self.fail_at = fail_at
        self.exc = exc or RuntimeError(f"injected failure at {fail_at}")
        self.calls: list[str] = []
        self.commits: list[str] = []

    def _maybe_fail(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            raise self.exc

    def add_all(self) -> None:
        self._maybe_fail("add_all")

    def commit(self, message: str) -> None:
        self._maybe_fail("commit")
        self.commits.append(message)

    def push(self) -> None:
        self._maybe_fail("push")


@pytest.fixture
def out(a_core_rows, build_date):
    return build_artifacts(build_trials(list(a_core_rows.values()), build_date), **BUILD_KW)


@pytest.fixture
def dirs(tmp_path):
    return tmp_path / "public" / "data", tmp_path / ".staging"


def _publish_once(out, dirs, git=None):
    public, staging = dirs
    stage(out, staging)
    return promote(out, public, staging, git or FakeGit(), message="data: 首次發布")


def test_happy_path_publishes_and_verifies(out, dirs):
    public, _ = dirs
    result = _publish_once(out, dirs)
    assert result.published is True
    verify_published(public)

    manifest = read_published_manifest(public)
    assert manifest["datasetVersion"] == out.manifest["datasetVersion"]
    on_disk = {
        p.relative_to(public).as_posix()
        for p in public.rglob("*.json")
        if p.relative_to(public).as_posix() != MANIFEST_NAME
    }
    assert on_disk == set(out.published)


# ---------------------------------------------------------------- B5 注入點

@pytest.mark.parametrize("fail_at", ["add_all", "commit", "push"])
def test_b5_git_step_failure_leaves_no_partial_commit(out, dirs, fail_at):
    """`git add` 只含部分變更／commit 失敗／push 失敗，各一個注入點。"""
    public, staging = dirs
    stage(out, staging)
    git = FakeGit(fail_at=fail_at)

    with pytest.raises(PipelineError) as exc:
        promote(out, public, staging, git, message="data: x")
    assert exc.value.code is ErrorCode.PROMOTION_FAILED
    assert exc.value.layer.value == "publish"

    # 不存在部分發布的 commit：失敗於 commit 之前 → 沒有 commit；
    # 失敗於 push → commit 存在但未推出，runner 隨即丟棄整個 working tree
    if fail_at in ("add_all", "commit"):
        assert git.commits == []
    else:
        assert len(git.commits) == 1


def test_b5_deploy_activation_failure(out, dirs):
    """push 成功但**部署啟用失敗**。前一個成功部署仍為 authoritative。"""
    public, staging = dirs
    stage(out, staging)

    def deploy():
        raise RuntimeError("Cloudflare Pages 啟用失敗")

    with pytest.raises(PipelineError) as exc:
        promote(out, public, staging, FakeGit(), message="data: x", deploy=deploy)
    assert exc.value.code is ErrorCode.PROMOTION_FAILED


@pytest.mark.parametrize("exc", [KeyboardInterrupt(), SystemExit(1)],
                         ids=["SIGTERM", "workflow-cancel"])
def test_b5_non_exception_termination(out, dirs, exc):
    """**非例外式終止**（SIGTERM／取消）也必須走同一條處置。

    只接 `Exception` 的實作會讓這條路徑完全沒有處置——那是 B5 明列的注入點。
    """
    public, staging = dirs
    stage(out, staging)
    git = FakeGit(fail_at="commit", exc=exc)

    with pytest.raises(PipelineError) as err:
        promote(out, public, staging, git, message="data: x")
    assert err.value.code is ErrorCode.PROMOTION_FAILED
    assert git.commits == []


def test_b5_integrity_failure_before_any_state_change(dirs, build_date):
    """staging 驗證失敗時，**正式 artifact 完全沒被碰過**。"""
    public, staging = dirs
    public.mkdir(parents=True)
    (public / "sentinel.json").write_bytes(b"{}")

    broken = build_artifacts(build_trials([], build_date), **BUILD_KW)
    broken.manifest = {**broken.manifest, "artifactDigest": "0" * 64}

    with pytest.raises(PipelineError) as exc:
        stage(broken, staging)
    assert exc.value.code is ErrorCode.INTEGRITY_DIGEST
    assert (public / "sentinel.json").exists(), "驗證失敗時不得動到正式目錄"


# ---------------------------------------------------------------- orphan 清理

def test_orphan_artifacts_are_removed(a_core_rows, build_date, dirs):
    """替換時必須刪掉不再被引用的舊檔——孤兒檔不會改變 artifactDigest，沒刪就完全靜默。"""
    public, staging = dirs
    first = build_artifacts(build_trials(list(a_core_rows.values()), build_date), **BUILD_KW)
    stage(first, staging)
    promote(first, public, staging, FakeGit(), message="data: 1")

    rows = [dict(r) for r in a_core_rows.values()]
    rows[0]["台灣預計受試者人數"] = "999"
    second = build_artifacts(build_trials(rows, build_date), **BUILD_KW)
    assert second.manifest["datasetVersion"] != first.manifest["datasetVersion"]
    stage(second, staging)
    promote(second, public, staging, FakeGit(), message="data: 2")

    verify_published(public)
    on_disk = {
        p.relative_to(public).as_posix()
        for p in public.rglob("*.json")
        if p.relative_to(public).as_posix() != MANIFEST_NAME
    }
    assert on_disk == set(second.published), "舊版的孤兒檔必須被刪除"


# ---------------------------------------------------------------- B9 no-change

def test_b9_no_change_does_not_commit(out, dirs, a_core_rows, build_date):
    """§9.4：`datasetVersion` 相同 → 不發布、不 commit、`builtAt` 不變。"""
    public, staging = dirs
    _publish_once(out, dirs)
    before = json.loads((public / MANIFEST_NAME).read_text(encoding="utf-8"))

    # 第二次跑：來源資料完全相同，只有 provenance 欄位不同
    # （§9.4 的排除清單：builtAt／fetchedAt／sourceSha256／artifactDigest 不進比較）
    rerun = build_artifacts(
        build_trials(list(a_core_rows.values()), build_date),
        build_date="2026-09-18",
        fetched_at="2026-10-01T09:00:00Z",
        built_at="2026-10-01T09:00:05Z",
        source_sha256="f" * 64,
    )
    assert rerun.manifest["datasetVersion"] == out.manifest["datasetVersion"]

    git = FakeGit()
    stage(rerun, staging)
    result = promote(rerun, public, staging, git, message="data: 不該發生")
    assert result.published is False
    assert result.reason == "no normalized change"
    assert git.commits == [], "無變動時不得 commit"

    after = json.loads((public / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert after["builtAt"] == before["builtAt"], "builtAt 必須維持已發布的值"
