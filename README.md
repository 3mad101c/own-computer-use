# own-computer-use

![License](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Tools](https://img.shields.io/badge/MCP%20tools-18-orange) ![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blueviolet)

A self-hosted MCP server that gives AI agents real control of a Windows PC: screen reading with built-in OCR (Arabic and English), mouse, keyboard, clipboard, and app launching. It runs on any plan, with any client, and blocks every action that could affect the outside world unless you explicitly allow it. that gives AI agents real control of a Windows PC: screen reading with built-in OCR (Arabic and English), mouse, keyboard, clipboard, and app launching. It runs on any plan, with any client, and blocks every action that could affect the outside world unless you explicitly allow it.

Works with Claude Code, Claude Desktop, Codex, Cursor, or any MCP client. Python only, no cloud component, no telemetry.

## Why this exists

Desktop computer-use features in commercial AI clients are locked behind plans and platforms. The alternative is to host the capability yourself. This is a pair of Python files speaking MCP over stdio. Point your client at it and your machine becomes the tool surface. If you pay per token through your own gateway (`ANTHROPIC_BASE_URL`), it works the same.

### What agents can do with it

**Seeing the screen** Three complementary tools. `computer_screenshot` captures the entire virtual screen and auto-scales it to model image limits. `computer_zoom` magnifies any region for reading small text (coordinates remain in full-screenshot space). `computer_read_screen` runs built-in OCR (RapidOCR) and returns visible text with coordinates, in Arabic and English, without any cloud calls.

**Acting** Click (left, right, middle, single, double, triple), type, scroll, drag, hold key, mouse down/up for sliders and multi-select. Typing goes through the clipboard, so Arabic and Unicode land correctly in any app.

**Timing-critical batches** Separate tool calls are seconds apart (one model round trip). Menus that close on blur and mid-flight buttons are unreachable at that pace. `computer_batch` runs several actions milliseconds apart in one call, and `computer_wait` tunes the gaps.

**System operations** `computer_open_application` launches an app and reports what actually happened (opened, crashed on startup, no window after 8s) instead of always claiming success. `computer_focus_window` brings any window to the front by title substring. Clipboard read/write, cursor position, and waits complete the surface.

**Two supervision agents** `computer_selfcheck` verifies every subsystem (imports, audit log, capture, OCR engine, consent gate) and repairs what it can automatically. `computer_review` reads the audit log and returns CLEAN or REVIEW NEEDED by checking the last 30 actions against the task you state, flagging every action with real-world effects.

## What agents can actually do with it

This is full-machine control, not a browser extension. Anything a person does with a mouse and keyboard, the agent does through these 18 tools:

- **Every installed program.** Photoshop, CapCut, Premiere, Excel, Word, PowerPoint, OBS, Steam launchers, your own builds. `computer_open_application` starts them and reports the truth; clicks, typing, and hotkeys drive them.
- **Video and photo editing.** The agent can cut clips in CapCut or Premiere, drag timeline handles (press-hold via `computer_mouse_down_up`), apply filters through menus that need millisecond timing (`computer_batch`), and export.
- **Spreadsheets and documents.** Fill Excel cell by cell, format in Word, build slide decks, run macros with `computer_key`.
- **Messaging and email.** Read a thread with OCR, draft a reply, and send it once you approve. Reading needs no consent; sending always does.
- **Web apps.** Facebook, Telegram Web, dashboards, admin panels. OCR reads Arabic and English text on screen, so the agent can act on pages even where DOM tooling fails.
- **System work.** File Explorer, Control Panel dialogs, installers you built, settings panes. If it renders on your screen, it is reachable.

Writing quality is its own skill. When the agent writes personal messages on your behalf, pair it with the `humanizer` skill in Claude Code: replies in Messenger, WhatsApp, or email draft in a natural human voice (varied sentence rhythm, no AI tells), then pass your review before sending. The consent gate means nothing goes out until you have read it.

## Safety, enforced in code

Three gates sit between an agent and your machine.

**Self-harm guard.** Typing and key presses are blocked while an agent surface holds focus (Claude, VS Code, terminals). Text aimed at a chat window would land in the conversation itself, or execute as a shell command.

**Consent gate.** Every machine-mutating tool is blocked at server level unless a file named `CONSENT.txt` exists next to the server, starts with `ALLOW`, and is less than 10 minutes old: click, type, key (Enter), scroll, drag, mouse down/up, hold key, batch, and open_application. Read-only tools (screenshot, zoom, OCR, cursor position, clipboard read) stay free.

```
ALLOW send-reply-to-messenger
```

The gate auto-expires. A misaligned model cannot click Submit, type into your apps, or send messages unless you deliberately created that file within the last ten minutes. Injection-tested: `computer_open_application` rejects shell metacharacters (`& | ^ < > ! % "`) before any process starts, and OCR output is returned verbatim, never executed.

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

## A worked example

Ask your agent: "open Facebook Messenger, read the last message, reply to it."

The flow, as tested end-to-end:

1. `computer_open_application` launches Chrome at the Messenger URL and reports `opened: window "..."`.
2. `computer_read_screen(target_title="facebook")` brings the window forward and OCR-reads it, returning chat names, previews, and the input box position.
3. A click derived from OCR coordinates opens the conversation; another read shows the last message.
4. For the reply, you write `CONSENT.txt`. Without it the `computer_type` call returns `BLOCKED` and nothing is sent, by design.
5. With consent, the text is pasted, `Return` is sent, and `computer_review` confirms the audit trail matches the task.

Reading never requires consent. Writing and sending always do.

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

**Fast cold start.** Heavy libraries (pyautogui, mss, OCR) are imported lazily, and a boot-time thread pre-warms them while the MCP handshake runs. On a 2011 dual-core laptop, the first tool call takes about 8 seconds instead of over a minute.

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
