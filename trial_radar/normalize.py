"""§6.0 字元集與正規化的基礎定義。其餘各節引用本檔，**不得各自重寫**。

`searchNormalize` 與 `identityNormalize` **各自獨立驗證，不得共用實作**（§6.2）——
兩者看起來相近但用途相反：identity 要保守（不折疊標點與空白，寧可拆成兩個 Trial），
search 要寬鬆（折疊大小寫與空白，寧可多命中）。共用一份實作時，任一方的調整都會
靜默改變另一方。
"""
from __future__ import annotations

import re
import unicodedata

# §6.0：**ASCII 英數字元僅指 A–Z、a–z、0–9**，不含任何非 ASCII 字元。
# 必須明定，否則實作會相反：Python 的 "系統測試".isalnum() 回傳 True（中文被視為字母），
# 以 isalnum() 實作 §6.2.2 會使 `系統測試` **不會**被標記為 protocolNonIdentifier。
_NON_ASCII_ALNUM = re.compile(r"[^0-9A-Za-z]")
_WHITESPACE = re.compile(r"\s+")


def nfkc(s: str | None) -> str:
    return unicodedata.normalize("NFKC", s or "")


def identity_normalize(s: str | None) -> str:
    """`nfkc(strip(s))` 後轉大寫。**不做**標點移除、不壓內部空白、不剝前後綴。"""
    return nfkc((s or "").strip()).upper()


def loose_key(s: str | None) -> str:
    """`nfkc(s)` 後移除**所有非 ASCII 英數字元**再轉大寫。

    **僅用於偵測近似 protocol，絕不用於收斂**（§6.2.1）。
    """
    return _NON_ASCII_ALNUM.sub("", nfkc(s)).upper()


def conflict_text(s: str | None) -> str:
    """`nfkc(s)` 後移除**全部空白**（含全形空白）。用於 §6.4.2 的比較鍵。"""
    return _WHITESPACE.sub("", nfkc(s))


def search_normalize(s: str | None) -> str:
    """`nfkc(strip(s))` → casefold → 內部連續空白壓為單一空格（§8.1）。

    **不做**標點移除、不做連字號正規化。
    """
    return _WHITESPACE.sub(" ", nfkc((s or "").strip()).casefold())


#: §6.0 `strip` 的封閉字元集合：Unicode `White_Space=Yes` 的全部碼點。
#: **刻意不用 `\s`**：Python 的 `\s` 另含 U+001C–U+001F（非 White_Space），
#: 零寬字元（U+200B／U+FEFF／U+200C／U+200D）兩者都不含。facetNormalize 的壓縮與
#: strip 都以這組為準（r6 R6-1），其餘正規化維持既有實作，不在本次範圍。
_WHITE_SPACE = (
    "\u0009-\u000d \u0085   - "
    "    　"
)
_FACET_WS_RUN = re.compile(f"[{_WHITE_SPACE}]+")


def facet_normalize(s: str | None) -> str:
    """`nfkc(s)` → 內部連續空白壓為單一 U+0020 → 去前後空白（§6.0）。**只用於 applicant facet 的分組鍵**。

    空白一律指 `White_Space=Yes`（見 `_WHITE_SPACE`）；零寬字元不是空白，不被壓縮也不被移除。

    與 `search_normalize` 差在**不做 casefold**：facet 鍵會原樣顯示為篩選選項與統計卡
    標籤，而實測（2026-10-22，370 bucket）casefold 不多合併任何一組。

    為什麼需要：applicant 原本以 raw typed 分 bucket，只差尾隨空白／`\\t`／`\\r\\n`／
    CJK 相容字（U+F9B3）的同一申請者被拆成多個 bucket——實測 7 組、124 個 Trial
    落在旁支，最大一組勾主選項會漏掉 116/278（42%）。

    `nfkc` 放在 strip **之前**：NFKC 會把某些非空白字元展開出空白（如 U+00A8 `¨` →
    U+0020 U+0308），先 strip 再 NFKC 可能留下前後空白。

    回傳空字串代表「正規化後無內容」（如 typed 為 `" \\t"`），呼叫端須歸「未提供」，
    不得成為 bucket（§9.3.5）。
    """
    return _FACET_WS_RUN.sub(" ", nfkc(s)).strip(" ")


def has_ascii_alnum(s: str | None) -> bool:
    """§6.2.2：protocol 是否含任何 ASCII 英數字元。等價於 `loose_key(s) != ""`。"""
    return loose_key(s) != ""
