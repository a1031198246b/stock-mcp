import json
import subprocess
import sys


def _spawn_server():
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

    line = proc.stdout.readline()
    init_resp = json.loads(line)
    assert init_resp["id"] == 1
    assert "result" in init_resp

    # 2. initialized 通知
    proc.stdin.write((json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized"
    }) + "\n").encode())
    proc.stdin.flush()

    return proc


def test_ping_via_stdio():
    proc = _spawn_server()

    # 3. tools/call ping
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


def test_get_realtime_quote_listed_and_callable_via_stdio():
    """验证 get_realtime_quote 工具已注册并可通过 stdio 调用"""
    proc = _spawn_server()

    # 1. tools/list
    list_req = {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
        "params": {},
    }
    proc.stdin.write((json.dumps(list_req) + "\n").encode())
    proc.stdin.flush()

    line = proc.stdout.readline()
    list_resp = json.loads(line)
    assert list_resp["id"] == 2
    assert "result" in list_resp
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "get_realtime_quote" in tool_names
    assert "ping" in tool_names

    # 2. tools/call get_realtime_quote
    call_req = {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {
            "name": "get_realtime_quote",
            "arguments": {"codes": ["600519"]},
        }
    }
    proc.stdin.write((json.dumps(call_req) + "\n").encode())
    proc.stdin.flush()

    line = proc.stdout.readline()
    call_resp = json.loads(line)
    assert call_resp["id"] == 3
    assert "result" in call_resp
    # tqcenter 在 E2E 环境下未初始化, 应返回 DataSourceError -> "数据获取失败" 文本
    content = call_resp["result"]["content"]
    assert len(content) >= 1
    text = content[0]["text"]
    # 只要工具正常返回（不抛协议错）就算通过
    assert isinstance(text, str)
    assert len(text) > 0

    proc.terminate()
    proc.wait(timeout=5)
