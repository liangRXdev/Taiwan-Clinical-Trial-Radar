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


def has_ascii_alnum(s: str | None) -> bool:
    """§6.2.2：protocol 是否含任何 ASCII 英數字元。等價於 `loose_key(s) != ""`。"""
    return loose_key(s) != ""
