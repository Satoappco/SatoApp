"""Facebook Ads MCP client."""

from typing import List, Any
import os
from .base import BaseMCPClient, MCPTool


class FacebookMCPClient(BaseMCPClient):
    """MCP client for Facebook Ads data."""

    def __init__(self, access_token: str = None):
        """Initialize Facebook Ads MCP client.

        Args:
            access_token: Facebook access token for the user
        """
        server_path = os.getenv(
            "FACEBOOK_MCP_SERVER_PATH",
            "npx"  # Default to npx if server path not specified
        )
        super().__init__(server_path)
        self.access_token = access_token

    def get_server_command(self) -> List[str]:
        """Get the command to start the Facebook Ads MCP server."""
        # This is a placeholder - actual command depends on the MCP server implementation
        # Example: ["node", "/path/to/facebook-ads-mcp-server/index.js"]
        # or: ["npx", "@modelcontextprotocol/server-facebook-ads"]

        if self.server_path == "npx":
            return ["npx", "-y", "@modelcontextprotocol/server-facebook-ads"]
        else:
            return ["node", self.server_path]

    def get_env_vars(self) -> dict:
        """Get environment variables including Facebook access token."""
        env = os.environ.copy()
        if self.access_token:
            env["FACEBOOK_ACCESS_TOKEN"] = self.access_token
        return env

    def get_tools(self) -> List[Any]:
        """Get CrewAI-compatible tools for Facebook Ads."""

        # Define Facebook Ads tools
        tools = [
            MCPTool(
                client=self,
                tool_name="get_campaigns",
                tool_description="""Get Facebook Ads campaigns data.
                Arguments:
                - account_id: Facebook Ads account ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                - fields: List of fields to retrieve (e.g., ['name', 'impressions', 'clicks'])
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_campaign_insights",
                tool_description="""Get detailed insights for specific campaigns.
                Arguments:
                - campaign_ids: List of campaign IDs
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                - metrics: List of metrics (e.g., ['impressions', 'clicks', 'spend', 'conversions'])
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_ad_sets",
                tool_description="""Get Facebook Ads ad sets data.
                Arguments:
                - campaign_id: Campaign ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                """
            ),
            MCPTool(
                client=self,
                tool_name="get_audience_insights",
                tool_description="""Get audience demographics and behavior insights.
                Arguments:
                - account_id: Facebook Ads account ID
                - date_start: Start date (YYYY-MM-DD)
                - date_end: End date (YYYY-MM-DD)
                """
            ),
        ]

        return tools


class MockFacebookMCPClient(BaseMCPClient):
    """Mock Facebook MCP client for testing without real MCP server."""

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
                "campaigns": [
                    {
                        "id": "123456",
                        "name": "Summer Campaign 2025",
                        "impressions": 150000,
                        "clicks": 4500,
                        "spend": 2500.00,
                        "conversions": 120
                    }
                ]
            }
        }

    def get_tools(self) -> List[Any]:
        """Get mock tools."""
        return [
            MCPTool(
                client=self,
                tool_name="get_campaigns",
                tool_description="Get Facebook Ads campaigns data (MOCK)"
            ),
            MCPTool(
                client=self,
                tool_name="get_campaign_insights",
                tool_description="Get campaign insights (MOCK)"
            ),
        ]
