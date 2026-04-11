#!/usr/bin/env python3
"""Bot test harness — sends predefined queries to all bot endpoints for manual review."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

# ── Bot endpoint configuration ───────────────────────────────────────────────

BOTS = {
    "bratbot": {"endpoint": "/bratchat", "extra_fields": {}},
    "cami": {"endpoint": "/camichat", "extra_fields": {"pronoun": "male"}},
    "bonniebot": {"endpoint": "/bonniebot", "extra_fields": {"pronoun": "male"}},
}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_QUERIES = SCRIPT_DIR / "test_queries.yaml"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "test_results"


# ── Query loading ────────────────────────────────────────────────────────────

def load_queries(path: str) -> dict:
    """Load and validate test queries from a YAML file.

    Returns dict with 'single_turn' and 'multi_turn' keys.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Query file not found: {path}")

    with open(p) as f:
        data = yaml.safe_load(f)

    single = data.get("single_turn", [])
    multi = data.get("multi_turn", [])

    # Validate and apply defaults for single-turn queries
    for q in single:
        for field in ("name", "message"):
            if field not in q:
                raise ValueError(f"Single-turn query missing required field: {field}")
        q.setdefault("verbosity", 2)
        q.setdefault("description", "")

    # Validate multi-turn queries
    for q in multi:
        if "name" not in q:
            raise ValueError("Multi-turn query missing required field: name")
        if "turns" not in q or not q["turns"]:
            raise ValueError(f"Multi-turn query '{q['name']}' missing 'turns'")
        for turn in q["turns"]:
            if "message" not in turn:
                raise ValueError(
                    f"Multi-turn query '{q['name']}' has a turn missing 'message'"
                )
        q.setdefault("description", "")

    return {"single_turn": single, "multi_turn": multi}


# ── Payload building ─────────────────────────────────────────────────────────

def build_payload(
    bot_name: str,
    message: str,
    verbosity: int,
    history: list[dict],
) -> dict:
    """Build the JSON request payload for a specific bot endpoint."""
    bot = BOTS[bot_name]
    payload = {"message": message, "verbosity": verbosity, "history": history}
    payload.update(bot["extra_fields"])
    return payload


# ── Terminal output ──────────────────────────────────────────────────────────

MAX_REPLY_LEN = 60


def format_result_line(bot: str, record: dict) -> str:
    """Format a single result line for terminal output. Returns the formatted string."""
    if record["error"]:
        status = "\u2717"
        preview = record["error"][:MAX_REPLY_LEN]
    else:
        status = "\u2713"
        reply = record["response"].get("reply", "") if record["response"] else ""
        preview = reply[:MAX_REPLY_LEN]
        if len(reply) > MAX_REPLY_LEN:
            preview += "..."

    latency = f"{record['latency_seconds']:.2f}s" if record["latency_seconds"] else "-.--s"
    line = f"    {bot:<10s}{status} {latency:>6s}  \"{preview}\""

    # Append soft assertion results
    for a in record.get("soft_assertions", []):
        mark = "\u2713" if a["passed"] else "\u2717"
        line += f"  [contains: {a['expected']} {mark}]"

    return line


def print_result_line(bot: str, record: dict) -> None:
    """Print a formatted result line to stdout."""
    print(format_result_line(bot, record))


def print_summary(results: list[dict], output_path: str | None) -> None:
    """Print a summary of all test results."""
    total = len(results)
    errors = sum(1 for r in results if r["error"])
    success = total - errors
    flags = sum(
        1
        for r in results
        for a in r.get("soft_assertions", [])
        if not a["passed"]
    )

    print()
    print("\u2500\u2500 Summary \u2500" * 5)
    print(f"  {success}/{total} responses received")
    if errors:
        print(f"  {errors} errors")
    if flags:
        print(f"  {flags} soft assertion(s) flagged")
    if output_path:
        print(f"  Results: {output_path}")


# ── API runner ───────────────────────────────────────────────────────────────

def check_health(client: httpx.Client) -> bool:
    """Check if the model server is healthy. Returns True if OK."""
    try:
        resp = client.get("/health")
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def send_query(
    client: httpx.Client,
    bot_name: str,
    message: str,
    verbosity: int,
    history: list[dict],
) -> dict:
    """Send a single query to a bot endpoint. Returns a result dict."""
    endpoint = BOTS[bot_name]["endpoint"]
    payload = build_payload(bot_name, message, verbosity, history)

    start = time.monotonic()
    try:
        resp = client.post(endpoint, json=payload)
        latency = time.monotonic() - start
        resp.raise_for_status()
        data = resp.json()
        return {
            "status_code": resp.status_code,
            "response": data,
            "latency_seconds": round(latency, 2),
            "error": None,
        }
    except httpx.HTTPStatusError as e:
        latency = time.monotonic() - start
        return {
            "status_code": e.response.status_code,
            "response": None,
            "latency_seconds": round(latency, 2),
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except httpx.HTTPError as e:
        latency = time.monotonic() - start
        return {
            "status_code": None,
            "response": None,
            "latency_seconds": round(latency, 2),
            "error": str(e),
        }


def run_single_turn(
    client: httpx.Client,
    queries: list[dict],
    bots: list[str],
) -> list[dict]:
    """Run all single-turn queries against all bots. Returns list of result dicts."""
    results = []
    for query in queries:
        print(f"  {query['name']}")
        for bot in bots:
            result = send_query(
                client, bot, query["message"], query["verbosity"], history=[]
            )
            record = {
                "suite": "single_turn",
                "query_name": query["name"],
                "description": query.get("description", ""),
                "bot": bot,
                "endpoint": BOTS[bot]["endpoint"],
                "request": build_payload(bot, query["message"], query["verbosity"], []),
                "soft_assertions": [],
                **result,
            }
            print_result_line(bot, record)
            results.append(record)
    return results


def run_multi_turn(
    client: httpx.Client,
    queries: list[dict],
    bots: list[str],
) -> list[dict]:
    """Run all multi-turn queries against all bots. Returns list of result dicts."""
    results = []
    for query in queries:
        num_turns = len(query["turns"])
        for bot in bots:
            history: list[dict] = []
            for i, turn in enumerate(query["turns"], 1):
                print(f"  {query['name']} (turn {i}/{num_turns})")
                msg = turn["message"]
                result = send_query(client, bot, msg, verbosity=2, history=history)

                # Check soft assertions
                assertions = []
                if "expect_contains" in turn and result["response"]:
                    expected = turn["expect_contains"]
                    reply = result["response"].get("reply", "")
                    passed = expected.lower() in reply.lower()
                    assertions.append({
                        "type": "contains",
                        "expected": expected,
                        "passed": passed,
                    })

                record = {
                    "suite": "multi_turn",
                    "query_name": query["name"],
                    "description": query.get("description", ""),
                    "turn": i,
                    "total_turns": num_turns,
                    "bot": bot,
                    "endpoint": BOTS[bot]["endpoint"],
                    "request": build_payload(bot, msg, 2, history),
                    "soft_assertions": assertions,
                    **result,
                }
                print_result_line(bot, record)
                results.append(record)

                # Build history for next turn
                if result["response"]:
                    history.append({"role": "user", "content": msg})
                    history.append({
                        "role": "assistant",
                        "content": result["response"].get("reply", ""),
                    })
    return results
