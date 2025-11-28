"""
Unit tests for MCP validator functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock
from app.core.agents.mcp_clients.mcp_validator import (
    MCPValidator,
    ValidationStatus,
    MCPValidationResult
)


class TestMCPValidator:
    """Test MCP validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_successful_client(self):
        """Test validation of successful MCP client."""
        # Mock client with tools
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[
            Mock(name='tool1'),
            Mock(name='tool2'),
            Mock(name='tool3')
        ])

        validator = MCPValidator({'test_server': mock_client})
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].server == 'test_server'
        assert results[0].status == ValidationStatus.SUCCESS
        assert 'tool' in results[0].message.lower()

    @pytest.mark.asyncio
    async def test_validate_client_with_no_tools(self):
        """Test validation of MCP client with no tools."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[])

        validator = MCPValidator({'empty_server': mock_client})
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].server == 'empty_server'
        assert results[0].status == ValidationStatus.FAILED
        assert 'no tools' in results[0].message.lower()

    @pytest.mark.asyncio
    async def test_validate_client_error(self):
        """Test validation when client throws error."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=Exception("Connection failed"))

        validator = MCPValidator({'error_server': mock_client})
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].server == 'error_server'
        assert results[0].status == ValidationStatus.ERROR
        assert 'Connection failed' in results[0].error_detail

    @pytest.mark.asyncio
    async def test_validate_multiple_clients(self):
        """Test validation of multiple MCP clients."""
        # Mock successful client
        mock_client1 = Mock()
        mock_client1.get_tools = AsyncMock(return_value=[Mock(name='tool1')])

        # Mock failed client
        mock_client2 = Mock()
        mock_client2.get_tools = AsyncMock(return_value=[])

        validator = MCPValidator({
            'success_server': mock_client1,
            'failed_server': mock_client2
        })
        results = await validator.validate_all()

        assert len(results) == 2

        # Check summary
        summary = validator.get_summary()
        assert summary['total'] == 2
        assert summary['success'] == 1
        assert summary['failed'] == 1
        assert summary['error'] == 0

    @pytest.mark.asyncio
    async def test_validation_timing(self):
        """Test that validation tracks duration."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[Mock(name='tool1')])

        validator = MCPValidator({'test_server': mock_client})
        results = await validator.validate_all()

        assert results[0].duration_ms is not None
        assert results[0].duration_ms >= 0


class TestValidationResults:
    """Test validation result data structures."""

    def test_validation_result_creation(self):
        """Test creating validation result."""
        result = MCPValidationResult(
            server='test_server',
            status=ValidationStatus.SUCCESS,
            message='All tools available',
            duration_ms=150
        )

        assert result.server == 'test_server'
        assert result.status == ValidationStatus.SUCCESS
        assert result.message == 'All tools available'
        assert result.duration_ms == 150
        assert result.error_detail is None

    def test_validation_result_with_error(self):
        """Test creating validation result with error."""
        result = MCPValidationResult(
            server='error_server',
            status=ValidationStatus.ERROR,
            message='Validation failed',
            error_detail='Connection timeout',
            duration_ms=5000
        )

        assert result.server == 'error_server'
        assert result.status == ValidationStatus.ERROR
        assert result.error_detail == 'Connection timeout'
