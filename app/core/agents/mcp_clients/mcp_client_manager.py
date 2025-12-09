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
from datetime import datetime, timezone

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
        self.connection_ids: Dict[str, int] = {}  # Map platform names to connection IDs

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
        4. Reinitialize if validation removed platforms

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Step 1: Refresh tokens before initialization
            platforms_before_refresh = len(self.platforms)
            if self.enable_token_refresh:
                await self._refresh_tokens()
            else:
                logger.info("⚠️  Token refresh disabled via ENABLE_TOKEN_REFRESH=false")

            # Check if token refresh removed platforms
            if len(self.platforms) < platforms_before_refresh:
                logger.warning(
                    f"⚠️  Token refresh removed {platforms_before_refresh - len(self.platforms)} platform(s). "
                    f"Remaining: {self.platforms}"
                )

            # If no platforms remain, fail initialization
            if not self.platforms:
                logger.error("❌ No platforms remaining after token refresh")
                return False

            # Step 2: Initialize MCP clients
            success = await self._initialize_clients()
            if not success:
                logger.error("❌ Failed to initialize MCP clients")
                return False

            # Step 3: Validate tools
            platforms_before_validation = len(self.platforms)
            if self.enable_validation:
                await self._validate_clients()
            else:
                logger.info("⚠️  MCP validation disabled via ENABLE_MCP_VALIDATION=false")

            # Step 4: Reinitialize if validation removed platforms
            if len(self.platforms) < platforms_before_validation:
                logger.warning(
                    f"⚠️  Validation removed {platforms_before_validation - len(self.platforms)} platform(s). "
                    f"Remaining: {self.platforms}"
                )

                # If no platforms remain, fail initialization
                if not self.platforms:
                    logger.error("❌ No platforms remaining after validation")
                    return False

                # Cleanup old clients
                await self.cleanup()

                # Reinitialize with remaining platforms
                logger.info(f"🔄 Reinitializing MCP clients with remaining platforms: {self.platforms}")
                success = await self._initialize_clients()
                if not success:
                    logger.error("❌ Failed to reinitialize MCP clients after validation")
                    return False

            # Step 5: Update last_validated_at in database
            await self._update_validation_timestamps()

            logger.info(f"✅ MCP initialization complete with {len(self.platforms)} platform(s): {self.platforms}")
            return True

        except Exception as e:
            logger.error(f"❌ MCP client manager initialization failed: {e}", exc_info=True)
            return False

    async def _refresh_tokens(self):
        """Refresh OAuth tokens if needed. Remove platforms that fail token refresh."""
        platforms_to_remove = []

        try:
            logger.info(f"🔄 Refreshing tokens for platforms: {self.platforms}")

            # Convert platform strings to MCPServer enums
            mcp_servers = []
            if 'google' in self.platforms or 'google_analytics' in self.platforms:
                mcp_servers.append(MCPServer.GOOGLE_ANALYTICS_OFFICIAL)
            if 'google_ads' in self.platforms or 'google' in self.platforms:
                mcp_servers.append(MCPServer.GOOGLE_ADS_OFFICIAL)
            if 'facebook_ads' in self.platforms:
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
            try:
                refreshed_tokens = refresh_tokens_for_platforms(
                    campaigner_id=self.campaigner_id,
                    platforms=mcp_servers,
                    user_tokens=user_tokens
                )
                logger.debug(f"Refreshed tokens: {refreshed_tokens} platforms: {self.platforms}")
                # Check which platforms had their tokens successfully refreshed or maintained
                # If a token is missing from refreshed_tokens, it means refresh failed
                if 'google_analytics' in self.platforms:
                    if 'google_analytics' in refreshed_tokens:
                        if self.credentials.get('google_analytics'):
                            self.credentials['google_analytics']['refresh_token'] = refreshed_tokens['google_analytics']
                        logger.info("✅ Google Analytics token is valid")
                    else:
                        logger.warning("⚠️  Google Analytics token refresh failed, removing platform")
                        platforms_to_remove.append('google_analytics')

                if 'google_ads' in self.platforms:
                    if 'google_ads' in refreshed_tokens:
                        if self.credentials.get('google_ads'):
                            self.credentials['google_ads']['refresh_token'] = refreshed_tokens['google_ads']
                        logger.info("✅ Google Ads token is valid")
                    else:
                        logger.warning("⚠️  Google Ads token refresh failed, removing platform")
                        platforms_to_remove.append('google_ads')

                if 'facebook_ads' in self.platforms:
                    if 'facebook' in refreshed_tokens:
                        if self.credentials.get('facebook'):
                            self.credentials['facebook']['access_token'] = refreshed_tokens['facebook']
                        logger.info("✅ Facebook token is valid")
                    else:
                        logger.warning("⚠️  Facebook token refresh failed, removing platform")
                        platforms_to_remove.append('facebook_ads')

                logger.info(f"✅ Token refresh check completed for campaigner {self.campaigner_id}")

            except Exception as e:
                logger.error(f"❌ Token refresh failed: {e}", exc_info=True)
                # Remove all platforms since we can't determine which ones failed
                platforms_to_remove.extend(self.platforms)

        except Exception as e:
            logger.error(f"❌ Token refresh setup failed: {e}")
            # Remove all platforms since we can't proceed
            platforms_to_remove.extend(self.platforms)

        # Remove failed platforms
        if platforms_to_remove:
            for platform in platforms_to_remove:
                if platform in self.platforms:
                    self.platforms.remove(platform)
                    logger.warning(f"🚫 Removed platform '{platform}' due to token refresh failure")
                    # Also remove credentials
                    if platform in self.credentials:
                        del self.credentials[platform]

    async def _initialize_clients(self) -> bool:
        """Initialize MCP clients using registry."""
        try:
            logger.info(f"🚀 Initializing MCP clients for platforms: {self.platforms}")

            # Build server parameters using MCPSelector
            server_params_list = MCPSelector.build_all_server_params(
                platforms=self.platforms,
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
        """Validate MCP clients after initialization. Remove platforms that fail validation."""
        platforms_to_remove = []

        try:
            if not self.clients:
                logger.warning("⚠️  No MCP clients to validate")
                return

            logger.info("🔍 Validating MCP clients...")

            # Fetch connection IDs for failure logging
            await self._fetch_connection_ids()

            # Wrap single client in dict for validator
            clients_dict = {"mcp_client": self.clients}

            validator = MCPValidator(clients_dict, self.connection_ids)
            self.validation_results = await validator.validate_all()

            summary = validator.get_summary()
            logger.info(
                f"📊 MCP Validation Summary: "
                f"{summary['success']} success, "
                f"{summary['failed']} failed, "
                f"{summary['error']} error"
            )

            # Check which platforms failed validation and remove them
            from app.core.agents.mcp_clients.mcp_validator import ValidationStatus
            for result in self.validation_results:
                if result.status in [ValidationStatus.FAILED, ValidationStatus.ERROR]:
                    # Check error details to identify which platform failed
                    error_detail = str(result.error_detail or '').lower()
                    server_name = result.server.lower()

                    # Extract server hint if present
                    server_hint = None
                    if 'server hint:' in error_detail:
                        # Parse "Server hint: google_ads_mcp" from error_detail
                        import re
                        hint_match = re.search(r'server hint:\s*(\w+)', error_detail)
                        if hint_match:
                            server_hint = hint_match.group(1).lower()
                            logger.info(f"🔍 Detected failed server from hint: {server_hint}")

                    # Check if error mentions specific platform or server
                    if server_hint == 'google_analytics_mcp' or 'google_analytics' in server_name or 'google-analytics' in error_detail or 'analytics_mcp' in error_detail:
                        if 'google_analytics' not in platforms_to_remove:
                            platforms_to_remove.append('google_analytics')
                        logger.error(
                            f"❌ Google Analytics validation failed: {result.message}"
                        )
                        logger.debug(f"   Detail: {result.error_detail}")
                    elif server_hint == 'google_ads_mcp' or 'google_ads' in server_name or 'google-ads' in error_detail or 'ads_mcp' in error_detail:
                        if 'google_ads' not in platforms_to_remove:
                            platforms_to_remove.append('google_ads')
                        logger.error(
                            f"❌ Google Ads validation failed: {result.message}"
                        )
                        logger.debug(f"   Detail: {result.error_detail}")
                    elif server_hint == 'facebook_mcp' or 'facebook' in server_name or 'facebook' in error_detail or 'meta' in error_detail:
                        if 'facebook_ads' not in platforms_to_remove:
                            platforms_to_remove.append('facebook_ads')
                        logger.error(
                            f"❌ Facebook validation failed: {result.message}"
                        )
                        logger.debug(f"   Detail: {result.error_detail}")
                    else:
                        # Can't determine which platform - log the error but remove all platforms to be safe
                        logger.error(
                            f"❌ MCP validation failed but cannot determine platform: {result.message}"
                        )
                        logger.error(f"   Error detail (first 200 chars): {str(result.error_detail)[:200]}")
                        # Remove all platforms since we can't isolate the failure
                        platforms_to_remove.extend([p for p in self.platforms if p not in platforms_to_remove])

        except Exception as e:
            logger.error(f"❌ MCP validation failed: {e}", exc_info=True)
            # Remove all platforms since validation failed completely
            platforms_to_remove.extend(self.platforms)

        # Remove failed platforms
        if platforms_to_remove:
            for platform in platforms_to_remove:
                if platform in self.platforms:
                    self.platforms.remove(platform)
                    logger.warning(f"🚫 Removed platform '{platform}' due to validation failure")
                    # Also remove credentials
                    if platform in self.credentials:
                        del self.credentials[platform]

    async def _fetch_connection_ids(self):
        """Fetch connection IDs for each platform to enable failure logging."""
        try:
            with get_session() as session:
                for platform in self.platforms:
                    asset_type = None

                    if platform == 'google_analytics':
                        asset_type = AssetType.GA4
                    elif platform == 'google_ads':
                        asset_type = AssetType.GOOGLE_ADS_CAPS
                    elif platform == 'facebook_ads':
                        asset_type = AssetType.FACEBOOK_ADS_CAPS

                    if asset_type:
                        conn = session.exec(
                            select(Connection)
                            .join(DigitalAsset)
                            .where(
                                and_(
                                    Connection.campaigner_id == self.campaigner_id,
                                    DigitalAsset.asset_type == asset_type,
                                    DigitalAsset.is_active == True,
                                    Connection.revoked == False
                                )
                            )
                        ).first()

                        if conn:
                            self.connection_ids[platform] = conn.id
                            logger.debug(f"🔗 Mapped platform '{platform}' to connection ID {conn.id}")

        except Exception as e:
            logger.error(f"❌ Failed to fetch connection IDs: {e}")

    async def _update_validation_timestamps(self):
        """Update last_validated_at timestamp in database for successful validations."""
        try:
            if not self.validation_results:
                return

            now = datetime.now(timezone.utc)

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

    def get_active_platforms(self) -> List[str]:
        """
        Get list of currently active platforms (after token refresh and validation).

        Returns:
            List of active platform names
        """
        return self.platforms.copy()

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
