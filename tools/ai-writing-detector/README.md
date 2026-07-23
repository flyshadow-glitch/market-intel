# AI-writing detector (pre-send gate)

Scores a brief's prose for AI-writing tells before it goes out, so "reads human" is a
checked output rather than a hope.

`patterns.js` is vendored verbatim from
[conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
v3.16.0 (MIT — see `LICENSE`). It is dependency-free and needs Node >= 18. `score.js` is a
thin local wrapper.

## Use

```bash
node tools/ai-writing-detector/score.js digests/brief.txt --max 15
# or pipe the prose in:
printf '%s' "$BRIEF_TEXT" | node tools/ai-writing-detector/score.js --max 15
```

Prints a 0–100 score, a label, and any flagged issues, then exits non-zero if the score
exceeds `--max` (default 15). Modes: `--mode general` (default) or `--mode marketing`
(stricter on formulaic openers / future-narrative).

Score the **reader prose** — strip markdown links, tables, and callout/date chrome first;
the engine counts words and punctuation, so URLs and table pipes only add noise.

## Reading the result

A humanized brief scores in the low single digits (the tuned samples score **0**).
Investigate anything above ~15 before sending. The usual culprits:

- **em-dash overuse** — swap for colons, commas, or middle dots (`·`)
- **hollow intensifiers** — "genuinely", "truly", "vital", "significantly"
- **template phrasing** — "it's worth noting", "plays a crucial role", "in today's landscape"
