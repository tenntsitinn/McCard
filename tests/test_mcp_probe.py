import io
import json
import unittest

from mcp_probe import Client


class Response(io.BytesIO):
    def __init__(self, content, content_type="application/json", session=None):
        super().__init__(content)
        self.headers = {"Content-Type": content_type}
        if session:
            self.headers["Mcp-Session-Id"] = session


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return next(self.responses)


class ClientTests(unittest.TestCase):
    def test_initialize_and_session_propagation(self):
        client = Client("test-only")
        client.opener = Opener([
            Response(json.dumps({"id": 1, "result": {"protocolVersion": "2025-03-26"}}).encode(), session="test-session"),
            Response(b""),
            Response(b'{"id":3,"result":{"tools":[]}}'),
        ])
        client.initialize()
        self.assertEqual(client.tools(), [])
        headers = dict(client.opener.requests[-1].header_items())
        self.assertEqual(headers["Mcp-session-id"], "test-session")

    def test_sse_ignores_notifications_and_reads_response(self):
        client = Client("test-only")
        client.opener = Opener([Response(
            b'data: {"method":"notifications/progress"}\n\n'
            b'data: {"id":1,\n'
            b'data: "result":{"tools":[]}}\n\n',
            "text/event-stream",
        )])
        self.assertEqual(client.tools(), [])

    def test_write_tools_rejected_before_request(self):
        client = Client("test-only")
        with self.assertRaises(ValueError):
            client.call("create-order", {})

    def test_explicit_tool_scope_can_extend_the_client(self):
        client = Client("test-only", allowed_tools={"calculate-price"})
        client.request = lambda method, params: {"tool": params["name"]}
        self.assertEqual(client.call("calculate-price", {}), {"tool": "calculate-price"})
        with self.assertRaises(ValueError):
            client.call("create-order", {})


if __name__ == "__main__":
    unittest.main()
