"""Tests for the bot test harness utility functions."""

import textwrap
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_queries(tmp_path):
    """Write a minimal YAML query file and return its path."""
    content = textwrap.dedent("""\
        single_turn:
          - name: "greet"
            message: "hello"
            description: "greeting test"
          - name: "verbose"
            message: "explain"
            verbosity: 1
            description: "verbosity test"

        multi_turn:
          - name: "recall"
            description: "memory test"
            turns:
              - message: "I'm Alice"
              - message: "Who am I?"
                expect_contains: "Alice"
    """)
    p = tmp_path / "queries.yaml"
    p.write_text(content)
    return p


class TestLoadQueries:
    def test_loads_single_turn_queries(self, tmp_queries):
        from scripts.test_bots import load_queries

        queries = load_queries(str(tmp_queries))
        assert len(queries["single_turn"]) == 2
        assert queries["single_turn"][0]["name"] == "greet"
        assert queries["single_turn"][0]["message"] == "hello"

    def test_single_turn_verbosity_defaults_to_2(self, tmp_queries):
        from scripts.test_bots import load_queries

        queries = load_queries(str(tmp_queries))
        assert queries["single_turn"][0]["verbosity"] == 2
        assert queries["single_turn"][1]["verbosity"] == 1

    def test_loads_multi_turn_queries(self, tmp_queries):
        from scripts.test_bots import load_queries

        queries = load_queries(str(tmp_queries))
        assert len(queries["multi_turn"]) == 1
        assert queries["multi_turn"][0]["turns"][1]["expect_contains"] == "Alice"

    def test_raises_on_missing_file(self):
        from scripts.test_bots import load_queries

        with pytest.raises(FileNotFoundError):
            load_queries("/nonexistent/path.yaml")

    def test_raises_on_missing_required_field(self, tmp_path):
        from scripts.test_bots import load_queries

        bad = tmp_path / "bad.yaml"
        bad.write_text("single_turn:\n  - name: oops\n")
        with pytest.raises(ValueError, match="message"):
            load_queries(str(bad))


class TestBuildPayload:
    def test_bratbot_payload_has_no_pronoun(self):
        from scripts.test_bots import build_payload

        payload = build_payload("bratbot", "hello", verbosity=2, history=[])
        assert payload == {"message": "hello", "verbosity": 2, "history": []}
        assert "pronoun" not in payload

    def test_cami_payload_includes_pronoun(self):
        from scripts.test_bots import build_payload

        payload = build_payload("cami", "hello", verbosity=1, history=[])
        assert payload == {
            "message": "hello",
            "verbosity": 1,
            "pronoun": "male",
            "history": [],
        }

    def test_bonniebot_payload_includes_pronoun(self):
        from scripts.test_bots import build_payload

        payload = build_payload("bonniebot", "hello", verbosity=3, history=[])
        assert payload == {
            "message": "hello",
            "verbosity": 3,
            "pronoun": "male",
            "history": [],
        }

    def test_payload_includes_history(self):
        from scripts.test_bots import build_payload

        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
        ]
        payload = build_payload("bratbot", "what?", verbosity=2, history=history)
        assert payload["history"] == history
