/**
 * DOM 建構的唯一入口。
 *
 * **全站不使用 `innerHTML`。** 來源資料可到達的輸出 surface 很多（卡片、詳情、
 * filter option、命中標籤、統計 label、accessible name、URL 顯示，見 E4），
 * 逐處記得跳脫是行不通的——只要有一處忘記就是一個 XSS。
 * 這裡一律走 `textContent`／`setAttribute`，讓「忘記跳脫」在語法上不可能發生。
 *
 * 風險排序上 XSS 排在誤導與資料正確性之後（§10），但那是**取捨衝突時的優先序**，
 * 不是「可以不做」。本檔的成本接近零。
 */

type Attrs = Record<string, string | number | boolean | null | undefined>;
type Child = Node | string | null | undefined | false;

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Attrs = {},
  children: Child[] = [],
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = String(value);
    else if (key === "text") node.textContent = String(value);
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(value));
  }

  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

/** 清空並填入。`replaceChildren` 不會殘留舊節點的事件監聽。 */
export function mount(target: Element, ...children: Node[]): void {
  target.replaceChildren(...children);
}

/**
 * §7.2／E8 的標記 chip。
 *
 * **顏色不是唯一訊息載體**（skill 的無障礙規則）：每一態都帶符號前綴與
 * `aria-label`，色盲使用者與黑白列印同樣讀得出差異。
 */
export type FlagTone = "warn" | "info" | "muted";

export function chip(tone: FlagTone, text: string, aria?: string): HTMLSpanElement {
  const prefix = tone === "warn" ? "⚠" : tone === "info" ? "–" : "–";
  return el(
    "span",
    { class: `chip chip--${tone}`, "aria-label": aria ?? `${prefix} ${text}` },
    [`${prefix} ${text}`],
  );
}
