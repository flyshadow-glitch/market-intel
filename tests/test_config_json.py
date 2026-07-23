"""The host AI reads config/*.json directly — a typo breaks the skill silently.
These tests are the cheap insurance: every committed config parses, and the
files the skill's contract depends on carry their required keys."""
import json
import os

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def _load(name):
    with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def test_all_committed_configs_parse():
    for name in ("feeds.json", "watchlist.json", "presets.json",
                 "settings.json", "clients.example.json"):
        _load(name)   # raises on invalid JSON


def test_feeds_topics_have_categories():
    feeds = _load("feeds.json")
    assert feeds["topics"], "lens must have at least one topic"
    for t in feeds["topics"]:
        assert t.get("category"), f"topic missing category: {t}"
        assert t.get("tier") in ("primary", "context")


def test_presets_reader_profiles_contract():
    presets = _load("presets.json")
    profiles = presets["profiles"]
    assert presets["default"] in profiles
    for required in ("practitioner-brief", "leadership-radar", "both"):
        assert required in profiles, f"missing profile {required}"
    # the so-what question is the product — both real profiles must define it
    for name in ("practitioner-brief", "leadership-radar"):
        assert profiles[name].get("so_what_question"), f"{name} missing so_what_question"


def test_settings_preset_points_at_real_profile():
    settings = _load("settings.json")
    profiles = _load("presets.json")["profiles"]
    assert settings["preset"] in profiles


def test_no_client_topics_in_committed_configs():
    # real client names must never be committed — template is the only exception
    for name in ("feeds.json", "presets.json"):
        raw = json.dumps(_load(name))
        assert '"Client:' not in raw, f"{name} contains a Client: topic — move it to clients.local.json"
