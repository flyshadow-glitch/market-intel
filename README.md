# Market Intelligence

![tests](https://github.com/flyshadow-glitch/market-intel/actions/workflows/tests.yml/badge.svg)

A market-intelligence brief built as a **skill** for your own AI agent. It composes
three clean layers — and deliberately hand-rolls none of the plumbing.

**Two products, one engine**, selected by a reader profile in `config/presets.json`:

- **Practitioner Brief** — industry & methodology signal for analytics/measurement
  practitioners, weekly. *"What does this mean for how we measure and model?"*
- **Leadership Radar** — client/brand key updates, competitor moves, and market
  reaction for brand & commercial leadership, at a faster cadence. *"What would
  I say in my next client conversation?"* (Client names live only in a gitignored
  local config — see below.)

On first run the agent offers a 1-minute intake: it asks who the brief is for and
what to watch, then **writes your config itself** — no wizard, no code. Skip it and
the shipped default works out of the box.

> This instance's default lens is tuned to the **pharma / healthcare / life-sciences marketing
> vertical** (`config/feeds.json` queries + the curation lens). Retarget via the intake or by
> editing the config.

## Architecture

```
config/         the lens — WHAT to watch (topics, Exa queries, RSS feeds, repos)
   ↓
agent-reach     the reach — fetches from the open internet
   ├── Exa semantic search   (off-feed signal)
   ├── RSS publisher feeds   (AdExchanger, Digiday, Recast …)
   ├── gh                    (GitHub releases + repo discovery)
   └── Jina full-text        (read the article before writing the so-what)
   ↓
scripts/state.py   the memory — dedupe across weeks + long-term star trend
   ↓
SKILL.md → host AI synthesizes → brief (chat / Gmail draft / Slack message + Canvas)
   ↓
tools/ai-writing-detector   the gate — score the draft for AI-writing tells before it ships
```

**No LLM API key lives in this repo.** The agent you already pay for does the
gathering (driving agent-reach) and the synthesis. The only Python is the memory.

## Why this design

A generic chat AI can search the web, but it can't remember last week. This skill
splits the problem into the three things that actually matter:

- **Reach is a solved problem — don't reinvent it.** [agent-reach](https://github.com/Panniantong/agent-reach)
  already handles RSS, GitHub, semantic search, full-text reading, and the login-gated
  sources (Reddit, LinkedIn, X, YouTube). The skill uses it instead of shipping its own
  brittle fetchers.
- **Memory is the differentiator.** agent-reach is stateless. `scripts/state.py` is the
  one deterministic, tested piece: it remembers which releases and discoveries were
  already reported, so a release is surfaced **once** — that is what makes this a *weekly*
  product rather than a re-run.
- **Synthesis is the product.** The brief format lives in `SKILL.md`, so the quality
  standard travels with the repo. Every install produces the same decision-ready format.
- **Quality is checked, not hoped.** Before a brief ships, its prose runs through a vendored,
  deterministic AI-writing detector ([`tools/ai-writing-detector/`](tools/ai-writing-detector/),
  MIT) that scores tells like em-dash overuse, hollow intensifiers, and template phrasing.
  "Reads human" becomes a measured output, not a hope.

## Quick start

```bash
# 1. Clone into your agent's skills directory
git clone https://github.com/flyshadow-glitch/market-intel ~/.claude/skills/market-intel

# 2. Install the reach layer (zero-config core channels)
agent-reach install --env=auto && agent-reach doctor

# 3. (optional) gh auth login   # higher GitHub rate limit
# 4. In your agent: "run market intel"
```

See [install.md](install.md) for details and team setup.

## Configuration

All under `config/` — no code changes to retarget for a different field or team.

| File | What it controls |
|---|---|
| `feeds.json` | `topics`: per topic a `category` (= a brief section), `tier`, `exa_queries`, `rss` |
| `clients.example.json` | Template for **private client/brand watches** — copy to `clients.local.json` (gitignored) |
| `watchlist.json` | GitHub `repos` tracked for releases + `discovery_queries` |
| `presets.json` | **Reader profiles** (`practitioner-brief` / `leadership-radar` / `both`): audience, cadence, the so-what question, which sections render |
| `settings.json` | `mode` (`personal`/`team`), `output_dir`, `preset` (picks the profile) |

### Client / brand watches (keep private)

This repo may be public, so **real client names must never be committed.** To watch a specific
client or brand, copy `config/clients.example.json` to `config/clients.local.json` (which is
gitignored) and add your client topics there. The skill merges those topics into the lens at
run time; git can't push them. Pharma/biotech topics can add `clinicaltrials_sponsor` and
`pubmed_query` to enrich the watch with trial and publication signal. This way any teammate
who clones the repo gets the capability, while each person's client list stays on their machine.

**Enforce it (recommended).** The gitignore is the first line of defense; for a hard guarantee,
enable the bundled pre-commit hook once per clone:

```bash
git config core.hooksPath .githooks
```

It aborts any commit that would (1) stage a gitignored file (e.g. a force-added
`clients.local.json`), (2) put a `"Client:"` topic in any committed config other than the
template, (3) point `output_dir` at a tracked folder, or (4) contain a real-looking Slack ID
or any private term drawn from `clients.local.json` (catches "filled in the template in
place"). Naming also matters: any
`config/clients.*.json` is gitignored except `clients.example.json`, so `clients.local.json`,
`clients.prod.json`, etc. are all safe by default. A GitHub Actions job
(`.github/workflows/leak-guard.yml`) re-checks on every push as a server-side backstop —
the hook is opt-in per clone and skippable with `--no-verify`; CI is not.

**If a real client name is ever committed:** do not just delete-and-commit (that leaves it in
history). Scrub it with [`git filter-repo`](https://github.com/newren/git-filter-repo), force-push
the cleaned history, and notify whoever owns the client relationship.

## Automated weekly run (Windows)

`run.ps1` calls `claude --print` to run the skill headless and draft the brief to
Gmail via the Gmail MCP connector. Set `MARKET_INTEL_TO` in `.env` and point Task
Scheduler at `run.ps1`.

## Tests

```bash
# Windows
py -m pytest tests/ -v
# Linux / Mac
python -m pytest tests/ -v
```

`scripts/state.py` is the only code with logic, and it's fully covered: dedupe,
ordering, peek-vs-commit, and the history log.

## Persistence

Written to `output_dir` (default `digests/`, gitignored):

| File | Purpose |
|---|---|
| `releases.seen.json` | Dedup set — a release is reported once |
| `discovery.seen.json` | Dedup set for newly discovered repos |
| `history.jsonl` | Long-term star trend (one row per repo per run) |
| `signals-YYYY-MM-DD.md` | Optional raw-signal audit dump |

## License

MIT
