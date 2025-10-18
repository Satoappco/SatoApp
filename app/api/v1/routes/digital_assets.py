"""
Digital Assets API routes for fetching customer's connected services
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_

from app.core.auth import get_current_user
from app.models.users import Campaigner
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.config.database import get_session

router = APIRouter(prefix="/digital-assets", tags=["digital-assets"])


@router.get("/customer/{customer_id}")
async def get_customer_digital_assets(
    customer_id: int,
    current_campaigner: Campaigner = Depends(get_current_user),
    active_only: bool = Query(True, description="Return only active assets")
):
    """
    Get all digital assets (data sources) for a specific customer.
    Returns array of data source strings like ["ga4", "google_ads", "facebook"]
    
    This is used to send initial data_sources array to DialogCX.
    """
    try:
        with get_session() as session:
            # Build query conditions
            conditions = [
                DigitalAsset.customer_id == customer_id,
            ]
            
            if active_only:
                conditions.append(DigitalAsset.is_active == True)
            
            # Query digital assets
            statement = select(DigitalAsset).where(and_(*conditions))
            
            results = session.exec(statement).all()
            
            # Build data sources array of strings
            data_sources = []
            seen_sources = set()  # Track unique source names
            
            for digital_asset in results:
                # Map asset_type to data source name (from DataSource enum)
                source_name = _map_asset_type_to_source(digital_asset.asset_type)
                
                # Add to list if not already included
                if source_name not in seen_sources:
                    data_sources.append(source_name)
                    seen_sources.add(source_name)
            
            return {
                "success": True,
                "customer_id": customer_id,
                "data_sources": data_sources,  # Simple array of strings: ["ga4", "google_ads"]
                "total": len(data_sources)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get digital assets: {str(e)}"
        )


def _map_asset_type_to_source(asset_type: AssetType) -> str:
    """
    Map AssetType enum to DataSource enum string (from constants.py)
    Returns the string value from DataSource enum that matches the asset type
    """
    from app.core.constants import DataSource
    
    mapping = {
        AssetType.GA4: DataSource.GA4,  # "GA4"
        AssetType.GOOGLE_ADS: DataSource.GOOGLE_ADS,  # "google_ads"
        AssetType.FACEBOOK_ADS: DataSource.FACEBOOK_ADS,  # "facebook_ads"
        AssetType.SEARCH_CONSOLE: DataSource.GOOGLE_SEARCH_CONSOLE,  # "google_search_console"
        AssetType.SOCIAL_MEDIA: DataSource.FACEBOOK,  # "facebook" - Generic social media defaults to Facebook
        AssetType.ADVERTISING: "advertising",  # Generic advertising (not in DataSource enum yet)
        AssetType.EMAIL_MARKETING: "email_marketing",  # Not in DataSource enum yet
        AssetType.CRM: "crm",  # Not in DataSource enum yet
        AssetType.ECOMMERCE: "ecommerce",  # Not in DataSource enum yet
    }
    return mapping.get(asset_type, asset_type.value.lower())


@router.get("/customer/{customer_id}/summary")
async def get_customer_assets_summary(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a summary of digital assets by type for a customer.
    Useful for dashboard displays.
    """
    try:
        with get_session() as session:
            # Query all digital assets for this customer
            statement = select(DigitalAsset).where(
                DigitalAsset.customer_id == customer_id
            )
            
            assets = session.exec(statement).all()
            
            # Group by asset type
            summary = {}
            for asset in assets:
                asset_type = asset.asset_type.value
                if asset_type not in summary:
                    summary[asset_type] = {
                        "count": 0,
                        "active": 0,
                        "inactive": 0,
                        "providers": set()
                    }
                
                summary[asset_type]["count"] += 1
                if asset.is_active:
                    summary[asset_type]["active"] += 1
                else:
                    summary[asset_type]["inactive"] += 1
                summary[asset_type]["providers"].add(asset.provider)
            
            # Convert sets to lists for JSON serialization
            for asset_type in summary:
                summary[asset_type]["providers"] = list(summary[asset_type]["providers"])
            
            return {
                "success": True,
                "customer_id": customer_id,
                "summary": summary,
                "total_assets": len(assets)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get assets summary: {str(e)}"
        )
