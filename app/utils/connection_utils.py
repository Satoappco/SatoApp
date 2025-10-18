"""
Connection utilities for database connection management
Centralizes connection-related operations
"""

from typing import List, Dict, Any, Optional
import logging
from sqlmodel import select, and_
from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType

logger = logging.getLogger(__name__)


def get_facebook_connections(campaigner_id: int, customer_id: int, asset_type: str = "SOCIAL_MEDIA") -> List[tuple]:
    """
    Get Facebook connections for user/subclient with priority for real Page IDs
    
    Args:
        campaigner_id: User ID
        customer_id: Subclient ID
        asset_type: Type of asset (SOCIAL_MEDIA or ADVERTISING)
        
    Returns:
        List of (Connection, DigitalAsset) tuples
    """
    with get_session() as session:
        statement = select(Connection, DigitalAsset).join(
            DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
        ).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.customer_id == customer_id,  # Now direct on connections table
                DigitalAsset.provider == "Facebook",
                DigitalAsset.asset_type == getattr(AssetType, asset_type),
                Connection.revoked == False
            )
        )
        
        results = session.exec(statement).all()
        
        # Separate real Page IDs from fake ones
        real_page_connections = []
        fake_page_connections = []
        
        for conn, asset in results:
            if asset.asset_id and not asset.asset_id.startswith("fake_"):
                real_page_connections.append((conn, asset))
            else:
                fake_page_connections.append((conn, asset))
        
        # Always return real Page ID connections first, never fake ones
        if real_page_connections:
            logger.info(f"✅ Using {len(real_page_connections)} REAL Facebook Page ID(s)")
            return real_page_connections
        elif fake_page_connections:
            logger.warning(f"⚠️ Found {len(fake_page_connections)} fake Facebook Page ID(s) - These will cause API errors!")
            return []  # Return empty list to avoid using fake Page IDs
        else:
            return results


def get_ga4_connections(campaigner_id: int, customer_id: int) -> List[tuple]:
    """
    Get GA4 connections for user/subclient
    
    Args:
        campaigner_id: User ID
        customer_id: Subclient ID
        
    Returns:
        List of (Connection, DigitalAsset) tuples
    """
    with get_session() as session:
        statement = select(Connection, DigitalAsset).join(
            DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
        ).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.customer_id == customer_id,  # Now direct on connections table
                DigitalAsset.provider == "Google Analytics",
                DigitalAsset.asset_type == AssetType.ANALYTICS,
                Connection.revoked == False
            )
        )
        
        return session.exec(statement).all()


def get_google_ads_connections(campaigner_id: int, customer_id: int) -> List[tuple]:
    """
    Get Google Ads connections for user/subclient
    
    Args:
        campaigner_id: User ID
        customer_id: Subclient ID
        
    Returns:
        List of (Connection, DigitalAsset) tuples
    """
    with get_session() as session:
        statement = select(Connection, DigitalAsset).join(
            DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
        ).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.customer_id == customer_id,  # Now direct on connections table
                DigitalAsset.provider == "Google Ads",
                DigitalAsset.asset_type == AssetType.ADVERTISING,
                Connection.revoked == False
            )
        )
        
        return session.exec(statement).all()


def get_connection_by_id(connection_id: int) -> Optional[tuple]:
    """
    Get connection by ID
    
    Args:
        connection_id: Connection ID
        
    Returns:
        (Connection, DigitalAsset) tuple or None
    """
    with get_session() as session:
        statement = select(Connection, DigitalAsset).join(
            DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
        ).where(Connection.id == connection_id)
        
        result = session.exec(statement).first()
        return result


def get_user_connections_summary(campaigner_id: int, customer_id: int) -> Dict[str, int]:
    """
    Get summary of user's connections by provider and type
    
    Args:
        campaigner_id: User ID
        customer_id: Subclient ID
        
    Returns:
        Dictionary with connection counts by provider and type
    """
    with get_session() as session:
        statement = select(DigitalAsset.provider, DigitalAsset.asset_type).join(
            Connection, Connection.digital_asset_id == DigitalAsset.id
        ).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.customer_id == customer_id,  # Now direct on connections table
                Connection.revoked == False
            )
        )
        
        results = session.exec(statement).all()
        
        summary = {}
        for provider, asset_type in results:
            key = f"{provider}_{asset_type.value}"
            summary[key] = summary.get(key, 0) + 1
        
        return summary


def validate_connection_access(campaigner_id: int, connection_id: int) -> bool:
    """
    Validate that a user has access to a specific connection
    
    Args:
        campaigner_id: User ID
        connection_id: Connection ID
        
    Returns:
        True if user has access, False otherwise
    """
    with get_session() as session:
        statement = select(Connection).join(
            DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
        ).where(
            and_(
                Connection.id == connection_id,
                Connection.campaigner_id == campaigner_id,
                Connection.revoked == False
            )
        )
        
        result = session.exec(statement).first()
        return result is not None
