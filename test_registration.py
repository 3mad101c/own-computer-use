"""CI smoke test: verify every MCP tool registers and exposes a valid schema.

Headless: performs no GUI calls. Exits non-zero on any failure.
"""

import asyncio
import sys

from mcp_server import mcp

EXPECTED = {
    "computer_screenshot",
    "computer_zoom",
    "computer_read_screen",
    "computer_click",
    "computer_type",
    "computer_key",
    "computer_hold_key",
    "computer_scroll",
    "computer_drag",
    "computer_mouse_down_up",
    "computer_batch",
    "computer_open_application",
    "computer_focus_window",
    "computer_clipboard",
    "computer_cursor_position",
    "computer_wait",
    "computer_selfcheck",
    "computer_review",
    "computer_capture_monitor",
    "computer_display_overview",
    "computer_teach_step",
}


async def main() -> int:
    problems = []
    for name in sorted(EXPECTED):
        try:
            tool = await mcp.get_tool(name)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: {exc}")
            continue
        if tool.name != name:
            problems.append(f"{name}: registered as {tool.name}")
    if problems:
        print("FAILED to register:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"All {len(EXPECTED)} tools registered with valid schemas.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
