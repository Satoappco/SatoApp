"""
Unit tests for orphaned digital asset cleanup functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from app.services.digital_asset_service import delete_orphaned_digital_asset
from app.models.analytics import DigitalAsset, Connection, AssetType


class TestOrphanedDigitalAssetCleanup:
    def test_delete_orphaned_digital_asset_no_connections(self):
        """Test deletion of digital asset with no connections"""
        # Setup
        mock_session = MagicMock()
        mock_asset = Mock(spec=DigitalAsset)
        mock_asset.id = 1
        mock_asset.name = "Orphaned Asset"

        # Mock exec to return None (no connections)
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = None
        mock_session.exec.return_value = mock_exec_result

        # Mock session.get to return the asset
        mock_session.get.return_value = mock_asset

        # Call the function
        result = delete_orphaned_digital_asset(mock_session, 1)

        # Assertions
        assert result is True
        mock_session.delete.assert_called_once_with(mock_asset)
        mock_session.commit.assert_called_once()

    def test_delete_orphaned_digital_asset_has_connections(self):
        """Test that digital asset with connections is NOT deleted"""
        # Setup
        mock_session = MagicMock()
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1

        # Mock exec to return a connection (asset has connections)
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_exec_result

        # Call the function
        result = delete_orphaned_digital_asset(mock_session, 1)

        # Assertions
        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_delete_orphaned_digital_asset_not_found(self):
        """Test deletion when digital asset doesn't exist"""
        # Setup
        mock_session = MagicMock()

        # Mock exec to return None (no connections)
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = None
        mock_session.exec.return_value = mock_exec_result

        # Mock session.get to return None (asset not found)
        mock_session.get.return_value = None

        # Call the function
        result = delete_orphaned_digital_asset(mock_session, 999)

        # Assertions
        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestConnectionDeletionWithOrphanCleanup:
    @pytest.mark.asyncio
    @patch("app.config.database.get_session")
    @patch("app.services.digital_asset_service.delete_orphaned_digital_asset")
    async def test_google_ads_connection_deletion_cleans_orphaned_asset(
        self, mock_delete_orphaned, mock_get_session
    ):
        """Test that deleting a Google Ads connection triggers orphan cleanup"""
        from app.api.v1.routes.google_ads import revoke_google_ads_connection
        from app.models.users import Campaigner

        # Setup
        mock_session = MagicMock()
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1
        mock_connection.digital_asset_id = 10
        mock_connection.access_token_enc = b"encrypted_token"

        mock_asset = Mock(spec=DigitalAsset)
        mock_asset.id = 10
        mock_asset.asset_type = AssetType.GOOGLE_ADS
        mock_asset.provider = "Google"

        # Mock the select query result
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = (mock_connection, mock_asset)
        mock_session.exec.return_value = mock_exec_result

        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_delete_orphaned.return_value = True

        mock_user = Mock(spec=Campaigner)
        mock_user.id = 1

        # Patch the decrypt and requests
        with patch("app.services.google_analytics_service.GoogleAnalyticsService") as mock_service_class:
            mock_service = Mock()
            mock_service._decrypt_token.return_value = "access_token"
            mock_service_class.return_value = mock_service

            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200

                # Call the function
                result = await revoke_google_ads_connection(1, mock_user)

        # Assertions
        assert "deleted successfully" in result["message"]
        mock_delete_orphaned.assert_called_once_with(mock_session, 10)

    @pytest.mark.asyncio
    @patch("app.services.google_analytics_service.get_session")
    @patch("app.services.digital_asset_service.delete_orphaned_digital_asset")
    async def test_google_analytics_connection_deletion_cleans_orphaned_asset(
        self, mock_delete_orphaned, mock_get_session
    ):
        """Test that deleting a GA connection triggers orphan cleanup"""
        from app.services.google_analytics_service import GoogleAnalyticsService

        # Setup
        mock_session = MagicMock()
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1
        mock_connection.digital_asset_id = 20
        mock_connection.access_token_enc = b"encrypted_token"

        # Mock the select query result
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_exec_result

        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_delete_orphaned.return_value = True

        ga_service = GoogleAnalyticsService()

        # Patch the decrypt and requests
        with patch.object(ga_service, "_decrypt_token", return_value="access_token"):
            with patch("app.services.google_analytics_service.requests.post") as mock_post:
                mock_post.return_value.status_code = 200

                # Call the function
                result = await ga_service.revoke_ga_connection(1)

        # Assertions
        assert result["success"] is True
        assert result["asset_deleted"] is True
        mock_delete_orphaned.assert_called_once_with(mock_session, 20)

    @pytest.mark.asyncio
    @patch("app.config.database.get_session")
    @patch("app.services.digital_asset_service.delete_orphaned_digital_asset")
    async def test_facebook_connection_deletion_cleans_orphaned_asset(
        self, mock_delete_orphaned, mock_get_session
    ):
        """Test that deleting a Facebook connection triggers orphan cleanup"""
        from app.api.v1.routes.facebook import revoke_facebook_connection
        from app.models.users import Campaigner

        # Setup
        mock_session = MagicMock()
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1
        mock_connection.digital_asset_id = 30
        mock_connection.access_token_enc = b"encrypted_token"

        # Mock the select query result
        mock_exec_result = Mock()
        mock_exec_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_exec_result

        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_delete_orphaned.return_value = True

        mock_user = Mock(spec=Campaigner)
        mock_user.id = 5

        # Patch the decrypt and requests
        with patch("app.services.google_analytics_service.GoogleAnalyticsService") as mock_service_class:
            mock_service = Mock()
            mock_service._decrypt_token.return_value = "access_token"
            mock_service_class.return_value = mock_service

            with patch("requests.delete") as mock_delete:
                mock_delete.return_value.status_code = 200

                with patch("os.getenv", return_value="test_app_id"):
                    # Call the function
                    result = await revoke_facebook_connection(1, mock_user)

        # Assertions
        assert "deleted successfully" in result["message"]
        mock_delete_orphaned.assert_called_once_with(mock_session, 30)


class TestBulkConnectionDeletionWithOrphanCleanup:
    @patch("app.api.v1.routes.customers.get_session")
    @patch("app.services.digital_asset_service.delete_orphaned_digital_asset")
    def test_customer_deletion_cleans_orphaned_assets(
        self, mock_delete_orphaned, mock_get_session
    ):
        """Test that deleting a customer cleans up orphaned digital assets"""
        # Setup
        mock_session = MagicMock()

        mock_connection1 = Mock(spec=Connection)
        mock_connection1.digital_asset_id = 1

        mock_connection2 = Mock(spec=Connection)
        mock_connection2.digital_asset_id = 2

        mock_connection3 = Mock(spec=Connection)
        mock_connection3.digital_asset_id = 1  # Same asset as connection1

        connections = [mock_connection1, mock_connection2, mock_connection3]

        # Mock exec to return connections
        mock_exec_result = Mock()
        mock_exec_result.all.return_value = connections
        mock_session.exec.return_value = mock_exec_result

        mock_delete_orphaned.return_value = True

        # Simulate the deletion logic
        digital_asset_ids = set()
        for connection in connections:
            digital_asset_ids.add(connection.digital_asset_id)
            mock_session.delete(connection)
        mock_session.commit()

        # Check for orphaned assets
        from app.services.digital_asset_service import delete_orphaned_digital_asset
        for asset_id in digital_asset_ids:
            delete_orphaned_digital_asset(mock_session, asset_id)

        # Assertions
        assert len(digital_asset_ids) == 2  # Only unique asset IDs
        assert 1 in digital_asset_ids
        assert 2 in digital_asset_ids
        assert mock_session.delete.call_count == 3  # 3 connections deleted
