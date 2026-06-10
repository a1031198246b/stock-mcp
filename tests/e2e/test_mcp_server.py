import json
import subprocess
import sys


def test_ping_via_stdio():
    proc = subprocess.Popen(
        [sys.executable, "-m", "stock_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="E:/claude codeworkspace/stock-mcp",
    )

    # 1. initialize
    init_req = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1"},
        }
    }
    proc.stdin.write((json.dumps(init_req) + "\n").encode())
    proc.stdin.flush()

    # 2. 读 initialize 响应
    line = proc.stdout.readline()
    init_resp = json.loads(line)
    assert init_resp["id"] == 1
    assert "result" in init_resp

    # 3. initialized 通知
    proc.stdin.write((json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized"
    }) + "\n").encode())
    proc.stdin.flush()

    # 4. tools/call ping
    call_req = {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {
            "name": "ping",
            "arguments": {},
        }
    }
    proc.stdin.write((json.dumps(call_req) + "\n").encode())
    proc.stdin.flush()

    line = proc.stdout.readline()
    call_resp = json.loads(line)
    assert call_resp["id"] == 2
    assert "result" in call_resp
    # FastMCP 3.x wraps return in CallToolResult; dict goes to structuredContent
    assert call_resp["result"]["structuredContent"]["status"] == "ok"

    proc.terminate()
    proc.wait(timeout=5)
