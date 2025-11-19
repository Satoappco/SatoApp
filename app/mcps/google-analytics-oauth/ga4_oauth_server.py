#!/usr/bin/env python3
"""
Google Analytics 4 MCP Server with OAuth2 Support

This is a wrapper around the official Google Analytics MCP that supports
OAuth2 refresh tokens instead of requiring service account credentials.

It reads credentials from environment variables:
- GOOGLE_ANALYTICS_REFRESH_TOKEN: OAuth2 refresh token
- GOOGLE_ANALYTICS_PROPERTY_ID: GA4 property ID
- GOOGLE_ANALYTICS_CLIENT_ID: OAuth2 client ID
- GOOGLE_ANALYTICS_CLIENT_SECRET: OAuth2 client secret

Based on google-analytics-mcp but modified to use OAuth2 credentials.
"""

import os
import sys
from typing import Any, Dict, List
from google.analytics import admin_v1beta, data_v1beta
from google.api_core.gapic_v1.client_info import ClientInfo
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import proto

# Try to import from analytics_mcp if available (for tools definitions)
try:
    # Add the official GA MCP to path
    import pathlib
    ga_mcp_path = pathlib.Path(__file__).parent.parent / "google-analytics-mcp"
    if str(ga_mcp_path) not in sys.path:
        sys.path.insert(0, str(ga_mcp_path))

    from analytics_mcp.coordinator import mcp
    from analytics_mcp.tools.utils import proto_to_dict, construct_property_rn
except ImportError:
    # Fallback: create our own basic MCP setup
    from fastmcp import FastMCP
    mcp = FastMCP("Google Analytics 4 (OAuth2)")

    def proto_to_dict(obj: proto.Message) -> Dict[str, Any]:
        """Converts a proto message to a dictionary."""
        return type(obj).to_dict(
            obj, use_integers_for_enums=False, preserving_proto_field_name=True
        )

    def construct_property_rn(property_value: int | str) -> str:
        """Returns a property resource name in the format required by APIs."""
        property_num = None
        if isinstance(property_value, int):
            property_num = property_value
        elif isinstance(property_value, str):
            property_value = property_value.strip()
            if property_value.isdigit():
                property_num = int(property_value)
            elif property_value.startswith("properties/"):
                numeric_part = property_value.split("/")[-1]
                if numeric_part.isdigit():
                    property_num = int(numeric_part)
        if property_num is None:
            raise ValueError(
                f"Invalid property ID: {property_value}. "
                "A valid property value is either a number or a string starting "
                "with 'properties/' and followed by a number."
            )
        return f"properties/{property_num}"


# Configuration from environment variables
REFRESH_TOKEN = os.getenv("GOOGLE_ANALYTICS_REFRESH_TOKEN")
PROPERTY_ID = os.getenv("GOOGLE_ANALYTICS_PROPERTY_ID")
CLIENT_ID = os.getenv("GOOGLE_ANALYTICS_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_ANALYTICS_CLIENT_SECRET")

# Read-only scope for Analytics
_READ_ONLY_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

# Client info for user agent
_CLIENT_INFO = ClientInfo(user_agent="google-analytics-oauth-mcp/1.0.0")


def _create_oauth_credentials() -> Credentials:
    """Create OAuth2 credentials from refresh token.

    Returns:
        Google OAuth2 Credentials object

    Raises:
        ValueError: If required environment variables are missing
    """
    if not REFRESH_TOKEN:
        raise ValueError(
            "GOOGLE_ANALYTICS_REFRESH_TOKEN environment variable not set. "
            "Please provide an OAuth2 refresh token."
        )

    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError(
            "GOOGLE_ANALYTICS_CLIENT_ID and GOOGLE_ANALYTICS_CLIENT_SECRET "
            "environment variables must be set."
        )

    # Create credentials from refresh token
    credentials = Credentials(
        token=None,  # Will be fetched using refresh token
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=[_READ_ONLY_ANALYTICS_SCOPE]
    )

    # Refresh to get access token
    credentials.refresh(Request())

    return credentials


def create_admin_api_client() -> admin_v1beta.AnalyticsAdminServiceAsyncClient:
    """Returns a Google Analytics Admin API async client with OAuth2 credentials."""
    return admin_v1beta.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_oauth_credentials()
    )


def create_data_api_client() -> data_v1beta.BetaAnalyticsDataAsyncClient:
    """Returns a Google Analytics Data API async client with OAuth2 credentials."""
    return data_v1beta.BetaAnalyticsDataAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_oauth_credentials()
    )


# Tool definitions
@mcp.tool()
async def get_account_summaries() -> List[Dict[str, Any]]:
    """Retrieves information about the user's Google Analytics accounts and properties."""
    summary_pager = await create_admin_api_client().list_account_summaries()
    all_pages = [proto_to_dict(summary_page) async for summary_page in summary_pager]
    return all_pages


@mcp.tool(title="Gets details about a property")
async def get_property_details(property_id: int | str = None) -> Dict[str, Any]:
    """Returns details about a property.

    Args:
        property_id: The GA4 property ID. Uses GOOGLE_ANALYTICS_PROPERTY_ID env var if not specified.
    """
    prop_id = property_id or PROPERTY_ID
    if not prop_id:
        raise ValueError("property_id not specified and GOOGLE_ANALYTICS_PROPERTY_ID not set")

    client = create_admin_api_client()
    request = admin_v1beta.GetPropertyRequest(name=construct_property_rn(prop_id))
    response = await client.get_property(request=request)
    return proto_to_dict(response)


@mcp.tool(title="Run a Google Analytics report")
async def run_report(
    property_id: int | str = None,
    dimensions: List[str] = None,
    metrics: List[str] = None,
    date_range_start: str = "30daysAgo",
    date_range_end: str = "today",
    limit: int = 10
) -> Dict[str, Any]:
    """Run a Google Analytics 4 report.

    Args:
        property_id: GA4 property ID (uses env var if not specified)
        dimensions: List of dimension names (e.g., ["date", "city"])
        metrics: List of metric names (e.g., ["activeUsers", "sessions"])
        date_range_start: Start date (e.g., "2024-01-01", "7daysAgo", "today")
        date_range_end: End date
        limit: Maximum number of rows to return

    Returns:
        Dictionary containing the report data
    """
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest
    )

    prop_id = property_id or PROPERTY_ID
    if not prop_id:
        raise ValueError("property_id not specified and GOOGLE_ANALYTICS_PROPERTY_ID not set")

    # Build request
    request = RunReportRequest(
        property=construct_property_rn(prop_id),
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        metrics=[Metric(name=m) for m in (metrics or ["activeUsers"])],
        date_ranges=[DateRange(start_date=date_range_start, end_date=date_range_end)],
        limit=limit
    )

    # Execute request
    client = create_data_api_client()
    response = await client.run_report(request=request)

    return proto_to_dict(response)


def main():
    """Main entry point for the MCP server."""
    # Validate environment variables
    if not REFRESH_TOKEN:
        print(
            "Error: GOOGLE_ANALYTICS_REFRESH_TOKEN environment variable not set",
            file=sys.stderr
        )
        sys.exit(1)

    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "Error: GOOGLE_ANALYTICS_CLIENT_ID and GOOGLE_ANALYTICS_CLIENT_SECRET "
            "environment variables must be set",
            file=sys.stderr
        )
        sys.exit(1)

    if not PROPERTY_ID:
        print(
            "Warning: GOOGLE_ANALYTICS_PROPERTY_ID not set. "
            "You'll need to specify property_id in tool calls.",
            file=sys.stderr
        )

    print(f"Starting Google Analytics MCP server with OAuth2...", file=sys.stderr)
    print(f"Property ID: {PROPERTY_ID or '(not set)'}", file=sys.stderr)

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
