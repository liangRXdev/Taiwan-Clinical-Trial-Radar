"""由 `tests/fixtures/a_core/` 產生前端測試用的 artifact（`tests/fixtures/web_artifact/`）。

**與 `tests/fixtures/artifact_sample/` 是兩回事**：那一份是 B8 的證據，位元組被
`.gitattributes` 釘住、由 `build_sample.py` 以另一套獨立程式碼產生（規格要能被兩份程式碼
各自寫出來）。這一份相反——它**刻意就是現行 ETL 的輸出**，前端測試才會在資料契約改變時
立刻轉紅，而不是等到 M2 做完才發現前端讀的是想像中的形狀。

`tests/test_web_fixture.py` 會斷言本目錄的內容與現行 `build_artifacts` 逐位元相同。

用法：
    uv run python scripts/build_web_fixture.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trial_radar.artifacts import build_artifacts  # noqa: E402
from trial_radar.model import build_trials  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "web_artifact"

# 與 tests/conftest.py 的 BUILD_DATE 一致。**浮動的 build 當日與凍結 fixture 矛盾**
# ——§6.5 的「不晚於 build 當日」依賴當日日期。
BUILD_KW = dict(
    build_date="2026-09-18",
    fetched_at="2026-09-18T01:00:00Z",
    built_at="2026-09-18T01:02:03Z",
    source_sha256="0" * 64,
)


PROTOCOL = "臨床試驗計畫書編號"
#: 衍生列的 donor。固定挑明就不會因 a_core 補案例而悄悄換人。
WS_DONOR = "SAME-010"


def _whitespace_variant(rows: list[dict]) -> list[dict]:
    """加一列「僅尾隨空白」的衍生資料（§6.2 的合併案例）。

    **a_core 本身沒有空白變體**（`whitespace_only_variants` 對它回傳空清單），
    但前端詳情頁必須顯示合併後 Trial 的**全部** `protocolRaw`。fixture 少了這一類，
    對應的前端測試會退化成「沒有資料所以沒有反例」而靜默全綠。

    衍生而非改動 a_core：那份 fixture 的位元組被 `.gitattributes` 釘住，且 A 群的
    oracle 逐列對應，動它會連帶打翻 ETL 那一側的斷言。
    """
    donor = next(r for r in rows if r[PROTOCOL] == WS_DONOR)
    variant = dict(donor)
    variant[PROTOCOL] = donor[PROTOCOL] + " "
    # 收文號換掉，否則兩列逐位元相同，測到的是重複列而不是空白變體
    variant["TFDA收文號"] = "WEB-FIXTURE-WS"
    return [variant]


#: D1 的 canary：**每一欄一個全域唯一的 token**。
#:
#: 短欄 5 個與長欄 2 個是正面 canary（搜尋得到，且只在對應 scope 搜得到）；
#: 其餘 9 欄是負面 canary（任何 scope 都搜不到）。a_core 的自然值做不到這件事
#: ——它的「唯一值」多半同時出現在別欄，用它當 canary 測到的是巧合而不是欄位歸屬。
#:
#: token 一律 ASCII 大寫：§8.1 的 casefold 與 NFKC 折疊對它是恆等變換，
#: 搜不到時才能確定是欄位歸屬錯了，而不是正規化把 token 改掉了。
CANARY_TOKENS = {
    "臨床試驗計畫書編號": "CANARYPROTOCOLZZ",
    "臨床試驗計畫中文名稱": "CANARYTITLEZZ",
    "臨床試驗申請者": "CANARYAPPLICANTZZ",
    "適應症中文": "CANARYINDICATIONZZ",
    "TFDA收文號": "CANARYRECEIPTZZ",
    "試驗目的": "CANARYPURPOSEZZ",
    "主要評估指標": "CANARYENDPOINTZZ",
    "臨床試驗期別": "CANARYPHASEZZ",
    "本臨床試驗規模": "CANARYSCALEZZ",
    "試驗預計執行期間起": "CANARYSTARTZZ",
    "試驗預計執行期間迄": "CANARYENDZZ",
    "全球預計受試者人數": "CANARYGLOBALZZ",
    "台灣預計受試者人數": "CANARYLOCALZZ",
    "納入條件": "CANARYINCLUSIONZZ",
    "排除條件": "CANARYEXCLUSIONZZ",
    "資料更新時間": "CANARYUPDATEDZZ",
}


def _canary_row(rows: list[dict]) -> list[dict]:
    """加一列 16 欄各帶唯一 token 的衍生資料（D1）。

    衍生而非改動 a_core：那份 fixture 的位元組被 `.gitattributes` 釘住，
    且 A 群的 oracle 逐列對應，動它會連帶打翻 ETL 那一側的斷言。

    這一列刻意讓多個欄位落在「無法解析」狀態（期間、人數、更新時間都是文字），
    那是 canary 的代價而不是瑕疵——D1 驗的是**欄位歸屬**，不是解析結果。
    """
    template = dict(rows[0])
    row = {col: CANARY_TOKENS.get(col, template[col]) for col in template}
    assert set(row) == set(CANARY_TOKENS), (
        f"canary 欄位與來源欄位不符：多 {set(CANARY_TOKENS) - set(row)}、"
        f"少 {set(row) - set(CANARY_TOKENS)}"
    )
    return [row]


#: D6 的衝突 oracle：`欄位 → (值A, 值B)`。**每一個可篩選且可能衝突的欄位各一組**，
#: 外加四個長文字欄位（它們不可篩選，但照樣進 `conflictFields`）。
#:
#: a_core 只涵蓋 `臨床試驗期別`／`台灣預計受試者人數`／`全球預計受試者人數`／
#: `適應症中文`／`納入條件` 五欄；缺的七欄若不補，D6 會退化成「沒有資料所以沒有反例」
#: 而靜默全綠——那正是漏報，而漏報在本專案的風險排序裡最嚴重。
#:
#: **`資料更新時間` 不在此表且不可能在**：cohort 的定義就是「同一個可採計日期」，
#: 同一 cohort 內該欄 typed 必然相等。D6 對它立的是不變量而不是 fixture。
CONFLICT_PAIRS = {
    "本臨床試驗規模": ("多國多中心", "台灣單中心"),
    "臨床試驗申請者": ("測試甲藥廠股份有限公司", "測試乙藥廠股份有限公司"),
    "試驗預計執行期間起": ("2024/01/01", "2024/03/01"),
    "試驗預計執行期間迄": ("2027/12/31", "2028/06/30"),
    "排除條件": ("懷孕", "哺乳"),
    "試驗目的": ("評估療效", "評估安全性"),
    "主要評估指標": ("OS", "PFS"),
}

#: 衝突列共用的資料更新日。**兩列必須同日**，否則後者只是較新版本而非衝突。
CONFLICT_UPDATED_AT = "2025/06/01"


def _conflict_rows(rows: list[dict]) -> list[dict]:
    """為 `CONFLICT_PAIRS` 的每一欄產生一對同日、**只差該欄**的衍生列（D6）。

    兩列的 `TFDA收文號` 不同，那不影響結論——收文號不是呈現欄位（§6.4.1），
    不會進 `conflictFields`。若它是，這組 fixture 就會每一對都多一個衝突欄位，
    D6 的「精確集合」斷言立刻轉紅，而不是靜默通過。
    """
    donor = next(r for r in rows if r[PROTOCOL] == "BIG-001")
    out: list[dict] = []
    for n, (field, (a, b)) in enumerate(CONFLICT_PAIRS.items(), start=1):
        for half, value in enumerate((a, b)):
            row = dict(donor)
            row[PROTOCOL] = f"CONFLICT-{n:02d}"
            row["資料更新時間"] = CONFLICT_UPDATED_AT
            row["TFDA收文號"] = f"WEB-FIXTURE-CF{n:02d}{half}"
            row[field] = value
            out.append(row)
    return out


def build() -> tuple[dict[str, bytes], dict]:
    import datetime

    rows_path = ROOT / "tests" / "fixtures" / "a_core" / "rows.json"
    rows = list(json.loads(rows_path.read_text(encoding="utf-8"))["rows"].values())
    derived = _whitespace_variant(rows) + _canary_row(rows) + _conflict_rows(rows)
    trials = build_trials(rows + derived, datetime.date(2026, 9, 18))
    out = build_artifacts(trials, **BUILD_KW)
    return out.published, out.manifest


def main() -> int:
    published, manifest = build()

    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    FIXTURE.mkdir(parents=True)

    for path, data in published.items():
        target = FIXTURE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    # manifest 最後寫：它是唯一固定 URL，也是前端的入口
    (FIXTURE / "manifest.json").write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    )

    print(f"{len(published) + 1} 個檔案 → {FIXTURE.relative_to(ROOT)}")
    print(f"datasetVersion={manifest['datasetVersion']} "
          f"trialCount={manifest['trialCount']} recordCount={manifest['recordCount']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
