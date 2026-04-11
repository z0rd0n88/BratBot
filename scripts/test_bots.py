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
