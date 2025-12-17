"""
Digital Platform Service - Helper functions for managing digital platforms.

Provides upsert functionality to avoid duplicate digital platforms.
"""

from typing import Optional, Dict, Any
from sqlmodel import Session, select, and_
from app.models.analytics import DigitalPlatform, AssetType


def upsert_digital_platform(
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
) -> DigitalPlatform:
    """
    Create or update a digital platform.

    If a digital platform with the same (customer_id, external_id, asset_type) exists,
    it will be updated. Otherwise, a new one will be created.

    Args:
        session: Database session
        customer_id: Customer ID
        external_id: Platform's unique ID for this platform
        asset_type: Type of platform (GA4, GOOGLE_ADS, etc.)
        provider: Provider name (Google, Facebook, etc.)
        name: Human-readable name
        handle: Optional handle (@username, page name)
        url: Optional platform URL
        meta: Optional metadata dict
        is_active: Whether the platform is active

    Returns:
        DigitalPlatform: The created or updated digital platform
    """
    # Try to find existing platform
    statement = select(DigitalPlatform).where(
        and_(
            DigitalPlatform.customer_id == customer_id,
            DigitalPlatform.external_id == external_id,
            DigitalPlatform.asset_type == asset_type
        )
    )
    existing_platform = session.exec(statement).first()

    if existing_platform:
        # Update existing platform
        existing_platform.provider = provider
        existing_platform.name = name
        existing_platform.handle = handle
        existing_platform.url = url
        existing_platform.meta = meta or {}
        existing_platform.is_active = is_active
        session.add(existing_platform)
        session.commit()
        session.refresh(existing_platform)
        return existing_platform
    else:
        # Create new platform
        new_platform = DigitalPlatform(
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
        session.add(new_platform)
        session.commit()
        session.refresh(new_platform)
        return new_platform


def get_digital_platform(
    session: Session,
    customer_id: int,
    external_id: str,
    asset_type: AssetType
) -> Optional[DigitalPlatform]:
    """
    Get a digital platform by its unique identifiers.

    Args:
        session: Database session
        customer_id: Customer ID
        external_id: Platform's unique ID
        asset_type: Type of platform

    Returns:
        DigitalPlatform or None if not found
    """
    statement = select(DigitalPlatform).where(
        and_(
            DigitalPlatform.customer_id == customer_id,
            DigitalPlatform.external_id == external_id,
            DigitalPlatform.asset_type == asset_type
        )
    )
    return session.exec(statement).first()


def delete_orphaned_digital_platform(session: Session, digital_platform_id: int) -> bool:
    """
    Delete a digital platform if it has no connections.

    Args:
        session: Database session
        digital_platform_id: ID of the digital platform to check

    Returns:
        bool: True if the platform was deleted, False otherwise
    """
    from app.models.analytics import Connection

    # Check if the digital platform has any remaining connections
    statement = select(Connection).where(Connection.digital_platform_id == digital_platform_id)
    remaining_connections = session.exec(statement).first()

    if remaining_connections is None:
        # No connections remain, delete the digital platform
        platform = session.get(DigitalPlatform, digital_platform_id)
        if platform:
            session.delete(platform)
            session.commit()
            return True

    return False
