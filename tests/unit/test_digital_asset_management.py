"""
Unit tests for digital asset management
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from app.api.v1.routes.database_management import (
    delete_digital_asset,
    get_digital_asset_dependencies,
)
from app.models.analytics import DigitalAsset, Connection, AssetType
from fastapi import HTTPException


class TestDigitalAssetDeletion:
    @pytest.mark.asyncio
    @patch("app.api.v1.routes.database_management.get_session")
    async def test_delete_digital_asset_success_no_dependencies(self, mock_get_session):
        """Test successful deletion of digital asset with no dependencies"""
        # Mock session and asset
        mock_session = MagicMock()
        mock_asset = Mock(spec=DigitalAsset)
        mock_asset.id = 1
        mock_asset.name = "Test Asset"

        mock_session.get.return_value = mock_asset

        # Mock exec() to return an object with .all() method
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = []  # No connections
        mock_session.exec.return_value = mock_exec_result

        # Mock execute() to return an object with .fetchall() method
        mock_execute_result = MagicMock()
        mock_execute_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_execute_result

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Call the function
        result = await delete_digital_asset(1)

        # Assertions
        assert result["success"] is True
        assert result["message"] == "Digital asset deleted successfully"
        assert result["deleted"]["connections"] == 0
        assert result["deleted"]["campaign_mappings_updated"] == 0
        assert result["deleted"]["campaigns_affected"] == 0

        # Verify calls
        mock_session.get.assert_called_once_with(DigitalAsset, 1)
        mock_session.delete.assert_called_once_with(mock_asset)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.database_management.get_session")
    async def test_delete_digital_asset_with_connections(self, mock_get_session):
        """Test deletion of digital asset with connections"""
        # Mock session, asset, and connections
        mock_session = MagicMock()
        mock_asset = Mock(spec=DigitalAsset)
        mock_asset.id = 1
        mock_asset.name = "Test Asset"

        mock_connection1 = Mock(spec=Connection)
        mock_connection2 = Mock(spec=Connection)
        mock_connections = [mock_connection1, mock_connection2]

        mock_session.get.return_value = mock_asset

        # Mock exec() to return an object with .all() method
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = mock_connections
        mock_session.exec.return_value = mock_exec_result

        # Mock execute() to return an object with .fetchall() method
        mock_execute_result = MagicMock()
        mock_execute_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_execute_result

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Call the function
        result = await delete_digital_asset(1)

        # Assertions
        assert result["success"] is True
        assert result["deleted"]["connections"] == 2

        # Verify connections were deleted first
        assert mock_session.delete.call_count == 3  # 2 connections + 1 asset
        mock_session.delete.assert_any_call(mock_connection1)
        mock_session.delete.assert_any_call(mock_connection2)
        mock_session.delete.assert_any_call(mock_asset)

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.database_management.get_session")
    async def test_delete_digital_asset_not_found(self, mock_get_session):
        """Test deletion of non-existent digital asset"""
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Call the function and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await delete_digital_asset(999)

        assert exc_info.value.status_code == 404
        assert "Digital asset not found" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.database_management.get_session")
    async def test_get_digital_asset_dependencies(self, mock_get_session):
        """Test getting dependencies for a digital asset"""
        # Mock session, asset, and dependencies
        mock_session = MagicMock()
        mock_asset = Mock(spec=DigitalAsset)
        mock_asset.id = 1
        mock_asset.name = "Test Asset"
        mock_asset.asset_type = AssetType.GA4

        mock_connection = Mock(spec=Connection)
        mock_connections = [mock_connection]

        # Mock SQL results
        mock_campaigns_result = [Mock()]  # One campaign
        mock_mappings_result = [Mock(), Mock()]  # Two mappings

        mock_session.get.return_value = mock_asset

        # Mock exec() to return an object with .all() method
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = mock_connections
        mock_session.exec.return_value = mock_exec_result

        # Mock execute() to return objects with .fetchall() method
        mock_execute_campaigns = MagicMock()
        mock_execute_campaigns.fetchall.return_value = mock_campaigns_result
        mock_execute_mappings = MagicMock()
        mock_execute_mappings.fetchall.return_value = mock_mappings_result
        mock_session.execute.side_effect = [mock_execute_campaigns, mock_execute_mappings]

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Call the function
        result = await get_digital_asset_dependencies(1)

        # Assertions
        assert result["asset_id"] == 1
        assert result["asset_name"] == "Test Asset"
        assert result["asset_type"] == AssetType.GA4
        assert result["dependencies"]["connections"] == 1
        assert result["dependencies"]["campaigns"] == 1
        assert result["dependencies"]["campaign_mappings"] == 2
        assert result["can_delete"] is True

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.database_management.get_session")
    async def test_get_digital_asset_dependencies_not_found(self, mock_get_session):
        """Test getting dependencies for non-existent digital asset"""
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Call the function and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await get_digital_asset_dependencies(999)

        assert exc_info.value.status_code == 404
        assert "Digital asset not found" in exc_info.value.detail
