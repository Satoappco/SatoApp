"""MCP Server Registry and Selection System.

This module maintains a registry of all available MCP servers and provides
a configuration system to select which servers to load.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum
import logging
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)

# Get the absolute path to the local MCPs directory
# This allows us to use local MCP servers instead of external packages
MCPS_DIR = Path(__file__).parent.parent.parent.parent / "mcps"


class MCPServer(str, Enum):
    """Available MCP servers."""
    # Google Analytics
    GOOGLE_ANALYTICS_OAUTH = "google-analytics-oauth"  # OAuth2-compatible wrapper (RECOMMENDED)
    GOOGLE_ANALYTICS_OFFICIAL = "google-analytics-mcp"  # Official from Google (requires service account)
    GOOGLE_ANALYTICS_SURENDRANB = "surendranb-google-analytics-mcp"  # Alternative with optimizations
    GOOGLE_ANALYTICS_OLD = "mcp_google_analytics-0.0.3"  # Older version

    # Google Ads
    GOOGLE_ADS_OFFICIAL = "google-ads-mcp"  # Official from Google
    GOOGLE_ADS_COHNEN = "mcp-google-ads"  # Alternative by cohnen
    GOOGLE_ADS_ALT = "google_ads_mcp"  # Another alternative
    GOOGLE_ADS_SERVER = "google-ads-mcp-server"  # Server variant

    # Facebook/Meta Ads
    META_ADS = "meta-ads-mcp"  # Pipeboard Meta Ads MCP
    FACEBOOK_ADS_SERVER = "facebook-ads-mcp-server"  # Alternative
    FACEBOOK_ADS_LIBRARY = "facebook-ads-library-mcp"  # Ads Library API


class MCPServerConfig:
    """Configuration for individual MCP servers."""

    # Registry of all MCP servers with their configurations
    REGISTRY: Dict[MCPServer, Dict[str, Any]] = {
        # === GOOGLE ANALYTICS SERVERS ===
        MCPServer.GOOGLE_ANALYTICS_OAUTH: {
            "name": "Google Analytics (OAuth2)",
            "description": "OAuth2-compatible Google Analytics MCP server (uses refresh tokens)",
            "command": sys.executable,  # Use current Python interpreter
            "args": [str(MCPS_DIR / "google-analytics-oauth" / "ga4_oauth_server.py")],
            "service": "google_analytics",
            "working_directory": str(MCPS_DIR / "google-analytics-oauth"),
            "requires_credentials": ["refresh_token", "property_id", "client_id", "client_secret"],
            "env_mapping": {
                "refresh_token": "GOOGLE_ANALYTICS_REFRESH_TOKEN",
                "property_id": "GOOGLE_ANALYTICS_PROPERTY_ID",
                "client_id": "GOOGLE_ANALYTICS_CLIENT_ID",
                "client_secret": "GOOGLE_ANALYTICS_CLIENT_SECRET",
            }
        },

        MCPServer.GOOGLE_ANALYTICS_OFFICIAL: {
            "name": "Google Analytics (Official - Service Account)",
            "description": "Official Google Analytics MCP server (requires service account ADC)",
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "analytics_mcp.server"],  # Run the module
            "service": "google_analytics",
            "working_directory": str(MCPS_DIR / "google-analytics-mcp"),
            "requires_credentials": [],  # Uses ADC, not our credentials
            "env_mapping": {}
        },

        MCPServer.GOOGLE_ANALYTICS_SURENDRANB: {
            "name": "Google Analytics (Optimized)",
            "description": "GA4 MCP with smart optimizations by Surendran B from local mcps directory",
            "command": sys.executable,  # Use current Python interpreter
            "args": [str(MCPS_DIR / "surendranb-google-analytics-mcp" / "ga4_mcp_server.py")],
            "service": "google_analytics",
            "requires_credentials": ["refresh_token", "property_id"],
            "env_mapping": {
                "refresh_token": "GOOGLE_ANALYTICS_REFRESH_TOKEN",
                "property_id": "GOOGLE_ANALYTICS_PROPERTY_ID",
            }
        },

        # === GOOGLE ADS SERVERS ===
        MCPServer.GOOGLE_ADS_OFFICIAL: {
            "name": "Google Ads (Official)",
            "description": "Official Google Ads MCP server from local mcps directory",
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "ads_mcp.server"],  # Run the module
            "service": "google_ads",
            "working_directory": str(MCPS_DIR / "google_ads_mcp"),
            "requires_credentials": ["refresh_token", "developer_token", "client_id", "client_secret"],
            "env_mapping": {
                "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
                "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
                "client_id": "GOOGLE_ADS_CLIENT_ID",
                "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
                "customer_id": "GOOGLE_ADS_CUSTOMER_ID",
                "login_customer_id": "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
            }
        },

        MCPServer.GOOGLE_ADS_COHNEN: {
            "name": "Google Ads (Cohnen)",
            "description": "Alternative Google Ads MCP by Ernesto Cohnen from local mcps directory",
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "mcp_google_ads.server"],  # Run the module
            "service": "google_ads",
            "working_directory": str(MCPS_DIR / "mcp-google-ads"),
            "requires_credentials": ["refresh_token", "developer_token"],
            "env_mapping": {
                "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
                "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
            }
        },

        # === META/FACEBOOK ADS SERVERS ===
        MCPServer.META_ADS: {
            "name": "Meta Ads (Pipeboard)",
            "description": "Meta/Facebook Ads MCP by Pipeboard from local mcps directory",
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "meta_ads_mcp"],  # Run the module
            "service": "meta_ads",
            "working_directory": str(MCPS_DIR / "meta-ads-mcp"),
            "requires_credentials": ["access_token"],
            "env_mapping": {
                "access_token": "FACEBOOK_ACCESS_TOKEN",
                "app_id": "FACEBOOK_APP_ID",
                "app_secret": "FACEBOOK_APP_SECRET",
                "ad_account_id": "FACEBOOK_AD_ACCOUNT_ID",
            }
        },
    }

    # Default MCP selection (which servers to load by default)
    DEFAULT_SELECTION = {
        "google_analytics": MCPServer.GOOGLE_ANALYTICS_OAUTH,  # Use OAuth2 version by default
        "google_ads": MCPServer.GOOGLE_ADS_OFFICIAL,
        "meta_ads": MCPServer.META_ADS,
    }


class MCPSelector:
    """Selects and configures MCP servers based on user preferences."""

    @staticmethod
    def get_selected_servers(
        services: List[str],
        custom_selection: Optional[Dict[str, MCPServer]] = None
    ) -> List[MCPServer]:
        """Get list of MCP servers to load based on services and preferences.

        Args:
            services: List of services needed (e.g., ["google_analytics", "google_ads"])
            custom_selection: Custom server selection per service (overrides defaults)

        Returns:
            List of MCPServer enums to load
        """
        selection = custom_selection or MCPServerConfig.DEFAULT_SELECTION
        servers_to_load = []

        for service in services:
            if service in selection:
                servers_to_load.append(selection[service])
                logger.info(f"📋 Selected {selection[service].value} for {service}")
            else:
                logger.warning(f"⚠️  No MCP server configured for service: {service}")

        return servers_to_load

    @staticmethod
    def build_server_params(
        server: MCPServer,
        credentials: Dict[str, str]
    ) -> StdioServerParameters:
        """Build server parameters for MCPServerAdapter.

        Args:
            server: MCP server to configure
            credentials: Credentials for the service

        Returns:
            StdioServerParameters object for MCPServerAdapter
        """
        config = MCPServerConfig.REGISTRY.get(server)
        if not config:
            raise ValueError(f"Unknown MCP server: {server}")

        # Build environment variables from credentials
        env_vars = {}
        for cred_key, env_key in config["env_mapping"].items():
            if cred_key in credentials and credentials[cred_key]:
                env_vars[env_key] = str(credentials[cred_key])

        # Add working directory to PYTHONPATH if specified
        # This allows Python modules to be imported from the local MCP directory
        if "working_directory" in config:
            working_dir = config["working_directory"]
            current_pythonpath = os.environ.get("PYTHONPATH", "")
            if current_pythonpath:
                env_vars["PYTHONPATH"] = f"{working_dir}:{current_pythonpath}"
            else:
                env_vars["PYTHONPATH"] = working_dir

        # Check if required credentials are present
        missing_creds = []
        for required_cred in config["requires_credentials"]:
            env_key = config["env_mapping"].get(required_cred)
            if env_key and env_key not in env_vars:
                # Check if it's in environment variables as fallback
                if not os.getenv(env_key):
                    missing_creds.append(required_cred)

        if missing_creds:
            logger.warning(f"⚠️  {server.value} missing credentials: {missing_creds}")

        # Build server parameters using StdioServerParameters
        # This is the correct format for mcpadapt library when using stdio transport
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=env_vars,
            cwd=config.get("working_directory")  # Set working directory if specified
        )

        return server_params

    @staticmethod
    def build_all_server_params(
        platforms: List[str],
        google_analytics_credentials: Optional[Dict[str, str]] = None,
        google_ads_credentials: Optional[Dict[str, str]] = None,
        meta_ads_credentials: Optional[Dict[str, str]] = None,
        custom_selection: Optional[Dict[str, MCPServer]] = None
    ) -> List[StdioServerParameters]:
        """Build server parameters for all selected MCP servers.

        Args:
            platforms: List of platforms (e.g., ["google", "facebook"])
            google_analytics_credentials: GA credentials
            google_ads_credentials: Google Ads credentials
            meta_ads_credentials: Meta Ads credentials
            custom_selection: Custom MCP server selection

        Returns:
            List of StdioServerParameters objects for MCPServerAdapter
        """
        # Map platforms to services
        services = []
        if "google" in platforms or "both" in platforms:
            if google_analytics_credentials:
                services.append("google_analytics")
            if google_ads_credentials:
                services.append("google_ads")

        if "facebook" in platforms or "both" in platforms:
            if meta_ads_credentials:
                services.append("meta_ads")

        # Get selected servers
        selected_servers = MCPSelector.get_selected_servers(services, custom_selection)

        # Build parameters for each server
        server_params_list = []
        for server in selected_servers:
            config = MCPServerConfig.REGISTRY[server]
            service = config["service"]

            # Get credentials for this service
            credentials = {}
            if service == "google_analytics":
                credentials = google_analytics_credentials or {}
            elif service == "google_ads":
                credentials = google_ads_credentials or {}
            elif service == "meta_ads":
                credentials = meta_ads_credentials or {}

            try:
                params = MCPSelector.build_server_params(server, credentials)
                server_params_list.append(params)
                logger.info(f"✅ Configured {server.value}")
            except Exception as e:
                logger.error(f"❌ Failed to configure {server.value}: {e}")
                continue

        logger.info(f"✅ Configured {len(server_params_list)} MCP server(s)")
        return server_params_list


# Convenience function for backwards compatibility
def configure_all_mcps(
    platforms: List[str],
    google_analytics_credentials: Optional[Dict[str, str]] = None,
    google_ads_credentials: Optional[Dict[str, str]] = None,
    meta_ads_credentials: Optional[Dict[str, str]] = None,
    custom_selection: Optional[Dict[str, MCPServer]] = None
) -> List[StdioServerParameters]:
    """Configure all MCP servers (backwards compatible API).

    This is a wrapper around MCPSelector.build_all_server_params()
    """
    return MCPSelector.build_all_server_params(
        platforms,
        google_analytics_credentials,
        google_ads_credentials,
        meta_ads_credentials,
        custom_selection
    )
