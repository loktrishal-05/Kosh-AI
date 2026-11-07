"""Minimal MCP (JSON-RPC 2.0) server: tools/list, tools/call, resources/templates/list, resources/read, over stdio.
ponytail: hand-rolled subset of the MCP spec (no SSE/subscribe/prompts) to avoid a dependency; swap in the official `mcp` SDK when needed.
Air-gap: a tool whose name could file a return, reject an IMS invoice or approve/OTP anything cannot be registered at all."""
import inspect
import json
import re
import sys
from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

FORBIDDEN = re.compile(r"retfile|ims_reject|reject|authori[sz]e|otp|(^|_)file(_|$)|submit_return|sign_approval")
_JSON_TYPE = {int: "integer", bool: "boolean", dict: "object", list: "array"}


class ToolError(Exception):
    """Business-rule refusal; surfaced to the client as isError, never as a protocol crash."""


class Server:
    def __init__(self, name: str):
        self.name, self.tools, self.resources = name, {}, []

    def tool(self, fn=None, *, hitl: bool = False):
        def reg(f):
            if FORBIDDEN.search(f.__name__):
                raise ValueError(f"{f.__name__}: filing/approval tools must never be exposed to agents (FR-025)")
            props, req = {}, []
            for p in inspect.signature(f).parameters.values():
                if p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
                    continue
                props[p.name] = {"type": _JSON_TYPE.get(p.annotation, "string")}
                if p.default is inspect.Parameter.empty:
                    req.append(p.name)
            self.tools[f.__name__] = (f, {"name": f.__name__, "description": (f.__doc__ or "").strip(),
                                          "inputSchema": {"type": "object", "properties": props, "required": req},
                                          "annotations": {"hitlRequired": hitl}})
            return f
        return reg(fn) if fn else reg

    def resource(self, template: str):
        rx = re.compile("^" + re.sub(r"\\{(\w+)\\}", r"(?P<\1>[^/?]+)", re.escape(template)) + "$")
        return lambda f: (self.resources.append((template, rx, f)), f)[1]

    def call(self, name: str, args: dict | None = None):
        if name not in self.tools:
            raise ToolError(f"unknown tool {name}")
        try:
            return self.tools[name][0](**(args or {}))
        except TypeError as e:
            raise ToolError(f"bad arguments: {e}") from e

    def read(self, uri: str):
        u = urlsplit(uri)
        base = f"{u.scheme}://{u.netloc}{u.path}"
        for _, rx, f in self.resources:
            if m := rx.match(base):
                return f(**m.groupdict(), **dict(parse_qsl(u.query)))
        raise ToolError(f"no resource for {uri}")

    def handle(self, req: dict):
        m, p, rid = req.get("method"), req.get("params") or {}, req.get("id")
        ok = lambda r: {"jsonrpc": "2.0", "id": rid, "result": r}
        try:
            if m == "initialize":
                return ok({"protocolVersion": "2025-03-26", "serverInfo": {"name": self.name, "version": "0.1.0"},
                           "capabilities": {"tools": {}, "resources": {}}})
            if m == "tools/list":
                return ok({"tools": [t for _, t in self.tools.values()]})
            if m == "resources/templates/list":
                return ok({"resourceTemplates": [{"uriTemplate": t, "name": t} for t, _, _ in self.resources]})
            if m == "tools/call":
                try:
                    out = self.call(p.get("name"), p.get("arguments"))
                except ToolError as e:
                    return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
                return ok({"content": [{"type": "text", "text": dumps(out)}], "structuredContent": json.loads(dumps(out))})
            if m == "resources/read":
                return ok({"contents": [{"uri": p.get("uri"), "mimeType": "application/json", "text": dumps(self.read(p["uri"]))}]})
        except ToolError as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}
        if rid is None:                       # notification, no reply
            return None
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {m}"}}

    def serve_stdio(self):
        for line in sys.stdin:
            if line.strip() and (r := self.handle(json.loads(line))):
                sys.stdout.write(json.dumps(r) + "\n")
                sys.stdout.flush()


def dumps(x) -> str:
    return json.dumps(x, default=lambda o: format(o, "f") if isinstance(o, Decimal) else str(o))   # money stays exact strings
