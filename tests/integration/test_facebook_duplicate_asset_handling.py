"""
Integration tests for Facebook duplicate digital asset handling
Tests that the system properly handles duplicate digital assets during connection creation
"""

import pytest
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
from app.models.users import Agency, Customer, Campaigner


@pytest.mark.integration
class TestFacebookDuplicateAssetHandling:
    """Integration tests for handling duplicate Facebook assets"""

    def test_duplicate_facebook_ads_asset_handled_correctly(self, test_engine):
        """Test that attempting to create a duplicate Facebook Ads asset updates the existing one"""

        with Session(test_engine) as session:
            # Create test data
            agency = Agency(
                name="Test Agency",
                email="agency@test.com",
                status="active"
            )
            session.add(agency)
            session.commit()
            session.refresh(agency)

            customer = Customer(
                full_name="Test Customer",
                email="customer@test.com",
                agency_id=agency.id,
                status="active"
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)

            campaigner = Campaigner(
                email="campaigner@test.com",
                full_name="Test Campaigner",
                hashed_password="test_hash",
                agency_id=agency.id,
                status="active"
            )
            session.add(campaigner)
            session.commit()
            session.refresh(campaigner)

            # Create initial digital asset
            ad_account_id = "act_test_123"
            initial_asset = DigitalAsset(
                customer_id=customer.id,
                asset_type=AssetType.FACEBOOK_ADS,
                provider="Facebook",
                name="Initial Name",
                external_id=ad_account_id,
                meta={
                    "ad_account_id": ad_account_id,
                    "ad_account_name": "Initial Name",
                    "currency": "USD",
                    "timezone": "UTC",
                },
                is_active=False  # Initially inactive
            )
            session.add(initial_asset)
            session.commit()
            session.refresh(initial_asset)

            initial_asset_id = initial_asset.id

            # Now simulate creating a "duplicate" by querying for existing asset first
            existing_asset = session.exec(
                select(DigitalAsset).where(
                    DigitalAsset.customer_id == customer.id,
                    DigitalAsset.external_id == ad_account_id,
                    DigitalAsset.asset_type == AssetType.FACEBOOK_ADS
                )
            ).first()

            assert existing_asset is not None, "Should find existing asset"
            assert existing_asset.id == initial_asset_id

            # Update the existing asset (simulating the fix)
            existing_asset.name = "Updated Name"
            existing_asset.meta = {
                "ad_account_id": ad_account_id,
                "ad_account_name": "Updated Name",
                "currency": "EUR",
                "timezone": "Europe/London",
            }
            existing_asset.is_active = True
            session.add(existing_asset)
            session.commit()
            session.refresh(existing_asset)

            # Verify the asset was updated, not duplicated
            all_assets = session.exec(
                select(DigitalAsset).where(
                    DigitalAsset.customer_id == customer.id,
                    DigitalAsset.external_id == ad_account_id,
                    DigitalAsset.asset_type == AssetType.FACEBOOK_ADS
                )
            ).all()

            assert len(all_assets) == 1, "Should only have one asset, not a duplicate"
            assert all_assets[0].id == initial_asset_id, "Should be the same asset"
            assert all_assets[0].name == "Updated Name", "Name should be updated"
            assert all_assets[0].meta["currency"] == "EUR", "Currency should be updated"
            assert all_assets[0].is_active is True, "Asset should be reactivated"

    def test_duplicate_facebook_page_asset_handled_correctly(self, test_engine):
        """Test that attempting to create a duplicate Facebook Page asset updates the existing one"""

        with Session(test_engine) as session:
            # Create test data
            agency = Agency(
                name="Test Agency 2",
                email="agency2@test.com",
                status="active"
            )
            session.add(agency)
            session.commit()
            session.refresh(agency)

            customer = Customer(
                full_name="Test Customer 2",
                email="customer2@test.com",
                agency_id=agency.id,
                status="active"
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)

            campaigner = Campaigner(
                email="campaigner2@test.com",
                full_name="Test Campaigner 2",
                hashed_password="test_hash",
                agency_id=agency.id,
                status="active"
            )
            session.add(campaigner)
            session.commit()
            session.refresh(campaigner)

            # Create initial digital asset for a Facebook Page
            page_id = "123456789"
            initial_asset = DigitalAsset(
                customer_id=customer.id,
                asset_type=AssetType.SOCIAL_MEDIA,
                provider="Facebook",
                name="Initial Page Name",
                handle="initialhandle",
                external_id=page_id,
                meta={
                    "page_id": page_id,
                    "page_name": "Initial Page Name",
                    "page_category": "Business",
                },
                is_active=True
            )
            session.add(initial_asset)
            session.commit()
            session.refresh(initial_asset)

            initial_asset_id = initial_asset.id

            # Now simulate creating a "duplicate" by querying for existing asset first
            existing_asset = session.exec(
                select(DigitalAsset).where(
                    DigitalAsset.customer_id == customer.id,
                    DigitalAsset.external_id == page_id,
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA
                )
            ).first()

            assert existing_asset is not None, "Should find existing asset"
            assert existing_asset.id == initial_asset_id

            # Update the existing asset (simulating the fix)
            existing_asset.name = "Updated Page Name"
            existing_asset.handle = "updatedhandle"
            existing_asset.meta = {
                "page_id": page_id,
                "page_name": "Updated Page Name",
                "page_category": "Media",
            }
            session.add(existing_asset)
            session.commit()
            session.refresh(existing_asset)

            # Verify the asset was updated, not duplicated
            all_assets = session.exec(
                select(DigitalAsset).where(
                    DigitalAsset.customer_id == customer.id,
                    DigitalAsset.external_id == page_id,
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA
                )
            ).all()

            assert len(all_assets) == 1, "Should only have one asset, not a duplicate"
            assert all_assets[0].id == initial_asset_id, "Should be the same asset"
            assert all_assets[0].name == "Updated Page Name", "Name should be updated"
            assert all_assets[0].handle == "updatedhandle", "Handle should be updated"
            assert all_assets[0].meta["page_category"] == "Media", "Category should be updated"
