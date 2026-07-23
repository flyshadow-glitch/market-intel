#!/usr/bin/env node
/**
 * Pre-send AI-writing gate for market-intel briefs.
 *
 * Scores a brief's reader-prose with the vendored avoid-ai-writing engine
 * (patterns.js, MIT — see LICENSE) and exits non-zero if the score exceeds
 * --max, so it can gate delivery. Score the PROSE a human reads: strip
 * markdown links, tables, and callout/date chrome first (the engine counts
 * words and punctuation, so URLs and pipes just add noise).
 *
 * Usage:
 *   node tools/ai-writing-detector/score.js <file> [--mode general|marketing] [--max 15]
 *   printf '%s' "$TEXT" | node tools/ai-writing-detector/score.js [--max 15]
 */
const fs = require('fs');
const AIDetector = require('./patterns.js');

const args = process.argv.slice(2);
let file = null, mode = 'general', max = 15;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--mode') mode = args[++i];
  else if (args[i] === '--max') max = Number(args[++i]);
  else if (!args[i].startsWith('--')) file = args[i];
}

const text = file ? fs.readFileSync(file, 'utf8') : fs.readFileSync(0, 'utf8');
const r = AIDetector.analyzeText(text, { contextMode: mode });

console.log(`score=${r.score}  label=${r.label}  mode=${mode}  words=${(r.stats && r.stats.wordCount) || '?'}  issues=${(r.issues || []).length}`);
for (const it of (r.issues || [])) {
  const ex = it.match ?? it.excerpt ?? it.snippet ?? it.text ?? it.phrase ?? it.word ?? it.message ?? it.detail ?? '';
  const shown = ex !== '' ? String(ex)
    : JSON.stringify(Object.fromEntries(Object.entries(it).filter(([k]) => !['severity', 'category', 'type', 'weight'].includes(k))));
  console.log(`  [${it.severity}] ${it.category || it.type}: ${shown.slice(0, 120)}`);
}
if (r.tooLong) { console.log('note: text too long to score in one pass; score section by section'); process.exit(0); }
if (r.score > max) {
  console.error(`\nFAIL: score ${r.score} > ${max}. Rewrite the flagged lines before sending.`);
  process.exit(1);
}
console.log(`\nOK: score ${r.score} <= ${max}.`);
