"""Tier 0 payload 的**建置期估算**，寫成 CI artifact（F1／F2 的對照用）。

**這支腳本不判定 F1。** F1 的唯一 oracle 是部署端實際 response 的實收位元組
（plan.md §17 F1 的四條量測邊界），而本腳本算的是 brotli quality 11 的建置期估算值。
Cloudflare 的動態壓縮約 q4–q5，**比 q11 大**，所以這裡的數字**一定低估**。

那它有什麼用：**單向的 fail-closed**。低估值都已經超過門檻時，實際傳輸必然也超過，
不必等部署就知道有問題。反過來則什麼都不能宣告——通過本腳本不代表 F1 通過。
拿它宣告 F1 合格，與 v0.7 用 gzip 宣告合格是同一個錯。

Tier 0 的檔案集合（§17 F1）：
  資料層（封閉，恰為三個）  manifest.json ＋ trials-index.<h>.json ＋ stats.<h>.json
  bundle                    `dist/` 的 HTML／JS／CSS

用法：
    uv run python scripts/measure_payload.py --out reports/payload.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import brotli

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DATA = ROOT / "public" / "data"
DIST = ROOT / "dist"

#: §17 F1：以整數 bytes 封存的十進位門檻。**不得改寫成 1,572,864**——
#: v0.8 同時存在兩個口徑，落在中間的 bundle 可依任一口徑宣告通過。
THRESHOLD_BYTES = 1_500_000

#: bundle 端納入量測的副檔名。**本站不載入任何外部資源**（含網頁字型），
#: 有一天改為自託管字型時這裡要一起加，否則會漏算。
BUNDLE_SUFFIXES = {".html", ".js", ".css"}

#: §11 F2：按需檔案的壓縮基線。**不計入 F1**，超出記錄值 20% 在 CI 告警。
BASELINE_PATH = ROOT / "payload-baseline.json"


def brotli_size(data: bytes) -> int:
    """quality 11。**與 manifest 的 `brotliBytes` 同一組參數**，兩者才可對照。"""
    return len(brotli.compress(data, quality=11))


def tier0_data_files(manifest: dict) -> list[tuple[str, Path]]:
    """資料層的封閉子集合：manifest 自身 ＋ trials-index ＋ stats。

    **不是「全部 public/data」**：search 檔與 shard 都在按需路徑上，冷啟動不下載。
    把它們算進來會得到一個沒有任何使用者付過的數字。
    """
    out = [("manifest.json", PUBLIC_DATA / "manifest.json")]
    for key in ("trialsIndex", "stats"):
        rel = manifest["files"][key]["path"]
        out.append((rel, PUBLIC_DATA / rel))
    return out


def check_on_demand(manifest: dict) -> dict:
    """§11 F2：逐一重算按需檔案的 q11，與基線比較。

    **以 artifact 的實際位元組重算，不讀 manifest 的 `brotliBytes`**——
    後者是 manifest 自己宣稱的值，而 `datasetVersion` 與 `artifactDigest` 都不含
    manifest 自身（§9.3.2），改它不會讓任何 digest 比較轉紅。拿它當基線比較的輸入
    等於「manifest 說多少就信多少」的循環自證。
    """
    if not BASELINE_PATH.exists():
        return {"status": "no-baseline", "files": [], "warnings": []}

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    ratio_limit = baseline.get("warnRatio", 1.20)

    files, warnings = [], []
    for key, recorded in baseline["files"].items():
        meta = manifest["files"].get(key)
        if meta is None:
            warnings.append({"file": key, "brotliBytes": 0, "baselineBytes": recorded["brotliBytes"],
                             "ratio": 0.0, "note": "manifest 已無此檔"})
            continue
        path = PUBLIC_DATA / meta["path"]
        actual = brotli_size(path.read_bytes())
        base_bytes = recorded["brotliBytes"]
        ratio = actual / base_bytes if base_bytes else float("inf")
        row = {"file": key, "path": meta["path"], "brotliBytes": actual,
               "baselineBytes": base_bytes, "ratio": round(ratio, 4)}
        files.append(row)
        if ratio > ratio_limit:
            warnings.append(row)

    return {"status": "ok", "warnRatio": ratio_limit, "files": files, "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    manifest_path = PUBLIC_DATA / "manifest.json"
    if not manifest_path.exists():
        # **fail-closed**：沒有已發布的資料時不得回報一個只含 bundle 的漂亮數字。
        print(
            f"找不到 {manifest_path.relative_to(ROOT)}；"
            "Tier 0 量測須以已發布的 public/data/ 為對象（尚未跑過資料發布？）",
            file=sys.stderr,
        )
        return 2
    if not DIST.exists():
        print(f"找不到 {DIST.relative_to(ROOT)}；請先 npm run build", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    entries: list[dict] = []
    for label, path in tier0_data_files(manifest):
        if not path.exists():
            print(f"manifest 指向不存在的檔案：{label}", file=sys.stderr)
            return 2
        entries.append({"kind": "data", "path": label, "brotliBytes": brotli_size(path.read_bytes())})

    for path in sorted(DIST.rglob("*")):
        if path.is_file() and path.suffix in BUNDLE_SUFFIXES:
            entries.append({
                "kind": "bundle",
                "path": str(path.relative_to(DIST)).replace("\\", "/"),
                "brotliBytes": brotli_size(path.read_bytes()),
            })

    total = sum(e["brotliBytes"] for e in entries)
    over = total > THRESHOLD_BYTES

    on_demand = check_on_demand(manifest)

    report = {
        "note": (
            "建置期 brotli q11 估算值，**不是 F1 的驗收結果**。"
            "Cloudflare 動態壓縮約 q4–q5，實際傳輸大於此值。"
        ),
        "datasetVersion": manifest["datasetVersion"],
        "thresholdBytes": THRESHOLD_BYTES,
        "totalBrotliBytes": total,
        "headroomBytes": THRESHOLD_BYTES - total,
        "exceedsThreshold": over,
        "files": entries,
        # §11 F2：與 Tier 0 **分開列出**，不相加——兩者的門檻與語意都不同
        "onDemand": on_demand,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    for e in entries:
        print(f"  {e['kind']:6} {e['brotliBytes']:>9,}  {e['path']}")
    print(f"  {'TOTAL':6} {total:>9,}  （門檻 {THRESHOLD_BYTES:,}，餘 {THRESHOLD_BYTES - total:,}）")

    for w in on_demand["warnings"]:
        print(
            f"  ⚠ F2：{w['file']} 為 {w['brotliBytes']:,} bytes，"
            f"超出基線 {w['baselineBytes']:,} 的 {w['ratio']:.0%}",
            file=sys.stderr,
        )
    if on_demand["warnings"]:
        # **告警不是失敗**（§11 F2）：上游資料長大是正常的，要的是有人看到並決定，
        # 不是擋住月更新。真正該擋的是 F1，那由 total 判定。
        print("  （F2 為告警，不影響 exit code）", file=sys.stderr)

    if over:
        print(
            "估算值已超過門檻——實際傳輸只會更大，不必等部署即可判定 F1 不合格。",
            file=sys.stderr,
        )
        return 1
    print("估算值在門檻內。**這不等於 F1 通過**，F1 要對真實部署量過才算數。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
