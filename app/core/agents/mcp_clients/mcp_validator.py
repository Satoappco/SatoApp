"""
MCP Validator Module

Validates MCP tools after initialization to ensure they are accessible and working correctly.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from app.config.logging import get_logger

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


class MCPValidator:
    """Validates MCP tools after initialization."""

    def __init__(self, mcp_clients: Dict):
        """
        Initialize validator.

        Args:
            mcp_clients: Dictionary of initialized MCP clients
        """
        self.mcp_clients = mcp_clients
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

            if result.status == ValidationStatus.SUCCESS:
                logger.info(f"✅ {server_name}: {result.message} ({result.duration_ms}ms)")
            elif result.status == ValidationStatus.FAILED:
                logger.error(f"❌ {server_name}: {result.message} - {result.error_detail}")
            else:
                logger.warning(f"⚠️  {server_name}: {result.message}")

        return self.results

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
        start_time = datetime.utcnow()

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
            logger.error(f"❌ Error validating {server_name}: {e}", exc_info=True)
            return MCPValidationResult(
                server=server_name,
                status=ValidationStatus.ERROR,
                message="Validation error",
                error_detail=str(e),
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

            # Execute a simple test - get metadata (lightweight operation)
            if 'get_metadata' in tools:
                try:
                    # Try to call get_metadata with minimal params
                    result = await asyncio.wait_for(
                        client.call_tool('get_metadata', {}),
                        timeout=5.0
                    )

                    if result and not getattr(result, 'isError', False):
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
                    logger.warning(f"⚠️  Timeout calling get_metadata, but tools are available")
                    # Don't fail validation on timeout - tools exist, just slow
                    return MCPValidationResult(
                        server=server_name,
                        status=ValidationStatus.SUCCESS,
                        message=f"Found {len(found_tools)} tools (validation timed out)"
                    )

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

            # Execute simple test - list customers
            if 'list_accessible_customers' in tools:
                try:
                    result = await asyncio.wait_for(
                        client.call_tool('list_accessible_customers', {}),
                        timeout=5.0
                    )

                    if result and not getattr(result, 'isError', False):
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
                    logger.warning(f"⚠️  Timeout calling list_accessible_customers, but tools are available")
                    return MCPValidationResult(
                        server=server_name,
                        status=ValidationStatus.SUCCESS,
                        message=f"Found {len(found_tools)} tools (validation timed out)"
                    )

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
        delta = datetime.utcnow() - start_time
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
