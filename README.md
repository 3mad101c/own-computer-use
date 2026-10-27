# own-computer-use

![License](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Tools](https://img.shields.io/badge/MCP%20tools-18-orange) ![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blueviolet)

A self-hosted MCP server that gives AI agents real control of a Windows PC: screen reading with built-in OCR (Arabic and English), mouse, keyboard, clipboard, and app launching. It runs on any plan, with any client, and blocks every action that could affect the outside world unless you explicitly allow it.

Works with Claude Code, Claude Desktop, Codex, Cursor, or any MCP client. Python only, no cloud component, no telemetry.

## Why this exists

Desktop computer-use features in commercial AI clients are locked behind plans and platforms. The alternative is to host the capability yourself. This is a pair of Python files speaking MCP over stdio. Point your client at it and your machine becomes the tool surface. If you pay per token through your own gateway (`ANTHROPIC_BASE_URL`), it works the same.

## What the agent can actually do

This is full-machine control, not a browser extension. Anything a person does with a mouse and keyboard, the agent does through these 18 tools.

**Every installed program.** Photoshop, CapCut, Premiere, Excel, Word, PowerPoint, OBS, game launchers, your own builds. `computer_open_application` starts them and reports what actually happened; clicks, typing, and hotkeys drive them.

**Video and photo editing.** Cut clips in CapCut or Premiere, drag timeline handles with press-hold (`computer_mouse_down_up`), apply filters through menus that need millisecond timing (`computer_batch`), export the result.

**Spreadsheets and documents.** Fill Excel cell by cell, format in Word, assemble slide decks, trigger macros with `computer_key`.

**Messaging and email.** Read a thread with OCR, draft a reply, send it once you approve. Reading needs no consent; sending always does.

**Web apps.** Facebook, Telegram Web, dashboards, admin panels, anything behind a login. OCR reads Arabic and English text straight off the screen, so the agent acts on pages that DOM tooling cannot reach.

**System work.** File Explorer, Control Panel dialogs, installers, settings panes. If it renders on your screen, it is reachable.

**Anything with a GUI, and anything without one.** The agent uses a terminal or API for file and data work when that is faster, and switches to the GUI for the parts that need a real window. `computer_selfcheck` keeps the whole surface healthy between runs.

Writing quality is a separate skill. When the agent drafts personal messages on your behalf, pair it with the `humanizer` skill in Claude Code: replies in Messenger, WhatsApp, or email come out in a natural human voice instead of sounding like a model, and you read them before anything is sent.

## The 18 tools

| Category | Tools |
|---|---|
| See | `computer_screenshot` (entire virtual screen, auto-scaled to model limits) · `computer_zoom` (magnify a region; coordinates stay in full-screenshot space) · `computer_read_screen` (built-in OCR, Arabic and English, optional atomic `target_title` focus+read) |
| Act *(consent-gated)* | `computer_click` (left/right/middle, single/double/triple) · `computer_type` (clipboard paste, Arabic and Unicode safe) · `computer_key` · `computer_hold_key` · `computer_scroll` · `computer_drag` · `computer_mouse_down_up` (press-hold for sliders and multi-select) |
| Batch *(consent-gated)* | `computer_batch` — several actions milliseconds apart in one call, for timing-critical UI: menus that close on blur, mid-flight buttons |
| System | `computer_open_application` *(consent-gated, injection-guarded)* — honest launch report: opened, crashed on startup, no window after 8s · `computer_focus_window` (bring any window forward by title substring) · `computer_clipboard` (read/write) · `computer_cursor_position` · `computer_wait` |
| Agents | `computer_selfcheck` (verify + auto-repair imports, audit log, capture, OCR, gate) · `computer_review` (audit the last 30 actions against your stated task, return CLEAN or REVIEW NEEDED) |

## Built on FastMCP, tuned for speed

The server is a [FastMCP](https://gofastmcp.com) stdio server, so it plugs into every MCP client that speaks the standard protocol, and FastMCP handles tool schemas, validation, and error shaping for you.

Speed was a design constraint, not an afterthought. On a 2011 dual-core laptop (the machine this was built on), a naive version of the same server took over a minute to answer its first call.

| Optimization | Effect |
|---|---|
| Lazy imports | `tools/list` answers without loading pyautogui, mss, or the OCR engine |
| Boot warm-up thread | Heavy libraries load in the background while the MCP handshake runs, so the first real call lands in ~8s instead of 60s+ |
| Full virtual screen capture | One `mss` grab of the whole desktop; no per-monitor round trips |
| Screenshot downscale in-process | PIL resize at capture time, never on the model side |
| One-shot tool calls | `computer_batch` removes the model round trip between actions (seconds to milliseconds) |
| Cached OCR engine | RapidOCR is instantiated once per server, not per read |

The result: a first call in seconds, subsequent calls in milliseconds, and a batch of ten actions in one model turn.

## Safety, enforced in code

Three gates sit between an agent and your machine.

**Self-harm guard.** Typing and key presses are blocked while an agent surface holds focus (Claude, VS Code, terminals). Text aimed at a chat window would land in the conversation itself, or execute as a shell command.

**Consent gate.** Every machine-mutating tool is blocked at server level unless a file named `CONSENT.txt` exists next to the server, starts with `ALLOW`, and is less than 10 minutes old:

```
ALLOW send-reply-to-messenger
```

Blocked without it: click, type, key (Enter), scroll, drag, mouse down/up, hold key, batch, open_application. Free: screenshot, zoom, OCR, cursor position, clipboard read.

The gate auto-expires. A misaligned model cannot click Submit, type into your apps, or send messages unless you deliberately created that file within the last ten minutes. `computer_open_application` also rejects shell metacharacters (`& | ^ < > ! % "`) before any process starts, and OCR output is returned verbatim, never executed.

**Audit log.** Every executed action lands in `actions.log` with a timestamp and its arguments (1 MB rotation). `computer_review` turns the log into a verdict. A failsafe on the host side: jamming the mouse into a screen corner aborts input injection.

## Installation

Windows, Python 3.10+.

```bash
git clone https://github.com/3mad101c/own-computer-use.git
cd own-computer-use
pip install -r requirements.txt
claude mcp add own-computer-use --scope user -- python C:\path\to\mcp_server.py
claude mcp list    # expect: own-computer-use ... Connected
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "own-computer-use": {
      "command": "python",
      "args": ["C:\\path\\to\\mcp_server.py"]
    }
  }
}
```

OCR is optional. Without `rapidocr_onnxruntime` everything else works; install it for `computer_read_screen`:

```bash
pip install rapidocr-onnxruntime
```

## Worked examples

**Edit a video.** "Open my CapCut project in Downloads, cut the clip at 00:12, export it."

The agent launches CapCut, reads the timeline with OCR, clicks the split point, exports, and reports what happened at each step. Clicking the export button needs a live `CONSENT.txt`; everything up to it does not.

**Fill a spreadsheet.** "Open budget.xlsx, put last month's totals in column D, bold the header."

Excel launches, the agent types into cells, uses `computer_key` for formatting, and saves with Ctrl+S.

**Handle a message.** "Read my last message on Messenger and reply that I'll call later."

`computer_read_screen` reads the thread, the agent drafts in a human voice (with the `humanizer` skill), shows you the text, and only sends once you approve and `CONSENT.txt` is live.

**Review what happened.** "Review the last 30 actions against the task I gave you."

`computer_review` returns CLEAN or REVIEW NEEDED, listing every action with real-world effects.

## Standalone CLI agent

`agent.py` runs the same computer-use loop outside MCP: it streams Anthropic's `computer_toolset_20260801` on `claude-opus-5-5` and executes each requested action locally, honoring the same consent file.

```bash
python agent.py "open calculator and compute 7*8"
```

It needs `ANTHROPIC_API_KEY` in the environment. It also honors `ANTHROPIC_BASE_URL`, so your own gateway works.

## Architecture

A few decisions worth knowing before you extend it.

**Coordinate space.** Screenshots are downscaled to a 1568 px long edge. The scale factor is tracked, and every coordinate the model sends in screenshot space is mapped back to physical pixels inside `screen.py`. The model never sees your resolution or DPI.

**Full virtual screen.** Capture uses `mss` monitor 0 (the entire virtual desktop), so an app opening on a second display cannot produce a screenshot of the wrong screen.

**Files:**

```
mcp_server.py   FastMCP stdio server: 18 tools, guards, consent gate, OCR
screen.py       capture, coordinate mapping, input actions, audit log
agent.py        optional standalone Claude-API computer-use loop
skills/         SKILL.md teaching agents the look-act-look discipline
test_all_tools.py  stdio integration test for the whole tool surface
```

## Known limitations

Windows only (Win32 focus and input injection). macOS and Linux ports are welcome.

Elevated applications (Task Manager, UAC prompts) reject synthetic input by Windows UIPI design.

RapidOCR reads English well and Arabic acceptably; treat it as a reading aid and confirm critical text with a zoomed screenshot.

IME layouts can alter `computer_key` and `computer_hold_key` (virtual keycodes pass through the IME). Clipboard-paste typing is immune.

## License

MIT
