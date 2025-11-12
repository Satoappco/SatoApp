"""Google Analytics MCP Server - Connect to Google Analytics API through MCP."""

import sys
from . import server

__version__ = "0.0.1"

def main():
    """Main entry point for the package."""
    print("Starting Google Analytics MCP server...", file=sys.stderr)
    server.mcp.run()

if __name__ == "__main__":
    main()
