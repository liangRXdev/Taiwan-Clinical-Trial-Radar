"""依序跑完全部 fixture 自檢，任一支非零即整體非零。

M1 的 CI 會用它當 gate 之一。現在先當本機入口，省得逐支記路徑。

跑法：`python tests/fixtures/run_all.py`
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CHECKS = [
    ("A 群（資料模型與收斂）", "check_a_core.py"),
    ("B 群（§9.5 失敗分類注入）", os.path.join("b_failures", "check_b_failures.py")),
    ("B8（datasetVersion／artifactDigest）", os.path.join("artifact_sample", "check_b8.py")),
    ("B6（§9.3.6 不變量反例）", os.path.join("artifact_sample", "check_b6.py")),
    ("C4（sentinel 的三個 mutation）", os.path.join("artifact_sample", "check_c4.py")),
]


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    results = []
    for label, rel in CHECKS:
        p = subprocess.run([sys.executable, os.path.join(HERE, rel)],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        results.append((label, rel, p.returncode, p.stdout))
        if p.returncode != 0:
            print(p.stdout)
            print(p.stderr, file=sys.stderr)

    width = max(len(l) for l, _, _, _ in results)
    print("\n" + "=" * (width + 22))
    for label, rel, rc, out in results:
        n_pass = out.count("  PASS  ")
        n_fail = out.count("  FAIL  ")
        print(f"{label:<{width}}  {'OK  ' if rc == 0 else 'FAIL'}  "
              f"{n_pass:>3} pass / {n_fail} fail")
    print("=" * (width + 22))

    failed = [l for l, _, rc, _ in results if rc != 0]
    if failed:
        print(f"\n{len(failed)} 支未通過：{failed}")
        return 1
    print("\n全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
