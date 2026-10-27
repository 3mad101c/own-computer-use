"""Own Computer Use agent — Claude Opus 5.5 + computer toolset, local Windows host.

Run:  python agent.py "your task"
Env:  ANTHROPIC_API_KEY (required unless an `ant auth login` profile exists)
      ANTHROPIC_BASE_URL  (optional - your own gateway)
"""

import sys

import anthropic

from screen import execute_action

MODEL = "claude-opus-5-5"
MAX_TURNS = 40  # hard stop so the loop can't run away

SYSTEM_PROMPT = """You are a computer-use agent running on the user's Windows 11 machine, in Arabic-language UI where applicable.
- After every click or key action, take a screenshot before deciding the next step.
- Coordinates you send are in the pixel space of the screenshot the host returned.
- Type text via the `type` member (clipboard paste is handled host-side, Arabic works).
- Stop and report when the task is done, or when blocked (wrong window, permission dialog, login needed)."""


def run_task(client, task):
    messages = [{"role": "user", "content": task}]
    tools = [{"type": "computer_toolset_20260801"}]

    for _turn in range(MAX_TURNS):
        # Streaming: long turns + 64K output would hit HTTP timeouts otherwise.
        with client.messages.stream(
            model=MODEL,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Append the full assistant turn (thinking/tool_use/text - all of it).
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            # Server hit an iteration cap mid-turn: re-send to continue.
            continue
        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            return f"REFUSED: {detail}"
        if response.stop_reason != "tool_use":
            texts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
            return "\n".join(texts) or "(no text in final response)"

        # Execute every tool call Claude made this turn (often several).
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                print(f"  [{block.type}] skipped")
                continue
            name = block.name
            result = execute_action(name, block.input, CURRENT_SCALE[0])
            # Only screenshot/zoom return (image, scale); image dict otherwise.
            content = result[0] if isinstance(result, tuple) else result
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "toolset_name": "computer",  # required echo for toolset calls
                "content": content,
            })
        messages.append({"role": "user", "content": tool_results})

    return f"Stopped after MAX_TURNS={MAX_TURNS} without finishing."


def main():
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        print("Usage: python agent.py \"task in quotes\"")
        sys.exit(2)

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL

    # Warm-up capture: compute the scale factor once; screen size never changes
    # mid-run, so one value serves every coordinate conversion.
    from screen import capture_screen
    _, scale = capture_screen()
    CURRENT_SCALE[0] = scale
    print(f"Screen scale: {scale:.4f} | Task: {task}\n")

    print(run_task(client, task))


CURRENT_SCALE = [1.0]

if __name__ == "__main__":
    main()
