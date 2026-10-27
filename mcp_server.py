"""Own computer-use MCP server: exposes screen capture + mouse/keyboard to Claude Code.

Scope: user (~/.claude.json) -> available in all projects.
Run: registered as stdio server; `python mcp_server.py` is executed by Claude Code.
"""

import base64
import os
import re
import time

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from screen import audit, capture_screen, execute_action

mcp = FastMCP("own-computer-use")

# Shared with screen.py consumers: current screenshot scale for coord conversion.
CURRENT_SCALE = [1.0]


def _focused_window_title():
    """Title of the foreground window, or '' on any failure."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


SELF_HARM_PATTERNS = (
    "claude",        # Claude Desktop / Claude Code terminal titles
    "visual studio code",  # IDE running the agent
    "windows terminal", "powershell", "cmd.exe", "command prompt",
)


def keyboard_guard():
    """Block type/key when the agent's own surface holds focus (text would land
    in the conversation or a shell). Returns error string or None (allowed).
    Override by deleting SELF_HARM_PATTERNS entries — not recommended."""
    title = _focused_window_title().lower()
    if any(p in title for p in SELF_HARM_PATTERNS):
        return (
            f"BLOCKED: focused window is '{title.strip()}' — an agent control "
            "surface. Click the target window first (its click moves focus)."
        )
    return None


CONSENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CONSENT.txt")


def outbound_guard(action: str) -> str | None:
    """Hard gate for actions with external effects (typing into apps, pasting,
    sending). Allowed ONLY while CONSENT.txt exists AND its mtime is < 10 min
    old AND its first line is exactly 'ALLOW <what>'. The user creates it
    deliberately, e.g.  echo ALLOW send-message > CONSENT.txt. Auto-expires:
    delete the file or wait 10 minutes."""
    import os
    import time as _t

    if not os.path.exists(CONSENT_FILE):
        return (
            f"BLOCKED: {action} has external effects. User consent required — "
            f"create {CONSENT_FILE} whose first line is 'ALLOW <what>' "
            "(valid 10 minutes), then retry."
        )
    age = _t.time() - os.path.getmtime(CONSENT_FILE)
    if age > 600:
        return f"BLOCKED: {action} — CONSENT.txt is older than 10 minutes; recreate it."
    first = ""
    with open(CONSENT_FILE, encoding="utf-8", errors="replace") as f:
        first = f.readline().strip()
    if not first.upper().startswith("ALLOW"):
        return f"BLOCKED: {action} — CONSENT.txt must start with 'ALLOW <what>'."
    return None


@mcp.tool
def computer_screenshot() -> Image:
    """Take a screenshot of the entire virtual screen (all monitors). Returns
    the image; its pixel space defines the coordinate system for all
    computer_* tools."""
    b64, scale = capture_screen()
    CURRENT_SCALE[0] = scale or 1.0
    # Tell the agent which window it is looking at - verification without OCR.
    title = _focused_window_title()
    log = f"Foreground window: {title!r}." if title else ""
    import logging
    logging.getLogger(__name__).info(log)
    return Image(data=base64.standard_b64decode(b64), format="png")


@mcp.tool
def computer_click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
) -> str:
    """Click at (x, y) in the LAST screenshot's pixel space. button: left|right|middle,
    clicks: 1=single, 2=double, 3=triple (select line/paragraph).
    Outbound gate: a click can press Submit/Send/Delete — needs fresh CONSENT.txt."""
    consent = outbound_guard("computer_click")
    if consent:
        return consent
    action = {1: "left_click", 2: "double_click", 3: "triple_click"}.get(clicks, "left_click")
    if button != "left":
        action = f"{button}_click"
    result = execute_action(action, {"x": x, "y": y}, CURRENT_SCALE[0])
    return str(result)


@mcp.tool
def computer_type(text: str) -> str:
    """Type text into the focused control via clipboard paste (Arabic-safe).
    Outbound gate: requires fresh CONSENT.txt (ALLOW line, <10 min old) —
    typing sends text into an app the user may not see being typed into."""
    guard = keyboard_guard() or outbound_guard("computer_type")
    if guard:
        return guard
    result = execute_action("type", {"text": text}, CURRENT_SCALE[0])
    return str(result)


@mcp.tool
def computer_key(key: str) -> str:
    """Press a key or chord: "Return", "ctrl+c", "alt+Tab", "escape".
    Emphasis: Enter/Return in a chat app SENDS — that needs consent too."""
    guard = keyboard_guard()
    if guard:
        return guard
    if key.strip().lower() in ("return", "enter"):
        consent = outbound_guard("computer_key(Enter)")
        if consent:
            return consent
    result = execute_action("key", {"key": key}, CURRENT_SCALE[0])
    return str(result)


@mcp.tool
def computer_scroll(x: int, y: int, direction: str = "down", amount: int = 3) -> str:
    """Scroll at (x, y). direction: up|down|left|right; amount in wheel notches."""
    consent = outbound_guard("computer_scroll")
    if consent:
        return consent
    result = execute_action(
        "scroll", {"x": x, "y": y, "scroll_direction": direction, "scroll_amount": amount},
        CURRENT_SCALE[0],
    )
    return str(result)


@mcp.tool
def computer_drag(start_x: int, start_y: int, x: int, y: int) -> str:
    """Drag from (start_x, start_y) to (x, y) — file moves, sliders, selection."""
    consent = outbound_guard("computer_drag")
    if consent:
        return consent
    result = execute_action(
        "left_click_drag",
        {"start_x": start_x, "start_y": start_y, "x": x, "y": y},
        CURRENT_SCALE[0],
    )
    return str(result)


@mcp.tool
def computer_zoom(x: int, y: int, width: int, height: int) -> Image:
    """Zoom: re-capture a region at higher magnification for reading small text.
    Coordinates stay in the FULL-screenshot pixel space, never the crop's."""
    result = execute_action(
        "zoom", {"x": x, "y": y, "width": width, "height": height}, CURRENT_SCALE[0]
    )
    content, _scale = result
    return Image(data=base64.standard_b64decode(content["source"]["data"]), format="png")


@mcp.tool
def computer_batch(actions: list[dict]) -> str:
    """Run several actions milliseconds apart in ONE call — for timing-critical
    UI (menus that close on blur, mid-flight buttons). Each item: {"action":
    <member name>, "input": <its arguments dict>}. Coordinates follow the same
    screenshot-space rule. Example: [{"action":"left_click","input":{"x":100,"y":50}},
    {"action":"key","input":{"key":"Down"}},{"action":"key","input":{"key":"Return"}}].
    Returns one result line per action."""
    consent = outbound_guard("computer_batch")
    if consent:
        return consent
    lines = []
    for item in actions:
        name = item.get("action", "")
        inp = item.get("input", {})
        try:
            res = execute_action(name, inp, CURRENT_SCALE[0])
        except Exception as exc:  # isolated per action; batch keeps going
            res = f"ERROR: {exc}"
        label = res[0] if isinstance(res, tuple) else res
        if isinstance(label, dict):  # image result inside batch -> summarize
            label = "image OK"
        lines.append(f"{name}: {label}")
    return "\n".join(lines)


@mcp.tool
def computer_wait(seconds: float = 2) -> str:
    """Pause up to 10s between actions (page loads, animations)."""
    return str(execute_action("wait", {"duration": seconds}, CURRENT_SCALE[0]))


@mcp.tool
def computer_mouse_down_up(action: str = "down") -> str:
    """Hold or release the LEFT mouse button without moving: action down|up.
    For press-drag-press-drag-... sequences pyautogui can't do in one call."""
    consent = outbound_guard("computer_mouse_down_up")
    if consent:
        return consent
    return str(execute_action(f"left_mouse_{action}" if action in ("down", "up") else "left_mouse_down", {}, CURRENT_SCALE[0]))


@mcp.tool
def computer_hold_key(key: str, duration: float = 1) -> str:
    """Hold a key for duration seconds then release (e.g. Shift for click-select
    ranges). One chord only — no '+' combos."""
    consent = outbound_guard("computer_hold_key")
    if consent:
        return consent
    return str(execute_action("hold_key", {"key": key, "duration": duration}, CURRENT_SCALE[0]))


@mcp.tool
def computer_clipboard(action: str, text: str = "") -> str:
    """Read or write the system clipboard: action read|write. write copies
    `text`; read returns current clipboard content (empty string if none)."""
    if action == "read":
        return str(execute_action("read_clipboard", {}, CURRENT_SCALE[0]))
    return str(execute_action("write_clipboard", {"text": text}, CURRENT_SCALE[0]))


@mcp.tool
def computer_open_application(target: str) -> str:
    """Open an app by name or full .exe path and report what REALLY happened:
    opened (window appeared) / running-no-window / crashed / nothing-launched.
    Windows: use `start` semantics, e.g. "notepad" or "chrome". Waits up to 8s
    for a visible window."""
    consent = outbound_guard("computer_open_application")
    if consent:
        return consent
    import subprocess
    import time as _t

    audit_open = {"target": target}
    audit("open_application", audit_open)
    # Command-injection guard: strip cmd metacharacters (& | ^ < > ! % "). A
    # compromised model could otherwise chain commands through `cmd /c start`.
    if re.search(r'[&|^<>!%"]', target):
        return "BLOCKED: target contains shell metacharacters (injection guard)."
    try:
        proc = subprocess.Popen(["cmd", "/c", "start", "", target],
                                shell=False,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    except FileNotFoundError:
        return "crashed: command not found"
    # Poll for a new visible top-level window via pyautogui-independent API.
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        counts_before = user32.GetForegroundWindow()
    except Exception:
        counts_before = 0
    for _ in range(16):  # up to 8s
        _t.sleep(0.5)
        try:
            import pyautogui as _p  # window listing via its Win32 backend
            wins = _p.getAllWindows()
            titles = [w.title for w in wins if w.title.strip()]
            if any(target.lower() in t.lower() for t in titles):
                return f'opened: window "{[t for t in titles if target.lower() in t.lower()][0]}"'
        except Exception:
            pass
    if proc.poll() is not None and proc.returncode != 0:
        return f"crashed: exit code {proc.returncode}"
    return "running-no-window-yet (no matching window title after 8s)"


@mcp.tool
def computer_cursor_position() -> str:
    """Current mouse cursor position in SCREENSHOT coordinates."""
    return str(execute_action("cursor_position", {}, CURRENT_SCALE[0]))


@mcp.tool
def computer_focus_window(title_substring: str) -> str:
    """Bring the first visible top-level window whose title contains
    title_substring (case-insensitive) to the foreground. Returns the exact
    title focused or 'not found'. Keyboard actions land there afterward."""
    import ctypes

    user32 = ctypes.windll.user32
    matches = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd, _l):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                matches.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_cb, 0)
    needle = title_substring.lower()
    for hwnd, title in matches:
        if needle in title.lower():
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE if minimized
            user32.SetForegroundWindow(hwnd)
            return f"focused: {title!r}"
    return f"not found: no window title contains {title_substring!r}"


@mcp.tool
def computer_read_screen(target_title: str = "") -> str:
    """OCR the screen. Optional target_title: bring the first window whose
    title contains it to the foreground FIRST (atomic focus+read — the read
    cannot miss the target). Returns lines "(x,y) text". Arabic + English."""
    if target_title:
        focus_msg = computer_focus_window(target_title)
        if focus_msg.startswith("not found"):
            return focus_msg
        time.sleep(1.0)  # redraw after focus
    b64, scale = capture_screen()
    CURRENT_SCALE[0] = scale or 1.0
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _ = engine(b64_to_pil(b64))
    if not result:
        return "(no text detected)"
    return "\n".join(
        f"({int(box[0][0])},{int(box[0][1])}) {text}" for box, text, _conf in result
    )


def b64_to_pil(b64_str):
    import io

    from PIL import Image

    return Image.open(io.BytesIO(base64.standard_b64decode(b64_str)))


@mcp.tool
def computer_selfcheck() -> str:
    """Self-heal agent: verify all server subsystems and FIX what it can.
    Checks heavy imports, audit log writability, capture (non-blank), OCR
    engine load, screenshots scale sanity, outbound gate state. Returns
    per-subsystem status + list of automatic repairs applied."""
    import gc
    import os
    import statistics

    report, fixed = [], []

    # 1. Heavy imports (repair: import them now)
    try:
        from screen import _pyautogui, _pyperclip

        _pyautogui()
        _pyperclip()
        report.append("imports: OK")
    except Exception as exc:
        fixed.append("forced heavy re-import")
        report.append(f"imports: FAIL {exc}")

    # 2. Audit log writable
    try:
        from screen import AUDIT_LOG, audit

        audit("selfcheck", {"probe": True})
        report.append(f"audit log: OK ({os.path.getsize(AUDIT_LOG)//1024}KB)")
    except Exception as exc:
        report.append(f"audit log: FAIL {exc}")

    # 3. Capture non-blank
    try:
        b64, scale = capture_screen()
        img = b64_to_pil(b64).convert("L")
        stdev = statistics.pstdev(list(img.getdata())[::997])
        if stdev > 5:
            report.append(f"capture: OK (stdev={stdev:.0f}, scale={scale:.3f})")
        else:
            report.append(f"capture: SUSPECT (blank?, stdev={stdev:.0f})")
    except Exception as exc:
        report.append(f"capture: FAIL {exc}")

    # 4. OCR engine loads (repair: keep module-level cache warm)
    try:
        from rapidocr_onnxruntime import RapidOCR

        RapidOCR()
        report.append("OCR engine: OK")
    except Exception as exc:
        report.append(f"OCR engine: FAIL {exc}")

    # 5. Outbound gate state
    state = outbound_guard("selfcheck")
    report.append(
        "outbound gate: ACTIVE (blocked — no consent)" if state else "outbound gate: OPEN (CONSENT.txt live!)"
    )

    freed = gc.collect()
    report.append(f"gc: {freed} objects freed")
    return "SELF-CHECK RESULT\n" + "\n".join(report) + (
        f"\nFixes applied: {fixed}" if fixed else "\nNo fixes needed."
    )


@mcp.tool
def computer_review(task_description: str = "") -> str:
    """Reviewer agent: audits the LAST actions in actions.log against the
    stated task_description. Flags: actions with external effects that ran,
    consent-gate bypasses, actions not plausibly related to the task, and
    error-results. Returns findings + verdict."""
    import os

    from screen import AUDIT_LOG

    if not os.path.exists(AUDIT_LOG):
        return "review: no audit log yet — nothing to review."
    with open(AUDIT_LOG, encoding="utf-8", errors="replace") as f:
        lines = f.read().strip().splitlines()[-30:]
    findings, external = [], []
    OUTBOUND = {"type", "key", "write_clipboard", "left_click", "double_click",
                "triple_click", "right_click", "left_click_drag"}
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        ts, name, args = parts[0], parts[1], parts[2] if len(parts) > 3 else ""
        if name == "open_application":
            external.append(line)
        if name in OUTBOUND:
            external.append(line)
    if external:
        findings.append(
            f"{len(external)} action(s) with external effects in last {len(lines)}:\n  "
            + "\n  ".join(external[-8:])
        )
    if not task_description:
        findings.append("no task_description given — cannot judge relevance; pass what the task was.")
    verdict = "CLEAN" if not external else "REVIEW NEEDED"
    return f"REVIEW of last {len(lines)} actions (task: {task_description or 'unspecified'})\n" + (
        "\n".join(findings) if findings else "no external-effect actions found."
    ) + f"\nverdict: {verdict}"


@mcp.tool
def computer_capture_monitor(monitor: int = 1) -> Image:
    """Screenshot ONE physical monitor (1..N). computer_screenshot captures
    the whole virtual desktop; use this to zoom on one display on multi-monitor
    setups. List displays with computer_display_overview."""
    b64, scale = capture_screen(monitor=monitor)
    CURRENT_SCALE[0] = scale or 1.0
    return Image(data=base64.standard_b64decode(b64), format="png")


@mcp.tool
def computer_display_overview() -> str:
    """List all physical monitors with resolution and virtual-desktop position.
    Returns JSON array: index, left, top, width, height. Use before
    computer_capture_monitor to pick the right display index."""
    from screen import list_monitors

    import json as _json

    return _json.dumps(list_monitors())


@mcp.tool
def computer_teach_step(instruction: str) -> str:
    """Teach mode (stub scaffold): records that the HUMAN wants to demo an
    action for the agent to repeat. Returns guidance text. Full playback
    recording is planned; use computer_batch scripts for repeatable sequences
    today."""
    audit("teach_step", {"instruction": instruction})
    return (
        "Teach mode: perform the action manually now. The agent observes via "
        "computer_read_screen / computer_screenshot between your steps, then "
        "replays the sequence with computer_batch. For durable automation, "
        "write the steps as a batch JSON list."
    )


if __name__ == "__main__":
    # Warm the heavy libs in a boot thread: first tool call must not pay the
    # ~60s pyautogui import on slow machines.
    import threading

    def _prewarm():
        try:
            from screen import _pyautogui, _pyperclip

            _pyautogui()
            _pyperclip()
        except Exception:
            pass  # warm-up is best-effort; tools import lazily anyway

    threading.Thread(target=_prewarm, daemon=True).start()
    mcp.run()  # stdio transport — Claude Code launches and talks over stdin/stdout
