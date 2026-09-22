"""H 群驗收：CI gate、月更新、供應鏈與時區（H1／H2／H4／H5）。

**這些斷言讀的是 workflow YAML 本身**，不是「CI 有沒有跑過」。一個沒有被登記的
gate、一個被移回浮動 tag 的 `uses`、一個悄悄加上的 `continue-on-error`，
在 CI 全綠的畫面上長得跟正常一模一樣——只有對帳看得出來。

H3（上線當天 dispatch 兩次驗冪等）是**執行時**的驗收，不在本檔：它要求真的連網
跑兩次，見 `PROGRESS.md` 的上線紀錄。
"""
from __future__ import annotations

import datetime
import re
import subprocess
import sys
import zoneinfo
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_data import taipei_build_date, verify_remote_tip  # noqa: E402
from trial_radar.errors import EXIT_CODE_OF, LAYER_OF, ErrorCode, PipelineError  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
UPDATE = WORKFLOWS / "update-data.yml"
DEPLOY = WORKFLOWS / "deploy.yml"

#: 全部 workflow。供應鏈與權限的斷言一律**掃完整集合**，漏一個等於那一個沒被約束。
ALL_WORKFLOWS = [CI, UPDATE, DEPLOY]

#: §17 H1 的**最低 gate 集合**。workflow 的 job 名稱必須與此雙向相等。
#:
#: 新增 gate 要同時改這裡與 `ci.yml`，那是刻意的摩擦——只改一邊的兩種後果
#: （gate 沒跑、或 gate 沒登記）都無法從 CI 的綠燈看出來。
REQUIRED_GATES = {
    "lint",
    "typecheck",
    "pytest",
    "vitest",
    "playwright",
    "a11y",
    "payload",
}

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def all_uses(doc: dict) -> list[str]:
    out: list[str] = []
    for job in doc["jobs"].values():
        if "uses" in job:  # reusable workflow
            out.append(job["uses"])
        for step in job.get("steps", []):
            if "uses" in step:
                out.append(step["uses"])
    return out


def iter_nodes(node):
    """遞迴走訪整份 YAML，用來找**任何層級**的 `continue-on-error`。"""
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from iter_nodes(v)
    elif isinstance(node, list):
        for v in node:
            yield from iter_nodes(v)


# ───────────────────────────────────────────────────────────── H1

def test_ci_jobs_與最低_gate_集合雙向相等():
    jobs = set(load(CI)["jobs"])
    assert jobs == REQUIRED_GATES, (
        f"workflow 多出：{sorted(jobs - REQUIRED_GATES)}；"
        f"清單中而 workflow 沒有：{sorted(REQUIRED_GATES - jobs)}"
    )


def test_沒有任何_continue_on_error():
    for path in ALL_WORKFLOWS:
        for node in iter_nodes(load(path)):
            if isinstance(node, dict):
                assert "continue-on-error" not in node, f"{path.name} 出現 continue-on-error"


@pytest.mark.parametrize("path", ALL_WORKFLOWS, ids=lambda p: p.name)
def test_gate_指令不得吞掉失敗(path: Path):
    """`|| true`、`|| :`、`; true` 會讓一個失敗的 gate 亮綠燈。"""
    text = path.read_text(encoding="utf-8")
    for pattern in ("|| true", "|| :", "; true", "set +e"):
        assert pattern not in text, f"{path.name} 出現 {pattern!r}"


def test_每個_gate_都真的跑了某個指令():
    for name, job in load(CI)["jobs"].items():
        commands = [s["run"] for s in job["steps"] if "run" in s]
        assert commands, f"gate {name} 沒有任何 run 步驟"


# ───────────────────────────────────────────────────────────── H1 注入

def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    # **明示 utf-8**：Windows 的 `text=True` 走 cp950，ruff 的輸出含它解不掉的位元組
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def test_lint_gate_對注入的缺陷會失敗(tmp_path: Path):
    """**gate 要能轉紅才算 gate。** 注入一個 ruff 抓得到的缺陷，斷言 exit 非零。"""
    bad = tmp_path / "bad.py"
    bad.write_text("import os\n", encoding="utf-8")  # F401 unused-import
    ok = _run("uv", "run", "ruff", "check", "--isolated", "--select", "F", str(bad), cwd=ROOT)
    assert ok.returncode != 0, f"注入 F401 後 ruff 仍回 0：{ok.stdout}"

    good = tmp_path / "good.py"
    good.write_text("import os\n\nprint(os.name)\n", encoding="utf-8")
    clean = _run("uv", "run", "ruff", "check", "--isolated", "--select", "F", str(good), cwd=ROOT)
    assert clean.returncode == 0, f"乾淨檔案卻失敗，gate 無法分辨好壞：{clean.stdout}"


def test_payload_gate_在沒有已發布資料時_fail_closed(tmp_path: Path):
    """**沒有資料時不得回報一個只含 bundle 的漂亮數字。**"""
    out = _run(
        "uv", "run", "python", str(ROOT / "scripts" / "measure_payload.py"),
        "--out", str(tmp_path / "p.json"),
        cwd=tmp_path,  # 不在 repo 根目錄，找不到 public/data
    )
    # 腳本以 ROOT 推導路徑，故此處只斷言「缺任一前置條件即非零」
    if not (ROOT / "public" / "data" / "manifest.json").exists():
        assert out.returncode != 0
        assert "Tier 0" in out.stderr or "找不到" in out.stderr


def test_每個_fixture_檔案都在版控內():
    """**clean checkout 跑得起來才算數。**

    2026-09-22 的第一次 CI：`tests/fixtures/b_failures/inputs/*.zip` 被 `.gitignore`
    的 `*.zip`（本意是擋 42 MB 的來源下載）掃到，從未進版控。本機因為留著產生物
    而完全看不出來，clean checkout 上 B1 的整組測試以 FileNotFoundError 掛掉。

    這條掃的是**測試實際會讀的 fixture 目錄**，不是「有沒有忘記 git add」的泛泛檢查。
    """
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "tests/fixtures"],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.split()
    )
    skip_dirs = {"__pycache__"}
    skip_names = {"_num.txt"}

    missing = []
    for path in (ROOT / "tests" / "fixtures").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in skip_dirs for part in path.parts) or path.name in skip_names:
            continue
        if path.suffix in {".pyc"}:
            continue
        if rel not in tracked:
            missing.append(rel)

    assert not missing, f"fixture 未進版控，clean checkout 會失敗：{missing}"


def test_e2e_資料不得寫進已發布目錄():
    """promotion 的第二步是 `git add -A`——測試資料落在 `public/data/` 就會被當成
    正式資料集 commit 出去，而那個 commit 長得跟正常的一模一樣。"""
    script = (ROOT / "scripts" / "prepare-e2e-data.mjs").read_text(encoding="utf-8")
    target = re.search(r'^const TARGET = (.+)$', script, re.M)
    assert target is not None, "找不到 TARGET 定義"
    assert '"public"' not in target.group(1), f"e2e 資料寫進已發布目錄：{target.group(1)}"
    assert '"dist"' in target.group(1), target.group(1)


def test_ci_先_build_再複製_e2e_資料():
    """`vite build` 會清空 `dist/`；順序顛倒時 e2e 會對著 404 頁面全綠。"""
    for name in ("playwright", "a11y"):
        runs = [s["run"] for s in load(CI)["jobs"][name]["steps"] if "run" in s]
        build_i = next(i for i, c in enumerate(runs) if "npm run build" in c)
        data_i = next(i for i, c in enumerate(runs) if "e2e:data" in c)
        assert build_i < data_i, f"{name}：build 必須在複製 e2e 資料之前"


# ───────────────────────────────────────────────────────────── H4

@pytest.mark.parametrize("path", ALL_WORKFLOWS, ids=lambda p: p.name)
def test_所有_uses_釘不可變_sha(path: Path):
    for ref in all_uses(load(path)):
        assert "@" in ref, f"{path.name}：{ref} 沒有版本標記"
        _, _, rev = ref.partition("@")
        assert SHA40.match(rev), f"{path.name}：{ref} 不是 40 hex 的不可變 SHA"


@pytest.mark.parametrize("path", ALL_WORKFLOWS, ids=lambda p: p.name)
def test_預設_permissions_為最小(path: Path):
    doc = load(path)
    assert doc.get("permissions") == {"contents": "read"}, (
        f"{path.name} 的預設 permissions 不是最小集合：{doc.get('permissions')}"
    )


#: 允許提權的 job 與其**精確**權限集合。清單以外一律不得有 write。
ALLOWED_WRITE = {
    # promotion 要 commit／push；失敗要開 issue
    ("update-data.yml", "update"): {"contents", "issues"},
    # 部署本身用 Cloudflare API token，repo 這邊只需要開 issue 的權限
    ("deploy.yml", "deploy"): {"issues"},
}


def test_只有登記過的_job_擁有寫入權():
    for path in ALL_WORKFLOWS:
        for name, job in load(path)["jobs"].items():
            perms = job.get("permissions", {})
            writable = {k for k, v in perms.items() if v == "write"}
            expected = ALLOWED_WRITE.get((path.name, name), set())
            assert writable == expected, f"{path.name}:{name} 的寫入權 {writable} ≠ {expected}"


def test_部署以_ci_驗過的_commit_為輸入():
    """§9.2.3：該 commit 即 build 輸入的**唯一**來源。

    用分支 tip 會讓「CI 驗過的內容」與「實際部署的內容」在排隊期間分岔，
    而兩者在 log 上長得一模一樣。
    """
    steps = load(DEPLOY)["jobs"]["deploy"]["steps"]
    checkout = next(s for s in steps if "checkout" in s.get("uses", ""))
    assert checkout["with"]["ref"] == "${{ env.TARGET_SHA }}", checkout["with"]
    assert "workflow_run.head_sha" in load(DEPLOY)["jobs"]["deploy"]["env"]["TARGET_SHA"]


def test_月更新那條路徑不得用_workflow_run_head_sha():
    """**這個 bug 會讓每個月的資料更新靜默不上線。**

    `workflow_run.head_sha` 指的是「觸發那個 run 的 commit」，而月更新會**自己再
    commit 一個新的**（資料）。用 head_sha 會部署資料更新**之前**那份 `public/data/`，
    而部署後的線上版本驗證比的是它自己剛建的那份——所以還會通過。
    2026-09-22 因為 schemaVersion bump 才第一次顯形（站台 fail-closed）。
    """
    target = load(DEPLOY)["jobs"]["deploy"]["env"]["TARGET_SHA"]
    # head_sha 必須被 CI 這個條件包住，不能無條件使用
    assert "workflow_run.name == 'CI'" in target, f"head_sha 未以上游為條件：{target}"
    assert "github.sha" in target, "月更新那條路徑須退回分支 tip"


def test_部署記錄實際_checkout_的_commit():
    """兩條上游取 SHA 的方式不同，log 裡查得出部署的是哪一份才追得下去。"""
    runs = [s.get("run", "") for s in load(DEPLOY)["jobs"]["deploy"]["steps"]]
    assert any("git rev-parse HEAD" in r for r in runs), "沒有記錄實際 checkout 的 commit"


def test_部署同時掛在_ci_與月更新之後():
    """月更新的 commit 由 `GITHUB_TOKEN` 推送，**不會觸發 CI**。

    只掛 CI 的話資料更新永遠不會被部署出去，而且是靜默的。
    """
    doc = load(DEPLOY)
    triggers = doc.get("on") or doc.get(True)
    upstream = triggers["workflow_run"]["workflows"]
    assert set(upstream) == {"CI", "月更新資料"}, upstream
    assert triggers["workflow_run"]["branches"] == ["main"]


def test_部署只在上游成功時執行():
    cond = load(DEPLOY)["jobs"]["deploy"]["if"]
    assert "workflow_run.conclusion == 'success'" in cond, cond


def test_部署自己跑一次_payload_gate():
    """資料更新的 commit 沒跑過 CI，這是它唯一的 payload 檢查。"""
    runs = [s.get("run", "") for s in load(DEPLOY)["jobs"]["deploy"]["steps"]]
    assert any("measure_payload.py" in r for r in runs), "部署少了 payload gate"


def test_部署後驗證線上版本():
    """§9.2.3：部署啟用成功後該版本才是 authoritative。

    wrangler 回報成功但線上還是舊版時，沒有這一步就會靜默停在舊資料上。
    """
    steps = load(DEPLOY)["jobs"]["deploy"]["steps"]
    deploy_i = next(i for i, s in enumerate(steps) if "pages deploy" in s.get("run", ""))
    verify_i = next(i for i, s in enumerate(steps) if "datasetVersion" in s.get("run", "")
                    and "pages.dev" in s.get("run", ""))
    assert deploy_i < verify_i, "驗證須在部署之後"
    assert "exit 1" in steps[verify_i]["run"], "版本不符時必須 fail-closed"


def test_通知路徑不依賴既有的_label():
    """**失敗通知壞掉的時機，正好是沒有人在看的時候。**

    2026-09-22 部署鏈首次實跑：`gh issue create --label deploy` 因為 repo 沒有那個
    label 而整個指令失敗，通知完全沒發出去。兩個 workflow 的通知步驟因此都要先
    `gh label create --force`（冪等）。
    """
    for path, job in ((DEPLOY, "deploy"), (UPDATE, "update")):
        notify = next(s for s in load(path)["jobs"][job]["steps"] if s.get("if") == "failure()")
        run = notify["run"]
        assert "gh issue create" in run, path.name
        label = re.search(r'--label "([^"]+)"', run)
        assert label is not None, f"{path.name} 的通知沒有指定 label"
        assert f"gh label create {label.group(1)}" in run, (
            f"{path.name} 用了 label `{label.group(1)}` 卻沒有先建立它"
        )
        assert "--force" in run, f"{path.name} 的 label 建立不是冪等的"


def test_schema_對齊在兩條路徑上都被強制():
    """**資料先行**的兩道關。

    2026-09-22：`SCHEMA_VERSION` 1 → 2 推上去而 `public/data/` 還是 v1，
    部署把 v2 前端配 v1 資料送上線，站台約 7 分鐘不可用。
    部署本身是原子的（build 把 `public/` 複製進 `dist/`），
    要擋的是**同一個 commit 內部就不一致**。
    """
    ci_runs = [s.get("run", "") for s in load(CI)["jobs"]["pytest"]["steps"]]
    assert any("check_schema_alignment.py" in r for r in ci_runs), "CI 沒有 schema 對齊 gate"

    dep = load(DEPLOY)["jobs"]["deploy"]["steps"]
    dep_runs = [s.get("run", "") for s in dep]
    assert any("check_schema_alignment.py" in r for r in dep_runs), (
        "部署鏈沒有 schema 對齊 gate——月更新那條路徑不經過 CI"
    )

    # **必須在部署之前**，否則擋不住
    check_i = next(i for i, r in enumerate(dep_runs) if "check_schema_alignment.py" in r)
    deploy_i = next(i for i, r in enumerate(dep_runs) if "pages deploy" in r)
    assert check_i < deploy_i, "schema 對齊須在部署之前"


def test_f1_的真實量測有進部署_gate():
    """**F1 的 oracle 是部署端實收位元組，不是建置期估算。**

    M4 稽核發現：`measure-f1-live.mjs` 寫好了卻沒有被任何 workflow 呼叫，
    於是 F1 的四條量測邊界在 gate 層級一條都沒被強制——綠燈只代表
    `measure_payload.py` 的建置期估算通過，而那支腳本自己寫明它不能宣告 F1 通過。
    """
    steps = load(DEPLOY)["jobs"]["deploy"]["steps"]
    runs = [s.get("run", "") for s in steps]
    assert any("measure-f1-live.mjs" in r for r in runs), "部署鏈沒有跑真實部署的 F1 量測"

    # 必須在部署**之後**——量的是線上那一份
    deploy_i = next(i for i, r in enumerate(runs) if "pages deploy" in r)
    f1_i = next(i for i, r in enumerate(runs) if "measure-f1-live.mjs" in r)
    assert deploy_i < f1_i, "F1 量測須在部署之後"

    # 報告要留成 artifact（F1：列出納入檔案清單與總和寫入 CI artifact）
    assert any("reports/" in str(s.get("with", {}).get("path", "")) for s in steps), "F1 報告未留存"


def test_部署失敗會開_issue():
    steps = load(DEPLOY)["jobs"]["deploy"]["steps"]
    notify = next(s for s in steps if s.get("if") == "failure()")
    assert "gh issue create" in notify["run"]


def test_wrangler_版本釘死():
    """浮動版本＝把部署內容交給第三方隨時替換（H4 的同一條理由）。"""
    env = load(DEPLOY)["jobs"]["deploy"]["env"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(env["WRANGLER_VERSION"])), env["WRANGLER_VERSION"]
    runs = " ".join(s.get("run", "") for s in load(DEPLOY)["jobs"]["deploy"]["steps"])
    assert "wrangler@${WRANGLER_VERSION}" in runs, "部署指令未使用釘死的版本"


def test_ci_沒有任何_job_提權():
    for name, job in load(CI)["jobs"].items():
        assert "permissions" not in job, f"CI 的 {name} 不該覆寫 permissions"


# ───────────────────────────────────────────────────────────── H2

def test_月更新同時支援排程與手動且共用同一個_concurrency_group():
    doc = load(UPDATE)
    # PyYAML 會把裸 `on` 解析成布林 True（YAML 1.1），兩種鍵都接受
    triggers = doc.get("on") or doc.get(True)
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers

    conc = doc["concurrency"]
    assert isinstance(conc, dict)
    # **group 不得含 event name／ref**：含了就等於排程與手動各自一個佇列
    assert conc["group"] == "update-data", conc["group"]
    assert conc["cancel-in-progress"] is False, (
        "取消進行中的 run 可能落在 `git add -A` 與 commit 之間，那正是 §9.2.1 要排除的部分發布"
    )


def test_baseline_在取得發布權之後才取樣():
    """`actions/checkout` 預設取觸發時的 SHA；排隊後那是舊的。"""
    steps = load(UPDATE)["jobs"]["update"]["steps"]
    checkout_idx = next(i for i, s in enumerate(steps) if "checkout" in s.get("uses", ""))
    baseline_idx = next(i for i, s in enumerate(steps) if s.get("id") == "baseline")
    run_idx = next(i for i, s in enumerate(steps) if s.get("id") == "run")

    assert checkout_idx < baseline_idx < run_idx, "baseline 取樣須在 checkout 之後、管線之前"
    script = steps[baseline_idx]["run"]
    assert "git fetch" in script and "rev-parse" in script, "baseline 未顯式取遠端 tip"


def test_promotion_前再驗證版本未變():
    run_step = next(s for s in load(UPDATE)["jobs"]["update"]["steps"] if s.get("id") == "run")
    assert "--expect-head" in run_step["run"]
    assert "baseline.outputs.sha" in str(run_step.get("env", {}))


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


def _repo_with_remote(tmp_path: Path) -> tuple[Path, Path]:
    """建一個 clone ＋ 它的 origin。回傳 (工作副本, 上游)。"""
    upstream = tmp_path / "upstream.git"
    work = tmp_path / "work"
    seed = tmp_path / "seed"

    subprocess.run(["git", "init", "-q", "--bare", str(upstream)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    _git(seed, "config", "user.email", "t@example.com")
    _git(seed, "config", "user.name", "t")
    (seed / "a.txt").write_text("1", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "init")
    _git(seed, "remote", "add", "origin", str(upstream))
    _git(seed, "push", "-q", "origin", "main")

    subprocess.run(["git", "clone", "-q", str(upstream), str(work)], check=True)
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    return work, seed


def _in(cwd: Path, fn):
    import os

    prev = os.getcwd()
    os.chdir(cwd)
    try:
        return fn()
    finally:
        os.chdir(prev)


def test_tip_未變時放行(tmp_path: Path):
    """正向：沒有這條，一個「永遠拋錯」的實作也會讓下面那條全綠。"""
    work, _ = _repo_with_remote(tmp_path)
    tip = _git(work, "rev-parse", "origin/main")
    _in(work, lambda: verify_remote_tip("origin/main", tip))


def test_版本已變時_fail_closed(tmp_path: Path):
    """H2 的重疊情境：管線跑完前另一個 run 已發布 → **不得覆蓋**。"""
    work, seed = _repo_with_remote(tmp_path)
    stale = _git(work, "rev-parse", "origin/main")

    # 另一個 run 在這段期間發布了
    (seed / "b.txt").write_text("2", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "another run published")
    _git(seed, "push", "-q", "origin", "main")
    moved = _git(seed, "rev-parse", "HEAD")
    assert moved != stale

    with pytest.raises(PipelineError) as e:
        _in(work, lambda: verify_remote_tip("origin/main", stale))

    assert e.value.code is ErrorCode.BASELINE_MOVED
    assert e.value.detail["expected"] == stale
    assert e.value.detail["actual"] == moved


def test_無法確認_tip_時同樣_fail_closed(tmp_path: Path):
    """「問不到」與「已變」在發布安全性上是同一件事，不得因為 fetch 失敗就放行。"""
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("1", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")

    with pytest.raises(PipelineError) as e:  # 沒有 origin
        _in(tmp_path, lambda: verify_remote_tip("origin/main", "0" * 40))
    assert e.value.code is ErrorCode.BASELINE_MOVED


def test_baseline_moved_的_error_code_契約():
    assert LAYER_OF[ErrorCode.BASELINE_MOVED].value == "publish"
    codes = list(EXIT_CODE_OF.values())
    assert len(codes) == len(set(codes)), "exit code 必須兩兩相異"
    assert all(c != 0 for c in codes), "error code 的 exit code 不得為 0"


# ───────────────────────────────────────────────────────────── H5

@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        # 台北已是次日：UTC 16:00 起
        ("2026-09-21T16:00:00", "2026-09-22"),
        ("2026-09-21T23:59:59", "2026-09-22"),
        # 邊界另一側：UTC 15:59:59 仍是同日
        ("2026-09-21T15:59:59", "2026-09-21"),
        ("2026-09-21T00:00:00", "2026-09-21"),
        # 跨月與跨年
        ("2026-09-30T16:00:00", "2026-10-01"),
        ("2026-12-31T16:00:00", "2027-01-01"),
    ],
)
def test_builddate_以台北日曆日產生(utc: str, expected: str):
    now = datetime.datetime.fromisoformat(utc).replace(tzinfo=datetime.UTC)
    assert taipei_build_date(now).isoformat() == expected


def test_以_runner_的_utc_日期實作者必須失敗():
    """H5 的反向哨兵：若實作直接用 UTC 日期，上面那組會有一半對不上。"""
    now = datetime.datetime(2026, 9, 21, 16, 0, tzinfo=datetime.UTC)
    assert taipei_build_date(now) != now.date(), "UTC 與台北在此刻本就不同日"
    assert taipei_build_date(now) == now.astimezone(zoneinfo.ZoneInfo("Asia/Taipei")).date()
