"""Main entry point for Wins Finder MCP server."""

import sys
import logging
import os

# MCP servers should log to stderr - it's captured by Claude Desktop
# Only stdout must be kept clean for JSON-RPC protocol

# Configure basic logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr
)

# Import server
from wins_finder.mcp.server import mcp

def main():
    """Main entry point for console script and uvx."""
    logger = logging.getLogger(__name__)
    logger.info("Starting Wins Finder MCP Server")
    
    try:
        logger.info("About to call mcp.run()")
        mcp.run(show_banner=False)
        logger.info("mcp.run() completed normally")
    except KeyboardInterrupt:
        logger.info("MCP Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"MCP Server error: {str(e)}", exc_info=True)
        sys.exit(1)
    
    logger.info("Main function exiting")

if __name__ == "__main__":
    main()