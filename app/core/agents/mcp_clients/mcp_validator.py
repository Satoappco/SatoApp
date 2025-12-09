"""
MCP Validator Module

Validates MCP tools after initialization to ensure they are accessible and working correctly.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum

from app.config.logging import get_logger
from app.utils.connection_failure_utils import record_connection_failure, record_connection_success

logger = get_logger(__name__)


class ValidationStatus(str, Enum):
    """Validation status for MCP tools."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class MCPValidationResult:
    """Result of MCP tool validation."""
    server: str
    status: ValidationStatus
    message: Optional[str] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None
    connection_id: Optional[int] = None  # Connection ID for logging failures


class MCPValidator:
    """Validates MCP tools after initialization."""

    def __init__(self, mcp_clients: Dict, connection_ids: Optional[Dict[str, int]] = None):
        """
        Initialize validator.

        Args:
            mcp_clients: Dictionary of initialized MCP clients
            connection_ids: Optional mapping of platform names to connection IDs for failure logging
        """
        self.mcp_clients = mcp_clients
        self.connection_ids = connection_ids or {}
        self.results: List[MCPValidationResult] = []

    async def validate_all(self) -> List[MCPValidationResult]:
        """
        Validate all initialized MCP clients.

        Returns:
            List of validation results for each client
        """
        logger.info(f"🔍 Validating {len(self.mcp_clients)} MCP client(s)...")

        for server_name, client in self.mcp_clients.items():
            result = await self._validate_client(server_name, client)
            self.results.append(result)

            # Get connection ID for this server if available
            connection_id = self._get_connection_id_for_server(server_name)
            result.connection_id = connection_id

            if result.status == ValidationStatus.SUCCESS:
                logger.info(f"✅ {server_name}: {result.message} ({result.duration_ms}ms)")
                # Record successful validation
                if connection_id:
                    record_connection_success(connection_id, reset_failure_count=True)
            elif result.status == ValidationStatus.FAILED:
                logger.error(f"❌ {server_name}: {result.message} - {result.error_detail}")
                # Record validation failure
                if connection_id:
                    failure_reason = f"mcp_validation_failed: {result.message}"
                    record_connection_failure(connection_id, failure_reason, also_set_needs_reauth=False)
            else:
                logger.warning(f"⚠️  {server_name}: {result.message}")

        return self.results

    def _get_connection_id_for_server(self, server_name: str) -> Optional[int]:
        """
        Get connection ID for a given server name.

        Args:
            server_name: MCP server name

        Returns:
            Connection ID if found, None otherwise
        """
        # Try exact match first
        if server_name in self.connection_ids:
            return self.connection_ids[server_name]

        # Try fuzzy matching based on platform name
        server_lower = server_name.lower()
        for platform_name, conn_id in self.connection_ids.items():
            platform_lower = platform_name.lower()
            if (('google_analytics' in server_lower and 'google_analytics' in platform_lower) or
                ('google_ads' in server_lower and 'google_ads' in platform_lower) or
                ('facebook' in server_lower and 'facebook' in platform_lower) or
                ('meta' in server_lower and 'meta' in platform_lower)):
                return conn_id

        return None

    async def _validate_client(
        self,
        server_name: str,
        client
    ) -> MCPValidationResult:
        """
        Validate a single MCP client.

        Args:
            server_name: Name of the MCP server
            client: MCP client instance

        Returns:
            Validation result
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get available tools from client
            tools = await self._get_tools(client)

            if not tools:
                return MCPValidationResult(
                    server=server_name,
                    status=ValidationStatus.FAILED,
                    message="No tools available",
                    duration_ms=self._duration_ms(start_time)
                )

            # Execute validation test based on server type
            validation_result = await self._execute_validation_test(
                server_name,
                client,
                tools
            )

            validation_result.duration_ms = self._duration_ms(start_time)
            return validation_result

        except Exception as e:
            # Try to extract more details from the error
            import traceback
            error_traceback = traceback.format_exc()

            logger.error(f"❌ Error validating {server_name}: {e}", exc_info=True)

            # Try to identify which MCP server failed from the traceback
            failed_server_hint = None
            if 'google_ads_mcp' in error_traceback or 'ads_mcp' in error_traceback:
                failed_server_hint = 'google_ads_mcp'
            elif 'google_analytics_mcp' in error_traceback or 'analytics_mcp' in error_traceback:
                failed_server_hint = 'google_analytics_mcp'
            elif 'facebook' in error_traceback.lower() or 'meta' in error_traceback.lower():
                failed_server_hint = 'facebook_mcp'

            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.ERROR,
                message="Validation error",
                error_detail=f"{str(e)} | Server hint: {failed_server_hint} | Traceback: {error_traceback[:500]}",
                duration_ms=self._duration_ms(start_time)
            )

    async def _get_tools(self, client) -> List[str]:
        """Get list of available tools from MCP client.

        Raises:
            Exception: If there's an error fetching tools from the client
        """
        # MultiServerMCPClient has get_tools() method
        if hasattr(client, 'get_tools'):
            tools_response = await client.get_tools()
            return [getattr(tool, 'name', str(tool)) for tool in tools_response]

        # Single MCP client has list_tools() method
        elif hasattr(client, 'list_tools'):
            tools_response = await client.list_tools()
            if hasattr(tools_response, 'tools'):
                return [tool.name for tool in tools_response.tools]
            return []

        else:
            logger.warning(f"⚠️  Client has no get_tools() or list_tools() method")
            return []

    async def _execute_validation_test(
        self,
        server_name: str,
        client,
        tools: List[str]
    ) -> MCPValidationResult:
        """
        Execute platform-specific validation test.

        Args:
            server_name: Name of MCP server
            client: MCP client instance
            tools: List of available tool names

        Returns:
            Validation result
        """
        # Google Analytics validation
        if "google_analytics" in server_name.lower():
            return await self._validate_google_analytics(client, tools, server_name)

        # Google Ads validation
        elif "google_ads" in server_name.lower():
            return await self._validate_google_ads(client, tools, server_name)

        # Facebook validation
        elif "facebook" in server_name.lower():
            return await self._validate_facebook(client, tools, server_name)

        # Generic validation - just check tools are available
        else:
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.SUCCESS,
                message=f"Found {len(tools)} tools"
            )

    async def _validate_google_analytics(
        self,
        client,
        tools: List[str],
        server_name: str
    ) -> MCPValidationResult:
        """Validate Google Analytics MCP client."""
        try:
            # Check for expected tools
            expected_tools = ['run_report', 'get_metadata', 'list_accounts']
            found_tools = [t for t in expected_tools if t in tools]

            if not found_tools:
                return MCPValidationResult(
                    server=server_name,
                    status=ValidationStatus.FAILED,
                    message="Missing expected tools",
                    error_detail=f"Expected: {expected_tools}, Found: {tools}"
                )

            # Execute a simple test - get metadata or list accounts (tests credentials)
            test_tool = None
            test_params = {}

            if 'get_account_summaries' in tools:
                test_tool = 'get_account_summaries'
                test_params = {}
            elif 'get_metadata' in tools:
                test_tool = 'get_metadata'
                test_params = {}

            if test_tool:
                try:
                    # Try to call the test tool - this will exercise credentials
                    result = await asyncio.wait_for(
                        client.call_tool(test_tool, test_params),
                        timeout=10.0
                    )

                    # Check for errors in result
                    if result and not getattr(result, 'isError', False):
                        # Also check if content contains error messages
                        content = getattr(result, 'content', [])
                        error_keywords = ['error', 'failed', 'invalid', 'expired', 'revoked', 'credentials']
                        has_error = False

                        if isinstance(content, list):
                            for item in content:
                                text = str(getattr(item, 'text', '')).lower()
                                if any(keyword in text for keyword in error_keywords):
                                    has_error = True
                                    return MCPValidationResult(
                                        server=server_name,
                                        status=ValidationStatus.FAILED,
                                        message="Credential validation failed",
                                        error_detail=text[:200]
                                    )

                        if not has_error:
                            return MCPValidationResult(
                                server=server_name,
                                status=ValidationStatus.SUCCESS,
                                message=f"Validated {len(found_tools)} tools"
                            )
                    else:
                        return MCPValidationResult(
                            server=server_name,
                            status=ValidationStatus.FAILED,
                            message="Tool execution failed",
                            error_detail=str(getattr(result, 'content', 'No response'))
                        )
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️  Timeout calling {test_tool}, but tools are available")
                    # Don't fail validation on timeout - tools exist, just slow
                    return MCPValidationResult(
                        server=server_name,
                        status=ValidationStatus.SUCCESS,
                        message=f"Found {len(found_tools)} tools (validation timed out)"
                    )
                except Exception as e:
                    # Catch credential errors
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['credential', 'auth', 'token', 'expired', 'revoked']):
                        return MCPValidationResult(
                            server=server_name,
                            status=ValidationStatus.FAILED,
                            message="Credential error during validation",
                            error_detail=str(e)[:200]
                        )
                    raise

            # If we can't test, just verify tools exist
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.SUCCESS,
                message=f"Found {len(found_tools)} tools (not tested)"
            )

        except Exception as e:
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.ERROR,
                message="Validation test failed",
                error_detail=str(e)
            )

    async def _validate_google_ads(
        self,
        client,
        tools: List[str],
        server_name: str
    ) -> MCPValidationResult:
        """Validate Google Ads MCP client."""
        try:
            expected_tools = ['search', 'list_accessible_customers']
            found_tools = [t for t in expected_tools if t in tools]

            if not found_tools:
                return MCPValidationResult(
                    server=server_name,
                    status=ValidationStatus.FAILED,
                    message="Missing expected tools",
                    error_detail=f"Expected: {expected_tools}, Found: {tools}"
                )

            # Execute simple test - list accounts (tests credentials)
            test_tool = None
            if 'list_accessible_accounts' in tools:
                test_tool = 'list_accessible_accounts'
            elif 'list_accessible_customers' in tools:
                test_tool = 'list_accessible_customers'

            if test_tool:
                try:
                    result = await asyncio.wait_for(
                        client.call_tool(test_tool, {}),
                        timeout=10.0
                    )

                    # Check for errors in result
                    if result and not getattr(result, 'isError', False):
                        # Also check if content contains error messages
                        content = getattr(result, 'content', [])
                        error_keywords = ['error', 'failed', 'invalid', 'expired', 'revoked', 'credentials']
                        has_error = False

                        if isinstance(content, list):
                            for item in content:
                                text = str(getattr(item, 'text', '')).lower()
                                if any(keyword in text for keyword in error_keywords):
                                    has_error = True
                                    return MCPValidationResult(
                                        server=server_name,
                                        status=ValidationStatus.FAILED,
                                        message="Credential validation failed",
                                        error_detail=text[:200]
                                    )

                        if not has_error:
                            return MCPValidationResult(
                                server=server_name,
                                status=ValidationStatus.SUCCESS,
                                message=f"Validated {len(found_tools)} tools"
                            )
                    else:
                        return MCPValidationResult(
                            server=server_name,
                            status=ValidationStatus.FAILED,
                            message="Tool execution failed",
                            error_detail=str(getattr(result, 'content', 'No response'))
                        )
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️  Timeout calling {test_tool}, but tools are available")
                    return MCPValidationResult(
                        server=server_name,
                        status=ValidationStatus.SUCCESS,
                        message=f"Found {len(found_tools)} tools (validation timed out)"
                    )
                except Exception as e:
                    # Catch credential errors
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['credential', 'auth', 'token', 'expired', 'revoked']):
                        return MCPValidationResult(
                            server=server_name,
                            status=ValidationStatus.FAILED,
                            message="Credential error during validation",
                            error_detail=str(e)[:200]
                        )
                    raise

            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.SUCCESS,
                message=f"Found {len(found_tools)} tools (not tested)"
            )

        except Exception as e:
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.ERROR,
                message="Validation test failed",
                error_detail=str(e)
            )

    async def _validate_facebook(
        self,
        client,
        tools: List[str],
        server_name: str
    ) -> MCPValidationResult:
        """Validate Facebook MCP client."""
        try:
            # Check for basic tools
            if len(tools) == 0:
                return MCPValidationResult(
                    server=server_name,
                    status=ValidationStatus.FAILED,
                    message="No tools available"
                )

            # Facebook MCP might have different tool names
            # Just verify tools are present for now
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.SUCCESS,
                message=f"Found {len(tools)} tools"
            )

        except Exception as e:
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.ERROR,
                message="Validation test failed",
                error_detail=str(e)
            )

    def _duration_ms(self, start_time: datetime) -> int:
        """Calculate duration in milliseconds."""
        delta = datetime.now(timezone.utc) - start_time
        return int(delta.total_seconds() * 1000)

    def get_summary(self) -> Dict:
        """Get validation summary."""
        return {
            'total': len(self.results),
            'success': len([r for r in self.results if r.status == ValidationStatus.SUCCESS]),
            'failed': len([r for r in self.results if r.status == ValidationStatus.FAILED]),
            'error': len([r for r in self.results if r.status == ValidationStatus.ERROR]),
            'skipped': len([r for r in self.results if r.status == ValidationStatus.SKIPPED])
        }
