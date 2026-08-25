#!/usr/bin/env python3
"""Cross-week memory for market-intel — the one thing agent-reach can't do.

agent-reach is stateless: every fetch is independent. This module is the
deterministic memory that makes the brief a *weekly* product rather than a
re-run: it remembers which releases and discoveries were already reported so
they are never surfaced twice, and accumulates a long-term star-trend log.

The host AI gathers signals via agent-reach, then calls this helper to filter
out anything already seen and to record what it reported. Persistence stays in
tested Python; reaching the internet stays in agent-reach.

CLI:
  state.py new releases google/meridian@v1.7.0 ...   # print keys not seen yet
  state.py seen releases google/meridian@v1.7.0 ...   # record keys as reported
  state.py new news <url> ...                          # news deduped by normalized URL
  state.py seen news <url> ...                         # record reported news URLs
  state.py history google/meridian=1431 ...           # append star counts
  state.py catalyst add 2026-11-30 "Acme Bio PDUFA"   # persist a forward catalyst
  state.py catalyst list [--today YYYY-MM-DD]          # upcoming catalysts (prunes past)

News keys are normalized (scheme/www/fragment/trailing-slash and tracking params
stripped; real query identifiers kept) so the same
story is reported once, while a genuine development at a NEW url surfaces on its own. The
catalyst calendar recurs a dated future event every run until its date passes — the honest
"reminder", distinct from re-reporting old news.
"""
import os
import re
import sys
import json
import argparse
from datetime import date

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "config")

_KINDS = {"releases": "releases.seen.json", "discovery": "discovery.seen.json",
          "news": "news.seen.json"}


# Query params that carry no article identity. Everything else is kept, because
# on plenty of publisher and IR portals the query string IS the article id
# (?id=, ?p=, ?storyId=) and dropping it merges unrelated stories into one key.
_TRACKING_PARAMS = {
    "utm", "oc", "gclid", "fbclid", "msclkid", "twclid", "yclid", "igshid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi", "ref", "referrer", "source",
    "cmpid", "cmp", "spm", "at_medium", "at_campaign", "s_kwcid",
}


def _normalize_news_key(url: str) -> str:
    """Normalize a news URL so trivial variance (scheme, www, tracking params,
    fragment, trailing slash, case, param order) doesn't defeat report-once. A
    genuinely different URL (a follow-up article, or a different ?id=) normalizes
    differently and stays new."""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#", 1)[0]
    path, _, query = u.partition("?")
    path = path.rstrip("/")
    if not query:
        return path
    kept = [
        part for part in query.split("&")
        if part and not (
            part.split("=", 1)[0].startswith("utm_")
            or part.split("=", 1)[0] in _TRACKING_PARAMS
        )
    ]
    return path + ("?" + "&".join(sorted(kept)) if kept else "")


def _key(kind: str, k: str) -> str:
    """Dedup key for a raw item — news is URL-normalized, everything else exact."""
    return _normalize_news_key(k) if kind == "news" else k


def resolve_output_dir() -> str:
    """Output dir from config/settings.json (default ./digests), made absolute."""
    out = "./digests"
    settings_path = os.path.join(CONFIG_DIR, "settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            out = json.load(f).get("output_dir", out) or out
    except FileNotFoundError:
        pass
    except Exception as e:
        print(
            f"WARNING: {settings_path} exists but could not be read ({e}); "
            f"falling back to default output dir {out!r}",
            file=sys.stderr,
        )
    if not os.path.isabs(out):
        out = os.path.normpath(os.path.join(REPO_ROOT, out))
    os.makedirs(out, exist_ok=True)
    return out


def _seen_path(kind: str, out_dir: str | None = None) -> str:
    if kind not in _KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(_KINDS)}")
    return os.path.join(out_dir or resolve_output_dir(), _KINDS[kind])


def load_seen(kind: str, out_dir: str | None = None) -> set:
    path = _seen_path(kind, out_dir)   # validates kind before the try
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()   # first run — no memory yet is normal
    except Exception as e:
        print(
            f"WARNING: {path} exists but could not be parsed ({e}); "
            f"treating {kind} memory as empty — this brief may repeat "
            f"previously reported items",
            file=sys.stderr,
        )
        return set()


def write_seen(kind: str, seen: set, out_dir: str | None = None) -> None:
    with open(_seen_path(kind, out_dir), "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def filter_new(kind: str, keys, out_dir: str | None = None) -> list:
    """Return keys not already seen, de-duplicated, preserving input order.
    Comparison uses the per-kind dedup key (news is URL-normalized); the
    original key is what's returned, so display/links are unchanged."""
    seen = load_seen(kind, out_dir)
    fresh, batch = [], set()
    for k in keys:
        if not k:
            continue
        nk = _key(kind, k)
        if nk not in seen and nk not in batch:
            fresh.append(k)
            batch.add(nk)
    return fresh


def mark_seen(kind: str, keys, out_dir: str | None = None) -> set:
    """Record keys as reported (stored as per-kind dedup keys); returns the set."""
    seen = load_seen(kind, out_dir)
    seen.update(_key(kind, k) for k in keys if k)
    write_seen(kind, seen, out_dir)
    return seen


# --- catalyst calendar: persisted forward-looking reminders (dated future events) ---

def _catalyst_path(out_dir: str | None = None) -> str:
    return os.path.join(out_dir or resolve_output_dir(), "catalysts.json")


def load_catalysts(out_dir: str | None = None) -> list:
    path = _catalyst_path(out_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"WARNING: {path} exists but could not be parsed ({e}); treating "
              f"catalysts as empty", file=sys.stderr)
        return []


def save_catalysts(items, out_dir: str | None = None) -> None:
    with open(_catalyst_path(out_dir), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def add_catalyst(date_str: str, label: str, out_dir: str | None = None) -> list:
    """Upsert a dated catalyst (idempotent on date+label)."""
    items = load_catalysts(out_dir)
    if not any(c.get("date") == date_str and c.get("label") == label for c in items):
        items.append({"date": date_str, "label": label})
    save_catalysts(items, out_dir)
    return items


def upcoming_catalysts(out_dir: str | None = None, today: str | None = None) -> list:
    """Return catalysts dated today-or-later, sorted; prune past ones from the file.

    `today` must be a zero-padded ISO date. This is a destructive read — it saves
    the pruned list — so an unparseable date is refused BEFORE the file is opened.
    Dates are compared as strings, and a non-ISO string ("Aug 21, 2026", "today",
    "2026-8-21") can sort above every real date, which would prune the entire
    ledger. Raising is the only safe response.
    """
    if today is None:
        today = date.today().isoformat()
    else:
        try:
            if date.fromisoformat(today).isoformat() != today:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(
                f"today must be a zero-padded ISO date (YYYY-MM-DD), got {today!r}; "
                f"refusing to prune the catalyst ledger on an unparseable date"
            ) from None

    def _keep(c) -> bool:
        d = c.get("date", "")
        try:
            date.fromisoformat(d)
        except (ValueError, TypeError):
            return True   # fail-open: surface a corrupt row, never silently prune it
        return d >= today

    items = load_catalysts(out_dir)
    upcoming = sorted((c for c in items if _keep(c)),
                      key=lambda c: (c.get("date", ""), c.get("label", "")))
    save_catalysts(upcoming, out_dir)   # pruning past events is the point
    return upcoming


def append_history(stars_by_repo: dict, out_dir: str | None = None,
                   today: str | None = None) -> None:
    """Append per-repo star counts to history.jsonl for long-term trend."""
    out_dir = out_dir or resolve_output_dir()
    today = today or date.today().isoformat()
    with open(os.path.join(out_dir, "history.jsonl"), "a", encoding="utf-8") as f:
        for repo, stars in stars_by_repo.items():
            f.write(json.dumps({"date": today, "repo": repo, "stars": stars}) + "\n")


def _parse_pairs(items):
    out = {}
    for item in items:
        if "=" not in item:
            continue
        repo, _, stars = item.partition("=")
        try:
            out[repo.strip()] = int(stars)
        except ValueError:
            continue
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="market-intel cross-week memory")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="print keys not seen yet (no write)")
    p_new.add_argument("kind", choices=sorted(_KINDS))
    p_new.add_argument("keys", nargs="*")

    p_seen = sub.add_parser("seen", help="record keys as reported")
    p_seen.add_argument("kind", choices=sorted(_KINDS))
    p_seen.add_argument("keys", nargs="*")

    p_hist = sub.add_parser("history", help="append repo=stars to history.jsonl")
    p_hist.add_argument("pairs", nargs="*")

    p_cat = sub.add_parser("catalyst", help="forward-looking catalyst calendar")
    cat_sub = p_cat.add_subparsers(dest="cat_cmd", required=True)
    p_cadd = cat_sub.add_parser("add", help="persist a dated catalyst (idempotent)")
    p_cadd.add_argument("date")
    p_cadd.add_argument("label")
    p_clist = cat_sub.add_parser("list", help="print upcoming catalysts; prune past")
    p_clist.add_argument("--today", default=None)

    args = p.parse_args(argv)

    if args.cmd == "new":
        for k in filter_new(args.kind, args.keys):
            print(k)
    elif args.cmd == "seen":
        mark_seen(args.kind, args.keys)
    elif args.cmd == "history":
        append_history(_parse_pairs(args.pairs))
    elif args.cmd == "catalyst":
        if args.cat_cmd == "add":
            add_catalyst(args.date, args.label)
        elif args.cat_cmd == "list":
            for c in upcoming_catalysts(today=args.today):
                print(f"{c['date']}  {c['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
