"""
Digital Asset Service - Helper functions for managing digital assets.

Provides upsert functionality to avoid duplicate digital assets.
"""

from typing import Optional, Dict, Any
from sqlmodel import Session, select, and_
from app.models.analytics import DigitalAsset, AssetType


def upsert_digital_asset(
    session: Session,
    customer_id: int,
    external_id: str,
    asset_type: AssetType,
    provider: str,
    name: str,
    handle: Optional[str] = None,
    url: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    is_active: bool = True
) -> DigitalAsset:
    """
    Create or update a digital asset.

    If a digital asset with the same (customer_id, external_id, asset_type) exists,
    it will be updated. Otherwise, a new one will be created.

    Args:
        session: Database session
        customer_id: Customer ID
        external_id: Platform's unique ID for this asset
        asset_type: Type of asset (GA4, GOOGLE_ADS, etc.)
        provider: Provider name (Google, Facebook, etc.)
        name: Human-readable name
        handle: Optional handle (@username, page name)
        url: Optional asset URL
        meta: Optional metadata dict
        is_active: Whether the asset is active

    Returns:
        DigitalAsset: The created or updated digital asset
    """
    # Try to find existing asset
    statement = select(DigitalAsset).where(
        and_(
            DigitalAsset.customer_id == customer_id,
            DigitalAsset.external_id == external_id,
            DigitalAsset.asset_type == asset_type
        )
    )
    existing_asset = session.exec(statement).first()

    if existing_asset:
        # Update existing asset
        existing_asset.provider = provider
        existing_asset.name = name
        existing_asset.handle = handle
        existing_asset.url = url
        existing_asset.meta = meta or {}
        existing_asset.is_active = is_active
        session.add(existing_asset)
        session.commit()
        session.refresh(existing_asset)
        return existing_asset
    else:
        # Create new asset
        new_asset = DigitalAsset(
            customer_id=customer_id,
            external_id=external_id,
            asset_type=asset_type,
            provider=provider,
            name=name,
            handle=handle,
            url=url,
            meta=meta or {},
            is_active=is_active
        )
        session.add(new_asset)
        session.commit()
        session.refresh(new_asset)
        return new_asset


def get_digital_asset(
    session: Session,
    customer_id: int,
    external_id: str,
    asset_type: AssetType
) -> Optional[DigitalAsset]:
    """
    Get a digital asset by its unique identifiers.

    Args:
        session: Database session
        customer_id: Customer ID
        external_id: Platform's unique ID
        asset_type: Type of asset

    Returns:
        DigitalAsset or None if not found
    """
    statement = select(DigitalAsset).where(
        and_(
            DigitalAsset.customer_id == customer_id,
            DigitalAsset.external_id == external_id,
            DigitalAsset.asset_type == asset_type
        )
    )
    return session.exec(statement).first()
