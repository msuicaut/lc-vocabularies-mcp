"""Command-line entry point for lc-vocabularies-mcp."""

import sys


def main():
    """Start the LC Vocabularies MCP server."""
    from lc_vocabularies_mcp.server import start_mcp_server

    port = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    start_mcp_server(port=port)


if __name__ == "__main__":
    main()
