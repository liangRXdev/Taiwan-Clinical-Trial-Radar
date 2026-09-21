/**
 * G2 的對比實算工具。
 *
 * **當場計算，不憑目視**（G2 明文）。house style 也記著同一條教訓：
 * 2026-08-20 曾把 4.26:1 說成 4.8:1，而那兩個數字落在 AA 判定的兩側。
 *
 * 背景取**實際堆疊後的顏色**：元素自己可能是 `transparent`，真正的背景來自祖先。
 * 只取自身 `background-color` 會對每個沒設背景的元素算出「黑字對透明」這種無意義的值。
 */

import type { Page } from "@playwright/test";

export interface ContrastSample {
  selector: string;
  text: string;
  fg: string;
  bg: string;
  ratio: number;
  fontSizePx: number;
  bold: boolean;
  /** WCAG AA：大字（≥24px，或 ≥18.66px 且粗體）門檻 3:1，其餘 4.5:1 */
  threshold: number;
  passes: boolean;
}

/**
 * 量測頁面上所有**帶可見文字**的元素。
 *
 * 只量葉節點（沒有元素子節點者）——祖先的 textContent 包含全部子孫文字，
 * 對它算對比會把一堆不同顏色的文字算成同一組。
 */
export async function sampleContrast(page: Page): Promise<ContrastSample[]> {
  return page.evaluate(() => {
    function parse(c: string): [number, number, number, number] {
      const m = c.match(/rgba?\(([^)]+)\)/);
      if (!m) return [0, 0, 0, 1];
      const parts = m[1]!.split(",").map((x) => parseFloat(x.trim()));
      return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0, parts[3] ?? 1];
    }

    function over(fg: [number, number, number, number], bg: [number, number, number]): [number, number, number] {
      const a = fg[3];
      return [
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
      ];
    }

    function luminance([r, g, b]: [number, number, number]): number {
      const f = (v: number) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    }

    function ratio(a: [number, number, number], b: [number, number, number]): number {
      const l1 = luminance(a);
      const l2 = luminance(b);
      const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
      return (hi + 0.05) / (lo + 0.05);
    }

    /** 沿祖先鏈堆疊背景，直到遇到不透明的那一層。 */
    function effectiveBg(node: Element): [number, number, number] {
      const stack: Array<[number, number, number, number]> = [];
      let cur: Element | null = node;
      while (cur !== null) {
        const c = parse(getComputedStyle(cur).backgroundColor);
        if (c[3] > 0) stack.push(c);
        if (c[3] === 1) break;
        cur = cur.parentElement;
      }
      let base: [number, number, number] = [255, 255, 255];
      for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i]!, base);
      return base;
    }

    function cssPath(node: Element): string {
      const parts: string[] = [];
      let cur: Element | null = node;
      while (cur !== null && parts.length < 4) {
        let seg = cur.tagName.toLowerCase();
        if (cur.className && typeof cur.className === "string") {
          seg += "." + cur.className.trim().split(/\s+/).slice(0, 2).join(".");
        }
        parts.unshift(seg);
        cur = cur.parentElement;
      }
      return parts.join(" > ");
    }

    const out: unknown[] = [];
    for (const node of document.querySelectorAll("body *")) {
      if (node.querySelector("*") !== null) continue; // 只量葉節點
      const text = (node.textContent ?? "").trim();
      if (text === "") continue;

      const style = getComputedStyle(node);
      if (style.visibility === "hidden" || style.display === "none") continue;
      const rect = node.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;

      const bg = effectiveBg(node);
      const fg = over(parse(style.color), bg);
      const fontSizePx = parseFloat(style.fontSize);
      const weight = parseInt(style.fontWeight, 10) || 400;
      const bold = weight >= 700;
      const large = fontSizePx >= 24 || (fontSizePx >= 18.66 && bold);
      const threshold = large ? 3 : 4.5;
      const r = ratio(fg, bg);

      out.push({
        selector: cssPath(node),
        text: text.slice(0, 40),
        fg: `rgb(${fg.map((x) => Math.round(x)).join(",")})`,
        bg: `rgb(${bg.map((x) => Math.round(x)).join(",")})`,
        ratio: Math.round(r * 100) / 100,
        fontSizePx,
        bold,
        threshold,
        passes: r >= threshold,
      });
    }
    return out;
  }) as Promise<ContrastSample[]>;
}
