# Installing the Market Intelligence skill

A skill you install into your own AI agent. Your agent does the gathering (via
agent-reach) and the synthesis using your existing subscription — no paid API key
lives in this repo.

## Claude Code

1. Clone this repo into your skills directory:
   ```bash
   git clone https://github.com/flyshadow-glitch/market-intel ~/.claude/skills/market-intel
   ```
2. Install **agent-reach** — the internet-reach layer this skill depends on
   (RSS, GitHub, Exa search, Jina full-text). **Pin to a released tag** rather than the
   moving `main` branch — agent-reach is a third-party CLI with broad shell access, so an
   unpinned auto-upgrade would pull unreviewed changes onto your machine:
   ```bash
   pipx install "git+https://github.com/Panniantong/agent-reach@v1.5.0"   # pin the version
   agent-reach install --env=auto
   agent-reach doctor          # confirm channels are live
   ```
   Bump the pin deliberately (review the diff first); check the latest tag at
   https://github.com/Panniantong/agent-reach/tags. On a corporate machine, run this past
   your security/Trust team before adopting.
3. (Optional) `gh auth login` so GitHub release checks use your account's higher
   rate limit instead of the anonymous 60/hr.
4. In Claude Code, say: **"run market intel"**. On a fresh install the agent offers a
   1-minute intake — who is the brief for (practitioner brief / leadership client radar /
   both) and what to watch — then writes your config itself, routing any client or brand
   names into the gitignored `clients.local.json`. Skip the intake and the shipped default
   lens works immediately. Either way it then gathers signals via agent-reach, dedupes
   against the cross-week memory (`scripts/state.py`), and writes the brief.

No model install, no LLM API key, no server. The only Python is `scripts/state.py`
(the memory); everything else is your agent + agent-reach.

## Customize

Edit the files in `config/`:
- `feeds.json` — your `topics`: per topic the `category`, `tier`, `exa_queries`
  (semantic search) and `rss` feeds (clean publisher feeds)
- `clients.example.json` → copy to `clients.local.json` (gitignored) for **private client /
  brand watches**. Real client names go ONLY in the local file — never commit them, this repo
  is public. Pharma topics may add `clinicaltrials_sponsor` and `pubmed_query` for enrichment.
  For a hard guarantee, enable the leak-guard hook once: `git config core.hooksPath .githooks`
  (see the README "Client / brand watches" section).
- `watchlist.json` — the GitHub repos you track for releases + `discovery_queries`
- `presets.json` — the reader profiles (`practitioner-brief` / `leadership-radar` / `both`);
  pick one via `preset` in `settings.json`. The profile sets the altitude of the so-what,
  the cadence, and which sections render — the lens files above set what is watched.
- `settings.json` — `output_dir` (point at a shared drive for a team archive), `mode`, `preset`

## Team vs personal

Same skill, config only:
- **Personal:** keep `output_dir` local, run on demand.
- **Team:** point `output_dir` at a shared drive and run on a schedule (cron / Task
  Scheduler via `run.ps1`). The shared memory means a release is reported once for the
  whole team; each member can still ask their own AI to re-angle the brief.

## Weekly automation (Windows)

`run.ps1` calls `claude --print` to run the skill headless and draft the brief to
Gmail. Set `MARKET_INTEL_TO=you@example.com` in `.env`, then point Task Scheduler at
`run.ps1`. Requires the Gmail MCP connector and agent-reach available in your Claude session.
