# Codex 覆審（M4 規格符合度稽核）— 第二輪

- 日期：2026-09-22
- 範圍：`.ai-review/plan.md` v0.9 **§11 驗收條件 A1–H5** 逐條比對實作與測試
- prompt：`.ai-review/codex-prompt-r2.md`
- commit：`fc12298`
- session：`rollout-2026-09-22T10-35-15-01a0c6f7`
- sandbox：read-only（未修改任何檔案）

> 第一輪（`codex-review.md` 的前身，已被本檔取代）跑到一半停住，只留下進度訊息。
> 本輪限縮為「只輸出 A1–H5 判定表」，八群全部完成。
>
> **以下為 Codex 原始輸出，原封不動。** 逐項覆核見 `verdict.md`——
> 其中已驗出至少一項 Codex 的證據有誤（E8），所以**不要直接採信本檔**。

**Codex 自行更正的一點**：A1–H5 在 v0.9 是 **§11**（line 897 起），不是我 prompt 裡寫的 §17。
我寫錯了，它查證後照實際章節稽核。

---

我會嚴格以 `.ai-review/plan.md` v0.9 §17 為唯一驗收基準，唯讀核對。先抽出 A1–H5 原文與測試索引；之後每完成一群，就先貼該群表格與判定，再繼續下一群。四種判定只用你指定的「符合／弱化／缺測／未實作」。

---

### A 群完成（A1–A10）

先指出一個規格定位衝突：目前 `.ai-review/plan.md` v0.9 的 A1–H5 位於 **§11（line 897 起）**，不是題述的 §17；我仍依 v0.9 中實際存在的 A1–H5 原文稽核。

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| A1 | 精確驗證來源列→Trial membership、三種不合併及四類空白合併邊界 | `trial_radar/identity.py:78`; `trial_radar/model.py:130` | `tests/test_a_identity.py:66`; `tests/test_a_whitespace_merge.py:250` | 弱化 | 核心 fixture 的 group 集合有精確比對；但四類新增空白案例在 `:280` 用 `expected_fps <= actual_fps`，不是規格要求的精確 membership，弱化實作可夾帶額外列而通過。 |
| A2 | 每一種必含 fixture 均須有明確 oracle，涵蓋日期、同日 cohort、sentinel、數值全型態 | `trial_radar/model.py:90`; `trial_radar/parsing.py` | `tests/test_a_identity.py:110`; `tests/fixtures/check_a_core.py:202` | 弱化 | `check_a_core.py` 對多數 fixture 分類有 oracle；但 pytest 主測試多處只驗「存在／至少一筆」，且沒有逐案例把全部 A2 類型綁到實作結果。 |
| A3 | reverse＋≥3 seeds＋交叉 property invariant，依序驗 inventory、逐檔 hash、tie semantics | `trial_radar/artifacts.py:186` | `tests/test_a_identity.py:179,201` | 弱化 | reverse/3 seeds、inventory、hash、tie semantics 有做；沒有獨立建立「重複列 × 平手 × 空 protocol」交叉 property invariant。 |
| A4 | 第一筆 tie-break mutation 必須由指定 oracle 殺死，且涵蓋 display/filter/stats；四長欄各自唯一衝突 | `trial_radar/model.py:208`; `trial_radar/artifacts.py:132` | `tests/test_a_identity.py:217,269,288` | 弱化 | 指定 tie 與四長欄衝突有驗；mutation 只檢查 `latestAmbiguous`/`displayFields`，沒有驗 filter 分組與 stats 輸出。 |
| A5 | 以獨立 row identity 精確比對 canonical fingerprint 完整 multiset（含 multiplicity） | `trial_radar/identity.py:22`; `trial_radar/model.py:90` | `tests/test_a_identity.py:319,336` | 弱化 | `:332–333` 只比較「各 multiplicity 的排序」與 unique 數量，沒有把每個獨立 row identity 對到特定 fingerprint，也未證明輸出完整保留該 multiset。 |
| A6 | 相同空 protocol 得唯一 `#0/#1`、單筆也 `#0`、multiset 保留且跨排列一致 | `trial_radar/identity.py:78`; `trial_radar/model.py:90` | `tests/test_a_identity.py:348,361,179` | 符合 | ID ordinal、單筆 `#0`、重複列保留與跨排列 artifact 一致均有實質斷言。 |
| A7 | 大小寫／NFKC collision、空白反例、U+200B 邊界及完整 collision report 精確配對 | `trial_radar/identity.py:113`; `trial_radar/qa.py:205` | `tests/test_a_identity.py:374,421,461` | 弱化 | group/member/`raw`/`strippedRaw` 配對大致精確；但 `fingerprints[]` 只驗非空、排序、長度 64，未逐一與獨立 expected fingerprint 精確相等。 |
| A8 | 注入 hash collision，驗 error、停止發布、正式 artifact 不變 | `trial_radar/identity.py:200`; `trial_radar/model.py:130` | `tests/test_a_identity.py:487` | 弱化 | 只在 `build_trials()` 驗 `ID_TRUNCATION_COLLISION`；未走發布流程，沒有斷言停止發布與既有正式 artifact 完整不變，也沒有獨立 recordId collision 情形。 |
| A9 | 驗 18 組 near-duplicate、空 key/singleton、不得影響收斂，及 whitespace×looseKey 交叉案例 | `trial_radar/identity.py:226`; `trial_radar/model.py:141` | `tests/test_a_identity.py:512,531,544` | 弱化 | 交叉案例做得具體；但測的是小 fixture 的少數群組，沒有驗規格指定的 **18 組實測案例**。 |
| A10 | 中文 `isalnum()` 反例必須標為 non-identifier | `trial_radar/normalize.py:50`; `trial_radar/model.py:161` | `tests/test_a_identity.py:604` | 符合 | 明確用「系統測試」證明 Unicode `isalnum()` 弱化實作會失敗。 |

A 群暫結：`符合` 2、`弱化` 8、`缺測` 0、`未實作` 0。接著查 B 群，會特別核對 `BASELINE_MOVED` 是否真的被 B1 的「每個 error code」矩陣納入。

---

### B 群完成（B1–B9）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| B1 | §9.5 每個 error code 均須實際測到相異 exit，且逐案證明正式發布狀態完全不變、無新增檔 | `trial_radar/errors.py:38-97`; `trial_radar/promotion.py:43` | `tests/test_b_failures.py:40,54`; `tests/test_h_workflows.py:437` | 弱化 | 17 code 的 enum/layer/exit mapping 與 oracle 清單有雙向集合比對；但不是每個 code 都實際跑完整 pipeline，也完全沒有逐 code 比對舊檔 inventory、逐檔 SHA、manifest 指向、artifactDigest、無新增正式檔。 |
| B2 | 每案以 structured code/layer 判定，並驗多異常 precedence | `trial_radar/errors.py:101,123` | `tests/test_b_failures.py:64,87,103` | 弱化 | 檔案型案例有實跑 structured oracle；其餘 injection-only code 多數只靠 oracle 宣告「covered」，不是每個 §9.5 code 都有實際 code+layer 測試。 |
| B3 | schema 通過後零列回 `ZERO_ROWS`，且已發布 digest 不變 | `trial_radar/source.py`; `trial_radar/promotion.py:43` | `tests/test_b_failures.py:189,199` | 弱化 | schema→零列與 bootstrap 均有驗；沒有建立既有發布狀態並驗 digest 不變。 |
| B4 | 完整門檻矩陣、精確比例、warning/success/fail、是否發布及 QA 結構化 warning | `trial_radar/source.py`; `trial_radar/qa.py:37` | `tests/test_b_failures.py:208,224,246`; `tests/test_b_cli.py:137` | 弱化 | 精確 `Fraction` 與真實基線反 rounding 很好；但逐案例沒有走 promotion，也未驗 `qa/quality-report.json` 的結構化 warning。 |
| B5 | 每個正式狀態變更後注入失敗，均證明不存在部分發布 commit | `trial_radar/promotion.py:73,112` | `tests/test_b_promotion.py:93,113,126` | 弱化 | 只覆蓋 git add/commit/push、deploy、KeyboardInterrupt/SystemExit；缺替換第一／部分／最後 artifact 後，以及刪 orphan 途中等注入點。 |
| B6 | I1–I8 每條各有獨立、自洽 mutation，exact violation set、反向哨兵與 unevaluable | `trial_radar/invariants.py` | `tests/test_b_invariants.py:115,223,236,246,255,291,323` | 弱化 | 多數 mutation 很完整，含三 facet、orphan record、I8 四型與 exact set；但 `I2`/`I7.*` 被 `:328` 手動加入 coverage 集合，未見各自獨立反例；現有跨版 mutation同時觸發 `I2` 與 `I7.artifactDigest`，不符合「各自獨立」。 |
| B7 | 前端遇跨版檔案須 fail-closed 顯示固定訊息；除 manifest 外檔名皆帶 hash | `src/app.ts:48,57`; `trial_radar/artifacts.py:243` | `tests/test_b_invariants.py:338,362` | 弱化 | hash 檔名有測；跨版本只測 Python invariant，沒有瀏覽器／前端測試證明 `src/app.ts` 真的停止混用並顯示「資料版本不一致，請重新載入」。 |
| B8 | datasetVersion 可重算、具敏感性、含 logical filename，且與 artifactDigest 分離 | `trial_radar/artifacts.py:65,78` | `tests/test_b_invariants.py:375,382,396,404,422` | 符合 | 同輸入、fixed-point、單字元、互換內容、兩 digest 分離與重算皆有具體 oracle。 |
| B9 | 同一來源二跑 no-change；source SHA 單獨變動仍不發布、不 commit、builtAt 不變 | `trial_radar/promotion.py:84-90` | `tests/test_b_promotion.py:185`; `tests/test_b_invariants.py:433,448` | 符合 | 實際走 promotion，斷言 `published=false`、無 commit、builtAt 保留；source SHA 變動也納入同一路徑。 |

`BASELINE_MOVED` 初步答案：**表面契約一致，完整 B1 不一致**。

- 規格表已新增 `BASELINE_MOVED`（`.ai-review/plan.md:829-831`）。
- 實作為 publish layer、exit 26（`trial_radar/errors.py:55,75,97`）。
- B1 的 enum/oracle 集合測試會把它算進 17 個 code（`tests/test_b_failures.py:40-61`），H2 也實際測 tip 已變與 fetch 失敗（`tests/test_h_workflows.py:395-440`）。
- 但 B1 還要求「每個 code 各一測試」都證明發布狀態完整不變；`BASELINE_MOVED` 與其餘 code 都沒有這套逐 code 的 artifact-state oracle。因此只能說 **code/layer/exit 的登記一致，B1 整體仍弱化**。

B 群暫結：`符合` 2、`弱化` 7、`缺測` 0、`未實作` 0。接著查 C 群。

---

### C 群完成（C1–C6）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| C1 | 兩分類欄各驗 typed/raw/facet/filter DOM/card 五處，未知值須 warning | `trial_radar/parsing.py`; `trial_radar/artifacts.py:132`; `src/ui/card.ts`; `src/ui/filters.ts` | `tests/test_c_sentinels.py:33,64` | 弱化 | 資料層 typed/raw/facet/flag 有驗，但測試註解自己承認 DOM 與卡片只用「資料層等價條件」代替（`:37-39`）；未直接斷言 filter DOM 無 `"0"`、卡片顯示「未提供」。 |
| C2 | 兩數值欄完整矩陣逐例驗 typed、exact flags、warning、UI、enroll 分類 | `trial_radar/parsing.py`; `src/lib/filter.ts`; `src/ui/card.ts` | `tests/test_c_sentinels.py:102-145`; `tests/e2e/filters.spec.ts:209` | 弱化 | parser 矩陣與 exact flags 完整；但不是逐案例驗 UI 文字與 `enroll` 歸類，e2e 只補 `20-40` 的 D8 案例。 |
| C3 | `N/A`／`NA`／空字串精確計數與對應 recordId，record 切換後可見文字精確相等 | `trial_radar/parsing.py`; `src/ui/detail.ts` | `tests/test_c_sentinels.py:150,165` | 弱化 | 只比精確計數並驗各列表內 ID 不重複，沒有把實際 recordId 集合與 oracle 精確相等；也沒有 record 切換後三型可見文字的精確測試。 |
| C4 | 三個獨立違規 mutation 必須分別使 C1/C3 指定 oracle 轉紅 | `trial_radar/parsing.py`; `trial_radar/artifacts.py:132` | `tests/fixtures/artifact_sample/check_c4.py:94-173` | 弱化 | 三個 mutation 與 exact failing-set 有做且 CI 會跑 fixture 自檢；但自檢明示只涵蓋資料層，C1 的 filter DOM/card oracle 沒被 mutation 驗證。 |
| C5 | §6.4.2 十五種狀態組合逐列有正例，表外 hard fail，指定等價／衝突案例完整 | `trial_radar/comparison.py:51` | `tests/test_c_sentinels.py:175,206,247` | 弱化 | 指定 pair 與複合狀態有驗；但所謂「15 列涵蓋」在 `:201-203` 只驗每列回傳非空 tuple，沒有寫死各列 expected key。回傳錯誤但非空的 key 仍可通過大部分列。 |
| C6 | `rawVariants` 僅在短欄 field flags；長欄任何輸出均不得出現；代表值與詳情逐筆完整 | `trial_radar/model.py:208`; `trial_radar/artifacts.py:88-113`; `src/ui/detail.ts` | `tests/test_c_sentinels.py:277-376` | 弱化 | field scope、代表值及短欄反向哨兵有做；「詳情每筆」只檢查模型 records，未檢查渲染 DOM；更重要的是 `:350-361` 宣稱全域掃描，但若 `rawVariants` 藏在新的 top-level key，迴圈不會 fail，未真正封死「任何新增鍵」。 |

C 群暫結：`符合` 0、`弱化` 6、`缺測` 0、`未實作` 0。接著查 D 群，會連同你指定的兩個既知問題（命中日期與 scope rollback）確認它們分別落在哪一條驗收。

---

### D 群完成（D1–D8）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| D1 | 5 短欄、2 長欄各有唯一 canary；9 不可搜尋欄負例；命中標籤集合精確相等 | `src/lib/search.ts`; `src/ui/card.ts:15-22,61` | `tests/web/dgroup.test.ts:89-176` | 符合 | 7 個正 canary、9 個負 canary、四 scope、標籤 exact set，並加上 cohort 每筆 record 都可命中的反向哨兵。 |
| D2 | 逐欄封存 normalization/operator，含正反邊界、中文、空查詢及 identity/search 分離 | `src/lib/search.ts`; `trial_radar/normalize.py:24,42` | `tests/web/dgroup.test.ts:180-235`; `tests/web/search.test.ts:23-66` | 弱化 | policy/operator 邊界幾乎都只用「標題」canary 跑，不是規格要求的**逐欄** `shouldMatch/mustNotMatch` pair；其他欄主要只有單一完整 token canary。 |
| D3 | 同一查詢的完整結果集合須涵蓋同欄、跨欄、缺詞、跨 record 排除 | `src/lib/search.ts` | `tests/web/dgroup.test.ts:238-278` | 弱化 | 跨欄與缺詞用 exact set；但「兩詞同欄」只用 `toContain`，跨-record 案也只驗目標 trial 不在，沒有對各 query 寫死完整結果集合。 |
| D4 | 六維度、OR/AND、端點、period、重複/未知/無效 param，逐案 exact IDs/order、exact URL、reload state | `src/lib/filter.ts`; `src/lib/urlState.ts`; `src/app.ts:148` | `tests/web/filter.test.ts:80-213`; `tests/web/urlState.test.ts:24-108`; `tests/e2e/filters.spec.ts:68-206` | 弱化 | UI 測試多為「操作後結果再與 reload 後自己相比」；跨維度只驗 subset/長度，不是寫死 expected IDs 與順序。這仍可讓同一個錯誤在前後一致地全綠。 |
| D5 | schema、DOM、URL parser、輸出 state 四處都不得有 trial-status 維度 | `src/lib/filter.ts`; `src/lib/urlState.ts`; `src/ui/filters.ts` | `tests/web/filter.test.ts:29-49`; `tests/web/urlState.test.ts:80`; `tests/e2e/filters.spec.ts:225-250` | 符合 | 四個 surface 都有封閉集合 oracle；中文禁字僅作 mutation guard。 |
| D6 | 每個可衝突篩選欄各有 ambiguous oracle；四長欄雖不可篩仍須形成 conflict | `trial_radar/model.py:208`; `src/lib/filter.ts` | `tests/web/dgroup.test.ts:281-342` | 弱化 | 長欄存在性與部分可篩選欄有驗；但 `EXPECT_CONFLICT` 只明列 7 欄，具體「不一致且不進任何值」只實測 scale/applicant（period 被 `continue`），未做到每個可能衝突且可篩選欄各一組。 |
| D7 | 四 scope、URL 重現、持續指示、零結果提示、失敗 rollback，且逐 transition 精確檔案集合與 bytes | `src/app.ts:107-126,140-145`; `src/lib/scope.ts`; `src/ui/scopeBar.ts` | `tests/web/urlState.test.ts:126-198`; `tests/e2e/scope-perf.spec.ts:39-156` | 弱化 | **已確認實作違反 rollback**：`onNavigate()` 忽略 `ensureScopeFiles()` 的 boolean，state/URL 不退回，且已成功載入的部分檔案留在 cache。e2e `:111-124` 只驗寫死錯誤文句；成本測試也只驗格式 regex，沒有逐起點→目標的 expected 檔案集合、總 bytes、UI 級距 exact oracle。 |
| D8 | `20-40` 同時進兩 bucket、卡片保留 raw；異常數值只進未提供 | `src/lib/filter.ts`; `src/ui/card.ts:50-56` | `tests/web/dgroup.test.ts:345-385`; `tests/e2e/filters.spec.ts:209-219` | 符合 | 資料邏輯與實際 DOM 都有驗，並驗異常數值不進任一 numeric bucket。 |

D 群暫結：`符合` 3、`弱化` 5、`缺測` 0、`未實作` 0。

另外，第一輪的命中日期問題也再次確認：`src/ui/card.ts:73-85` 只拿 `hit.recordId` 判斷「是否較舊」，真正顯示日期卻取 `trial.latestSourceDate`；`tests/web/render.test.ts:152-157` 更直接把這個錯誤值寫成 expected。它是**測試鎖住誤導行為**，但 D1 的一句驗收文字只規定命中欄位集合，沒有明列日期 oracle；我會在最終報告另列為「A1–H5 表外、但與 normative §7.2 衝突的確認缺陷」，避免硬塞進不相干編號。

接著查 E 群。

---

### E 群完成（E1–E8）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| E1 | 允許呈現的狀態概念須為封閉清單，三項免責精確存在，禁字不套來源原文 | `src/ui/text.ts`; `src/ui/disclaimer.ts` | `tests/web/inventory.test.ts:43-254` | 弱化 | 清單與文字 table 有雙向對帳；但它只掃預先選定的 `LABEL/FIELD_NOTE/META/...`，若元件內新增 inline 狀態陳述，不會進 `claimTables()`，封閉性仍可被繞過。 |
| E2 | facet inventory 雙向、完整 value/count multiset、分母閉合；統計 surface 不得只靠 CSS selector 識別 | `src/ui/stats.ts`; `trial_radar/artifacts.py:132` | `tests/web/render.test.ts:241-325`; `tests/web/meta.test.ts:160-184` | 弱化 | bucket/未提供/衝突/分母驗得具體；但 inventory 主 oracle 正是 `STAT_SURFACE_ATTR` selector（`:244-249`），與規格明文「不得只依 CSS class 或 card selector」衝突。把未核准統計放進普通 section 可繞過。 |
| E3 | metadata label 對 exact fixture 值，涵蓋首頁、結果、詳情及 record 切換 | `src/ui/meta.ts`; `src/app.ts` | `tests/web/meta.test.ts:46-209` | 弱化 | 值與來源重算完整；但「詳情／切換」只是重複呼叫同一 `renderMeta(manifest)`，沒有實際走首頁、結果頁、詳情頁與 record 切換的組裝流程。 |
| E4 | 建立所有來源可達 surface 的封閉 inventory，逐一注入 XSS | `src/ui/dom.ts`; 各 renderer | `tests/web/inventory.test.ts:257-433` | 弱化 | 8 個列舉 surface 均有注入，並禁 `innerHTML` 類 API；但 `covered` 與 inventory 都由同一測試手寫，新增第九個 surface 而不登記不會自動失敗，未真正證明 surface 集合封閉。 |
| E5 | 三項核心免責逐頁可見，且綁定 viewport、最小字級、對比 oracle | `src/ui/disclaimer.ts`; `src/styles.css` | `tests/e2e/a11y.spec.ts:118-190,304-323` | 弱化 | 三頁可見、viewport 面積與當場對比有驗；contrast collector雖記錄 `fontSizePx`，沒有任何「最小字級」門檻斷言。 |
| E6 | 四長欄全文精確、首尾 canary、record 切換後相符，含 22,490 字壓力案例 | `src/ui/detail.ts` | `tests/web/render.test.ts:191-209` | 弱化 | 只對一個 record 的四欄做全文 equality；未驗首尾 canary、切換後另一 record，也未驗 22,490 字元壓力案例。 |
| E7 | ambiguous 卡片不得洩漏全部候選的原形／截斷／正規化形式；長欄 conflict exact set 與詳情全候選 | `trial_radar/model.py:208`; `src/ui/card.ts:37-40,104`; `src/ui/detail.ts` | `tests/web/render.test.ts:44-102`; `tests/test_a_identity.py:269-302` | 弱化 | 短欄只掃 `raw.trim()` 原形，沒掃截斷與正規化後形式；長欄 UI 用手造 `Trial`，沒有從實際長欄-only fixture 驗 exact conflict set、卡片與詳情全部候選的整條鏈。 |
| E8 | dateUnknown/no protocol/near-duplicate/range 四類提示與限制都須成立 | `src/ui/card.ts:50-56,100-108`; `src/ui/detail.ts`; `src/lib/urlState.ts` | `tests/web/render.test.ts:105-137,219-225` | 弱化 | 四種顯示大致有測；但沒有任何測試斷言 `?protocol=` 不接受 non-identifier 值（repo 也沒有 `?protocol=` 對應程式碼，屬未採用而非被驗收證明）。 |

E 群暫結：`符合` 0、`弱化` 8、`缺測` 0、`未實作` 0。接著查 F 群，會逐條拆解 `measure_payload.py` 與 `measure-f1-live.mjs` 對 F1 四個封存邊界的覆蓋。

---

### F 群完成（F1–F4）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| F1 | 真實部署冷啟動至功能 readiness 的全部 response 實收 body ≤1,500,000 bytes，四邊界全守且產 CI artifact | `scripts/measure_payload.py:1-123`; `scripts/measure-f1-live.mjs:1-115` | `tests/test_f_payload.py:135`; `tests/test_h_workflows.py:132-142` | 弱化 | 兩腳本的角色註解正確，但 live 腳本未被任何 workflow 呼叫、未產 JSON CI artifact、未驗資料子集合恰為三檔；且它把 URL 去重後另行重抓，並非冷啟動那些 response 的實收 body，重複 request 也會漏算。 |
| F2 | 每個按需檔以 artifact 位元組獨立重算 q11，超基線 20% 在 CI 告警 | 無對應 gate；`scripts/measure_payload.py` 只量 Tier 0 | 無 | 未實作 | 三個按需 search 檔沒有基線比較、20% warning 或 CI artifact；`measure_payload.py` 根本未納入它們。 |
| F3 | ≥5 筆跨 shard 長文字 canary 不得進任何 Tier 0 logical value/bundle；displayFields key exact | `trial_radar/artifacts.py:93-113`; build output | `tests/test_f_payload.py:37-101` | 弱化 | 只檢查 `trials-index` 與模型衍生 canary；未遞迴走訪 Tier 0 **全部 response** 的字串葉、未驗 JS/CSS bundle、沒有 ≥5 筆跨 shard canary。 |
| F4 | production 規模、固定 corpus、input→DOM 完成、固定 runner/CPU throttle、p95≤300ms | `src/app.ts:47,148-171`; Playwright 測試本身 | `tests/e2e/scope-perf.spec.ts:159-236` | 弱化 | 規模、corpus、20 samples、p95 門檻與 report 有；但沒有固定 CPU throttle，也沒驗每次結果 DOM 已對應該 query（只等一個 `requestAnimationFrame` 並讀不到任何完成 sentinel），可量到舊 DOM／排程延遲而非真正完成時間；非 production 時整條 skip。 |

### F1 四條量測邊界的直接答案

兩支腳本的**設計角色文字**與規格一致：

- `measure_payload.py` 是 q11 建置期低估、只可單向 fail-closed，不能宣告 F1 通過。
- `measure-f1-live.mjs` 才自稱真實部署驗收器。

但實際強制力不一致：

1. **壓縮後 body bytes、非 header／非解壓長度／非 Resource Timing**：live 腳本用 `https.get()` chunk 長度，形式上符合；但它是瀏覽器完成後的**第二次重抓**，不是原冷啟動 response 本身，encoding/cache/CDN 行為可能不同，因此只算部分符合。
2. **混合 encoding 正常且全部計入**：live 腳本不排除 identity/gzip/br，這條有程式碼實作。
3. **readiness 前已發起者全部計入，即使晚完成**：監聽 `request` 是正確方向；但 `new Set(requested)` 會去除重複 request，違反「全部 network responses」。這條**沒有被完整強制**。
4. **不得用 manifest `brotliBytes` 當 F1 oracle**：live 腳本沒有使用 manifest 大小，符合；建置腳本也自行 q11 重算，且明示不是 F1。

更根本的缺口是：`.github/workflows/ci.yml` 與 `deploy.yml` 都只跑 `measure_payload.py`，**完全沒跑 `measure-f1-live.mjs`**。所以在 CI／部署 gate 層級，F1 的四條真實部署邊界其實沒有任何一條被強制；目前綠燈只代表建置期估算通過。

F 群暫結：`符合` 0、`弱化` 3、`未實作` 1、`缺測` 0。接著查 G 群。

---

### G 群完成（G1–G4）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| G1 | 四 viewport 下，所有可見文字、表單、focusable bounding box 均在 viewport 內 | `src/styles.css` | `tests/e2e/a11y.spec.ts:118-163` | 弱化 | 四尺寸與 `scrollWidth` 有測；bounding selector 不是所有可見文字（漏 `span/label/summary` 等），且只檢查 x 軸，並排除整個 `.filter__options` 內元素。 |
| G2 | 路由×狀態矩陣須與實際元件狀態 inventory 雙向對帳，逐格即時計算並輸出對比 | `src/styles.css`; 各 renderer | `tests/e2e/a11y.spec.ts:92-116,165-195`; `tests/e2e/contrast.ts:94-127` | 弱化 | 有即時計算與 JSON artifact；但矩陣只含瀏覽、有查詢、零結果、ambiguous、可選 dateUnknown、無效值、focus。缺 hover、disabled、warning 的完整分解、protocolNonIdentifier、numericRange、載入失敗等，也沒有與實際 component-state inventory 雙向對帳。 |
| G3 | 每類互動元件均驗 Tab 順序、Enter/Space、focus、trap、name/role/state/error 關聯 | 各 UI renderer | `tests/e2e/a11y.spec.ts:198-295`; `tests/web/render.test.ts:357-373` | 弱化 | 只對 checkbox 的 Space 行為做實質互動；沒有逐類覆蓋 radio、搜尋框 Enter、連結、details/summary、載入更多按鈕等，也未逐項 exact role/state。 |
| G4 | 若有圖表，替代 table/list 必須可達且資料精確相等；首版至少有數字卡與清單 | `src/ui/stats.ts`; `src/ui/meta.ts` | `tests/web/render.test.ts:241-325`; `tests/web/meta.test.ts:46-76` | 符合 | 專案未提供圖表，條件式分支不觸發；現有統計以可讀 table/list 與 metadata 數字呈現，E2/E3 已驗其資料。 |

G 群暫結：`符合` 1、`弱化` 3、`缺測` 0、`未實作` 0。最後查 H 群與 workflows，之後我會整合成完整 A1–H5 總表、無測試編號清單及三個必答問題。

---

### H 群完成（H1–H5）

| 驗收編號 | 規格要求（一句話） | 對應實作 file:line | 對應測試 file:line | 判定 | 說明 |
|---|---|---|---|---|---|
| H1 | 七 gate 與 workflow 雙向對帳；每個 gate 各注入已知失敗；不得 continue-on-error | `.github/workflows/ci.yml:32-143` | `tests/test_h_workflows.py:81-142` | 弱化 | 七 job 集合、禁吞錯與禁 continue-on-error 有驗；已知失敗只實測 lint，payload 測試在 repo 已有 manifest 時沒有 assertion，typecheck/pytest/vitest/Playwright/a11y 均無 mutation。 |
| H2 | 二跑完全冪等，且真實重疊 run 重新 checkout/baseline，promotion 前版本變動 fail-closed | `.github/workflows/update-data.yml:26-90`; `scripts/build_data.py` | `tests/test_h_workflows.py:321-440`; `tests/test_b_promotion.py:185` | 弱化 | concurrency、重新 checkout tip、`--expect-head` 與 clone/origin tip 變動有驗；但沒有兩個 workflow run 真正同時排隊的測試，也未在同一 H2 oracle 完整比對第二次 git tree、artifactDigest、HEAD。 |
| H3 | 上線日手動 dispatch 兩次，第二次重新下載同 SHA、全 pipeline、no-change、無 commit | `.github/workflows/update-data.yml:10-90` | 無；僅 `PROGRESS.md:915-916` 敘述 | 缺測 | workflow 支援 dispatch，但 repo 內沒有 run ID、stage log、兩次 source SHA、HEAD/commit 的可驗證測試或證據；進度文字不是測試。 |
| H4 | 所有 direct/indirect uses 與 container 均 pin SHA/digest；預設 read，唯資料更新 job 有 contents write | `.github/workflows/*.yml` | `tests/test_h_workflows.py:199-230,314` | 符合 | 目前三份 workflow 無 reusable workflow/container；所有現有 `uses` 皆 40-hex SHA，權限以 allowlist 精確比對，只有 update job 有 `contents: write`。 |
| H5 | buildDate 必須按 Asia/Taipei 日曆日，UTC 16:00–23:59 應為次日 | `scripts/build_data.py` (`taipei_build_date`) | `tests/test_h_workflows.py:446-469` | 符合 | 六組邊界參數與「直接取 UTC date 必須失敗」反向哨兵均存在。 |

H 群暫結：`符合` 2、`弱化` 2、`缺測` 1、`未實作` 0。

八群已全部逐條查完。現在整理完整總表與三個必答答案；不會執行測試或改檔，因本輪目標是唯讀規格符合度稽核。
