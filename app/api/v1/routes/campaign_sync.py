"""
Campaign Sync API Endpoints
For scheduled and manual campaign KPI syncing
"""

import os
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Depends, BackgroundTasks, status
from pydantic import BaseModel

from app.services.campaign_sync_service import CampaignSyncService
from app.core.auth import get_current_user
from app.models.users import Campaigner


router = APIRouter()

# Initialize service
sync_service = CampaignSyncService()


# Pydantic models for responses
class SyncSummaryResponse(BaseModel):
    """Response model for sync summary"""
    success: bool
    message: str
    kpi_goals_processed: int
    kpi_values_updated: int
    errors_count: int
    error_details: list
    duration_seconds: Optional[float] = None


class SyncStatusResponse(BaseModel):
    """Response model for sync status"""
    last_sync: Optional[str] = None
    next_scheduled_sync: str = "Daily at 2:00 AM (Jerusalem time)"


# Internal auth dependency
async def verify_internal_token(
    x_internal_auth_token: str = Header(..., alias="X-Internal-Auth-Token")
):
    """Verify internal auth token for Cloud Scheduler"""
    internal_token = os.getenv("INTERNAL_AUTH_TOKEN", "")
    if not internal_token:
        raise HTTPException(
            status_code=500,
            detail="Internal auth token not configured"
        )
    
    if x_internal_auth_token != internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )


@router.post("/internal/campaign-sync/scheduled", response_model=SyncSummaryResponse)
async def scheduled_campaign_sync(
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_internal_token)
):
    """
    Endpoint triggered by Cloud Scheduler daily at 2 AM
    Requires internal auth token
    """
    try:
        # Run sync in background
        result = sync_service.sync_all_kpi_goals()
        
        return SyncSummaryResponse(
            success=result["success"],
            message="Scheduled sync completed",
            kpi_goals_processed=result["kpi_goals_processed"],
            kpi_values_updated=result["kpi_values_updated"],
            errors_count=result["errors_count"],
            error_details=result.get("error_details", [])[:5],  # Limit to 5 errors in response
            duration_seconds=result.get("duration_seconds")
        )
    
    except Exception as e:
        print(f"❌ Error in scheduled sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/campaign-sync/sync-now", response_model=SyncSummaryResponse)
async def manual_sync_all(
    background_tasks: BackgroundTasks,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Manual sync for all customers
    Requires user authentication
    """
    try:
        # Run sync
        result = sync_service.sync_all_kpi_goals()
        
        return SyncSummaryResponse(
            success=result["success"],
            message=f"Sync completed by {current_user.email}",
            kpi_goals_processed=result["kpi_goals_processed"],
            kpi_values_updated=result["kpi_values_updated"],
            errors_count=result["errors_count"],
            error_details=result.get("error_details", [])[:10],  # Show more errors in manual sync
            duration_seconds=result.get("duration_seconds")
        )
    
    except Exception as e:
        print(f"❌ Error in manual sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/campaign-sync/sync-customer/{customer_id}", response_model=SyncSummaryResponse)
async def manual_sync_customer(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Manual sync for specific customer
    Requires user authentication
    """
    try:
        # Verify customer belongs to user's agency
        from app.config.database import get_session
        from app.models.users import Customer
        from sqlmodel import select
        
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if not customer or customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found or access denied"
                )
        
        # Run sync for this customer
        result = sync_service.sync_all_kpi_goals(customer_id=customer_id)
        
        return SyncSummaryResponse(
            success=result["success"],
            message=f"Sync completed for customer {customer_id}",
            kpi_goals_processed=result["kpi_goals_processed"],
            kpi_values_updated=result["kpi_values_updated"],
            errors_count=result["errors_count"],
            error_details=result.get("error_details", []),
            duration_seconds=result.get("duration_seconds")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in customer sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/campaign-sync/sync-campaign/{kpi_goal_id}", response_model=SyncSummaryResponse)
async def manual_sync_campaign(
    kpi_goal_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Manual sync for single campaign
    Requires user authentication
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import KpiGoal
        from sqlmodel import select
        
        with get_session() as session:
            # Get KPI goal
            kpi_goal = session.get(KpiGoal, kpi_goal_id)
            if not kpi_goal:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI goal not found"
                )
            
            # Verify customer belongs to user's agency
            from app.models.users import Customer
            customer = session.get(Customer, kpi_goal.customer_id)
            if not customer or customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            # Get connection and digital asset
            from app.models.analytics import Connection, DigitalAsset, AssetType
            
            if "Google Ads" in kpi_goal.advertising_channel or "Google" in kpi_goal.advertising_channel:
                connections = session.exec(
                    select(Connection, DigitalAsset).join(
                        DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                    ).where(
                        Connection.customer_id == kpi_goal.customer_id
                    )
                ).all()
                
                for connection, digital_asset in connections:
                    if digital_asset.provider == "Google Ads":
                        metrics = sync_service.fetch_google_ads_campaign_metrics(
                            kpi_goal.campaign_id, connection, digital_asset
                        )
                        if metrics:
                            sync_service.update_kpi_value(kpi_goal, metrics)
                        break
            
            elif "Facebook" in kpi_goal.advertising_channel:
                connections = session.exec(
                    select(Connection, DigitalAsset).join(
                        DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                    ).where(
                        Connection.customer_id == kpi_goal.customer_id
                    )
                ).all()
                
                for connection, digital_asset in connections:
                    if digital_asset.provider == "Facebook":
                        metrics = sync_service.fetch_facebook_campaign_metrics(
                            kpi_goal.campaign_id, connection, digital_asset
                        )
                        if metrics:
                            sync_service.update_kpi_value(kpi_goal, metrics)
                        break
        
        return SyncSummaryResponse(
            success=True,
            message="Campaign sync completed",
            kpi_goals_processed=1,
            kpi_values_updated=1,
            errors_count=0,
            error_details=[],
            duration_seconds=0
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in campaign sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/campaign-sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get last sync status and next scheduled run
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import KpiValue
        from sqlmodel import select, desc
        
        with get_session() as session:
            # Get most recently updated KPI value as indicator of last sync
            latest_kpi_value = session.exec(
                select(KpiValue).order_by(desc(KpiValue.updated_at))
            ).first()
            
            last_sync = latest_kpi_value.updated_at.isoformat() if latest_kpi_value else None
        
        return SyncStatusResponse(
            last_sync=last_sync,
            next_scheduled_sync="Daily at 2:00 AM (Jerusalem time)"
        )
    
    except Exception as e:
        print(f"❌ Error getting sync status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )

