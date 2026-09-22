/**
 * 載入 `tests/fixtures/web_artifact/`——**由現行 Python ETL 產生的真實 artifact**。
 *
 * 不手寫 JSON 假資料：手寫的形狀是「我以為 ETL 會輸出什麼」，而前端最容易出的錯
 * 正是讀一個實際不存在的欄位。`tests/test_web_fixture.py` 保證這份 fixture 與
 * 現行 `build_artifacts` 逐位元相同，契約一改兩邊一起紅。
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { densifyIndex } from "../../src/lib/schema.js";
import type { Manifest, Shard, Stats, SearchFile, TrialsIndex } from "../../src/lib/types.js";

const HERE = dirname(fileURLToPath(import.meta.url));
export const FIXTURE_DIR = join(HERE, "..", "fixtures", "web_artifact");

function readJson<T>(relPath: string): T {
  return JSON.parse(readFileSync(join(FIXTURE_DIR, relPath), "utf-8")) as T;
}

export const manifest = readJson<Manifest>("manifest.json");
// **與 app.ts 走同一個還原函式**：測試若讀稀疏原文而 app 讀稠密的，
// 兩邊會對同一份 fixture 得出不同結論，而那種落差不會有任何測試看得見。
export const index = densifyIndex(
  readJson<TrialsIndex>(manifest.files.trialsIndex.path),
  manifest.schemaVersion,
);
export const stats = readJson<Stats>(manifest.files.stats.path);
export const trials = index.trials;

export function searchFile(key: "searchShortAll" | "searchLongLatest" | "searchLongAll"): SearchFile {
  return readJson<SearchFile>(manifest.files[key].path);
}

export function shard(name: string): Shard {
  const meta = manifest.files.recordShards[name];
  if (meta === undefined) throw new Error(`fixture 無此 shard：${name}`);
  return readJson<Shard>(meta.path);
}

/** 依 raw protocol 取 Trial。fixture 換人時直接爆，不靜默回 undefined。 */
export function byProtocol(protocol: string) {
  const t = trials.find((x) => x.protocolRaw.includes(protocol));
  if (t === undefined) throw new Error(`fixture 無此 protocol：${protocol}`);
  return t;
}
