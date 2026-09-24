# Taiwan Clinical Trial Radar

**English** | [繁體中文](README.zh-TW.md)

A search tool for drug clinical trials in Taiwan. It turns the clinical trial review data published by the Taiwan Food and Drug Administration (TFDA) into a static website that is searchable, filterable and traceable to its data date. The site is in Traditional Chinese.

**Status: live** → <https://taiwan-clinical-trial-radar.pages.dev>

| | |
|---|---|
| Current data | Latest `資料更新時間` (data update time) is **2026-08-17** (5,888 trials / 18,736 review records) |
| Update frequency | Fetched automatically on the 1st of each month; nothing is published if content is unchanged |
| Specification | [`.ai-review/plan.md`](./.ai-review/plan.md) **v0.9** (the only normative version) |
| To-do / progress | [`TODO.md`](./TODO.md) / [`PROGRESS.md`](./PROGRESS.md) |

> `Taiwan-Clinical-Trial-Radar-spec.md` is the initial draft of 2026-09-12. Many parts of it were overturned by measurement and review; it is **kept as a historical document and has no normative force**.

---

## What this tool answers

1. Which drug clinical trials in Taiwan have been reviewed by the Ministry of Health and Welfare?
2. Which trials involve a given disease, trial title, protocol number or applicant?
3. What are a trial's phase, size, period, planned enrollment, primary endpoints and inclusion/exclusion criteria?
4. How current is the public data, and where should you confirm the latest status?

It is positioned as **an information-retrieval tool for clinicians**, not a patient trial-matching service.

## What this tool explicitly does not do

- It does not judge participant eligibility, and collects no medical records or free-text conditions.
- It shows no "recruiting" badge — **the source data has no execution-status field** (see below).
- It does not infer efficacy or safety, and does not imply that investigational drugs have TFDA marketing approval.
- It does not prioritize or quality-score trials.
- It collects no search strings, IPs or analytics.

## Data Source

| Dataset | ID | License |
|---|---:|---|
| Current status of drug clinical trials in Taiwan (台灣藥品臨床試驗現況) | 205 | Open Government Data License, version 1.0 |

- Export endpoint: `https://data.fda.gov.tw/data/opendata/export/205/csv` (returns a ZIP)
- Dataset page: `https://data.gov.tw/dataset/177198`

The MVP **uses dataset 205 only**. The four related exports — 206 (claimed indications), 207 (sites), 208 (investigational products) and 209 (active ingredients) — **have no verifiable trial identifier**, and their row counts don't agree with each other (512,140 / 27,774 / 28,800, etc.), so they cannot be safely mapped back to individual trials. The project has decided not to include them, and does not guess relationships by row order, name similarity or grouped counts.

## What the Data Actually Looks Like (downloaded 2026-09-18)

| Item | Measured |
|---|---|
| CSV file name | `205_2.csv` (UTF-8 with BOM) |
| ZIP / unzipped size | 42 MB / 166 MB |
| Data rows | 18,736 |
| Columns | 16 |
| Distinct protocol numbers | 5,882 (plus 6 rows with an empty protocol) |
| `資料更新時間` range | 2024/12/20 – 2026/08/17 |

### One row is not one trial

**This is the most important data fact in the project.** The 18,736 rows map to only 5,882 protocol numbers:

- 2,821 protocols have multiple rows; one protocol appears up to **23 times**.
- These repeated rows are **not pure duplicates**: of the 2,821 groups, only 61 have all 16 columns identical.
- The columns that differ most are `資料更新時間` (update time, 2,737 groups), `納入條件` (inclusion criteria, 1,927 groups), `排除條件` (exclusion criteria, 1,908 groups), `台灣預計受試者人數` (planned Taiwan enrollment, 395 groups), and even `臨床試驗期別` (trial phase, 102 groups) changes.

Conclusion: **one row = one review record, not one trial.** The site therefore consolidates by protocol number into about 5,888 trial units and keeps all review records for comparison.

("One row = one protocol version" is a reasonable inference but not proven by the data, so the site always uses the neutral term "review record" and never says "version N".)

`TFDA收文號` (TFDA receipt number) can't be a primary key: it has 2,788 duplicate keys, 266 blanks, and 30 non-numeric values such as `移案BPA`.

### When one day has several inconsistent records, the site doesn't pick one for you

`資料更新時間` has only date precision, with no time or version number. Of the 2,821 multi-row protocols, 846 groups tie on the latest date:

- **689 groups (81%)** have tied records identical in all 16 columns → the shared value is shown directly
- **157 groups** differ in the raw text; **143** of them still conflict by semantic comparison key → `納入條件` in 74 groups, `台灣預計受試者人數` in 21 (e.g. two same-day records saying `19` and `31`), `臨床試驗期別` in 3 (e.g. `Phase Ⅱ` vs `Phase Ⅰ,Phase Ⅱ`)
- The other 14 differ only in whitespace or full-/half-width characters → treated as **non-conflicting**; otherwise false alarms would teach people to ignore warnings

No column in the data can tell which record is current. So those 143 groups are **not** shown by arbitrarily picking one: result cards show only the non-conflicting shared fields, conflicting fields are marked "multiple inconsistent records on the same day — expand to check", and the detail page lists all records side by side, stating explicitly that **the order is unknown**.

Likewise, the site **shows no directional change arrows** (such as "20 → 30") — on a same-day tie the direction could be reversed. It only marks which fields have differing values.

### The same trial may appear twice (18 known groups)

The protocol-number primary key is only normalized with `strip + NFKC + uppercase`, **deliberately without stripping punctuation or collapsing whitespace** — automatically merging different numbers would cause mismatches, which is more dangerous than duplication. The cost is that different spellings of the same trial become two entries:

- `MK-3475-158` / `MK3475-158` (one hyphen missing)
- `9785-CL- 0123` / `9785-CL-0123` (an extra space)
- `ROR-PH-301(APD811-301` / `ROR-PH-301(APD811-301)` (unclosed parenthesis)
- `LOXO-RET-17001 (J2G-OX-JZJA)` / `LOXO-RET-17001（J2G-OX-JZJA）` (full-width parentheses)
- `BGB-16673-303` / `刪_BGB-16673-303` (an upstream deletion-marker prefix)

The site **does not merge automatically, but discloses proactively**: the detail page shows "protocol numbers with similar spellings" with links, and you decide whether they are the same trial.

### Some records' protocol-number field isn't a number

In 9 rows the field contains something other than a protocol number, including upstream test data (`系統測試`, `計畫書編號系統測試`, `臨床試驗計畫初版編號`), real trials without a number (`未列編號`, `科技部研究計畫(申請中)`, `IRB編號：...`), and wrong-field entries (applicant name typed into the number field).

The site **does not delete these rows** (deleting data would be rewriting the upstream), but labels them "source did not provide a protocol number", counts them under "no number provided" in statistics, and does not accept them as `?protocol=` query values.

### When enrollment is written as a range (1,340 rows)

`台灣預計受試者人數` is written as a range in 1,340 rows (7.2%), e.g. `20-40`, `8-12`. The site reads strict ranges as intervals and filters by **interval overlap** — a `20-40` row appears in both the "11–30" and "31–100" results, and the card shows the raw `20-40` so you can see it is an interval, not a single number.

But values like `約400` (about 400), `至少480` (at least 480) and `148(最多266)` (148, max 266) are **not parsed**: reading `約400` as 400 would drop the "about", which is inference, not data. They are shown as raw text labelled "source describes enrollment in words" and filed under "not provided" when filtering.

### The default search scope is narrowed

Searching the full index (all 18,736 review records × 7 fields) requires downloading **at least 4.1 MB** more (build-time estimate; actual transfer is larger), which is unacceptable on phones. So by default the search covers only 5 fields of the **latest review record** (protocol number, trial title, applicant, indication, TFDA receipt number) — that index is already part of the `trials-index` required at cold start; only widening the scope needs extra downloads.

`試驗目的` (trial objective), `主要評估指標` (primary endpoints) and **historical review records** are included only after manually widening the scope; the control sits in the search results area and tells you up front how much will be downloaded. A zero-result search also suggests where you could widen to — **the narrowed default is never hidden**.

### Stability limits of trial IDs

The site's trial / record IDs are derived from source content and are **only guaranteed stable for the same source snapshot**. If upstream reorders, adds, removes or edits fields, IDs may change; don't treat them as permanent identifiers of the same entity over time. When sharing links, keep the protocol number as well.

### The source has no execution status

The official dataset page mentions `執行狀態` (execution status), but **that column is not among the 16 actually exported**. So the site offers no Recruiting / Active filter, shows no recruiting badge, and keeps no related feature flag.

**Passing TFDA review ≠ currently recruiting.** The oldest records go back to 2024/12/20, and many trials' enrollment status has long since changed.

## Technical Architecture

- Data pipeline: Python 3.12+, generating static JSON shards at build time
- Frontend: TypeScript, no runtime API, no backend, no database
- Tests: pytest + Vitest / Playwright
- Deployment: **Cloudflare Pages** (dedicated origin)
- Automation: GitHub Actions (CI + monthly update)

The frontend never loads the 166 MB raw CSV. The payload uses a **tiered budget**: cold start for the default search scope **≤ 1,500,000 bytes**, with the widened search scope and long detail text (longest single row 22,490 characters) loaded on demand.

The threshold measures **the bytes actually received from deployed responses**, not a build-time compression estimate — the same bytes can differ by 50% between the two methods, and measuring a number no user ever pays is meaningless. Measured on 2026-09-22 (all network responses from cold start until search is ready):

| | Received (brotli) |
|---|---:|
| `trials-index` | 1,426,537 |
| bundle (JS + CSS + HTML) | 13,803 |
| `manifest` + `stats` | 11,412 |
| **Total** | **1,451,752** (3.2% headroom) |

**The site loads no external resources**, including web fonts. Before switching to a system font stack, the Google Fonts CJK subset was 63% of the cold start (2.49 MB), larger than the entire data layer; as a side effect, user IP and UA are no longer sent to a third party.

All data files use content-hashed file names resolved via `manifest.json`, the only fixed URL — this prevents browser or CDN caches from mixing different versions of the index and shards and showing the wrong records.

## License

- Code: see `LICENSE`.
- Data: sourced from TFDA open data under the Open Government Data License, version 1.0. Please keep the source attribution when reusing.

## Disclaimer

> This site organizes and searches government open data and does not represent the TFDA or any medical institution. **It does not provide current recruitment status**; **drugs used in trials are not thereby approved for marketing by the TFDA**. Data may be delayed; confirm trial status and eligibility with the official data source, trial sites and healthcare professionals. This tool provides no medical advice or participant eligibility determination.
