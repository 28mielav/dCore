"""Protocol-level tests for the dCore MCP server.

These drive the dispatcher the way a client does rather than calling handlers
directly, because the parts most likely to break are framing, error mapping and
notification handling, none of which a direct call exercises.
"""

from __future__ import annotations

import io
import json
import unittest

from dcore.mcp import prompts, resources, tools
from dcore.mcp.protocol import METHOD_NOT_FOUND, PARSE_ERROR, serve
from dcore.mcp.server import SUPPORTED_PROTOCOL_VERSIONS, build_dispatcher


def exchange(*messages: dict | str) -> list[dict]:
    """Feed frames through the real stdio loop and collect the responses."""
    lines = [
        message if isinstance(message, str) else json.dumps(message)
        for message in messages
    ]
    sink = io.StringIO()
    serve(build_dispatcher(), io.StringIO("\n".join(lines) + "\n"), sink)
    return [json.loads(line) for line in sink.getvalue().splitlines() if line.strip()]


def request(identifier: int, method: str, params: dict | None = None) -> dict:
    message = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        message["params"] = params
    return message


class HandshakeTests(unittest.TestCase):
    def test_initialize_echoes_a_supported_protocol_version(self) -> None:
        (response,) = exchange(request(1, "initialize", {"protocolVersion": "2024-11-05"}))
        self.assertEqual(response["result"]["protocolVersion"], "2024-11-05")

    def test_unknown_protocol_version_falls_back_to_the_newest_supported(self) -> None:
        (response,) = exchange(request(1, "initialize", {"protocolVersion": "1988-01-01"}))
        self.assertEqual(response["result"]["protocolVersion"], SUPPORTED_PROTOCOL_VERSIONS[0])

    def test_server_reports_the_package_version(self) -> None:
        import dcore

        (response,) = exchange(request(1, "initialize", {}))
        self.assertEqual(response["result"]["serverInfo"]["version"], dcore.__version__)

    def test_notifications_get_no_response(self) -> None:
        responses = exchange({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(responses, [])

    def test_unknown_notification_is_ignored_rather_than_answered(self) -> None:
        responses = exchange({"jsonrpc": "2.0", "method": "notifications/somethingNew"})
        self.assertEqual(responses, [])


class TransportTests(unittest.TestCase):
    def test_malformed_line_reports_parse_error_and_keeps_serving(self) -> None:
        responses = exchange("this is not json", request(2, "ping"))
        self.assertEqual(responses[0]["error"]["code"], PARSE_ERROR)
        self.assertEqual(responses[1]["result"], {})

    def test_unknown_method_is_method_not_found(self) -> None:
        (response,) = exchange(request(1, "nope/nope"))
        self.assertEqual(response["error"]["code"], METHOD_NOT_FOUND)

    def test_blank_lines_are_skipped(self) -> None:
        responses = exchange("", request(1, "ping"), "")
        self.assertEqual(len(responses), 1)


class ToolSurfaceTests(unittest.TestCase):
    def test_every_tool_advertises_an_object_schema(self) -> None:
        for descriptor in tools.descriptors():
            with self.subTest(tool=descriptor["name"]):
                self.assertEqual(descriptor["inputSchema"]["type"], "object")
                self.assertTrue(descriptor["description"].strip())
                self.assertTrue(descriptor["title"].strip())

    def test_tool_names_are_namespaced(self) -> None:
        for descriptor in tools.descriptors():
            self.assertTrue(descriptor["name"].startswith("dcore_"), descriptor["name"])

    def test_lint_accepts_inline_text_and_reports_findings(self) -> None:
        (response,) = exchange(request(1, "tools/call", {
            "name": "dcore_lint",
            "arguments": {
                "text": (
                    "demo:\n  type: world\n  events:\n"
                    "    on player tries to attack slime:\n"
                    "    - determine cancelled\n    - narrate unreachable\n"
                ),
                "filename": "probe.dsc",
            },
        }))
        result = response["result"]
        self.assertNotEqual(result.get("isError"), True)
        codes = {item["code"] for item in json.loads(result["content"][0]["text"])}
        self.assertIn("unreachable_after_terminal_command", codes)
        # A linter exiting non-zero on findings is doing its job, not failing.
        self.assertTrue(result["structuredContent"]["blocking"])

    def test_clean_script_is_not_blocking(self) -> None:
        (response,) = exchange(request(1, "tools/call", {
            "name": "dcore_lint",
            "arguments": {"text": "demo:\n  type: task\n  script:\n  - narrate hello\n"},
        }))
        result = response["result"]
        self.assertFalse(result["structuredContent"]["blocking"])

    def test_missing_script_input_is_a_tool_error_not_a_crash(self) -> None:
        (response,) = exchange(request(1, "tools/call", {"name": "dcore_lint", "arguments": {}}))
        self.assertTrue(response["result"]["isError"])

    def test_unknown_tool_is_a_tool_error(self) -> None:
        (response,) = exchange(request(1, "tools/call", {"name": "dcore_nope", "arguments": {}}))
        self.assertTrue(response["result"]["isError"])

    def test_inline_filename_cannot_escape_the_workspace(self) -> None:
        # A traversal basename must not place a file outside the temporary dir.
        (response,) = exchange(request(1, "tools/call", {
            "name": "dcore_lint",
            "arguments": {
                "text": "demo:\n  type: task\n  script:\n  - narrate hello\n",
                "filename": "../../escaped.dsc",
            },
        }))
        result = response["result"]
        self.assertNotEqual(result.get("isError"), True)
        findings = json.loads(result["content"][0]["text"] or "[]")
        for finding in findings:
            self.assertNotIn("..", finding["file"])


class ResourceTests(unittest.TestCase):
    def test_instructions_resource_is_present_and_carries_the_gates(self) -> None:
        (response,) = exchange(request(1, "resources/read", {"uri": "dcore://instructions"}))
        text = response["result"]["contents"][0]["text"]
        for expected in ("local-evidence gate", "seven-step execution gate", "Reflect"):
            self.assertIn(expected, text)

    def test_manifest_resource_is_json(self) -> None:
        (response,) = exchange(request(1, "resources/read", {"uri": "dcore://manifest"}))
        content = response["result"]["contents"][0]
        self.assertEqual(content["mimeType"], "application/json")
        self.assertEqual(json.loads(content["text"])["name"], "dCore")

    def test_unknown_resource_is_an_invalid_params_error(self) -> None:
        (response,) = exchange(request(1, "resources/read", {"uri": "dcore://nope"}))
        self.assertIn("error", response)

    def test_listed_resources_all_resolve(self) -> None:
        for descriptor in resources.descriptors():
            with self.subTest(uri=descriptor["uri"]):
                self.assertIn("contents", resources.read(descriptor["uri"]))


class PromptTests(unittest.TestCase):
    def test_prompts_render_with_required_arguments(self) -> None:
        (response,) = exchange(request(1, "prompts/get", {
            "name": "dcore_task",
            "arguments": {"request": "build a dog search session", "target": "paper 1.21.11"},
        }))
        text = response["result"]["messages"][0]["content"]["text"]
        self.assertIn("build a dog search session", text)
        self.assertIn("dcore://instructions", text)

    def test_missing_required_argument_is_reported(self) -> None:
        (response,) = exchange(request(1, "prompts/get", {"name": "dcore_task", "arguments": {}}))
        self.assertIn("error", response)

    def test_optional_argument_may_be_omitted(self) -> None:
        rendered = prompts.render("dcore_review", {"paths": "scripts/"})
        self.assertIn("scripts/", rendered["messages"][0]["content"]["text"])


if __name__ == "__main__":
    unittest.main()
