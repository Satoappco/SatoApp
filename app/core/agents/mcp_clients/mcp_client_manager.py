"""
Centralized MCP Client Manager

Orchestrates the complete MCP client lifecycle:
1. Token refresh (before initialization)
2. MCP client initialization (HTTP or STDIO transport)
3. Tool validation (after initialization)
4. Connection cleanup

This ensures all agents use the same reliable initialization flow.

Transport Modes:
- HTTP: Use HTTP/SSE microservices for better performance
- STDIO: Traditional subprocess-based communication (fallback)
- AUTO: Try HTTP first, fallback to STDIO on failure
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

from app.config.logging import get_logger
from app.core.oauth.token_refresh import refresh_tokens_for_platforms
from app.core.agents.mcp_clients.mcp_registry import MCPServer, MCPSelector
from app.core.agents.mcp_clients.mcp_validator import MCPValidator, MCPValidationResult
from app.core.agents.mcp_clients.http_client import HTTPMCPClient
from app.config.database import get_session
from app.models.analytics import Connection, AssetType, DigitalAsset
from app.utils.connection_utils import get_connection_by_platform
from sqlmodel import select, and_

logger = get_logger(__name__)


class UnifiedMCPClient:
    """
    Unified MCP client wrapper that provides a consistent interface
    for both HTTP and STDIO transport modes.
    """

    def __init__(self, clients_data):
        """
        Initialize unified client.

        Args:
            clients_data: Either a dict with HTTP clients or MultiServerMCPClient instance
        """
        if isinstance(clients_data, dict) and clients_data.get('type') == 'http':
            self.transport_mode = 'http'
            self.http_clients = clients_data['clients']
            self.stdio_client = None
        else:
            self.transport_mode = 'stdio'
            self.http_clients = None
            self.stdio_client = clients_data

    async def get_tools(self):
        """
        Get all available tools from MCP clients.

        Returns:
            List of LangChain BaseTool instances
        """
        if self.transport_mode == 'http':
            # For HTTP mode, aggregate tools from all HTTP clients and convert to LangChain tools
            from app.core.agents.mcp_clients.http_client import HTTPToolWrapper

            all_tools = []
            for platform, client in self.http_clients.items():
                try:
                    tools_data = await client.list_tools()

                    # Convert each HTTP tool dict to LangChain BaseTool
                    for tool_dict in tools_data:
                        tool_name = tool_dict.get('name', 'unknown')
                        tool_description = tool_dict.get('description', f'Tool from {platform}')

                        # Create HTTPToolWrapper instance
                        wrapped_tool = HTTPToolWrapper(
                            name=tool_name,
                            description=tool_description,
                            http_client=client,
                            tool_name=tool_name
                        )
                        all_tools.append(wrapped_tool)

                    logger.debug(f"✅ Converted {len(tools_data)} HTTP tools from {platform} to LangChain tools")

                except Exception as e:
                    logger.error(f"❌ Failed to get tools from {platform}: {e}")

            return all_tools
        else:
            # For STDIO mode, use MultiServerMCPClient's get_tools method
            return await self.stdio_client.get_tools()


class MCPTransportMode(str, Enum):
    """MCP transport mode."""
    HTTP = "http"  # Use HTTP/SSE microservices
    STDIO = "stdio"  # Use subprocess stdio transport
    AUTO = "auto"  # Try HTTP first, fallback to stdio


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
        credentials: Dict[str, Any],
        transport_mode: Optional[MCPTransportMode] = None
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
            transport_mode: Transport mode (HTTP, STDIO, AUTO). Defaults to AUTO.
        """
        self.campaigner_id = campaigner_id
        self.platforms = platforms
        self.credentials = credentials
        self.clients = None
        self.validation_results: List[MCPValidationResult] = []
        self.connection_ids: Dict[str, int] = {}  # Map platform names to connection IDs
        self.http_sessions: Dict[str, str] = {}  # Map platform names to HTTP session IDs

        # Determine transport mode from parameter or environment variable
        if transport_mode:
            self.transport_mode = transport_mode
        else:
            mode_str = os.getenv("MCP_TRANSPORT_MODE", "auto").lower()
            if mode_str == "http":
                self.transport_mode = MCPTransportMode.HTTP
            elif mode_str == "stdio":
                self.transport_mode = MCPTransportMode.STDIO
            else:
                self.transport_mode = MCPTransportMode.AUTO

        # HTTP service URLs
        self.http_service_urls = {
            'google_analytics': os.getenv("MCP_GA4_HTTP_URL", "http://localhost:8001"),
            'google_ads': os.getenv("MCP_GADS_HTTP_URL", "http://localhost:8002"),
            'facebook_ads': os.getenv("MCP_FB_HTTP_URL", "http://localhost:8003"),
        }

        # Feature flags (can be disabled via env vars)
        self.enable_token_refresh = os.getenv("ENABLE_TOKEN_REFRESH", "true").lower() == "true"
        self.enable_validation = os.getenv("ENABLE_MCP_VALIDATION", "true").lower() == "true"

        logger.info(f"🚀 MCPClientManager initialized with transport mode: {self.transport_mode.value}")

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
        """
        Initialize MCP clients using HTTP or STDIO transport.

        In AUTO mode, tries HTTP first and falls back to STDIO on failure.
        """
        try:
            logger.info(f"🚀 Initializing MCP clients for platforms: {self.platforms} (mode: {self.transport_mode.value})")

            # Try HTTP first if AUTO or HTTP mode
            if self.transport_mode in [MCPTransportMode.HTTP, MCPTransportMode.AUTO]:
                try:
                    success = await self._initialize_http_clients()
                    if success:
                        logger.info(f"✅ Successfully initialized HTTP transport")
                        return True
                    elif self.transport_mode == MCPTransportMode.HTTP:
                        # HTTP mode only, fail if HTTP doesn't work
                        logger.error("❌ HTTP transport failed and STDIO fallback disabled")
                        return False
                    else:
                        # AUTO mode, fall through to STDIO
                        logger.warning("⚠️  HTTP transport failed, falling back to STDIO")
                except Exception as e:
                    logger.error(f"❌ HTTP transport initialization error: {e}", exc_info=True)
                    if self.transport_mode == MCPTransportMode.HTTP:
                        return False
                    logger.warning("⚠️  Falling back to STDIO transport")

            # STDIO fallback (or STDIO mode)
            return await self._initialize_stdio_clients()

        except Exception as e:
            logger.error(f"❌ Failed to initialize MCP clients: {e}", exc_info=True)
            return False

    async def _initialize_http_clients(self) -> bool:
        """Initialize HTTP-based MCP clients."""
        try:
            import httpx

            logger.info("🌐 Attempting HTTP transport initialization...")

            # Initialize HTTP session for each platform
            http_clients = {}
            failed_platforms = []

            for platform in self.platforms:
                try:
                    # Get credentials for this platform
                    creds = self.credentials.get(platform)
                    if not creds:
                        logger.warning(f"⚠️  No credentials for {platform}, skipping HTTP init")
                        failed_platforms.append(platform)
                        continue

                    # Initialize HTTP connection
                    session_id = await self._initialize_http_connection(platform, creds)
                    if session_id:
                        self.http_sessions[platform] = session_id
                        # Create HTTP MCP client wrapper
                        base_url = self.http_service_urls.get(platform)
                        http_clients[platform] = HTTPMCPClient(
                            platform=platform,
                            base_url=base_url,
                            session_id=session_id
                        )
                        logger.info(f"✅ HTTP session created for {platform}: {session_id}")
                    else:
                        failed_platforms.append(platform)

                except Exception as e:
                    logger.error(f"❌ Failed to initialize HTTP for {platform}: {e}")
                    failed_platforms.append(platform)

            # If all platforms failed, return False
            if len(failed_platforms) == len(self.platforms):
                logger.error("❌ All platforms failed HTTP initialization")
                return False

            # Remove failed platforms
            for platform in failed_platforms:
                if platform in self.platforms:
                    self.platforms.remove(platform)
                    logger.warning(f"🚫 Removed {platform} due to HTTP init failure")

            # Store HTTP clients wrapper
            if http_clients:
                self.clients = {'type': 'http', 'clients': http_clients}
                logger.info(f"✅ Initialized {len(http_clients)} HTTP MCP client(s): {list(http_clients.keys())}")
                return True

            return False

        except ImportError:
            logger.error("❌ httpx not installed, cannot use HTTP transport")
            return False
        except Exception as e:
            logger.error(f"❌ HTTP client initialization failed: {e}", exc_info=True)
            return False

    async def _initialize_http_connection(self, platform: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Initialize HTTP connection for a specific platform.

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            import httpx

            base_url = self.http_service_urls.get(platform)
            if not base_url:
                logger.error(f"❌ No HTTP service URL configured for {platform}")
                return None

            # Build initialization request based on platform
            init_data = {}
            if platform == 'google_analytics':
                init_data = {
                    'refresh_token': credentials.get('refresh_token'),
                    'property_id': credentials.get('property_id'),
                    'client_id': credentials.get('client_id'),
                    'client_secret': credentials.get('client_secret')
                }
            elif platform == 'google_ads':
                init_data = {
                    'refresh_token': credentials.get('refresh_token'),
                    'customer_id': credentials.get('account_id'),  # account_id is the customer_id
                    'client_id': credentials.get('client_id'),
                    'client_secret': credentials.get('client_secret'),
                    'developer_token': credentials.get('developer_token')
                }
            elif platform == 'facebook_ads':
                init_data = {
                    'access_token': credentials.get('access_token'),
                    'account_id': credentials.get('account_id')
                }

            # Call /initialize endpoint
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{base_url}/initialize",
                    json=init_data
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('session_id')
                else:
                    logger.error(f"❌ HTTP init failed for {platform}: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Error initializing HTTP connection for {platform}: {e}")
            return None

    async def _initialize_stdio_clients(self) -> bool:
        """Initialize STDIO-based MCP clients (subprocess)."""
        try:
            logger.info("📟 Initializing STDIO transport...")

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
                logger.info(f"✅ Initialized {len(servers)} STDIO MCP server(s): {list(servers.keys())}")
                return True
            else:
                logger.warning("⚠️  No servers configured for MultiServerMCPClient")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to initialize STDIO clients: {e}", exc_info=True)
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

            # Extract actual client objects for validation
            if isinstance(self.clients, dict) and self.clients.get('type') == 'http':
                # For HTTP mode, clients are in self.clients['clients'] dict
                clients_dict = self.clients['clients']
            else:
                # For STDIO mode or single client, wrap in dict
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
                    # Use the platform field directly - no regex parsing needed!
                    platform = result.platform

                    if platform and platform in self.platforms:
                        # We know exactly which platform failed
                        if platform not in platforms_to_remove:
                            platforms_to_remove.append(platform)
                        logger.error(
                            f"❌ {platform} validation failed: {result.message}"
                        )
                        if result.error_detail:
                            logger.debug(f"   Detail: {result.error_detail}")
                    else:
                        # Cannot determine platform - log error and remove all to be safe
                        logger.error(
                            f"❌ MCP validation failed but cannot determine platform: {result.message}"
                        )
                        logger.error(f"   Server: {result.server}, Error: {result.error_detail[:200] if result.error_detail else 'None'}")
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
                    # Use centralized query to get connection
                    conn = get_connection_by_platform(
                        platform=platform,
                        campaigner_id=self.campaigner_id,
                        customer_id=None,  # Not filtering by customer_id
                        session=session
                    )

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
                    platform = None

                    # Map server name to platform
                    if 'google_analytics' in result.server.lower():
                        platform = 'google_analytics'
                    elif 'google_ads' in result.server.lower():
                        platform = 'google_ads'
                    elif 'facebook' in result.server.lower():
                        platform = 'facebook_ads'

                    if platform and result.status.value == 'success':
                        # Use centralized query to get connection
                        conn = get_connection_by_platform(
                            platform=platform,
                            campaigner_id=self.campaigner_id,
                            customer_id=None,
                            session=session
                        )

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
        Get initialized MCP clients wrapped in UnifiedMCPClient.

        Returns:
            UnifiedMCPClient instance or None
        """
        if self.clients is None:
            return None
        return UnifiedMCPClient(self.clients)

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
        """Cleanup MCP connections and HTTP sessions."""
        try:
            # Cleanup HTTP sessions if any
            if self.http_sessions:
                import httpx
                for platform, session_id in self.http_sessions.items():
                    try:
                        base_url = self.http_service_urls.get(platform)
                        if base_url:
                            async with httpx.AsyncClient(timeout=5.0) as client:
                                await client.delete(f"{base_url}/session/{session_id}")
                            logger.info(f"✅ Cleaned up HTTP session for {platform}")
                    except Exception as e:
                        logger.warning(f"⚠️  Error cleaning up HTTP session for {platform}: {e}")

                self.http_sessions.clear()

            # Cleanup MCP clients
            if self.clients:
                # Check if it's HTTP or STDIO client
                if isinstance(self.clients, dict) and self.clients.get('type') == 'http':
                    # HTTP clients already cleaned up above
                    pass
                else:
                    # MultiServerMCPClient cleanup happens automatically
                    pass

                logger.info("✅ MCP client cleanup complete")
                self.clients = None

        except Exception as e:
            logger.error(f"❌ Error during MCP cleanup: {e}")
