---
name: market-intel
description: Use when the user wants their weekly market-intelligence / industry-signal brief or their client/brand radar — e.g. "run market intel", "fetch this week's signals", "what's new in marketing analytics this week", "run the client radar". Gathers curated signals from the open internet via agent-reach, dedupes against a cross-week memory, then YOU synthesize a decision-ready brief for the configured reader profile. NOT for ad-hoc web search (use the host's own web tools for that).
---

# Market Intelligence

A weekly signal brief for analytics/marketing leaders. Three layers, cleanly split:

- **Reach** — [agent-reach](https://github.com/Panniantong/agent-reach) fetches from the
  open internet: RSS, GitHub (`gh`), Exa semantic search, Jina full-text, and (optional)
  Reddit / LinkedIn / X / YouTube. The skill does **not** hand-roll fetchers.
- **Memory** — `scripts/state.py` is the one deterministic piece: it remembers which
  releases/discoveries were already reported so nothing surfaces twice, and logs the
  long-term star trend. agent-reach is stateless; this is what makes it a *weekly* product.
- **Synthesis** — **YOU, the host AI**, drive the gather and write the brief. No LLM API
  key lives in this repo; the intelligence is your synthesis.

## Prerequisites

- **agent-reach** available in the environment. Its core channels are zero-config
  (Exa, Jina, `gh`, RSS — no keys, no login). Run `agent-reach doctor --json` first and
  pick commands by each platform's `active_backend`. If a channel is missing, **degrade
  gracefully** — gather what you can and say what you couldn't reach. The brief still ships.
- **You** (the host AI) for synthesis and delivery.

## When invoked

**0. First run? Offer the intake.** If `output_dir` contains no `releases.seen.json` and no
`discovery.seen.json`, this install has never produced a brief. Before gathering, offer to
tailor it — the config is just JSON and **you are the installer**:

> "You're currently set up with the default lens (marketing-analytics, pharma/healthcare tilt)
> and the Practitioner Brief profile. Want me to tailor it? Two quick questions."

If they accept, ask (one at a time):
1. **Who is this for?** (a) me / my practice — industry & methodology signal → `practitioner-brief`;
   (b) leadership — specific clients/brands, their competitors, market reaction → `leadership-radar`;
   (c) both.
2. **What field / which names?** For (a): their vertical — rewrite the `exa_queries` / `gnews`
   in `feeds.json` to that field. For (b): which clients or brands + main competitors — write
   those as topics in `config/clients.local.json` (copy `clients.example.json`; **that file is
   gitignored — real client or brand names must NEVER go into `feeds.json` or any committed
   file, this repo may be public**). Tell them where their names landed and why.

Then set `preset` in `settings.json` to their answer and continue with the run. If they skip
the intake, run with the defaults — the skill must always work out of the box.

**1. Read the lens** (all under `config/`):
- `feeds.json` → `topics`, each with `category` (the brief's topic), `tier`
  (`primary`/`context`), `exa_queries`, `gnews` (a Google News RSS URL floor), and `rss`
  (publisher feeds). Also `lookback_days`, `exa_results_per_query`.
- `watchlist.json` → `repos` (track for releases) + `discovery_queries`.
- `settings.json` → `output_dir` and `preset`; `presets.json` → the **reader profile** that
  preset names (audience, cadence, the mandatory so-what question, which sections appear).
  The profile governs synthesis — see "Reader profiles" below. Default: `practitioner-brief`.
- `clients.local.json` (optional; **gitignored — never commit, holds private client names**)
  → additional `topics` for client/brand watches, same schema as `feeds.json`. If the file
  exists, merge its `topics` into the lens. A client topic may set its own `lookback_days`
  (e.g. 30) to widen the window for slower-cadence brand/pharma news, and pharma topics may
  add `clinicaltrials_sponsor` (drives the ClinicalTrials.gov connector) and `pubmed_query`
  (drives the PubMed connector). An optional `account_scope` (free text — e.g. "AOR for HCP
  media in one division; exploring adjacent divisions") describes the actual engagement with
  this client; when present, `leadership-radar` uses it to weight
  relevance and mark each read in-scope vs. adjacent (see "Reader profiles"). A client topic
  may also set `tier` (`primary`/`context`, default `context`) — it decides who always gets a
  prose block vs. who surfaces only on a material event (see "Leadership-radar at scale"). Copy
  `clients.example.json` to start. Real client names live ONLY in this local file — never in
  `feeds.json` (the repo is public).

Run `agent-reach doctor --json` first to see which channels are live; gather only via
channels reporting `ok` and note any you skipped.

**2. Gather via agent-reach.** Compute the recency floor: `cutoff = today − lookback_days`
(a topic may override the global with its own `lookback_days` — use that wider window for it).
Then for each topic:
- **Search (prefer Exa).** If `exa_search` is live: for each `exa_queries` entry →
  `mcporter call 'exa.web_search_exa(query: "<q>", numResults: <exa_results_per_query>)'`.
  Exa is semantic — cleaner and catches off-feed signal. **Enforce recency yourself:** Exa
  ranks by *relevance, not recency*, and the wrapper has **no date parameter**. Read the
  `Published:` field on each returned result and **drop anything older than `cutoff`**
  (keep undated results — fail-open, like RSS). That is why `exa_results_per_query` is set
  high (~10): you need a big enough pool that the recent subset still has signal. If a topic
  comes back empty after the date filter, say so — a quiet fortnight is a valid result.
  **If Exa is off**, fall back to the topic's `gnews` floor: fetch that Google News RSS URL
  (noisier — lean harder on the curation lens). Use Exa *or* gnews, not both, to avoid dupes.
- **`rss`** → fetch each publisher feed; keep entries on/after `cutoff`, discard older ones
  (recirculated old news is not this week's signal).
- **Client topics only (`Client:` categories):** when a material event surfaces (data readout,
  regulatory action, launch, financing, M&A), run **one follow-up Exa query** for the market
  reaction to that specific event (e.g. `"analyst reaction <company> <event>"`). Leadership
  reads the reaction as much as the event.

For the watchlist:
- **each repo** → latest release: `gh release list --repo <repo> --limit 3`; for repos that
  ship via git tags only (e.g. Meridian) fall back to `gh api repos/<repo>/tags`. Capture
  tag, date, notes, URL. Window: last 60 days.
- **`discovery_queries`** → `gh search repos "<q>" --sort stars --limit 10` to surface
  new-to-you tools.

Then **read full text of the 2–3 items you'll actually feature** → `curl -s https://r.jina.ai/<url>`.
Write the *so what* from the real article, not a snippet. Optional, only if it sharpens a
point: Reddit / LinkedIn / X for practitioner sentiment; YouTube / podcast transcripts for
conference or earnings signal.

**3. Apply memory (dedupe).** Build keys and filter through `state.py` — it persists what
was already reported so you never repeat a release, discovery, or news story:
- release keys = `"<repo>@<tag>"`, discovery keys = `"<owner>/<name>"`, **news keys = the
  article URL**.
- `python scripts/state.py new releases <key> <key> ...` → prints only the **new** ones; keep those.
- `python scripts/state.py new discovery <key> <key> ...` → same.
- `python scripts/state.py new news <url> <url> ...` → same, for news/leadership-radar items.
  News is deduped by *normalized URL*, so the same story is reported once — but a genuine
  **development at a new URL surfaces on its own** (report-once-per-chapter, not per-story).
  This is what makes a weekly / twice-weekly cadence safe: Monday's story won't repeat Thursday,
  but Thursday's follow-up will.
- Drop Exa/RSS items outside `lookback_days`.

Do **not** use news-dedup to silence a still-relevant *future catalyst* — that's the catalyst
calendar's job (step 5), and it is the honest "reminder", not a re-report.

**4. Write the brief** — the format below. This is the deliverable.

**5. Record what you reported** (so next run doesn't repeat it):
- `python scripts/state.py seen releases <reported keys...>`
- `python scripts/state.py seen discovery <reported keys...>`
- `python scripts/state.py seen news <reported urls...>` (leadership-radar / news items)
- `python scripts/state.py history <repo>=<stars> ...` (optional long-term trend log)
- **Catalyst calendar** — whenever an event names a dated future milestone (PDUFA date, a
  shareholder/merger vote, a coverage decision, a readout window), record it:
  `python scripts/state.py catalyst add <YYYY-MM-DD> "<label>"`. It recurs each run until the
  date passes, then auto-prunes. This is the *reminder* mechanism: a forward countdown, never a
  re-report of old news. Only add genuinely-announced dates — hold soft/estimated windows out of
  the calendar and mention them in prose instead. **In the brief, surface only the next ~45 days**
  (the reactable horizon) as the "Catalysts ahead" section; the full forward list persists in
  state and each item resurfaces as its date nears, so a Feb-2027 PDUFA doesn't ride in every
  weekly brief. `python scripts/state.py catalyst list --today <YYYY-MM-DD>` prints them all;
  filter to the horizon when rendering.
- Optional audit: dump the raw gathered signals to `<output_dir>/signals-<date>.md`.

**6. Deliver** (only if asked) — chat / Gmail draft / Slack. See "Delivery".

## Voice (how every brief should read)

Write like a sharp colleague explaining it to you, not a wire service. Default across all profiles:
- **Full sentences, not fragments.** "Shares fell 24% after the coverage stall" reads human;
  "−24%, coverage stall" reads like a machine.
- **Gloss jargon on first use.** The first time a brief says clean room, incrementality, PDUFA,
  MRC accreditation, adequate provision, add a short plain-language aside. Assume one smart reader
  who isn't a specialist in that corner.
- **Land every item on a concrete so-what for *us*.** Not "important to watch" but "read their
  launch deck this week" / "bring this to the QBR" / "re-baseline before July numbers move budget."
  Name the action.
- **Plain over abstract.** "The measurement ground is shifting" beats "measurement paradigms are
  evolving." Say the real thing.
- **Warm, not fluffy.** Humanize the phrasing; never pad. No hype words, no throat-clearing.

Length and register are set per profile by its `tone` in `presets.json` — the practitioner brief
runs fuller and explanatory; the leadership radar stays an executive skim (humanize the words, not
the length). **Read the active profile's `tone` and follow it**; edit that one line to retune
without touching this baseline.

**Pre-send gate (do this before delivering).** Score the brief's reader-prose with the vendored
detector: `node tools/ai-writing-detector/score.js <file> --max 15` (strip links/tables/chrome
first — score what a human reads). It rates AI-writing tells 0–100 (em-dash overuse, hollow
intensifiers like "genuinely", template phrasing). A humanized brief scores in the low single
digits; if it comes back above ~15, rewrite the flagged lines and re-score before sending. Engine
is avoid-ai-writing (MIT); see `tools/ai-writing-detector/`.

## The brief format (this is the product)

A busy leader reads it in under a minute. Aim for **under 300 words** even with several
topics — brevity per item, breadth across topics.

**Bottom line** — one or two sentences. The single thing the reader should walk away with.
Not a summary of contents. A point of view.

**One block per topic** — the topics are the `category` values from `feeds.json`. For each
topic that has a real signal this week:
- A short header (the topic name).
- One line on what happened, naming specific players/events, each linked to its source.
- A ***So what:*** line — the implication for the reader's work or positioning.
  **Mandatory.** No so-what, cut the block.

**What shipped** — only real releases that survived the memory filter. One line each, linked:
what's new and why it matters. If nothing shipped, write "Nothing shipped this week." Star
counts are not a signal and never appear.

**On the radar** — at most 3 one-liners for things worth knowing but not acting on. Tag each
with relevance in parentheses, e.g. "(matters if you touch CTV planning)".

### Hard rules

- The so-what is the product. Every item — in every section, in every reader profile, on a
  first run or a recurring one — carries its one-line implication for the reader (for
  `leadership-radar` that's "the read"), or it is cut. Never list an item as a bare headline
  with no takeaway, including an already-reported item still worth a mention.
- **Every item links to its real source.** Carry the URL from the gathered signal onto every
  headline, release, and discovery. Never invent a link or an item. Render per channel (see Delivery).
- **Balance across topics.** A high-volume topic (often MMM) must not crowd out a quieter but
  important one. A single strong signal in a quiet topic still earns its block.
- No raw headline dumps. More than 3 items in a block without synthesis means you're doing it wrong.
- Lead with the conclusion, then the evidence. Specific over vague: "Circana closed its Nielsen
  MMM acquisition" beats "there was M&A activity in the measurement space".

## Reader profiles

The format above is the **canonical (practitioner-brief)** rendering. `settings.json` →
`preset` names a profile in `presets.json`; the profile changes the *altitude*, never the
quality bar. Same hard rules always apply (so-what mandatory, every item linked, balance).

- **`practitioner-brief`** — exactly the format above. The so-what answers: *what does this
  mean for how we measure, model, and run analytics?*
- **`leadership-radar`** — for brand, commercial, and account leadership. Gathers ONLY
  the `Client:` topics from `clients.local.json` (skip `feeds.json` topics and the entire
  watchlist/releases gather — leaders don't read GitHub tags). **Scales to many accounts via
  tiering + a materiality gate — see "Leadership-radar at scale" below.** For each account that
  earns a prose block:
  1. **What happened** — the event(s), one line each, linked.
  2. **Market reaction** — analyst / press / competitor response, linked. If none found, say so.
  3. **The read** — 1–2 lines max: *what would the reader want to say in their next client
     conversation, or have their team watch?* Light touch — leaders form their own view; your
     job is the right signal at the right moment, not an essay. **If the client's topic sets
     `account_scope`**, say explicitly whether this event sits inside that scope ("squarely in
     our media remit — bring it to the next client review") or outside it ("outside our current/pilot
     scope — track for brand awareness, not an action item").
  **After all blocks, one cross-client triage line** — "If you read one thing: `<item>`,
  because `<reason>`" — the single most useful item across every account this run, not just the
  biggest headline. Weight `account_scope` relevance above raw size when picking it. This goes
  first in the Bottom line callout (see Delivery).
  No "What shipped" section. Cadence can be faster (see the profile's `cadence`); the memory
  layer keeps repeats out even at higher frequency.

  #### Leadership-radar at scale (the tier + materiality rules)

  At 3 accounts everything gets a block; at 25+ that is an unreadable wall and the glance
  can't hold one bullet per account. So a block is *earned*, by two governed rules — the
  config decides, you apply it:

  **Tier** (each client topic sets `tier: primary` or `tier: context`; the MD owns tiering by
  strategic priority = spend + growth/pilot status + renewal-or-risk timing, not spend alone):
  - **primary** — a flagship; always *eligible* for a prose block and always at least a coverage
    row. A quiet primary gets a one-line "Quiet this period — nothing material" block (silence
    about a flagship is itself signal).
  - **context** — *eligible* for a prose block only when the materiality gate fires; otherwise a
    coverage row.

  **Prose budget — the real compression lever at scale.** Eligibility is not a block. Cap prose
  at **`prose_budget` accounts (default 5 — roughly 3 primary + 2 strongest context)**. Tested
  reality: at real account density most clients have material news *every run* (a 10-account test
  came back 9/10 "material", and 7 prose blocks already ran long), so "material" is the norm, not
  the signal — it cannot be the thing that earns prose. Fill the budget by priority, then stop:
  1. primary accounts with an in-scope material event;
  2. remaining primary accounts with any material event;
  3. context accounts ranked by scope relevance first, then materiality;
  4. any leftover primary accounts as one-line quiet blocks.
  Everything past the budget — **including material context accounts** — is table-only, never
  dropped. The triage line + coverage table carry them. This is what keeps a 25-account brief a
  triage report, not a roundup. (If total accounts ≤ `prose_budget`, everyone eligible gets a
  block and the cap never bites.)

  **Materiality gate** (run each candidate event through, in order — deterministic given inputs):
  1. **Event-class gate.** Keep only: regulatory action (approval / CRL / warning letter /
     label change / recall); clinical data readout / GO-NO-GO / trial halt; launch, indication
     expansion, or pricing move; M&A / financing / activist stake; C-suite or division-head
     change *with a strategy angle*; crisis (cyber, litigation, supply/manufacturing); earnings
     *only if it moved the stock or changed guidance*. Discard awards, sponsorships, routine
     partnership PR, thought-leadership, weekly-IR-page filler.
  2. **Corroboration test.** The market-reaction query you already run *is* the test: if a real
     second source reacted (analyst note, stock move, competitor response, trade press), it is
     material. **If nothing corroborates it, it drops to the coverage table, not prose** — a
     company calling its own news "transformative" is not corroboration.
  3. **Scope weighting.** An event touching the client's `account_scope` clears the gate at a
     *lower* bar — a smaller, in-scope, divisional story outranks a bigger corporate one we
     can't act on (a divisional earnings note we run media for outranks a larger company's M&A
     we don't touch). State the scope link out loud so the weighting is auditable.

  **Coverage table (mandatory, fail-visible — but not embedded in the brief).** Every account —
  both tiers, every run — appears as one row: `account · tier · last checked · status (material /
  minor / quiet)`. This is what makes an absent prose block trustworthy at scale: a missing
  account provably means "swept, nothing material," never "forgot to look." Borderline items
  become a `minor` row, never a silent drop. **Deliver it as a linked companion, not inline:**
  put the full roster in its own Canvas (or omit it) and link to it from the brief with one line
  ("→ Coverage: all N accounts swept"). Embedding an N-row table bloats the brief and buries the
  signal; the link keeps the completeness guarantee without the weight. Prose blocks appear in
  prose-budget fill order (above); every account — in prose or not — still gets its coverage row
  in the linked doc.
- **`both`** — radar blocks first, then practitioner topic blocks, one Bottom line spanning
  both. "What shipped" appears only in the practitioner half.

If `preset` names a profile that doesn't exist in `presets.json`, say so and fall back to
`practitioner-brief`.

## Curation lens

KEEP: new measurement methodologies; MMM/attribution tooling releases or acquisitions;
privacy/measurement regulation; AI applied to marketing analytics; major platform measurement
changes (Google, Meta, retail media); budget-allocation research. **Prioritize the pharma /
healthcare / life-sciences marketing vertical** — HCP & DTC measurement, omnichannel analytics,
MLR-compliant marketing data — and when two items compete for a slot, keep the one with a
pharma/health angle.

DISCARD: brand campaigns; ad creative awards; executive hires with no strategy angle; PR/funding
with no methodology angle; pure-AI news with no marketing-data connection; and general
clinical/regulatory/market-access pharma news with no marketing-or-measurement angle (that is a
client-watch concern, not this lens). **Also hard-discard, regardless of topic fit: sponsored /
advertorial content, "N things to know" listicles, and undated evergreen vendor pages** — they
are the classic filler a reader spots instantly and loses trust over.

NO PADDING — a short brief is a good brief. When a topic is genuinely quiet, write one line
("Quiet this fortnight.") and move on; never manufacture volume by promoting a marginal item to
look complete. Three all-signal items beat six half-filler ones. When narrative is thin, lean on
"What shipped" and the coverage/tooling sections as the anchor rather than reaching.

ASSUME A GEN-AI SIBLING BRIEF. Readers already get general gen-AI and AI-in-R&D coverage
elsewhere (a separate #gen-ai / frontier-models digest). So this brief's AI items qualify ONLY
with a direct pharma-**commercial** angle — martech, orchestration, HCP/DTC engagement,
measurement. A frontier-model release, an AI-in-drug-discovery story, or generic enterprise-AI
news is out of lens here; if one is too big to ignore, give it a single "context (likely already
in the gen-AI brief)" line, never a full block. Do not re-tell what the sibling brief covers.

CLIENT BRAND WATCH: for any topic whose `category` starts with "Client:", the brand-watch
intent overrides the marketing-analytics filter above — KEEP that company's own corporate
news, clinical/data readouts, regulatory actions, financing, partnerships, and pipeline
updates even with no methodology angle. For pharma/biotech clients, enrich the agent-reach
gather with the ClinicalTrials.gov connector (trials by sponsor + the lead asset's trial
status) and the PubMed connector (recent publications on the company or its assets); carry
their real source URLs onto each item like any other.

To retarget for a different reader, edit the lens here plus `feeds.json` / `watchlist.json`.
The brief *format* above stays fixed (that is the standardized quality); the lens and sources
are what each person personalizes.

**Docs & examples must use FICTIONAL placeholder names (e.g. "Acme Bio"), never a real client
— not even a shortened form.** The leak-guard hook matches the full configured client name and
scope; a short form (e.g. "Acme" for a client configured as "Acme Bio Inc.") can slip past it,
so a real name in a committed example is a real leak. Fictional-only removes the risk at source.

## Delivery (only if asked)

The brief is the artifact that reaches a human — never send the raw signals. Same content,
rendered to fit the channel. **Lead with the bottom line (BLUF)** — a director reads the first
line and the bold bits. **Length ceilings:** a glance surface is 75–150 words / ≤5 bullets
(~20–30 sec read); the full brief stays ≤300 words / ≤1 min. One sentence per item; never more
than 3 items in a block without synthesis.

- **Chat (default)**: markdown. Links as `[title](url)`. Add a table (pipeline / catalyst
  calendar) where it earns its place; charts may be rendered inline if the host supports it.
- **Slack (layered — preferred for senior audiences)**: deliver in two tiers.
  1. A short **message** = the glance: a bold one-line bottom line + 3–5 bullets, each with a
     `[title](url)` link. Standard markdown (bold/italic/links/tables render; **no images**).
     Hold to the 75–150-word ceiling — it must fit one screen without scrolling.
  2. A **Canvas** (`slack_create_canvas`, Canvas-flavored markdown) = the full brief. Use its
     real layout tools — a flat bullet dump under headers under-uses the format.
     **Separate news from record-keeping.** A `leadership-radar` Canvas carries two different
     kinds of content and the reader must be able to tell them apart at a glance:
     *(a) News (this period)* — the triage callout, the prose blocks, and the coverage table:
     what changed, deduped so it never repeats. *(b) Standing reference* — the "Catalysts ahead"
     horizon: forward reminders that recur until their date, not things that happened. Put all
     the news first, then a `---` rule, then the reference under a plain **"Standing reference"**
     heading. Never interleave a forward catalyst into a news block. The full report-once ledger,
     trend log, and out-of-horizon catalysts stay in `state` files — they are the system's memory,
     not brief content.
     - **Bottom line** goes in a `::: {.callout} ... :::` block, not a plain paragraph — it's
       the one thing the reader must not miss. In `leadership-radar`, open it with the
       cross-client "If you read one thing" triage line (see Reader profiles), then the
       broader summary.
     - A `## ![](slack_date:YYYY-MM-DD)` heading marks the brief's date as a real date chip
       (date-only — never append a day name or extra text to it).
     - **"What shipped" and "On the radar"** render as small markdown **tables**
       (item/date/link | so-what, or item | why-it-matters) — they're reference data, not
       narrative, and scan better as a table than a bullet list.
     - `leadership-radar`'s **coverage table** (account · tier · last checked · status) is *not*
       embedded — it goes in its own linked Canvas, referenced from the brief by a single
       "→ Coverage (all N accounts swept)" line. It's the fail-visible proof every account was
       swept, kept out of the main flow so the brief stays signal-only.
     - `leadership-radar`'s **"the read"** (the mandatory 1–2 line takeaway per client): with
       **≤3–4 prose blocks**, each read gets its own `::: {.callout}` right after that client's
       what-happened / market-reaction lines. With **more blocks than that, drop the per-client
       read callouts** — many callouts become visual noise — and render each read inline as a
       bold *The read:* line. The one Bottom-line callout (with the triage line) always stays.
     - Reserve callouts sparingly. A callout on every block defeats the point of highlighting —
       topic-block so-whats stay inline (bold label + italic *So what:* line).
     - Tables and callouts are standalone top-level blocks — they cannot nest inside each
       other or inside a layout column.
     Link the Canvas from the glance ("→ Full brief"). It stays inside the workspace — prefer
     it over an external link for client material.
  For a weekly cadence use `slack_schedule_message`. Slack/Canvas cannot render charts — if a
  chart genuinely helps, use Gmail or a chat render, not Slack.
- **Gmail**: the connector supports drafts only (no send). Send `htmlBody` — a clean branded
  email: a navy (`#1B3A4B`) header bar with the date, a "Bottom line" callout, one section per
  topic with a bold header and a *So what* line, every item an inline hyperlink, a "What shipped"
  strip, and an "On the radar" list. Tables/charts may be embedded as inline HTML/SVG. Subject:
  `Market Intelligence — <date>`. Create the draft addressed to the user; they send it.

The pillars/topics shown come straight from the configured categories — do not invent or hardcode them.

## Configuration (all under `config/`, user-editable)

- `feeds.json` — `topics`: per topic a `category`, `tier`, `exa_queries`, and `rss` feeds;
  plus `lookback_days` and `exa_results_per_query`.
- `clients.local.json` — **gitignored** private client/brand watches (real client names go
  ONLY here, never in the committed config). Copy from `clients.example.json` to start.
- `watchlist.json` — GitHub `repos` to track for releases + `discovery_queries`.
- `presets.json` — **reader profiles** (`practitioner-brief` / `leadership-radar` / `both`):
  audience, cadence, the mandatory so-what question, and which sections render.
- `settings.json` — `mode` (`personal`/`team`), `output_dir`, `preset` (picks the profile).

To retarget for a different team, edit `feeds.json` / `watchlist.json` — no code changes.

## Notes

- **`scripts/state.py` is the only code** and the only thing with tests. It owns the cross-week
  memory: `releases.seen.json`, `discovery.seen.json`, and `history.jsonl` in `output_dir`.
  Everything else — reaching the internet — is agent-reach; everything smart is your synthesis.
- Releases are deduped across runs and limited to the last 60 days; repos that ship via git tags
  instead of GitHub Releases (e.g. Meridian) fall back to the latest tag. Discoveries are
  "new to our scans", not high-star repeats.
- A broken channel is skipped, not fatal. A quiet week still produces a valid brief ("Nothing
  shipped this week", a short take, and whatever is genuinely on the radar).
- Never commit agent-reach credentials or cookies to this repo.
