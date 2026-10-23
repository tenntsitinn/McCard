"""Read-only McDonald's MCP inspection; raw results stay in ignored data/."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://mcp.mcd.cn"
READ_TOOLS = {"query-meals", "query-meal-detail", "query-nearby-stores", "now-time-info", "order-list"}


def validate_token(token):
    if not isinstance(token, str):
        raise ValueError("MCP Token 格式不正确，请从官方页面重新复制。")
    token = token.strip()
    if not token or len(token) > 8192 or any(not 33 <= ord(char) <= 126 for char in token):
        raise ValueError("MCP Token 格式不正确，请只粘贴官方页面复制的 Token，不要包含中文、空格或引号。")
    return token


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def token_from_local():
    token = os.environ.get("MCD_TOKEN", "").strip()
    if not token and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "MCD_TOKEN":
                token = value.strip().strip("\"'")
    if not token:
        raise ValueError("请在环境变量或项目 .env 中设置 MCD_TOKEN。")
    return validate_token(token)


class Client:
    def __init__(self, token, allowed_tools=None):
        self.token = validate_token(token)
        self.allowed_tools = frozenset(READ_TOOLS if allowed_tools is None else allowed_tools)
        self.session = None
        self.number = 0
        self.version = "2025-03-26"
        self.opener = build_opener(NoRedirect())

    def request(self, method, params=None, notification=False):
        self.number += 1
        message = {"jsonrpc": "2.0", "method": method}
        if not notification:
            message["id"] = self.number
        if params is not None:
            message["params"] = params
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.version,
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        request = Request(ENDPOINT, json.dumps(message).encode(), headers)
        try:
            with self.opener.open(request, timeout=45) as response:
                self.session = response.headers.get("Mcp-Session-Id", self.session)
                if notification:
                    return None
                if "text/event-stream" in response.headers.get("Content-Type", ""):
                    data = []
                    result = None
                    for raw_line in response:
                        line = raw_line.decode("utf-8").rstrip("\r\n")
                        if line.startswith("data:"):
                            data.append(line[5:].lstrip(" "))
                        elif not line and data:
                            event = json.loads("\n".join(data))
                            data = []
                            if event.get("id") == message["id"]:
                                result = event
                                break
                    if result is None:
                        raise ValueError("SSE 未返回匹配的响应。")
                else:
                    result = json.load(response)
        except HTTPError as exc:
            raise ValueError(f"MCP HTTP {exc.code}，请检查凭据和服务状态。") from None
        if result.get("id") != message["id"] or "error" in result:
            raise ValueError("MCP 返回协议错误或响应编号不匹配。")
        return result["result"]

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": self.version,
            "capabilities": {},
            "clientInfo": {"name": "mcd-preset-probe", "version": "0.1.0"},
        })
        if result.get("protocolVersion") not in {"2025-03-26", "2025-06-18", "2025-11-25"}:
            raise ValueError("服务端协商了未支持的协议版本。")
        self.version = result["protocolVersion"]
        self.request("notifications/initialized", notification=True)
        return result

    def tools(self):
        tools, cursor, seen = [], None, set()
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools
            if cursor in seen:
                raise ValueError("工具分页游标重复。")
            seen.add(cursor)

    def call(self, name, arguments):
        if name not in self.allowed_tools:
            raise ValueError("探查入口仅允许已列出的菜单、门店与时间查询。")
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", choices=sorted(READ_TOOLS))
    parser.add_argument("--arguments", type=Path, help="工具参数 JSON 文件")
    args = parser.parse_args()
    try:
        client = Client(token_from_local())
        client.initialize()
        output = ROOT / "data" / "mcp"
        output.mkdir(parents=True, exist_ok=True)
        if args.tool:
            arguments = json.loads(args.arguments.read_text(encoding="utf-8-sig")) if args.arguments else {}
            if not isinstance(arguments, dict):
                raise ValueError("工具参数必须是 JSON 对象。")
            result = client.call(args.tool, arguments)
            path = output / f"{args.tool}.json"
        else:
            result = client.tools()
            path = output / "tools.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"响应已保存至 {path}")
        if isinstance(result, dict) and (
            result.get("isError")
            or result.get("structuredContent", {}).get("success") is False
        ):
            parser.exit(1, "工具返回业务错误，请检查本地响应。\n")
    except (ValueError, OSError) as exc:
        # 不输出响应体或请求头，避免凭据泄漏。
        parser.exit(1, f"探查失败：{str(exc).replace(client.token, '[REDACTED]') if 'client' in locals() else '请检查本地 Token 配置'}\n")


if __name__ == "__main__":
    main()
