/**
 * §7.4／E8：`?protocol=` 的 identity 比對、canonical 導向與拒收規則。
 *
 * **這條驗收原本是靜默不存在的**：`urlState.ts` 有 parse 與 build，URL 會原樣
 * 保留 `?protocol=`，但 `app.ts` 從不讀 `state.protocol`——使用者以為查了，
 * 看到的卻是未篩選的瀏覽頁。M4 的規格符合度稽核才把它挖出來。
 */

import { describe, expect, it } from "vitest";

import { hasAsciiAlnum, identityNormalize, lookupProtocol } from "../../src/lib/protocol.js";
import { LABEL } from "../../src/ui/text.js";
import { trials } from "./fixture.js";

/** 有合法編號、且未被標為 non-identifier 的 Trial。 */
const usable = trials.find((t) => !t.protocolNonIdentifier && t.protocolRaw.length > 0)!;

describe("§6.0 identityNormalize（與 Python 的 identity_normalize 同一定義）", () => {
  it("strip → NFKC → upper", () => {
    expect(identityNormalize("  mk-3475-158  ")).toBe("MK-3475-158");
    expect(identityNormalize("ＭＫ－３４７５")).toBe("MK-3475");
  });

  it("**不剝標點、不壓內部空白**——那是 identity 與 search 的分界", () => {
    expect(identityNormalize("MK-3475-158")).not.toBe(identityNormalize("MK3475158"));
    expect(identityNormalize("CGMH 2311280002")).not.toBe(identityNormalize("CGMH2311280002"));
    expect(identityNormalize("9785-CL-  0123")).toBe("9785-CL-  0123");
  });

  it("空白-only 正規化後為空字串", () => {
    expect(identityNormalize("   ")).toBe("");
    expect(identityNormalize("　")).toBe("");
  });
});

describe("§6.0 hasAsciiAlnum（ASCII 英數僅指 A–Z a–z 0–9）", () => {
  it("**中文不算英數**——Unicode 屬性類別與 Python 的 `isalnum()` 會判反", () => {
    expect(hasAsciiAlnum("系統測試")).toBe(false);
    expect(hasAsciiAlnum("未列編號")).toBe(false);
    // JS 的 `\w` 預設就是 ASCII-only，這一側天然安全；真正的陷阱是 Unicode 屬性
    // 類別，以及 Python 的 `isalnum()`——後者正是 §6.0 特別點名的那個坑。
    expect(/\w/.test("系統測試"), "JS 的 \\w 是 ASCII-only").toBe(false);
    expect(/\p{Alphabetic}/u.test("系統測試"), "改用 Unicode 屬性就會判反").toBe(true);
  });

  it("全形英數 NFKC 後算數", () => {
    expect(hasAsciiAlnum("ＭＫ１")).toBe(true);
  });

  it("含任一 ASCII 英數即成立", () => {
    expect(hasAsciiAlnum("IRB編號：A1")).toBe(true);
    expect(hasAsciiAlnum("（）－")).toBe(false);
  });
});

describe("§7.4 lookupProtocol", () => {
  it("精確命中 → 回傳該 Trial", () => {
    const raw = usable.protocolRaw[0]!;
    expect(lookupProtocol(trials, raw)).toEqual({ kind: "match", trialId: usable.id });
  });

  it("大小寫與全形差異仍命中（identity 正規化後比對）", () => {
    const raw = usable.protocolRaw[0]!;
    expect(lookupProtocol(trials, raw.toLowerCase())).toEqual({
      kind: "match",
      trialId: usable.id,
    });
    expect(lookupProtocol(trials, `  ${raw}  `)).toEqual({ kind: "match", trialId: usable.id });
  });

  it("**少一個連字號不得命中**——identity 不剝標點，那是兩個 Trial", () => {
    const withHyphen = trials.find((t) => t.protocolRaw.includes("MK-3475-158"));
    const without = trials.find((t) => t.protocolRaw.includes("MK3475-158"));
    expect(withHyphen).toBeDefined();
    expect(without).toBeDefined();
    expect(lookupProtocol(trials, "MK-3475-158")).toEqual({
      kind: "match",
      trialId: withHyphen!.id,
    });
    expect(lookupProtocol(trials, "MK3475-158")).toEqual({ kind: "match", trialId: without!.id });
  });

  it("**E8：non-identifier 的值不接受**，且不得說成「查無結果」", () => {
    const bad = trials.find((t) => t.protocolNonIdentifier && t.protocolRaw.length > 0);
    expect(bad, "fixture 須有 protocolNonIdentifier 的 Trial").toBeDefined();
    expect(lookupProtocol(trials, bad!.protocolRaw[0]!)).toEqual({
      kind: "rejected",
      reason: "nonIdentifier",
    });
  });

  it("純中文／純符號值直接拒收（不必先查得到）", () => {
    expect(lookupProtocol(trials, "系統測試")).toEqual({ kind: "rejected", reason: "nonIdentifier" });
    expect(lookupProtocol(trials, "（）")).toEqual({ kind: "rejected", reason: "nonIdentifier" });
    expect(lookupProtocol(trials, "   ")).toEqual({ kind: "rejected", reason: "nonIdentifier" });
  });

  it("形狀合法但本站沒有 → `notFound`，**與 `rejected` 分開**", () => {
    expect(lookupProtocol(trials, "NOSUCHPROTOCOL-9999")).toEqual({ kind: "notFound" });
  });

  it("兩種失敗的文案不同，且 notFound 明說「不代表該試驗不存在」", () => {
    expect(LABEL.protocolRejected("系統測試")).not.toBe(LABEL.protocolNotFound("系統測試"));
    expect(LABEL.protocolNotFound("X")).toContain("不代表該試驗不存在");
    expect(LABEL.protocolRejected("X")).toContain("不是計畫書編號");
  });
});
