from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
import uvicorn

from dial_mcp.call_manager import CallManager
from dial_mcp.config import load_config
from dial_mcp.server import create_mcp_server

logger = logging.getLogger("dial-mcp")


def find_config_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path

    candidates = [
        Path("config.yaml"),
        Path("config.yml"),
        Path.home() / ".dial-mcp" / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    print("Error: No config file found. Create config.yaml or pass --config <path>")
    print("See config.example.yaml for the expected format.")
    sys.exit(1)


async def run_sse_server(host: str, port: int, config_path: str) -> None:
    config = load_config(config_path)
    call_manager = CallManager()
    mcp_server = create_mcp_server(config, call_manager)

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as (
            read_stream,
            write_stream,
        ):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    server_config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(server_config)
    await server.serve()


async def run_stdio_server(config_path: str) -> None:
    from mcp.server.stdio import stdio_server

    config = load_config(config_path)
    call_manager = CallManager()
    mcp_server = create_mcp_server(config, call_manager)

    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP server that gives AI agents phone call capabilities",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Interactive setup — creates config.yaml")
    init_parser.add_argument("-o", "--output", default="config.yaml", help="Output path (default: config.yaml)")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config.yaml")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Run as HTTP/SSE server")
    serve_parser.add_argument("--config", help="Path to config.yaml")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")

    # Default: stdio mode (backwards compatible)
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--serve", action="store_true", help="(deprecated) Use 'serve' subcommand instead")
    parser.add_argument("--host", default="0.0.0.0", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8080, help=argparse.SUPPRESS)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.command == "init":
        from dial_mcp.init import run_init
        run_init(output_path=args.output, force=args.force)
        return

    if args.command == "serve" or getattr(args, "serve", False):
        config_path = find_config_path(getattr(args, "config", None))
        host = getattr(args, "host", "0.0.0.0")
        port = getattr(args, "port", 8080)
        logger.info(f"Using config: {config_path}")
        logger.info(f"Starting SSE server on {host}:{port}")
        asyncio.run(run_sse_server(host, port, config_path))
    else:
        config_path = find_config_path(args.config)
        logger.info(f"Using config: {config_path}")
        asyncio.run(run_stdio_server(config_path))
