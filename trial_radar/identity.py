"""§6.2 identity normalization、§6.3 canonical serialization 與 ID、三層碰撞偵測。

**ID 只保證對相同來源快照穩定**（§6.3.5）。上游重排、增刪或修改欄位時 ID 可能變動；
不得宣稱 ID 跨快照代表同一實體。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .errors import ErrorCode, PipelineError
from .fields import COLUMNS, PROTOCOL
from .normalize import identity_normalize, loose_key

US = "\x1f"  # U+001F


def sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_serialization(row: dict[str, str]) -> bytes:
    """§6.3。對 16 欄的 **raw 值**（已去 BOM、未經任何正規化），依 canonical 欄位順序，
    逐欄輸出 `<UTF-8 位元組長度的十進位 ASCII>` + U+001F + `<欄位 UTF-8 位元組>`，
    欄位之間再以 U+001F 分隔。

    長度前綴使任何欄位內容（含分隔符本身）都不造成歧義——**這是 canonical serialization
    對 16 欄 tuple 一對一的依據**。

    任一欄位含 U+001F 時硬失敗 `SOURCE_CONTROL_CHAR`。實測本快照無 U+001F，故此檢查
    目前恆不觸發，**但不得省略**：省了以後分隔符可被內容偽造，identity 收斂可能把兩列併成一列。
    """
    parts = []
    for col in COLUMNS:
        v = row[col]
        if US in v:
            raise PipelineError(
                ErrorCode.SOURCE_CONTROL_CHAR,
                f"欄位含 U+001F：{col}",
                {"field": col},
            )
        parts.append(f"{len(v.encode('utf-8'))}{US}{v}")
    return US.join(parts).encode("utf-8")


@dataclass(frozen=True)
class IdentityKey:
    """§6.3.1。`kind` 為 'P'（protocol）或 'H'（內容雜湊）。"""

    kind: str
    value: str
    ordinal: int | None = None  # H: 分支才有；一律存在且從 0 起

    def render(self) -> str:
        if self.kind == "P":
            return f"P:{self.value}"
        return f"H:{self.value}#{self.ordinal}"


def trial_id(identity_key: str) -> str:
    """§6.3.3：`"t" + sha256hex(identityKey)[:16]`。"""
    return "t" + sha256hex(identity_key.encode("utf-8"))[:16]


def record_id(tid: str, canonical: bytes, ordinal: int) -> str:
    """§6.3.3：`trialId + "r" + sha256hex(canonicalSerialization)[:16] + "#" + k`。

    §6.3.2 的 ordinal 規則**同樣套用於 recordId**：一律存在且從 `#0` 起。
    """
    return f"{tid}r{sha256hex(canonical)[:16]}#{ordinal}"


def shard_key(tid: str) -> str:
    """§6.3.3：`trialId` 的第 2–3 個字元（sha256 的前 2 hex）。值域 00–ff。"""
    return tid[1:3]


def assign_identity_keys(rows: list[dict[str, str]]) -> list[IdentityKey]:
    """為每一列配出 identity key（§6.3.1／§6.3.2），順序對應輸入。

    **判定依據是 `identityNormalize` 後是否為空，不是 raw 是否為空**——空白-only 的
    protocol（如三個 ASCII 空白、U+3000）走 H: 分支，raw 仍完整保留供稽核。
    以 `raw == ""` 實作者會把那些列誤走 P: 分支並產生 identity key `"P:"` 的碰撞。

    `H:` 分支的 ordinal 由 **canonical serialization 排序後配置，不依輸入列序**。
    那些列逐位元相同，序號分配在內容上不可區分，輸出仍確定（A3 要求跨排列逐檔 hash 相同）。
    """
    canon = [canonical_serialization(r) for r in rows]

    # 先收集所有走 H: 分支的列，依 content hash 分組
    hash_groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        if identity_normalize(row[PROTOCOL]) == "":
            hash_groups.setdefault(sha256hex(canon[i]), []).append(i)

    ordinal_of: dict[int, int] = {}
    for idxs in hash_groups.values():
        # 同一 content hash 內的列逐位元相同；依 canonical 位元組排序後配號，
        # 結果與輸入列序無關
        for k, i in enumerate(sorted(idxs, key=lambda j: canon[j])):
            ordinal_of[i] = k

    keys: list[IdentityKey] = []
    for i, row in enumerate(rows):
        ident = identity_normalize(row[PROTOCOL])
        if ident:
            keys.append(IdentityKey("P", ident))
        else:
            keys.append(IdentityKey("H", sha256hex(canon[i]), ordinal_of[i]))
    return keys


def detect_identity_collision(rows: list[dict[str, str]], keys: list[IdentityKey]) -> None:
    """§6.2／§6.3.4 第一層：`strip(raw)` **不同**而 `identityNormalize` 後相同 → 硬失敗。

    fail-closed 而非保留為兩個 Trial：合併會誤配，保留兩個同鍵 Trial 會讓 URL 不唯一，
    硬失敗使月更新維持 last-known-good。

    **分組鍵是 `strip(raw)` 不是 raw**（v0.8）。`identityNormalize` 的定義本身含 `strip()`，
    以 raw 分組等於宣告「正規化不准折疊任何東西」，那樣正規化就沒有作用——實資料
    18,736 列有 4 組僅尾隨一個空白的 protocol，照舊寫法管線一次都跑不完（exit 22）。

    界線畫在 `strip` 而非「全部折疊」：尾隨空白在任何識別碼體系都不承載語意，不可能
    用來區分兩個不同試驗；大小寫與 NFKC 全形折疊則**可能**（`abc-1` 與 `ABC-1` 未必
    同一個計畫書），那兩類維持硬失敗。
    """
    # 先只分組。fingerprint 要算 canonical serialization，成本不低而絕大多數執行不會碰撞，
    # 所以**延到確定有碰撞群之後才算**，且只算該群的列。
    by_key: dict[str, dict[str, list[int]]] = {}
    for i, (row, key) in enumerate(zip(rows, keys, strict=True)):
        if key.kind != "P":
            continue
        by_key.setdefault(key.value, {}).setdefault(row[PROTOCOL].strip(), []).append(i)

    colliding = {k: v for k, v in by_key.items() if len(v) > 1}
    if not colliding:
        return

    # §9.8 兩層結構：group → members。**`trialId` 不可用來區分 member**——碰撞成員共用
    # 同一個 identity key，而 trialId 由 identity key 導出，因此群內必然相同。
    # `strippedRaw` 必須寫出：它是判定成立的依據本身，少了它看 report 的人無法分辨
    # 這是真碰撞還是實作漏了 §6.2 的 strip 而誤報。
    groups = []
    for ident, by_stripped in sorted(colliding.items()):
        members = []
        for stripped, idxs in sorted(by_stripped.items()):
            # **固定為陣列**：一個 member 可以對應多個 raw（`"ABC "` 與 `" ABC"` 的
            # strip 相同卻是同一個 member），型別時而字串時而陣列會讓讀 report 的人
            # 與 schema validator 各自猜一種。
            members.append(
                {
                    "raws": sorted({rows[i][PROTOCOL] for i in idxs}),
                    "strippedRaw": stripped,
                    "fingerprints": sorted(
                        {sha256hex(canonical_serialization(rows[i])) for i in idxs}
                    ),
                }
            )
        groups.append(
            {
                "identityNormalized": ident,
                "trialId": trial_id(IdentityKey("P", ident).render()),
                "members": members,
            }
        )

    raise PipelineError(
        ErrorCode.IDENTITY_COLLISION,
        f"{len(groups)} 個 identity 正規化碰撞群",
        {"groups": groups},
    )


def whitespace_only_variants(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """§6.2：僅前後空白不同而被合併的 protocol 群，供 QA report 揭露。

    **合併是靜默的，揭露不是。** 這些群不會造成硬失敗，但它們是上游輸入品質的訊號；
    只在程式裡合併而不寫進結構化報告，下個月多出一組時沒有任何東西會顯示出來。
    """
    by_norm: dict[str, set[str]] = {}
    for row in rows:
        raw = row[PROTOCOL]
        norm = identity_normalize(raw)
        if not norm:
            continue
        by_norm.setdefault(norm, set()).add(raw)
    return [
        {
            "identityNormalized": k,
            # §6.2：**以 Trial 為單位，一個 Trial 最多一則**，故帶 trialId。
            # 它由 identity key 導出，不需要先建出 Trial 就能算。
            "trialId": trial_id(IdentityKey("P", k).render()),
            "rawProtocols": sorted(v),
        }
        for k, v in sorted(by_norm.items())
        if len(v) > 1
    ]


def detect_truncation_collisions(
    key_to_tid: dict[str, str], record_map: dict[str, bytes]
) -> None:
    """§6.3.4 第二／三層：16-hex 截短碰撞 → 硬失敗 `ID_TRUNCATION_COLLISION`。

    實測 16,328 個不同紀錄的 16-hex 截短 0 碰撞，**仍須偵測**。
    A8 以注入的雜湊替身驅動這條分支（真實 64 位元碰撞需約 2^32 次雜湊，不可建構）。
    """
    tid_owners: dict[str, list[str]] = {}
    for ikey, tid in key_to_tid.items():
        tid_owners.setdefault(tid, []).append(ikey)
    tid_collisions = {t: sorted(v) for t, v in tid_owners.items() if len(v) > 1}

    rid_owners: dict[str, list[str]] = {}
    for rid, canon in record_map.items():
        rid_owners.setdefault(rid, []).append(sha256hex(canon))
    rid_collisions = {r: sorted(set(v)) for r, v in rid_owners.items() if len(set(v)) > 1}

    if tid_collisions or rid_collisions:
        raise PipelineError(
            ErrorCode.ID_TRUNCATION_COLLISION,
            "16-hex 截短碰撞",
            {"trialId": tid_collisions, "recordId": rid_collisions},
        )


def near_duplicate_groups(protocols: set[str]) -> dict[str, list[str]]:
    """§6.2.1：以 `looseKey` 分組，**只有含 ≥2 個不同 identity key 的組**才輸出。

    `looseKey` 為空字串者（protocol 不含任何 ASCII 英數字元）**不納入任何 group**，
    否則會把所有非編號值錯歸成一群。
    """
    groups: dict[str, set[str]] = {}
    for p in protocols:
        lk = loose_key(p)
        if not lk:
            continue
        groups.setdefault(lk, set()).add(identity_normalize(p))
    return {
        lk: sorted(idents) for lk, idents in groups.items() if len(idents) > 1
    }
