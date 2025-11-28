"""
Centralized MCP Client Manager

Orchestrates the complete MCP client lifecycle:
1. Token refresh (before initialization)
2. MCP client initialization
3. Tool validation (after initialization)
4. Connection cleanup

This ensures all agents use the same reliable initialization flow.
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.config.logging import get_logger
from app.core.oauth.token_refresh import refresh_tokens_for_platforms
from app.core.agents.mcp_clients.mcp_registry import MCPServer, MCPSelector
from app.core.agents.mcp_clients.mcp_validator import MCPValidator, MCPValidationResult
from app.config.database import get_session
from app.models.analytics import Connection, AssetType, DigitalAsset
from sqlmodel import select, and_

logger = get_logger(__name__)


class MCPClientManager:
    """
    Centralized manager for MCP client lifecycle.

    Handles token refresh, initialization, and validation in one place.
    All agents should use this manager instead of managing MCP clients directly.
    """

    def __init__(
        self,
        campaigner_id: int,
        platforms: List[str],
        credentials: Dict[str, Any]
    ):
        """
        Initialize MCP Client Manager.

        Args:
            campaigner_id: ID of the campaigner
            platforms: List of platform names (e.g., ['google', 'facebook'])
            credentials: Dict with platform credentials
                {
                    'google_analytics': {...},
                    'google_ads': {...},
                    'facebook': {...}
                }
        """
        self.campaigner_id = campaigner_id
        self.platforms = platforms
        self.credentials = credentials
        self.clients = None
        self.validation_results: List[MCPValidationResult] = []

        # Feature flags (can be disabled via env vars)
        self.enable_token_refresh = os.getenv("ENABLE_TOKEN_REFRESH", "true").lower() == "true"
        self.enable_validation = os.getenv("ENABLE_MCP_VALIDATION", "true").lower() == "true"

    async def initialize(self) -> bool:
        """
        Initialize MCP clients with automatic token refresh and validation.

        This is the main entry point that orchestrates:
        1. Token refresh (if enabled)
        2. MCP client initialization
        3. Tool validation (if enabled)

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Step 1: Refresh tokens before initialization
            if self.enable_token_refresh:
                await self._refresh_tokens()
            else:
                logger.info("⚠️  Token refresh disabled via ENABLE_TOKEN_REFRESH=false")

            # Step 2: Initialize MCP clients
            success = await self._initialize_clients()
            if not success:
                logger.error("❌ Failed to initialize MCP clients")
                return False

            # Step 3: Validate tools
            if self.enable_validation:
                await self._validate_clients()
            else:
                logger.info("⚠️  MCP validation disabled via ENABLE_MCP_VALIDATION=false")

            # Step 4: Update last_validated_at in database
            await self._update_validation_timestamps()

            return True

        except Exception as e:
            logger.error(f"❌ MCP client manager initialization failed: {e}", exc_info=True)
            return False

    async def _refresh_tokens(self):
        """Refresh OAuth tokens if needed."""
        try:
            logger.info(f"🔄 Refreshing tokens for platforms: {self.platforms}")

            # Convert platform strings to MCPServer enums
            mcp_servers = []
            if 'google' in self.platforms:
                mcp_servers.append(MCPServer.GOOGLE_ANALYTICS_OFFICIAL)
                mcp_servers.append(MCPServer.GOOGLE_ADS_OFFICIAL)
            if 'facebook' in self.platforms:
                mcp_servers.append(MCPServer.META_ADS)

            # Build user_tokens dict from credentials
            user_tokens = {}
            if self.credentials.get('google_analytics'):
                user_tokens['google_analytics'] = self.credentials['google_analytics'].get('refresh_token')
            if self.credentials.get('google_ads'):
                user_tokens['google_ads'] = self.credentials['google_ads'].get('refresh_token')
            if self.credentials.get('facebook'):
                user_tokens['facebook'] = self.credentials['facebook'].get('access_token')

            # Refresh tokens
            refreshed_tokens = refresh_tokens_for_platforms(
                campaigner_id=self.campaigner_id,
                platforms=mcp_servers,
                user_tokens=user_tokens
            )

            # Update credentials with refreshed tokens
            if 'google_analytics' in refreshed_tokens and self.credentials.get('google_analytics'):
                self.credentials['google_analytics']['refresh_token'] = refreshed_tokens['google_analytics']
                logger.info("✅ Updated Google Analytics credentials with refreshed token")

            if 'google_ads' in refreshed_tokens and self.credentials.get('google_ads'):
                self.credentials['google_ads']['refresh_token'] = refreshed_tokens['google_ads']
                logger.info("✅ Updated Google Ads credentials with refreshed token")

            if 'facebook' in refreshed_tokens and self.credentials.get('facebook'):
                self.credentials['facebook']['access_token'] = refreshed_tokens['facebook']
                logger.info("✅ Updated Facebook credentials with refreshed token")

            logger.info(f"✅ Token refresh completed for campaigner {self.campaigner_id}")

        except Exception as e:
            logger.error(f"⚠️  Token refresh failed, continuing with existing tokens: {e}")
            # Don't fail initialization on token refresh errors
            # Validation will catch if tokens are invalid

    async def _initialize_clients(self) -> bool:
        """Initialize MCP clients using registry."""
        try:
            logger.info(f"🚀 Initializing MCP clients for platforms: {self.platforms}")

            # Convert platform strings to MCPServer enums
            mcp_servers = []
            if 'google' in self.platforms:
                # Use official servers
                mcp_servers.append(MCPServer.GOOGLE_ANALYTICS_OFFICIAL)
                mcp_servers.append(MCPServer.GOOGLE_ADS_OFFICIAL)
            if 'facebook' in self.platforms:
                mcp_servers.append(MCPServer.META_ADS)

            if not mcp_servers:
                logger.warning("⚠️  No MCP servers configured")
                return False

            # Build server parameters using MCPSelector
            server_params_list = MCPSelector.build_all_server_params(
                platforms=mcp_servers,
                google_analytics_credentials=self.credentials.get('google_analytics'),
                google_ads_credentials=self.credentials.get('google_ads'),
                meta_ads_credentials=self.credentials.get('facebook')
            )

            if not server_params_list:
                logger.warning("⚠️  No MCP server parameters built")
                return False

            # Initialize MultiServerMCPClient
            from langchain_mcp_adapters.client import MultiServerMCPClient

            # Convert StdioServerParameters to MultiServerMCPClient format
            servers = {}
            for idx, params in enumerate(server_params_list):
                # Use service name as key (extract from working directory or use index)
                server_name = f"server_{idx}"
                if params.cwd:
                    # Extract service name from working directory path
                    from pathlib import Path
                    cwd_path = Path(params.cwd)
                    server_name = cwd_path.name.replace("-", "_")

                servers[server_name] = {
                    "command": params.command,
                    "args": params.args,
                    "env": params.env or {},
                    "transport": "stdio"
                }

            # Create MultiServerMCPClient
            if servers:
                self.clients = MultiServerMCPClient(servers)
                logger.info(f"✅ Initialized {len(servers)} MCP server(s): {list(servers.keys())}")
                return True
            else:
                logger.warning("⚠️  No servers configured for MultiServerMCPClient")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to initialize MCP clients: {e}", exc_info=True)
            return False

    async def _validate_clients(self):
        """Validate MCP clients after initialization."""
        try:
            if not self.clients:
                logger.warning("⚠️  No MCP clients to validate")
                return

            logger.info("🔍 Validating MCP clients...")

            # Wrap single client in dict for validator
            clients_dict = {"mcp_client": self.clients}

            validator = MCPValidator(clients_dict)
            self.validation_results = await validator.validate_all()

            summary = validator.get_summary()
            logger.info(
                f"📊 MCP Validation Summary: "
                f"{summary['success']} success, "
                f"{summary['failed']} failed, "
                f"{summary['error']} error"
            )

            # Warn if there are failures
            if summary['failed'] > 0 or summary['error'] > 0:
                logger.warning(
                    f"⚠️  Some MCP tools may not be available. "
                    f"Check validation results for details."
                )

        except Exception as e:
            logger.error(f"❌ MCP validation failed: {e}", exc_info=True)
            # Don't fail initialization on validation errors

    async def _update_validation_timestamps(self):
        """Update last_validated_at timestamp in database for successful validations."""
        try:
            if not self.validation_results:
                return

            now = datetime.utcnow()

            with get_session() as session:
                # Update connections if validated successfully
                for result in self.validation_results:
                    asset_type = None

                    if 'google_analytics' in result.server.lower():
                        asset_type = AssetType.GA4
                    elif 'google_ads' in result.server.lower():
                        asset_type = AssetType.GOOGLE_ADS_CAPS
                    elif 'facebook' in result.server.lower():
                        asset_type = AssetType.FACEBOOK_ADS_CAPS

                    if asset_type and result.status.value == 'success':
                        conn = session.exec(
                            select(Connection)
                            .join(DigitalAsset)
                            .where(
                                and_(
                                    Connection.campaigner_id == self.campaigner_id,
                                    DigitalAsset.asset_type == asset_type,
                                    DigitalAsset.is_active == True
                                )
                            )
                        ).first()

                        if conn:
                            conn.last_validated_at = now
                            session.add(conn)

                session.commit()
                logger.info("✅ Updated validation timestamps in database")

        except Exception as e:
            logger.error(f"⚠️  Failed to update validation timestamps: {e}")
            # Don't fail on timestamp update errors

    def get_clients(self):
        """
        Get initialized MCP clients.

        Returns:
            MultiServerMCPClient instance or None
        """
        return self.clients

    def get_validation_results(self) -> List[MCPValidationResult]:
        """
        Get validation results.

        Returns:
            List of MCPValidationResult
        """
        return self.validation_results

    async def cleanup(self):
        """Cleanup MCP connections."""
        try:
            if self.clients:
                # MultiServerMCPClient cleanup happens automatically
                logger.info("✅ MCP client cleanup complete")
                self.clients = None
        except Exception as e:
            logger.error(f"❌ Error during MCP cleanup: {e}")
