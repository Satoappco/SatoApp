#!/usr/bin/env python3
"""
MCP Validation Script

This script validates that MCP servers can be initialized and their tools loaded
without going through the full chat workflow.

Usage:
    python scripts/validate_mcp.py [--server SERVER_NAME] [--customer-id ID]

Examples:
    # Validate all MCP servers
    python scripts/validate_mcp.py

    # Validate specific server
    python scripts/validate_mcp.py --server google-analytics-mcp

    # Validate with customer credentials
    python scripts/validate_mcp.py --customer-id 1
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.agents.crew.mcp_registry import MCPSelector, MCPServer, MCPServerConfig
from app.core.agents.graph.agents import AnalyticsCrewPlaceholder
from crewai_tools import MCPServerAdapter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def print_section(text: str):
    """Print a formatted section header."""
    print(f"\n{'-'*80}")
    print(f"  {text}")
    print(f"{'-'*80}\n")


async def validate_server(server: MCPServer, credentials: dict, timeout: int = 30):
    """Validate a single MCP server.

    Args:
        server: MCP server enum
        credentials: Dictionary of credentials for the server
        timeout: Timeout in seconds for validation

    Returns:
        Tuple of (success: bool, tools_count: int, error: str)
    """
    config = MCPServerConfig.REGISTRY.get(server)
    if not config:
        return False, 0, f"Unknown server: {server}"

    print(f"🔍 Validating {config['name']}...")
    print(f"   Description: {config['description']}")
    print(f"   Service: {config['service']}")

    try:
        # Build server parameters
        server_params = MCPSelector.build_server_params(server, credentials)

        print(f"   Command: {server_params.command}")
        print(f"   Args: {server_params.args}")
        print(f"   Working Dir: {server_params.cwd}")
        print(f"   Environment vars: {list(server_params.env.keys()) if server_params.env else []}")

        # Try to initialize the server with timeout
        print(f"   Starting MCP server...")

        try:
            async with asyncio.timeout(timeout):
                with MCPServerAdapter([server_params]) as tools:
                    tool_count = len(tools)
                    print(f"   ✅ Success! Loaded {tool_count} tools")

                    if tool_count > 0:
                        print(f"   📋 Available tools:")
                        for i, tool in enumerate(tools[:5], 1):  # Show first 5 tools
                            print(f"      {i}. {tool.name}")
                        if tool_count > 5:
                            print(f"      ... and {tool_count - 5} more")

                    return True, tool_count, None

        except asyncio.TimeoutError:
            return False, 0, f"Timeout after {timeout}s"

    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ Failed: {error_msg}")
        import traceback
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return False, 0, error_msg


async def validate_all_servers(customer_id: int = None):
    """Validate all configured MCP servers."""

    print_header("MCP Server Validation")

    # Get credentials for customer or use default
    google_analytics_creds = None
    google_ads_creds = None
    meta_ads_creds = None

    if customer_id:
        print(f"📊 Fetching credentials for customer ID: {customer_id}")
        # Use the same method as AnalyticsCrew
        analytics_placeholder = AnalyticsCrewPlaceholder(llm=None)
        google_analytics_creds = analytics_placeholder._fetch_google_analytics_token(customer_id)

        if google_analytics_creds:
            print(f"   ✅ Found Google Analytics credentials")
            print(f"      Property ID: {google_analytics_creds.get('property_id')}")
        else:
            print(f"   ⚠️  No Google Analytics credentials found")
    else:
        print("ℹ️  No customer ID provided, using environment variables")
        print("   To test with customer credentials, use --customer-id flag")

    # Test each service
    results = {}

    print_section("Testing Google Analytics MCP Servers")

    for server in [MCPServer.GOOGLE_ANALYTICS_OFFICIAL, MCPServer.GOOGLE_ANALYTICS_SURENDRANB]:
        if google_analytics_creds:
            success, tools, error = await validate_server(server, google_analytics_creds)
        else:
            success, tools, error = await validate_server(server, {})

        results[server.value] = {
            "success": success,
            "tools": tools,
            "error": error
        }

    # Google Ads (skip if no credentials)
    if google_ads_creds:
        print_section("Testing Google Ads MCP Servers")
        for server in [MCPServer.GOOGLE_ADS_OFFICIAL]:
            success, tools, error = await validate_server(server, google_ads_creds)
            results[server.value] = {
                "success": success,
                "tools": tools,
                "error": error
            }

    # Meta Ads (skip if no credentials)
    if meta_ads_creds:
        print_section("Testing Meta Ads MCP Servers")
        success, tools, error = await validate_server(MCPServer.META_ADS, meta_ads_creds)
        results[MCPServer.META_ADS.value] = {
            "success": success,
            "tools": tools,
            "error": error
        }

    # Print summary
    print_header("Validation Summary")

    total = len(results)
    passed = sum(1 for r in results.values() if r["success"])
    failed = total - passed

    print(f"Total Servers: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if passed > 0:
        print(f"\n✅ Successful Validations:")
        for server, result in results.items():
            if result["success"]:
                print(f"   • {server}: {result['tools']} tools")

    if failed > 0:
        print(f"\n❌ Failed Validations:")
        for server, result in results.items():
            if not result["success"]:
                print(f"   • {server}: {result['error']}")

    print()

    # Return exit code
    return 0 if failed == 0 else 1


async def validate_single_server(server_name: str, customer_id: int = None):
    """Validate a single MCP server."""

    print_header(f"MCP Server Validation: {server_name}")

    # Find server enum
    server_enum = None
    for server in MCPServer:
        if server.value == server_name:
            server_enum = server
            break

    if not server_enum:
        print(f"❌ Unknown server: {server_name}")
        print(f"\nAvailable servers:")
        for server in MCPServer:
            print(f"   • {server.value}")
        return 1

    # Get credentials
    config = MCPServerConfig.REGISTRY.get(server_enum)
    service = config["service"]

    credentials = {}

    if customer_id and service == "google_analytics":
        analytics_placeholder = AnalyticsCrewPlaceholder(llm=None)
        credentials = analytics_placeholder._fetch_google_analytics_token(customer_id) or {}

    # Validate
    success, tools, error = await validate_server(server_enum, credentials)

    print_header("Result")

    if success:
        print(f"✅ Validation PASSED")
        print(f"   Tools loaded: {tools}")
        return 0
    else:
        print(f"❌ Validation FAILED")
        print(f"   Error: {error}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate MCP server configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all servers
  python scripts/validate_mcp.py

  # Validate specific server
  python scripts/validate_mcp.py --server google-analytics-mcp

  # Validate with customer credentials
  python scripts/validate_mcp.py --customer-id 1

  # List available servers
  python scripts/validate_mcp.py --list
        """
    )

    parser.add_argument(
        "--server",
        "-s",
        help="Validate specific server (e.g., google-analytics-mcp)"
    )

    parser.add_argument(
        "--customer-id",
        "-c",
        type=int,
        help="Customer ID to fetch credentials from database"
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available MCP servers"
    )

    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=30,
        help="Timeout in seconds for each server (default: 30)"
    )

    args = parser.parse_args()

    # List servers
    if args.list:
        print_header("Available MCP Servers")
        for server in MCPServer:
            config = MCPServerConfig.REGISTRY.get(server)
            print(f"• {server.value}")
            print(f"  Name: {config['name']}")
            print(f"  Service: {config['service']}")
            print(f"  Description: {config['description']}")
            print()
        return 0

    # Validate specific server or all servers
    if args.server:
        exit_code = asyncio.run(validate_single_server(args.server, args.customer_id))
    else:
        exit_code = asyncio.run(validate_all_servers(args.customer_id))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
