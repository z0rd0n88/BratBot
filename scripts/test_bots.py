#!/usr/bin/env python3
"""Bot test harness — sends predefined queries to all bot endpoints for manual review."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
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


# ── JSON output ──────────────────────────────────────────────────────────────

def save_json_results(
    results: list[dict],
    metadata: dict,
    output_dir: Path,
) -> Path:
    """Save full results to a timestamped JSON file. Returns the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(results)
    errors = sum(1 for r in results if r.get("error"))
    flags = sum(
        1
        for r in results
        for a in r.get("soft_assertions", [])
        if not a.get("passed")
    )

    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    output = {
        "timestamp": datetime.now(UTC).isoformat(),
        **metadata,
        "results": results,
        "summary": {
            "total": total,
            "success": total - errors,
            "errors": errors,
            "soft_assertion_flags": flags,
        },
    }

    path = output_dir / f"results_{ts}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return path


# ── HTML report ──────────────────────────────────────────────────────────────

def generate_html_report(
    results: list[dict],
    metadata: dict,
    output_dir: Path,
) -> Path:
    """Generate a self-contained HTML report. Returns the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(results)
    errors = sum(1 for r in results if r.get("error"))
    flags = sum(
        1
        for r in results
        for a in r.get("soft_assertions", [])
        if not a.get("passed")
    )

    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

    # Group results by (suite, query_name)
    grouped: dict[str, list[dict]] = {}
    for r in results:
        key = f"{r.get('suite', 'unknown')}:{r.get('query_name', 'unknown')}"
        grouped.setdefault(key, []).append(r)

    # Build result cards
    cards_html = ""
    for key, group in grouped.items():
        suite, name = key.split(":", 1)
        desc = group[0].get("description", "")
        cards_html += f'<div class="card"><h3>{name} <span class="suite">[{suite}]</span></h3>\n'
        if desc:
            cards_html += f"<p class=\"desc\">{_esc(desc)}</p>\n"
        for r in group:
            bot = r.get("bot", "?")
            turn_label = ""
            if "turn" in r:
                turn_label = f" (turn {r['turn']}/{r['total_turns']})"

            if r.get("error"):
                status_class = "error"
                status_icon = "\u2717"
                body = f"<pre class=\"error-text\">{_esc(r['error'])}</pre>"
            else:
                status_class = "ok"
                status_icon = "\u2713"
                reply = r.get("response", {}).get("reply", "") if r.get("response") else ""
                body = f"<pre>{_esc(reply)}</pre>"

            latency = f"{r.get('latency_seconds', 0):.2f}s"

            assertions_html = ""
            for a in r.get("soft_assertions", []):
                a_class = "pass" if a["passed"] else "fail"
                a_icon = "\u2713" if a["passed"] else "\u2717"
                assertions_html += (
                    f'<span class="assertion {a_class}">'
                    f"[contains: {_esc(a['expected'])} {a_icon}]</span> "
                )

            cards_html += (
                f'<details class="{status_class}">'
                f"<summary>{status_icon} <b>{_esc(bot)}</b>{turn_label} "
                f"<span class=\"latency\">{latency}</span> {assertions_html}</summary>\n"
                f"<div class=\"detail\">\n"
                f"<h4>Request</h4><pre>{_esc(json.dumps(r.get('request', {}), indent=2))}</pre>\n"
                f"<h4>Response</h4>{body}\n"
                f"</div></details>\n"
            )
        cards_html += "</div>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bot Test Report — {ts}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px;
    margin: 2rem auto; padding: 0 1rem; background: #1a1a2e; color: #e0e0e0; }}
  h1 {{ color: #e94560; }}
  .stats {{ display: flex; gap: 2rem; margin-bottom: 2rem; }}
  .stat {{ background: #16213e; padding: 1rem 1.5rem; border-radius: 8px; }}
  .stat b {{ font-size: 1.5rem; display: block; }}
  .stat.errors b {{ color: #e94560; }}
  .stat.success b {{ color: #0f3460; }}
  .card {{ background: #16213e; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
  .card h3 {{ margin: 0 0 0.5rem; color: #e94560; }}
  .suite {{ font-size: 0.75rem; color: #888; font-weight: normal; }}
  .desc {{ color: #aaa; font-size: 0.9rem; margin: 0 0 0.5rem; }}
  details {{ margin: 0.25rem 0; padding: 0.5rem; border-radius: 4px; }}
  details.ok {{ border-left: 3px solid #4ecca3; }}
  details.error {{ border-left: 3px solid #e94560; }}
  summary {{ cursor: pointer; list-style: none; }}
  summary::-webkit-details-marker {{ display: none; }}
  .latency {{ color: #888; font-size: 0.85rem; }}
  .detail {{ padding: 0.5rem 0 0 1rem; }}
  pre {{ background: #0f3460; padding: 0.75rem; border-radius: 4px;
    white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; }}
  .error-text {{ color: #e94560; }}
  .assertion.pass {{ color: #4ecca3; }}
  .assertion.fail {{ color: #e94560; font-weight: bold; }}
  h4 {{ margin: 0.5rem 0 0.25rem; color: #aaa; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Bot Test Report</h1>
<p>Base URL: <code>{_esc(metadata.get('base_url', '?'))}</code> | Generated: {ts}</p>
<div class="stats">
  <div class="stat success"><b>{total - errors}/{total}</b> Responses</div>
  <div class="stat errors"><b>{errors}</b> Errors</div>
  <div class="stat"><b>{flags}</b> Assertions Flagged</div>
</div>
{cards_html}
</body>
</html>"""

    path = output_dir / f"report_{ts}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _esc(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Bot test harness — send predefined queries to bot endpoints for manual review",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Model server base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--bots",
        nargs="+",
        choices=list(BOTS.keys()),
        default=list(BOTS.keys()),
        help="Bots to test (default: all)",
    )
    parser.add_argument(
        "--suite",
        choices=["single", "multi", "all"],
        default="all",
        help="Test suite to run (default: all)",
    )
    parser.add_argument(
        "--queries",
        default=str(DEFAULT_QUERIES),
        help=f"Path to query YAML file (default: {DEFAULT_QUERIES})",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for results (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    # Load queries
    try:
        queries = load_queries(args.queries)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading queries: {e}", file=sys.stderr)
        sys.exit(1)

    # Create HTTP client
    client = httpx.Client(base_url=args.base_url, timeout=httpx.Timeout(60.0, connect=5.0))

    print(f"Testing bots at {args.base_url}...")

    # Health check
    if not check_health(client):
        print(f"Health check FAILED — is the server running at {args.base_url}?", file=sys.stderr)
        client.close()
        sys.exit(1)
    print("Health check: OK\n")

    all_results: list[dict] = []

    # Run single-turn tests
    if args.suite in ("single", "all") and queries["single_turn"]:
        print("\u2500\u2500 Single-Turn Tests \u2500" * 4)
        results = run_single_turn(client, queries["single_turn"], args.bots)
        all_results.extend(results)

    # Run multi-turn tests
    if args.suite in ("multi", "all") and queries["multi_turn"]:
        print()
        print("\u2500\u2500 Multi-Turn Tests \u2500" * 4)
        results = run_multi_turn(client, queries["multi_turn"], args.bots)
        all_results.extend(results)

    client.close()

    # Save results
    metadata = {
        "base_url": args.base_url,
        "bots_tested": args.bots,
        "suite": args.suite,
    }

    json_path = save_json_results(all_results, metadata, output_dir)
    print_summary(all_results, str(json_path))

    if args.html:
        html_path = generate_html_report(all_results, metadata, output_dir)
        print(f"  HTML report: {html_path}")


if __name__ == "__main__":
    main()
