"""Security verification: prove the consent gate and injection guard work.

Runs against a fresh mcp_server.py process over stdio. No GUI actions execute:

  python test_security.py               # 13-tool consent matrix
  python test_security.py --injection   # 6 command-injection payloads

Exit code 0 = all assertions held. Non-zero = the claim in SECURITY.md is false.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONSENT = ROOT / "CONSENT.txt"

MUTATING = [
    ("computer_click", {"x": 640, "y": 400}),
    ("computer_type", {"text": "consent-matrix-probe"}),
    ("computer_key", {"key": "Return"}),
    ("computer_scroll", {"x": 640, "y": 400}),
    ("computer_drag", {"start_x": 1, "start_y": 1, "x": 2, "y": 2}),
    ("computer_mouse_down_up", {"action": "down"}),
    ("computer_hold_key", {"key": "ctrl", "duration": 0.1}),
    ("computer_open_application", {"target": "notepad"}),
    ("computer_batch", {"actions": [{"action": "key", "input": {"key": "Return"}}]}),
]

READ_ONLY = [
    ("computer_screenshot", {}),
    ("computer_zoom", {"x": 0, "y": 0, "width": 10, "height": 10}),
    ("computer_cursor_position", {}),
    ("computer_clipboard", {"action": "read"}),
]

INJECTION_PAYLOADS = [
    "notepad & calc",
    "calc | whoami",
    "x^y",
    "a<b",
    "foo%PATH%",
    ' say "hi',
]


def call_tools(calls, timeout_s=180):
    """Start a server, invoke each (name, args), return {name: result_text}."""
    env = dict(os.environ)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env=env,
    )
    results = {}

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    send({"jsonrpc": "2.0", "id": 0, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "test_security", "version": "1"}}})
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    for i, (name, args) in enumerate(calls, start=1):
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call",
              "params": {"name": name, "arguments": args}})

    def reader():
        for raw in proc.stdout:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            idx = msg.get("id")
            if idx and 1 <= idx <= len(calls):
                text = ""
                for block in msg.get("result", {}).get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]
                    elif block.get("type") == "image":
                        text = "IMAGE"
                results[calls[idx - 1][0]] = text

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.time() + timeout_s
    while len(results) < len(calls) and time.time() < deadline:
        time.sleep(0.5)
    proc.terminate()
    return results


def consent_matrix() -> int:
    if CONSENT.exists():
        print(f"ABORT: {CONSENT} exists — remove it before running this test.")
        return 2
    print("Consent matrix (no CONSENT.txt present)")
    print("-" * 62)
    results = call_tools(MUTATING + READ_ONLY)
    failures = []
    for name, _ in MUTATING:
        text = results.get(name, "TIMEOUT")
        blocked = text.startswith("BLOCKED")
        print(f"  {'PASS' if blocked else 'FAIL'}  {name:28s} must be BLOCKED")
        if not blocked:
            failures.append(f"{name}: {text[:60]}")
    for name, _ in READ_ONLY:
        text = results.get(name, "TIMEOUT")
        ok = text and not text.startswith("BLOCKED") and text != "TIMEOUT"
        print(f"  {'PASS' if ok else 'FAIL'}  {name:28s} must be allowed")
        if not ok:
            failures.append(f"{name}: {text[:60]}")
    if CONSENT.exists():
        print("WARNING: CONSENT.txt appeared during the run — results are void.")
        failures.append("consent file present during test")
    print("-" * 62)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print("  -", f)
        return 1
    print(f"All {len(MUTATING)} mutating tools blocked, "
          f"{len(READ_ONLY)} read-only tools allowed.")
    return 0


def injection_test() -> int:
    print("Command-injection guard (consent live, so the metacharacter guard "
          "is what must reject)")
    print("-" * 62)
    CONSENT.write_text("ALLOW security-test-injection\n", encoding="utf-8")
    try:
        failures = []
        # One payload per server call: results keyed by tool name would collide
        # if all payloads shared one call.
        for payload in INJECTION_PAYLOADS:
            res = call_tools(
                [("computer_open_application", {"target": payload})], timeout_s=120
            )
            text = res.get("computer_open_application", "TIMEOUT")
            rejected = "injection guard" in text or text.startswith("BLOCKED")
            print(f"  {'PASS' if rejected else 'FAIL'}  {payload!r:24s} must be rejected")
            if not rejected:
                failures.append(f"{payload}: {text[:70]}")
        print("-" * 62)
        if failures:
            print(f"FAILED ({len(failures)}):")
            for f in failures:
                print("  -", f)
            return 1
        print(f"All {len(INJECTION_PAYLOADS)} payloads rejected before any process started.")
        return 0
    finally:
        if CONSENT.exists():
            CONSENT.unlink()
        print("cleaned up CONSENT.txt")


if __name__ == "__main__":
    if "--injection" in sys.argv:
        sys.exit(injection_test())
    sys.exit(consent_matrix())
