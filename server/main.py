#!/usr/bin/env python3
"""Small stdio MCP server and JSON CLI. Python 3.10+, standard library only."""
import argparse
import json
import sys
from pathlib import Path

from router import Router, RouterError, VERSION

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "route-input.json").read_text())
ROUTER = Router()
TOOLS = [
    {"name": "router_status", "description": "Check decision router setup without revealing keys or making API calls.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "preview_routing", "description": "Validate task dependencies and inspect the exact decision payload without API calls. Does not choose models.",
     "inputSchema": SCHEMA, "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "route_tasks", "description": "Choose native Codex subagent model/effort profiles using Drex Max, with one Jev 1.14 backup attempt for failed or uncertain decisions. Sends supplied task summaries through separately billed OpenRouter. Returns a dependency-aware plan for the host to execute through native collaboration tools.",
     "inputSchema": SCHEMA,
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}},
]


def call(name, args):
    if name == "router_status":
        if args != {}:
            raise RouterError("router_status accepts no arguments")
        return ROUTER.status()
    if name == "preview_routing":
        return ROUTER.preview(args)
    if name == "route_tasks":
        return ROUTER.route(args)
    raise RouterError("Unknown tool")


def reply(req):
    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in req:
        return None
    result = {"jsonrpc": "2.0", "id": req["id"]}
    method, params = req["method"], req.get("params", {})
    if not isinstance(params, dict):
        return dict(result, error={"code": -32602, "message": "Invalid params"})
    if method == "initialize":
        requested = params.get("protocolVersion")
        versions = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
        value = {"protocolVersion": requested if requested in versions else versions[-1],
                 "capabilities": {"tools": {"listChanged": False}},
                 "serverInfo": {"name": "jev-codex-router", "version": VERSION}}
    elif method == "ping":
        value = {}
    elif method == "tools/list":
        value = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            data = call(params.get("name"), params.get("arguments", {}))
            value = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, allow_nan=False)}],
                     "structuredContent": data, "isError": False}
        except (RouterError, TypeError, ValueError):
            # Details are available in CLI validation. MCP must not echo unsafe arguments.
            value = {"content": [{"type": "text", "text": "Invalid router input; check the tool schema, candidates and dependency graph."}], "isError": True}
    else:
        return dict(result, error={"code": -32601, "message": "Method not found"})
    return dict(result, result=value)


def serve():
    while True:
        line = sys.stdin.buffer.readline(256001)
        if not line:
            break
        if len(line) > 256000:
            print("MCP input exceeds limit", file=sys.stderr)
            return 1
        try:
            response = reply(json.loads(line))
        except (ValueError, UnicodeError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="serve", choices=("serve", "status", "preview", "route"))
    args = parser.parse_args()
    if args.command == "serve":
        return serve()
    try:
        if args.command == "status":
            value = ROUTER.status()
        else:
            data = sys.stdin.buffer.read(256001)
            if len(data) > 256000:
                raise RouterError("Input too large")
            value = call("preview_routing" if args.command == "preview" else "route_tasks", json.loads(data))
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if value.get("status") == "fallback_plan" else 0
    except (RouterError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
