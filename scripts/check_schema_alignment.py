"""三處 schemaVersion 必須一致：ETL、前端、已發布的 artifact。

**這是「資料先行」的強制點。** 部署是原子的（`npm run build` 把 `public/` 複製進
`dist/`，bundle 與資料同一個 commit），所以真正的風險不是兩者時間差，而是
**同一個 commit 內部就不一致**——改了 schema、推了程式碼，但 `public/data/` 還是
上一版的 artifact。那個 commit 一旦部署，前端會對資料 fail-closed，整個站台不可用。

2026-09-22 就是這樣壞了約 7 分鐘：`SCHEMA_VERSION` 1 → 2 推上去，
而 `public/data/` 還是 v1（資料要連網重建，不在那次 commit 裡）。

擋法：

- **CI 跑這支**（`tests/test_schema_alignment.py`）→ schema 改了而資料沒跟上時 CI 紅，
  而部署只在 CI 綠時觸發，所以壞組合根本不會被部署。
- **部署鏈也跑這支** → 月更新那條路徑不經過 CI，需要自己再驗一次。

修法不是「調整部署順序」而是「資料先行」：改 schema 後先跑一次資料更新
（`update-data.yml`，會以新 schema 重建並 commit），資料 commit 落地後
分支 tip 才是一致的，那時部署才會通過。

用法：
    uv run python scripts/check_schema_alignment.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "public" / "data" / "manifest.json"
TS_SCHEMA = ROOT / "src" / "lib" / "schema.ts"


def etl_version() -> int:
    """ETL 端的 `SCHEMA_VERSION`。直接 import，不用正規表示式猜。"""
    sys.path.insert(0, str(ROOT))
    from trial_radar.artifacts import SCHEMA_VERSION

    return SCHEMA_VERSION


def frontend_version() -> int:
    """前端的 `SUPPORTED_SCHEMA_VERSION`。

    以正規表示式讀 TS 原始碼——這裡**不可以**改成從 build 產物讀：
    build 產物是這支腳本要保護的東西之一，拿它當輸入就是循環。
    """
    text = TS_SCHEMA.read_text(encoding="utf-8")
    m = re.search(r"SUPPORTED_SCHEMA_VERSION\s*=\s*(\d+)", text)
    if m is None:
        raise SystemExit(f"在 {TS_SCHEMA.relative_to(ROOT)} 找不到 SUPPORTED_SCHEMA_VERSION")
    return int(m.group(1))


def published_version() -> int | None:
    """已發布 artifact 的 `schemaVersion`。尚未發布過時回 None。"""
    if not MANIFEST.exists():
        return None
    return int(json.loads(MANIFEST.read_text(encoding="utf-8"))["schemaVersion"])


def main() -> int:
    etl = etl_version()
    fe = frontend_version()
    pub = published_version()

    print(f"  ETL   （trial_radar/artifacts.py）  schemaVersion = {etl}")
    print(f"  前端  （src/lib/schema.ts）        supported     = {fe}")
    print(f"  已發布（public/data/manifest.json）schemaVersion = {pub}")

    if etl != fe:
        print(
            f"\nETL 與前端的 schemaVersion 不一致（{etl} ≠ {fe}）。"
            "兩者是同一份契約的兩側，必須同時改。",
            file=sys.stderr,
        )
        return 1

    if pub is None:
        # 尚未發布過任何 artifact——這是合法的初始狀態，不擋
        print("\n尚未發布過 artifact，略過已發布版本的比對。")
        return 0

    if pub != etl:
        print(
            f"\n**已發布的資料是 schemaVersion {pub}，而程式碼要求 {etl}。**\n"
            "部署這個組合會讓前端對資料 fail-closed，整個站台不可用。\n"
            "\n"
            "**資料先行**：先跑一次 `update-data.yml`（會以新 schema 重建並 commit），\n"
            "資料 commit 落地之後分支 tip 才是一致的，那時部署才會通過。",
            file=sys.stderr,
        )
        return 1

    print("\n三處一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
