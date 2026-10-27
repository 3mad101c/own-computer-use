# Security model and test evidence

This document states exactly what the server prevents, what it does not, and the
tests that back each claim. Run every test yourself; nothing here is asserted
without a command you can execute.

## What the consent gate blocks

Nine tools change machine state and are refused at server level unless
`CONSENT.txt` sits next to the server, its first line starts with `ALLOW`, and
its modification time is under ten minutes old:

`computer_click`, `computer_type`, `computer_key` (Enter), `computer_scroll`,
`computer_drag`, `computer_mouse_down_up`, `computer_hold_key`,
`computer_batch`, `computer_open_application`.

Four tools only read and are always available: `computer_screenshot`,
`computer_zoom`, `computer_read_screen`, `computer_cursor_position`, plus
`computer_clipboard` in read mode.

### Verify it

```bash
cd <repo>
python test_security.py
```

`test_security.py` runs a thirteen-call matrix against a fresh server process:
nine mutating tools must return `BLOCKED`, four read-only tools must succeed, and
the test asserts no `CONSENT.txt` existed during the run. It prints one line per
tool and exits non-zero on any mismatch.

## Command-injection guard

`computer_open_application` passes its target to `cmd /c start`. Shell
metacharacters (`& ^ | < > ! % "`) are rejected before any process starts.

### Verify it

```bash
python test_security.py --injection
```

Six payloads are attempted (`notepad & calc`, `calc | whoami`, and four others)
with a live consent file, so the metacharacter guard is what rejects them, not
the consent gate. All six must return the injection-guard refusal.

## Keyboard self-harm guard

`computer_type` and `computer_key` refuse while the focused window belongs to an
agent surface (Claude, VS Code, terminals). Without this, text aimed at a chat
window would land in the agent's own conversation or execute as a shell command.

## Audit trail

Every executed action appends one line to `actions.log` with a timestamp and its
arguments, rotating at 1 MB. `computer_review` reads the last thirty actions and
returns `CLEAN` or `REVIEW NEEDED` against a task you describe.

## What this does not do

The gates are behavior controls, not a security boundary. The server runs with
your user privileges. They stop a misaligned or prompt-injected agent from
acting without your say-so. They do not stop malware that already runs as you.
An attacker who can write files as your user can also write `CONSENT.txt`.

Elevated applications (Task Manager, UAC prompts) reject synthetic input by
Windows UIPI. That is a Windows boundary, and this server does not try to cross
it.

Report a gap in any of these claims as a GitHub issue with the command that
reproduces it.
