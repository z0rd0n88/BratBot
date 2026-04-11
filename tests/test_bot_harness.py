"""Tests for the bot test harness utility functions."""

import json
import textwrap

import pytest


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


class TestFormatResultLine:
    def test_success_line(self):
        from scripts.test_bots import format_result_line

        record = {
            "bot": "bratbot",
            "latency_seconds": 1.23,
            "response": {"reply": "Oh wow, someone actually said hi to me today"},
            "error": None,
            "soft_assertions": [],
        }
        line = format_result_line("bratbot", record)
        assert "\u2713" in line
        assert "1.23s" in line
        assert "bratbot" in line
        assert "Oh wow" in line

    def test_error_line(self):
        from scripts.test_bots import format_result_line

        record = {
            "bot": "cami",
            "latency_seconds": 0.5,
            "response": None,
            "error": "HTTP 500: Internal Server Error",
            "soft_assertions": [],
        }
        line = format_result_line("cami", record)
        assert "\u2717" in line
        assert "cami" in line

    def test_truncates_long_reply(self):
        from scripts.test_bots import format_result_line

        record = {
            "bot": "bratbot",
            "latency_seconds": 1.0,
            "response": {"reply": "A" * 200},
            "error": None,
            "soft_assertions": [],
        }
        line = format_result_line("bratbot", record)
        assert "..." in line
        assert len(line) < 200

    def test_soft_assertion_pass(self):
        from scripts.test_bots import format_result_line

        record = {
            "bot": "bratbot",
            "latency_seconds": 1.0,
            "response": {"reply": "Your name is Alex"},
            "error": None,
            "soft_assertions": [{"type": "contains", "expected": "Alex", "passed": True}],
        }
        line = format_result_line("bratbot", record)
        assert "[contains: Alex \u2713]" in line

    def test_soft_assertion_fail(self):
        from scripts.test_bots import format_result_line

        record = {
            "bot": "bratbot",
            "latency_seconds": 1.0,
            "response": {"reply": "I forgot"},
            "error": None,
            "soft_assertions": [{"type": "contains", "expected": "Alex", "passed": False}],
        }
        line = format_result_line("bratbot", record)
        assert "[contains: Alex \u2717]" in line


class TestSaveJsonResults:
    def test_writes_valid_json(self, tmp_path):
        from scripts.test_bots import save_json_results

        results = [
            {
                "suite": "single_turn",
                "query_name": "greet",
                "bot": "bratbot",
                "endpoint": "/bratchat",
                "request": {"message": "hi", "verbosity": 2, "history": []},
                "response": {"request_id": "abc", "reply": "hey"},
                "status_code": 200,
                "latency_seconds": 1.0,
                "soft_assertions": [],
                "error": None,
            }
        ]
        metadata = {
            "base_url": "http://localhost:8000",
            "bots_tested": ["bratbot"],
            "suite": "all",
        }

        path = save_json_results(results, metadata, tmp_path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["base_url"] == "http://localhost:8000"
        assert len(data["results"]) == 1
        assert data["summary"]["total"] == 1
        assert data["summary"]["success"] == 1
        assert data["summary"]["errors"] == 0

    def test_summary_counts_errors(self, tmp_path):
        from scripts.test_bots import save_json_results

        results = [
            {"error": None, "soft_assertions": []},
            {"error": "timeout", "soft_assertions": []},
            {
                "error": None,
                "soft_assertions": [{"passed": False}],
            },
        ]
        metadata = {"base_url": "http://test", "bots_tested": [], "suite": "all"}

        path = save_json_results(results, metadata, tmp_path)
        data = json.loads(path.read_text())

        assert data["summary"]["total"] == 3
        assert data["summary"]["success"] == 2
        assert data["summary"]["errors"] == 1
        assert data["summary"]["soft_assertion_flags"] == 1
