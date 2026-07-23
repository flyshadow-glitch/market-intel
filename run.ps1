# run.ps1 — scheduled market-intel brief (headless via `claude --print`)
# Usage: .\run.ps1 [-Profile <name>]
#   -Profile leadership-radar   → force that reader profile for this run
#   (omit)                      → use settings.json `preset` (default practitioner-brief)
# Requires:
#   - claude CLI in PATH, with the agent-reach skill available
#   - agent-reach core channels working (run `agent-reach doctor` once to verify)
# NOTE: a headless `claude --print` session does NOT carry claude.ai connectors (e.g. Slack).
#   It gathers via agent-reach and drafts to Gmail if that connector is present; for Slack
#   delivery, run the skill interactively. Gather + synthesis is the host AI; state.py is memory.

param([string]$Profile)

$ErrorActionPreference = "Stop"
$REPO = $PSScriptRoot

# Load .env if present (MARKET_INTEL_TO, optional GITHUB_TOKEN for higher gh limits)
$ENV_FILE = Join-Path $REPO ".env"
if (Test-Path $ENV_FILE) {
    Get-Content $ENV_FILE | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]*)\s*=\s*(.+)\s*$") {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
}

$TODAY = (Get-Date).ToString("yyyy-MM-dd")
$RECIPIENT = if ($env:MARKET_INTEL_TO) { $env:MARKET_INTEL_TO } else { "me" }
$PROFILE_CLAUSE = if ($Profile) { "Use the '$Profile' reader profile for this run." } else { "Use the reader profile named by settings.json `preset` (default practitioner-brief)." }

Write-Host "==> Running market-intel skill ($TODAY)..."
Push-Location $REPO
try {
    $PROMPT = "Run the market-intel skill end to end for today ($TODAY). Read SKILL.md and the lens in config/. $PROFILE_CLAUSE Gather this window's signals via agent-reach (Exa for topic/client queries, RSS for publisher feeds, gh for watchlist releases/discovery). Dedupe with scripts/state.py so nothing repeats — releases, discovery, AND news (seen news <url>); for any dated future milestone use scripts/state.py catalyst add, and render scripts/state.py catalyst list as the 'Catalysts ahead' section. Read full text of featured items via Jina, write the brief per SKILL.md for the active profile, score its reader-prose with tools/ai-writing-detector/score.js (--max 15) and rewrite anything flagged above that, then deliver per that profile's delivery target; if that channel's connector is unavailable in this headless session, fall back to a Gmail draft addressed to $RECIPIENT and say so. Record what you reported with scripts/state.py before finishing."
    claude --print $PROMPT
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "claude --print returned non-zero. Check output above — the brief may not have been delivered."
    }
} finally {
    Pop-Location
}
