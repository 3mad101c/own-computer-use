# Launch posts — own-computer-use

Ready-to-paste copy for each platform. Links are correct as written.

Repo: https://github.com/3mad101c/own-computer-use

---

## 1. Reddit — r/ClaudeAI (best first post)

**Title:** I built the computer-use feature I was locked out of — 21 MCP tools, Windows, MIT

**Body:**

I wanted desktop computer use in Claude Code but it's gated. So I built it as an MCP server instead, and it turned out better than I expected.

What it does: 21 tools. Screenshots, clicks, typing (Arabic + English, clipboard-paste so it works in any layout), scrolling, drag, clipboard, app launching, window focus. Multi-monitor. Built-in OCR so the agent reads what's actually on your screen instead of guessing from pixels.

The part I care most about: every mutating action is blocked by default. The agent can't click, type, scroll, or launch anything unless you drop a `CONSENT.txt` file starting with `ALLOW`, and it expires in 10 minutes. Reading is always free. After an ambiguous go-ahead led to a message going out as me, I made that a hard gate in the server rather than a promise.

Also in there: a command-injection guard on app launching (pen-tested, rejects `& | ^ < > ! % "`), a rotating audit log of every action, and two supervision agents. `selfcheck` verifies and repairs the server; `review` audits the last 30 actions against your stated task.

Built and tested on a 2011 i7-2620M. Cold start is 7.6s after lazy imports plus a boot warm-up thread, down from over a minute.

Works with Claude Code, Claude Desktop, Codex, Cursor, any MCP client. Any plan. MIT, no telemetry, no cloud, no account.

https://github.com/3mad101c/own-computer-use

Happy to answer anything about the safety model or the Windows input internals.

---

## 2. X / Twitter

**Tweet 1:**
I got tired of computer use being gated, so I built it as an MCP server.

21 tools. Windows. MIT.

Screenshots, clicks, typing in Arabic and English, OCR that reads your actual screen, multi-monitor.

Every mutating action blocked until you drop a CONSENT.txt.

https://github.com/3mad101c/own-computer-use

**Tweet 2 (thread continuation):**
The security design is the interesting part:

- 9 mutating tools gated behind a consent file that expires in 10 minutes
- 4 read-only tools always free
- first call 7.6s on a 2011 laptop, down from 60s+
- audit log of every action

Built it after a message went out as me from an ambiguous "go ahead".

---

## 3. LinkedIn

Built something I've wanted for a while: a self-hosted Computer Use MCP server for Windows.

Desktop computer use is locked behind plans and platforms in most AI clients. I hosted the capability myself instead: a pair of Python files speaking MCP over stdio, so any client can drive a real Windows machine.

21 tools cover the full surface. Screen capture across multiple monitors, OCR in Arabic and English, mouse and keyboard input, clipboard, app launching, and millisecond-apart action batches for menus that close on blur.

The design decision I keep coming back to is defaults. Every action that changes the machine is blocked unless the user deliberately creates a consent file, and that consent expires after ten minutes. Reading the screen is always free. That split, read freely and write only on live consent, is what makes it usable for real work rather than a demo.

It also handles the reliability work: a command-injection guard on app launching, a rotating audit log, a self-repair agent, and a review agent that checks what actually ran against what was asked.

MIT licensed, no telemetry, no accounts. Tested end to end on Windows 11.

https://github.com/3mad101c/own-computer-use

---

## 4. Hacker News — Show HN

**Title:** Show HN: Own-computer-use – self-hosted Computer Use MCP server for Windows

**Body:**

I built this because desktop computer use is gated behind plans and platforms in the major AI clients, and I wanted it on my own terms.

It's an MCP server over stdio, so it works with Claude Code, Claude Desktop, Codex, Cursor, or any MCP client. Python, two main files, no cloud component.

21 tools: capture (whole virtual desktop or one monitor), built-in OCR with per-line coordinates, clicks/drag/scroll/keyboard, millisecond-apart batches, clipboard, app launching with honest status reporting, window focus.

The part I'd want a reviewer to look at is the safety model. Every mutating tool is blocked at the server level unless a `CONSENT.txt` file exists next to the server, starts with `ALLOW`, and is under ten minutes old. I added that after an ambiguous verbal approval caused a real message to be sent from my account. The gate is in the code, not in the prompt, so a misaligned model can't type or send anything without it. Read-only tools stay free.

App launching strips cmd metacharacters before spawning, pen-tested against six injection payloads. Every action appends to a rotating audit log. Two supervision tools: one verifies and repairs the server's subsystems, one audits recent actions against the task that was requested.

Performance mattered because I developed it on a 2011 dual-core laptop. Lazy imports plus a boot warm-up thread brought the first tool call from over a minute down to about 8 seconds.

Feedback on the safety model especially welcome. MIT.

https://github.com/3mad101c/own-computer-use
