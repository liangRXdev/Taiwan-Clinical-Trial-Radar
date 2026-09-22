"""schemaVersion 三處對齊（ETL／前端／已發布 artifact）。

**這是 2026-09-22 那次站台停擺的對策。** 當時 `SCHEMA_VERSION` 1 → 2 推上去，
而 `public/data/` 還是 v1（資料要連網重建，不在那次 commit 裡），
部署把 v2 前端配 v1 資料送上線，前端 fail-closed，站台約 7 分鐘不可用。

部署其實**已經是原子的**（`npm run build` 把 `public/` 複製進 `dist/`，
bundle 與資料同一個 commit）。所以要擋的不是「兩者時間差」，
而是**同一個 commit 內部就不一致**。

CI 綠才觸發部署，所以這條測試紅 → 壞組合根本不會被部署。
月更新那條路徑不經過 CI，因此 `deploy.yml` 自己再跑一次同一支腳本。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_schema_alignment import (  # noqa: E402
    etl_version,
    frontend_version,
    main,
    published_version,
)


def test_三處_schemaversion_一致():
    etl, fe, pub = etl_version(), frontend_version(), published_version()
    assert etl == fe, f"ETL {etl} ≠ 前端 {fe}——兩者是同一份契約的兩側"
    if pub is not None:
        assert pub == etl, (
            f"已發布的資料是 v{pub} 而程式碼要求 v{etl}。"
            "**資料先行**：先跑一次資料更新讓新 schema 的 artifact 落地，再部署。"
        )


def test_腳本以_exit_code_表達判定():
    """CI 與部署鏈都靠 exit code，不靠訊息字串。"""
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_schema_alignment.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_前端版本不是從_build_產物讀的():
    """build 產物是這支腳本要保護的東西之一，拿它當輸入就是循環自證。"""
    src = (ROOT / "scripts" / "check_schema_alignment.py").read_text(encoding="utf-8")
    assert "src/lib/schema.ts" in src.replace("\\", "/") or 'TS_SCHEMA' in src
    assert "dist" not in src.split('"""', 2)[-1], "不得從 dist/ 讀前端版本"


@pytest.mark.parametrize(
    ("etl", "fe", "pub", "expected"),
    [
        (2, 2, 2, 0),
        (2, 2, None, 0),      # 尚未發布過，合法的初始狀態
        (2, 1, 2, 1),         # ETL 與前端不同步
        (2, 2, 1, 1),         # **2026-09-22 的那一格**：資料落後
        (1, 1, 2, 1),         # 資料超前（回退程式碼但沒回退資料）
    ],
)
def test_判定矩陣(monkeypatch, etl, fe, pub, expected):
    """**每一格都要有案例。** 只測「一致時回 0」的話，一個永遠回 0 的實作會全綠。"""
    import scripts.check_schema_alignment as mod

    monkeypatch.setattr(mod, "etl_version", lambda: etl)
    monkeypatch.setattr(mod, "frontend_version", lambda: fe)
    monkeypatch.setattr(mod, "published_version", lambda: pub)
    assert main() == expected
