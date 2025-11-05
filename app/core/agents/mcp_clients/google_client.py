"""Google Analytics MCP client."""

from typing import List, Any
import os
from .base import BaseMCPClient, MCPTool


class GoogleMCPClient(BaseMCPClient):
    """MCP client for Google Analytics data."""

    def __init__(self, google_ads_token: str = None, google_analytics_token: str = None):
        """Initialize Google Analytics MCP client.

        Args:
            google_ads_token: Google Ads OAuth token for the user
            google_analytics_token: Google Analytics OAuth token for the user
        """
        server_path = os.getenv(
            "GOOGLE_MCP_SERVER_PATH",
            "npx"  # Default to npx if server path not specified
        )
        super().__init__(server_path)
        self.google_ads_token = google_ads_token
        self.google_analytics_token = google_analytics_token

    def get_server_command(self) -> List[str]:
        """Get the command to start the Google Analytics MCP server."""
        # This is a placeholder - actual command depends on the MCP server implementation
        # Example: ["node", "/path/to/google-analytics-mcp-server/index.js"]
        # or: ["npx", "@modelcontextprotocol/server-google-analytics"]

        if self.server_path == "npx":
            return ["npx", "-y", "@modelcontextprotocol/server-google-analytics"]
        else:
            return ["node", self.server_path]

    def get_env_vars(self) -> dict:
        """Get environment variables including Google access tokens."""
        env = os.environ.copy()
        if self.google_ads_token:
            env["GOOGLE_ADS_ACCESS_TOKEN"] = self.google_ads_token
        if self.google_analytics_token:
            env["GOOGLE_ANALYTICS_ACCESS_TOKEN"] = self.google_analytics_token
        return env

    def get_tools(self) -> List[Any]:
        """Get CrewAI-compatible tools for Google Analytics."""

        # Define Google Analytics tools
        tools = [
            MCPTool(
                client=self,
                tool_name="get_analytics_report",
                tool_description="""Get Google Analytics data report.
                Arguments:
                - property_id: GA4 property ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                - metrics: List of metrics (e.g., ['sessions', 'users', 'bounceRate'])
                - dimensions: List of dimensions (e.g., ['date', 'source', 'medium'])
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_traffic_sources",
                tool_description="""Get traffic sources breakdown.
                Arguments:
                - property_id: GA4 property ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_conversion_funnel",
                tool_description="""Get conversion funnel data.
                Arguments:
                - property_id: GA4 property ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                - funnel_name: Name of the conversion funnel
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_user_demographics",
                tool_description="""Get user demographics data.
                Arguments:
                - property_id: GA4 property ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_page_performance",
                tool_description="""Get page-level performance data.
                Arguments:
                - property_id: GA4 property ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                """
            ),
        ]

        return tools


class MockGoogleMCPClient(BaseMCPClient):
    """Mock Google Analytics MCP client for testing without real MCP server."""

    def __init__(self):
        """Initialize mock client."""
        # Don't call super().__init__() to avoid requiring server path
        self.server_path = "mock"
        self.server_args = []
        self.session = None

    def get_server_command(self) -> List[str]:
        """Return mock command."""
        return ["echo", "mock"]

    async def connect(self):
        """Mock connect - does nothing."""
        pass

    async def disconnect(self):
        """Mock disconnect - does nothing."""
        pass

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Return mock data."""
        return {
            "success": True,
            "data": {
                "sessions": 45000,
                "users": 32000,
                "bounce_rate": 42.5,
                "conversions": 890,
                "conversion_rate": 1.98,
                "traffic_sources": {
                    "organic": 18000,
                    "direct": 12000,
                    "paid": 10000,
                    "social": 5000
                }
            }
        }

    def get_tools(self) -> List[Any]:
        """Get mock tools."""
        return [
            MCPTool(
                client=self,
                tool_name="get_analytics_report",
                tool_description="Get Google Analytics report (MOCK)"
            ),
            MCPTool(
                client=self,
                tool_name="get_traffic_sources",
                tool_description="Get traffic sources (MOCK)"
            ),
        ]
