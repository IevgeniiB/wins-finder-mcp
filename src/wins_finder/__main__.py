"""Main entry point for Wins Finder MCP server."""

import sys
from wins_finder.mcp.server import mcp

def main():
    """Main entry point for console script and uvx."""
    try:
        mcp.run(show_banner=False)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()