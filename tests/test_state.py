import json
import state


def test_filter_new_returns_unseen(tmp_path):
    state.write_seen("releases", {"a@1", "b@2"}, out_dir=str(tmp_path))
    fresh = state.filter_new("releases", ["a@1", "c@3", "d@4"], out_dir=str(tmp_path))
    assert fresh == ["c@3", "d@4"]   # a@1 already seen


def test_filter_new_dedupes_within_batch(tmp_path):
    fresh = state.filter_new("discovery", ["x/y", "x/y", "z/w"], out_dir=str(tmp_path))
    assert fresh == ["x/y", "z/w"]   # same key twice in one batch collapses


def test_filter_new_preserves_order(tmp_path):
    fresh = state.filter_new("releases", ["c", "a", "b"], out_dir=str(tmp_path))
    assert fresh == ["c", "a", "b"]


def test_filter_new_does_not_write(tmp_path):
    state.filter_new("releases", ["a@1"], out_dir=str(tmp_path))
    # peeking must not persist — a@1 still counts as new on the next call
    assert state.filter_new("releases", ["a@1"], out_dir=str(tmp_path)) == ["a@1"]


def test_mark_seen_persists_union(tmp_path):
    state.write_seen("releases", {"a@1"}, out_dir=str(tmp_path))
    state.mark_seen("releases", ["b@2", "c@3"], out_dir=str(tmp_path))
    assert state.load_seen("releases", out_dir=str(tmp_path)) == {"a@1", "b@2", "c@3"}


def test_new_then_seen_roundtrip(tmp_path):
    out = str(tmp_path)
    keys = ["google/meridian@v1.7.0", "dbt-labs/dbt-core@v2.0.0"]
    assert state.filter_new("releases", keys, out_dir=out) == keys
    state.mark_seen("releases", keys, out_dir=out)
    assert state.filter_new("releases", keys, out_dir=out) == []   # nothing new now


def test_load_seen_missing_file_is_empty(tmp_path):
    assert state.load_seen("discovery", out_dir=str(tmp_path)) == set()


def test_load_seen_missing_file_is_silent(tmp_path, capsys):
    state.load_seen("discovery", out_dir=str(tmp_path))
    assert capsys.readouterr().err == ""   # first run is normal, no warning


def test_load_seen_corrupt_file_warns_and_resets(tmp_path, capsys):
    (tmp_path / "releases.seen.json").write_text("{not valid json", encoding="utf-8")
    assert state.load_seen("releases", out_dir=str(tmp_path)) == set()
    err = capsys.readouterr().err
    assert "WARNING" in err            # fail loud: corruption is visible,
    assert "releases.seen.json" in err  # not a silent memory wipe


def test_unknown_kind_raises(tmp_path):
    try:
        state.filter_new("bogus", ["x"], out_dir=str(tmp_path))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_append_history_writes_jsonl(tmp_path):
    state.append_history({"google/meridian": 1431, "facebookexperimental/Robyn": 1474},
                         out_dir=str(tmp_path), today="2026-06-23")
    lines = (tmp_path / "history.jsonl").read_text().strip().splitlines()
    rows = [json.loads(l) for l in lines]
    assert {"date": "2026-06-23", "repo": "google/meridian", "stars": 1431} in rows
    assert all(r["date"] == "2026-06-23" for r in rows)


def test_append_history_appends_not_overwrites(tmp_path):
    state.append_history({"a": 1}, out_dir=str(tmp_path), today="2026-06-16")
    state.append_history({"a": 2}, out_dir=str(tmp_path), today="2026-06-23")
    lines = (tmp_path / "history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2   # second run appended, did not clobber


def test_parse_pairs_skips_malformed():
    pairs = state._parse_pairs(["google/meridian=1431", "broken", "x=notanint", "y=7"])
    assert pairs == {"google/meridian": 1431, "y": 7}


# --- news dedup (report-once by normalized URL) ---

def test_normalize_news_key_ignores_scheme_www_query_slash():
    n = state._normalize_news_key
    assert n("https://www.Example.com/A/B/?utm_source=x#frag") == n("http://example.com/a/b")


def test_news_dedup_by_normalized_url(tmp_path):
    out = str(tmp_path)
    state.mark_seen("news", ["https://www.example.com/a?utm_source=x"], out_dir=out)
    # /a already seen (same story, trivial URL variance); /b is new
    fresh = state.filter_new("news", ["http://example.com/a/", "https://example.com/b"], out_dir=out)
    assert fresh == ["https://example.com/b"]


def test_news_new_url_surfaces_as_development(tmp_path):
    out = str(tmp_path)
    state.mark_seen("news", ["https://site.com/story-part-1"], out_dir=out)
    # a development at a new URL must NOT be suppressed
    assert state.filter_new("news", ["https://site.com/story-part-2"], out_dir=out) == ["https://site.com/story-part-2"]


def test_release_keys_not_normalized(tmp_path):
    # releases/discovery stay exact — normalization is news-only
    out = str(tmp_path)
    state.mark_seen("releases", ["google/meridian@V1.7.0"], out_dir=out)
    assert state.filter_new("releases", ["google/meridian@v1.7.0"], out_dir=out) == ["google/meridian@v1.7.0"]


# --- catalyst calendar (persisted forward reminders) ---

def test_catalyst_add_and_list_prunes_past(tmp_path):
    out = str(tmp_path)
    state.add_catalyst("2026-11-30", "Acme Bio drug PDUFA", out_dir=out)
    state.add_catalyst("2026-06-01", "already passed", out_dir=out)
    up = state.upcoming_catalysts(out_dir=out, today="2026-07-20")
    assert [c["label"] for c in up] == ["Acme Bio drug PDUFA"]
    # past entry is pruned from the file, not just hidden
    assert [c["label"] for c in state.load_catalysts(out_dir=out)] == ["Acme Bio drug PDUFA"]


def test_catalyst_add_is_idempotent(tmp_path):
    out = str(tmp_path)
    state.add_catalyst("2026-11-30", "X", out_dir=out)
    state.add_catalyst("2026-11-30", "X", out_dir=out)
    assert len(state.load_catalysts(out_dir=out)) == 1


def test_upcoming_catalysts_sorted_by_date(tmp_path):
    out = str(tmp_path)
    state.add_catalyst("2026-12-01", "later", out_dir=out)
    state.add_catalyst("2026-08-01", "sooner", out_dir=out)
    up = state.upcoming_catalysts(out_dir=out, today="2026-07-20")
    assert [c["label"] for c in up] == ["sooner", "later"]


def test_main_news_roundtrip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(state, "resolve_output_dir", lambda: str(tmp_path))
    state.main(["seen", "news", "https://x.com/a?utm=1"])
    state.main(["new", "news", "https://www.x.com/a/"])
    assert capsys.readouterr().out.strip() == ""   # deduped across scheme/www/query


def test_main_catalyst_add_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(state, "resolve_output_dir", lambda: str(tmp_path))
    state.main(["catalyst", "add", "2026-11-30", "Acme Bio PDUFA"])
    state.main(["catalyst", "list", "--today", "2026-07-20"])
    out = capsys.readouterr().out
    assert "2026-11-30" in out and "Acme Bio PDUFA" in out


# --- news dedup: tracking params are noise, article identifiers are not ---

def test_normalize_news_key_keeps_meaningful_query(tmp_path):
    n = state._normalize_news_key
    # ?id= IS the article identity on many IR portals — must not collapse
    assert n("https://ir.example.com/news.php?id=101") != n("https://ir.example.com/news.php?id=202")


def test_normalize_news_key_strips_known_trackers():
    n = state._normalize_news_key
    bare = n("https://example.com/a")
    for junk in ("?utm_source=x&utm_medium=y", "?oc=5", "?gclid=abc", "?fbclid=abc",
                 "?mc_cid=1&mc_eid=2", "?ref=twitter"):
        assert n("https://example.com/a" + junk) == bare, junk


def test_normalize_news_key_query_order_insensitive():
    n = state._normalize_news_key
    assert n("https://example.com/a?b=2&id=1") == n("https://example.com/a?id=1&b=2")


def test_normalize_news_key_mixes_tracker_and_identifier():
    n = state._normalize_news_key
    assert n("https://ir.example.com/n.php?id=101&utm_source=news") == \
           n("https://ir.example.com/n.php?id=101")


def test_news_dedup_does_not_over_merge_distinct_articles(tmp_path):
    out = str(tmp_path)
    state.mark_seen("news", ["https://ir.example.com/news.php?id=101"], out_dir=out)
    fresh = state.filter_new("news", ["https://ir.example.com/news.php?id=202"], out_dir=out)
    assert fresh == ["https://ir.example.com/news.php?id=202"]


# --- catalyst calendar: a read must never destroy the ledger ---

def test_upcoming_catalysts_rejects_malformed_today(tmp_path):
    import pytest
    out = str(tmp_path)
    state.add_catalyst("2026-11-30", "Acme Bio PDUFA", out_dir=out)
    for bad in ("Aug 21, 2026", "August 21 2026", "today", "abc", "9999", "2026-8-21"):
        with pytest.raises(ValueError):
            state.upcoming_catalysts(out_dir=out, today=bad)


def test_upcoming_catalysts_preserves_file_on_malformed_today(tmp_path):
    import pytest
    out = str(tmp_path)
    state.add_catalyst("2026-11-30", "Acme Bio PDUFA", out_dir=out)
    state.add_catalyst("2027-02-23", "Acme Bio second PDUFA", out_dir=out)
    with pytest.raises(ValueError):
        state.upcoming_catalysts(out_dir=out, today="Aug 21, 2026")
    # the ledger must be exactly as it was — a failed read writes nothing
    assert len(state.load_catalysts(out_dir=out)) == 2


def test_upcoming_catalysts_keeps_unparseable_stored_dates(tmp_path):
    # fail-open: a corrupt row is surfaced, never silently pruned
    out = str(tmp_path)
    state.save_catalysts([{"date": "not-a-date", "label": "corrupt row"},
                          {"date": "2026-11-30", "label": "good"}], out_dir=out)
    up = state.upcoming_catalysts(out_dir=out, today="2026-08-21")
    assert "corrupt row" in [c["label"] for c in up]
    assert len(state.load_catalysts(out_dir=out)) == 2
