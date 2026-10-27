"""Self-test: exercise all 7 tools over stdio against the patched server."""
import json, subprocess, sys, time

def rpc(method, id_=None, **params):
    m = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        m["id"] = id_
        m["params"] = params
    return json.dumps(m)

procs_input = []
proc = subprocess.Popen([sys.executable, "mcp_server.py"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL)
def send(line):
    proc.stdin.write((line + "\n").encode()); proc.stdin.flush()

# init handshake
send(rpc("initialize", 0, protocolVersion="2024-11-05", capabilities={}, clientInfo={"name":"t","version":"1"}))
send(rpc("notifications/initialized"))
send(rpc("tools/call", 1, name="computer_screenshot", arguments={}))
send(rpc("tools/call", 2, name="computer_type", arguments={"text": "hello"}))
send(rpc("tools/call", 3, name="computer_key", arguments={"key": "escape"}))
send(rpc("tools/call", 4, name="computer_scroll", arguments={"x": 700, "y": 400, "direction": "down", "amount": 1}))
send(rpc("tools/call", 5, name="computer_drag", arguments={"start_x": 500, "start_y": 500, "x": 600, "y": 500}))
send(rpc("tools/call", 6, name="computer_zoom", arguments={"x": 0, "y": 0, "width": 400, "height": 300}))
proc.stdin.close()

results = {}
t0 = time.time()
for raw in proc.stdout:
    try: msg = json.loads(raw)
    except json.JSONDecodeError: continue
    if "id" in msg and msg["id"] is not None:
        r = msg.get("result", {})
        kinds = [b.get("type") for b in r.get("content", [])]
        results[msg["id"]] = (kinds, r.get("isError", False), round(time.time()-t0, 1))
proc.wait(timeout=30)

names = {1: "screenshot", 2: "type", 3: "key", 4: "scroll", 5: "drag", 6: "zoom"}
ok = True
for i, name in names.items():
    kinds, iserr, dt = results.get(i, ("TIMEOUT", True, 99))
    status = "PASS" if (not iserr and kinds) else "FAIL"
    if status == "FAIL": ok = False
    print(f"{name:10s} {status}  {kinds}  {dt}s")
sys.exit(0 if ok else 1)
