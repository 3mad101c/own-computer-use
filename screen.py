"""Screen adapter: capture, scale, click/type/key execution on Windows.

Heavy imports (mss/PIL/pyautogui/pyperclip) are lazy: MCP tools/list must
answer fast on slow machines, so nothing heavy loads before the first call.
"""

import base64
import io
import json
import os
import time

# Claude image limits: long edge max 1568px for computer use screenshots.
MAX_EDGE = 1568

# Audit log: every executed action appends one line here (rotating by size).
AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "actions.log")
_AUDIT_MAX_BYTES = 1_000_000


def audit(name, inp):
    """Append one line per action; rotate when the file exceeds the cap."""
    try:
        if os.path.exists(AUDIT_LOG) and os.path.getsize(AUDIT_LOG) > _AUDIT_MAX_BYTES:
            os.replace(AUDIT_LOG, AUDIT_LOG + ".old")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts}  {name}  {json.dumps(inp, ensure_ascii=False)[:200]}\n")
    except OSError:
        pass  # audit must never break an action


def _pyperclip():
    import pyperclip

    return pyperclip


def _pyautogui():
    import pyautogui

    pyautogui.FAILSAFE = True  # slam mouse to corner to abort
    pyautogui.PAUSE = 0.05
    return pyautogui


def capture_screen():
    """Capture full virtual screen (all monitors), downscale if needed.
    Returns (b64_png, scale)."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        # monitors[0] = entire virtual screen (all monitors merged) - immune to
        # "app opened on the other display" mismatch. mon=1 is primary only.
        shot = sct.shot(mon=0)
        img = Image.open(shot)
        orig_w, orig_h = img.size
        scale = 1.0
        if max(orig_w, orig_h) > MAX_EDGE:
            scale = MAX_EDGE / max(orig_w, orig_h)
            new_size = (round(orig_w * scale), round(orig_h * scale))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("ascii"), scale


def _to_real_coords(x, y, scale):
    """Model sends coords in the scaled screenshot space -> real pixels."""
    return round(x / scale), round(y / scale)


def execute_action(name, inp, scale):
    """Execute one computer-toolset member call.

    Returns the tool_result `content`:
      - tuple/image dict for screenshot/zoom
      - "OK" string for everything else.
    Coordinates arrive in SCALED space (the screenshot we sent), so convert.
    Every action is audited to actions.log.
    """
    audit(name, inp)

    if name == "screenshot":
        b64, _ = capture_screen()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            },
        }

    if name == "zoom":
        # Zoom into a region: capture, crop, upscale small crops for clarity.
        x, y = inp.get("x", 0), inp.get("y", 0)
        w, h = inp.get("width", 0), inp.get("height", 0)
        safe_scale = scale if scale else 1.0
        rx, ry = _to_real_coords(x, y, safe_scale)
        rw, rh = max(round(w / safe_scale), 1), max(round(h / safe_scale), 1)
        import mss
        from PIL import Image

        with mss.mss() as sct:
            region = {"left": rx, "top": ry, "width": rw, "height": rh}
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        # Upscale small crops so text is readable, then cap long edge.
        crop_scale = min(MAX_EDGE / max(img.size), 3)
        scale_factor = safe_scale
        if crop_scale > 1:
            img = img.resize(
                (round(img.width * crop_scale), round(img.height * crop_scale)),
                Image.LANCZOS,
            )
            scale_factor = safe_scale / crop_scale
        if max(img.size) > MAX_EDGE:
            down = MAX_EDGE / max(img.size)
            img = img.resize(
                (round(img.width * down), round(img.height * down)),
                Image.LANCZOS,
            )
            scale_factor = scale_factor * down
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.standard_b64encode(buf.getvalue()).decode("ascii"),
            },
        }, scale_factor

    if name == "left_click":
        x, y = inp.get("x"), inp.get("y")
        if x is None or y is None:
            return "ERROR: left_click needs x,y"
        rx, ry = _to_real_coords(x, y, scale)
        _pyautogui().click(rx, ry)
        return "OK"

    if name == "double_click":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().doubleClick(rx, ry)
        return "OK"

    if name == "triple_click":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().click(rx, ry, clicks=3)
        return "OK"

    if name == "right_click":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().click(rx, ry, button="right")
        return "OK"

    if name == "middle_click":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().click(rx, ry, button="middle")
        return "OK"

    if name == "hover":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().moveTo(rx, ry)
        return "OK"

    if name == "left_click_drag":
        sx, sy = _to_real_coords(inp["start_x"], inp["start_y"], scale)
        ex, ey = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().moveTo(sx, sy)
        _pyautogui().drag(ex - sx, ey - sy, duration=0.3)
        return "OK"

    if name == "scroll":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().moveTo(rx, ry)
        amount = int(inp.get("scroll_amount", 1))
        direction = inp.get("scroll_direction", "down")
        # Windows: one wheel notch = 120 units.
        if direction == "down":
            _pyautogui().scroll(-amount * 120)
        elif direction == "up":
            _pyautogui().scroll(amount * 120)
        elif direction == "right":
            _pyautogui().hscroll(amount * 120)
        elif direction == "left":
            _pyautogui().hscroll(-amount * 120)
        return "OK"

    if name == "type":
        # Paste via clipboard: safe with Arabic/non-QWERTY keyboard layouts.
        text = inp.get("text", "")
        _pyperclip().copy(text)
        time.sleep(0.05)
        _pyautogui().hotkey("ctrl", "v")
        time.sleep(0.1)
        return "OK"

    if name == "key":
        # e.g. "Return", "ctrl+c", "alt+Tab"
        raw = inp.get("key", "")
        keys = [k.lower() for k in raw.split("+")]
        keys = [_SPECIAL.get(k, k) for k in keys]
        if len(keys) == 1:
            _pyautogui().press(keys[0])
        else:
            _pyautogui().hotkey(*keys)
        return "OK"

    if name == "wait":
        time.sleep(min(float(inp.get("duration", 2)), 10))
        return "OK"

    if name == "left_mouse_down":
        _pyautogui().mouseDown()
        return "OK"

    if name == "left_mouse_up":
        _pyautogui().mouseUp()
        return "OK"

    if name == "hold_key":
        # hold_key {"key": "ctrl", "duration": 2} — hold then release.
        p = _pyautogui()
        k = _SPECIAL.get(inp.get("key", "").lower(), inp.get("key", "").lower())
        p.keyDown(k)
        time.sleep(min(float(inp.get("duration", 1)), 10))
        p.keyUp(k)
        return "OK"

    if name == "read_clipboard":
        return _pyperclip().paste()

    if name == "write_clipboard":
        _pyperclip().copy(inp.get("text", ""))
        return "OK"

    if name == "mouse_move":
        rx, ry = _to_real_coords(inp["x"], inp["y"], scale)
        _pyautogui().moveTo(rx, ry)
        return "OK"

    if name in ("cursor_position",):
        pos = _pyautogui().position()
        return f"X={pos.x},Y={pos.y}"

    return f"OK (action {name} acknowledged, not implemented)"


_SPECIAL = {
    "return": "enter",
    "escape": "esc",
}
