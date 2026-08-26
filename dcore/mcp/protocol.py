"""JSON-RPC 2.0 over stdio, which is all the MCP stdio transport is.

dCore ships with `dependencies = []` and is expected to run from a Custom GPT
Knowledge zip, a CI runner and a developer machine without an install step. An
SDK dependency for the agent surface would be the only thing standing between a
fresh Python 3.12 and a working server, so the transport is implemented here.

The transport is deliberately dumb: newline-delimited JSON in, newline-delimited
JSON out. Framing with Content-Length headers belongs to LSP, not MCP.

The loop never dies on bad input. A malformed line answers with a parse error and
keeps serving, because an editor that sends one broken frame should not lose its
session.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Protocol, TextIO

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    """An error that maps onto a JSON-RPC error object rather than a traceback."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


class Handler(Protocol):
    def __call__(self, params: dict[str, Any]) -> Any: ...


@dataclass
class Request:
    method: str
    params: dict[str, Any]
    id: Any = None
    is_notification: bool = False


def parse_message(line: str) -> Request:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as error:
        raise JsonRpcError(PARSE_ERROR, "invalid JSON", str(error)) from error
    if not isinstance(message, dict):
        raise JsonRpcError(INVALID_REQUEST, "message must be a JSON object")
    method = message.get("method")
    if not isinstance(method, str):
        raise JsonRpcError(INVALID_REQUEST, "message has no method")
    params = message.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        # MCP never uses positional params, so a list here is a client bug worth
        # reporting instead of silently coercing.
        raise JsonRpcError(INVALID_PARAMS, "params must be an object")
    return Request(method, params, message.get("id"), "id" not in message)


class Dispatcher:
    """Maps method names onto handlers and turns exceptions into JSON-RPC errors."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def method(self, name: str) -> Callable[[Handler], Handler]:
        def register(handler: Handler) -> Handler:
            self._handlers[name] = handler
            return handler

        return register

    def known(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def handle(self, request: Request) -> dict[str, Any] | None:
        """Return the response, or None for a notification."""
        handler = self._handlers.get(request.method)
        if handler is None:
            if request.is_notification:
                # Unknown notifications are ignored by design; the spec allows a
                # client to announce things a server never opted into.
                return None
            raise JsonRpcError(METHOD_NOT_FOUND, f"unknown method: {request.method}")
        result = handler(request.params)
        if request.is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request.id, "result": result if result is not None else {}}


def error_response(request_id: Any, error: JsonRpcError) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": error.payload()}


def read_messages(stream: TextIO) -> Iterator[str]:
    for line in stream:
        text = line.strip()
        if text:
            yield text


def serve(
    dispatcher: Dispatcher,
    source: TextIO | None = None,
    sink: TextIO | None = None,
) -> int:
    """Run the stdio loop until the input stream closes."""
    source = source if source is not None else sys.stdin
    sink = sink if sink is not None else sys.stdout
    for line in read_messages(source):
        request_id: Any = None
        try:
            request = parse_message(line)
            request_id = request.id
            response = dispatcher.handle(request)
        except JsonRpcError as error:
            response = error_response(request_id, error)
        except Exception as error:  # noqa: BLE001 - a tool bug must not kill the session
            response = error_response(
                request_id, JsonRpcError(INTERNAL_ERROR, type(error).__name__, str(error))
            )
        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False) + "\n")
            sink.flush()
    return 0
