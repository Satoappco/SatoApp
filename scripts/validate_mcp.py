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
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.agents.mcp_clients.mcp_registry import (
    MCPSelector,
    MCPServer,
    MCPServerConfig,
)
from app.core.agents.graph.agents import AnalyticsCrewPlaceholder
from crewai_tools import MCPServerAdapter
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# load environment variables from ../.env file if it exists
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


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


async def validate_server(
    server: MCPServer, credentials: dict, timeout: int = 30, test_tools: bool = False
):
    """Validate a single MCP server.

    Args:
        server: MCP server enum
        credentials: Dictionary of credentials for the server
        timeout: Timeout in seconds for validation
        test_tools: Whether to actually call tools to validate credentials

    Returns:
        Tuple of (success: bool, tools_count: int, error: str)
    """
    config = MCPServerConfig.REGISTRY.get(server)
    if not config:
        return False, 0, f"Unknown server: {server}"

    print(f"🔍 Validating {config['name']}...")
    print(f"   Description: {config['description']}")
    print(f"   Service: {config['service']}")
    print(f"   Credentials: {credentials.keys() if credentials else 'None'}")

    try:
        # Build server parameters
        server_params = MCPSelector.build_server_params(server, credentials)

        print(f"   Command: {server_params.command}")
        print(f"   Args: {server_params.args}")
        print(f"   Working Dir: {server_params.cwd}")
        print(
            f"   Environment vars: {list(server_params.env.keys()) if server_params.env else []}"
        )

        # Print environment variable values for debugging
        if server_params.env:
            print(f"\n   🔐 Environment variables being set:")
            for key, value in server_params.env.items():
                print(f"      {key}: {value}")
            print()

        # Try to initialize the server with timeout
        print(f"   Starting MCP server...")

        try:
            async with asyncio.timeout(timeout):
                with MCPServerAdapter([server_params]) as tools:
                    tool_count = len(tools)
                    print(f"   ✅ Success! Loaded {tool_count} tools")
                    show_max_cnt = 10
                    if tool_count > 0:
                        print(f"   📋 Available tools:")
                        for i, tool in enumerate(
                            tools[:show_max_cnt], 1
                        ):  # Show first 5 tools
                            print(f"      {i}. {tool.name}")
                        if tool_count > show_max_cnt:
                            print(f"      ... and {tool_count - show_max_cnt} more")

                        # Test tools if requested
                        if test_tools and credentials:
                            print(f"\n   🧪 Testing tool execution with credentials...")
                            success = await test_mcp_tool(
                                tools, config["service"], credentials
                            )
                            if not success:
                                return (
                                    False,
                                    tool_count,
                                    "Tool execution failed (credentials may be invalid)",
                                )

                    return True, tool_count, None

        except asyncio.TimeoutError:
            return False, 0, f"Timeout after {timeout}s"

    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ Failed: {error_msg}")
        import traceback

        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return False, 0, error_msg


async def test_mcp_tool(tools, service: str, credentials: dict):
    """Test a tool to validate credentials work.

    Args:
        tools: List of MCP tools
        service: Service name (google_analytics, google_ads, etc.)
        credentials: Credentials dictionary

    Returns:
        bool: True if tool execution succeeded
    """
    try:
        if service == "google_analytics":
            # Try to call get_account_summaries
            account_tool = next((t for t in tools if "account" in t.name.lower()), None)
            if account_tool:
                print(f"      Calling {account_tool.name}...")
                result = account_tool._run()
                print(f"      Result: {result}")
                print(f"      ✅ Tool execution successful")
                return True
            else:
                print(f"      ⚠️  No account tool found to test")
                return True  # Don't fail if tool not found

        elif service == "google_ads":
            # Try to list accessible customers
            customer_tool = next(
                (
                    t
                    for t in tools
                    if "customer" in t.name.lower() or "accessible" in t.name.lower()
                ),
                None,
            )
            if customer_tool:
                print(f"      Calling {customer_tool.name}...")
                result = customer_tool._run()
                print(f"      Result: {result}")
                print(f"      ✅ Tool execution successful")
                return True
            else:
                print(f"      ⚠️  No customer tool found to test")
                return True

        elif service == "meta_ads":
            # Try to get account info
            account_tool = next(
                (
                    t
                    for t in tools
                    if "account" in t.name.lower() or "me" in t.name.lower()
                ),
                None,
            )
            if account_tool:
                print(f"      Calling {account_tool.name}...")
                result = account_tool._run()
                print(f"      Result: {result}")

                # Check if result contains an error
                try:
                    import json

                    result_data = (
                        json.loads(result) if isinstance(result, str) else result
                    )
                    if isinstance(result_data, dict) and "error" in result_data:
                        print(
                            f"      ❌ Tool execution failed: {result_data['error'].get('message', 'Unknown error')}"
                        )
                        return False
                except (json.JSONDecodeError, TypeError):
                    # If we can't parse the result, assume it's not an error
                    pass

                print(f"      ✅ Tool execution successful")
                return True
            else:
                print(f"      ⚠️  No account tool found to test")
                return True

        return True

    except Exception as e:
        print(f"      ❌ Tool execution failed: {str(e)}")
        return False


async def validate_all_servers(
    campaigner_id: int, customer_id: int = None, test_tools: bool = False
):
    """Validate all configured MCP servers."""

    print_header("MCP Server Validation")

    # Get credentials for customer or use default
    google_analytics_creds = None
    google_ads_creds = None
    meta_ads_creds = None

    if customer_id:
        print(
            f"📊 Fetching credentials for customer ID: {customer_id}, campaigner_id: {campaigner_id}"
        )
        # Use the same method as AnalyticsCrew
        analytics_placeholder = AnalyticsCrewPlaceholder(llm=None)
        google_analytics_creds = analytics_placeholder._fetch_google_analytics_token(
            customer_id, campaigner_id
        )
        google_ads_creds = analytics_placeholder._fetch_google_ads_token(
            customer_id, campaigner_id
        )
        meta_ads_creds = analytics_placeholder._fetch_meta_ads_token(
            customer_id, campaigner_id
        )

        if google_analytics_creds:
            print(f"   ✅ Found Google Analytics credentials")
            print(f"      Property ID: {google_analytics_creds.get('property_id')}")
            print(f"      Client ID: {google_analytics_creds.get('client_id')}")
            print(
                f"      Client Secret: {google_analytics_creds.get('client_secret')[:10]}..."
                if google_analytics_creds.get("client_secret")
                else "      Client Secret: None"
            )
            print(
                f"      Refresh Token: {google_analytics_creds.get('refresh_token')[:20]}..."
                if google_analytics_creds.get("refresh_token")
                else "      Refresh Token: None"
            )
            print(
                f"      Access Token: {google_analytics_creds.get('access_token')[:20]}..."
                if google_analytics_creds.get("access_token")
                else "      Access Token: None"
            )

            # Print full credentials for debugging (be careful with this in production!)
            print(f"\n   🔐 FULL CREDENTIALS (for debugging):")
            for key, value in google_analytics_creds.items():
                if value and isinstance(value, str) and len(value) > 50:
                    print(f"      {key}: {value[:30]}...{value[-10:]}")
                else:
                    print(f"      {key}: {value}")
        else:
            print(f"   ⚠️  No Google Analytics credentials found")

        if google_ads_creds:
            print(f"\n   ✅ Found Google Ads credentials")
            print(f"      Customer ID: {google_ads_creds.get('customer_id')}")
            print(
                f"      Developer Token: {google_ads_creds.get('developer_token')[:10]}..."
                if google_ads_creds.get("developer_token")
                else "      Developer Token: None"
            )
            print(
                f"      Refresh Token: {google_ads_creds.get('refresh_token')[:20]}..."
                if google_ads_creds.get("refresh_token")
                else "      Refresh Token: None"
            )
        else:
            print(f"   ⚠️  No Google Ads credentials found")

        if meta_ads_creds:
            print(f"\n   ✅ Found Facebook/Meta Ads credentials")
            print(f"      Ad Account ID: {meta_ads_creds.get('ad_account_id')}")
            print(
                f"      Access Token: {meta_ads_creds.get('access_token')[:20]}..."
                if meta_ads_creds.get("access_token")
                else "      Access Token: None"
            )
        else:
            print(f"   ⚠️  No Facebook/Meta Ads credentials found")
    else:
        print("ℹ️  No customer ID provided, using environment variables")
        print("   To test with customer credentials, use --customer-id flag")

    if test_tools:
        print("   🧪 Tool execution testing ENABLED")
    else:
        print("   ℹ️  Tool execution testing DISABLED (use --test-tools to enable)")

    # Test each service
    results = {}

    print_section("Testing Google Analytics MCP Servers")

    for server in [
        MCPServer.GOOGLE_ANALYTICS_OFFICIAL,
        MCPServer.GOOGLE_ANALYTICS_SURENDRANB,
    ]:
        if google_analytics_creds:
            success, tools, error = await validate_server(
                server, google_analytics_creds, test_tools=test_tools
            )
        else:
            success, tools, error = await validate_server(
                server, {}, test_tools=test_tools
            )

        results[server.value] = {"success": success, "tools": tools, "error": error}

    # Google Ads (skip if no credentials)
    if google_ads_creds:
        print_section("Testing Google Ads MCP Servers")
        for server in [MCPServer.GOOGLE_ADS_OFFICIAL]:
            success, tools, error = await validate_server(
                server, google_ads_creds, test_tools=test_tools
            )
            results[server.value] = {"success": success, "tools": tools, "error": error}

    # Meta Ads (skip if no credentials)
    if meta_ads_creds:
        print_section("Testing Meta Ads MCP Servers")
        success, tools, error = await validate_server(
            MCPServer.META_ADS, meta_ads_creds, test_tools=test_tools
        )
        results[MCPServer.META_ADS.value] = {
            "success": success,
            "tools": tools,
            "error": error,
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


async def validate_single_server(
    server_name: str,
    campaigner_id: int,
    customer_id: int = None,
    test_tools: bool = False,
):
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

    print(f"🔍 Validating server: {server_enum.value}")
    # Get credentials
    config = MCPServerConfig.REGISTRY.get(server_enum)
    service = config["service"]

    credentials = {}

    if customer_id:
        print(
            f"📊 Fetching credentials for customer ID: {customer_id}, campaigner_id: {campaigner_id}"
        )
        analytics_placeholder = AnalyticsCrewPlaceholder(llm=None)

        if service == "google_analytics":
            credentials = (
                analytics_placeholder._fetch_google_analytics_token(
                    customer_id, campaigner_id
                )
                or {}
            )
        elif service == "google_ads":
            credentials = (
                analytics_placeholder._fetch_google_ads_token(
                    customer_id, campaigner_id
                )
                or {}
            )
        elif service == "meta_ads":
            credentials = (
                analytics_placeholder._fetch_meta_ads_token(customer_id, campaigner_id)
                or {}
            )

        if credentials:
            print(f"   ✅ Found {service} credentials")
            print(f"\n   🔐 FULL CREDENTIALS (for debugging):")
            for key, value in credentials.items():
                if value and isinstance(value, str) and len(value) > 100:
                    print(f"      {key}: {value[:30]}...{value[-10:]}")
                else:
                    print(f"      {key}: {value}")
            print()
        else:
            print(f"   ⚠️  No {service} credentials found")

    # Validate
    success, tools, error = await validate_server(
        server_enum, credentials, test_tools=test_tools
    )

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
        """,
    )

    parser.add_argument(
        "--server", "-s", help="Validate specific server (e.g., google-analytics-mcp)"
    )

    parser.add_argument(
        "--customer-id",
        "-c",
        type=int,
        help="Customer ID to fetch credentials from database",
    )

    parser.add_argument(
        "--campaigner-id",
        "-i",
        type=int,
        help="Campaigner ID to fetch credentials from database",
    )

    parser.add_argument(
        "--list", "-l", action="store_true", help="List available MCP servers"
    )

    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=30,
        help="Timeout in seconds for each server (default: 30)",
    )

    parser.add_argument(
        "--test-tools",
        action="store_true",
        help="Actually call MCP tools to validate credentials work",
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
        exit_code = asyncio.run(
            validate_single_server(
                args.server, args.campaigner_id, args.customer_id, args.test_tools
            )
        )
    else:
        exit_code = asyncio.run(
            validate_all_servers(args.campaigner_id, args.customer_id, args.test_tools)
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
