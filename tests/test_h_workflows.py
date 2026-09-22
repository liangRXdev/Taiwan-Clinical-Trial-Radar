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
    for path in (CI, UPDATE):
        for node in iter_nodes(load(path)):
            if isinstance(node, dict):
                assert "continue-on-error" not in node, f"{path.name} 出現 continue-on-error"


@pytest.mark.parametrize("path", [CI, UPDATE], ids=lambda p: p.name)
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

@pytest.mark.parametrize("path", [CI, UPDATE], ids=lambda p: p.name)
def test_所有_uses_釘不可變_sha(path: Path):
    for ref in all_uses(load(path)):
        assert "@" in ref, f"{path.name}：{ref} 沒有版本標記"
        _, _, rev = ref.partition("@")
        assert SHA40.match(rev), f"{path.name}：{ref} 不是 40 hex 的不可變 SHA"


@pytest.mark.parametrize("path", [CI, UPDATE], ids=lambda p: p.name)
def test_預設_permissions_為最小(path: Path):
    doc = load(path)
    assert doc.get("permissions") == {"contents": "read"}, (
        f"{path.name} 的預設 permissions 不是最小集合：{doc.get('permissions')}"
    )


def test_只有資料更新_job_擁有寫入權():
    for path in (CI, UPDATE):
        for name, job in load(path)["jobs"].items():
            perms = job.get("permissions", {})
            writable = {k for k, v in perms.items() if v == "write"}
            if path is UPDATE and name == "update":
                assert writable == {"contents", "issues"}, writable
            else:
                assert not writable, f"{path.name}:{name} 不該有寫入權：{writable}"


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
