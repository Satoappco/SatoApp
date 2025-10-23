"""
Database Management API routes
Handles CRUD operations for all database tables:
- KPI Catalog & KPI Goals
- Agent Config & Routing Rules
- Customer Logs & Detailed Execution Logs
- Digital Assets & Connections
- User Management (Campaigners, Agencies, Customers)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_
from pydantic import BaseModel, Field, ValidationError

from app.core.auth import get_current_user
from app.core.api_auth import verify_admin_token
from app.models.users import Campaigner, Agency, Customer
from app.models.analytics import KpiCatalog, KpiGoal, KpiValue, KpiSettings, DigitalAsset, Connection, UserPropertySelection
from app.models.agents import AgentConfig, RoutingRule, CustomerLog, DetailedExecutionLog
from app.config.database import get_session
from app.config.logging import get_logger

logger = get_logger(__name__)

# REMOVED IMPORTS (tables deleted from database):
# - PerformanceMetric, AnalyticsCache, NarrativeReport (deleted tables)
# - ChatMessage, WebhookEntry, AnalysisExecution (deleted tables)

router = APIRouter(prefix="/database", tags=["database-management"])


def _format_kpi_value(kpi_settings: List[KpiSettings], kpi_type: str, index: int) -> Optional[str]:
    """
    Format KPI value from KPI Settings into the expected string format.
    Returns formatted string like "CPA < 133.0 ₪" or None if not found.
    """
    try:
        # Find the KPI setting for the specified type and index
        matching_settings = [s for s in kpi_settings if s.kpi_type == kpi_type]
        
        if index <= len(matching_settings):
            setting = matching_settings[index - 1]  # index is 1-based
            return f"{setting.kpi_name} {setting.direction} {setting.default_value} {setting.unit}"
        
        return None
    except Exception as e:
        logger.error(f"Error formatting KPI value: {str(e)}")
        return None


# ===== Pydantic Schemas =====

class KpiCatalogCreate(BaseModel):
    """Schema for creating a KPI Catalog entry"""
    subtype: str = Field(max_length=50)
    primary_metric: str = Field(max_length=100)
    primary_submetrics: str
    secondary_metric: str = Field(max_length=100)
    secondary_submetrics: str
    lite_primary_metric: str = Field(max_length=100)
    lite_primary_submetrics: str
    lite_secondary_metric: str = Field(max_length=100)
    lite_secondary_submetrics: str


class KpiCatalogUpdate(BaseModel):
    """Schema for updating a KPI Catalog entry"""
    subtype: Optional[str] = Field(None, max_length=50)
    primary_metric: Optional[str] = Field(None, max_length=100)
    primary_submetrics: Optional[str] = None
    secondary_metric: Optional[str] = Field(None, max_length=100)
    secondary_submetrics: Optional[str] = None
    lite_primary_metric: Optional[str] = Field(None, max_length=100)
    lite_primary_submetrics: Optional[str] = None
    lite_secondary_metric: Optional[str] = Field(None, max_length=100)
    lite_secondary_submetrics: Optional[str] = None


class KpiSettingsCreate(BaseModel):
    """Schema for creating a KPI Settings entry (Admin-only)"""
    campaign_objective: str = Field(max_length=100)
    kpi_name: str = Field(max_length=255)
    kpi_type: str = Field(max_length=20)  # "Primary" or "Secondary"
    direction: str = Field(max_length=10)  # "<" or ">"
    default_value: float
    unit: str = Field(max_length=50)


class KpiSettingsUpdate(BaseModel):
    """Schema for updating a KPI Settings entry (Admin-only)"""
    campaign_objective: Optional[str] = Field(None, max_length=100)
    kpi_name: Optional[str] = Field(None, max_length=255)
    kpi_type: Optional[str] = Field(None, max_length=20)
    direction: Optional[str] = Field(None, max_length=10)
    default_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)


class KpiSettingsBulkUpdateItem(BaseModel):
    """Schema for individual KPI setting in bulk update"""
    id: int
    campaign_objective: Optional[str] = Field(None, max_length=100)
    kpi_name: Optional[str] = Field(None, max_length=255)
    kpi_type: Optional[str] = Field(None, max_length=20)
    direction: Optional[str] = Field(None, max_length=10)
    default_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)


class KpiSettingsBulkUpdate(BaseModel):
    """Schema for bulk updating multiple KPI Settings"""
    settings: List[KpiSettingsBulkUpdateItem] = Field(description="List of KPI settings to update")


class KpiGoalCreate(BaseModel):
    """Schema for creating a KPI Goal entry"""
    customer_id: int
    campaign_id: str = Field(max_length=50)
    campaign_name: str = Field(max_length=255)
    campaign_status: str = Field(max_length=50, default="ACTIVE")
    
    # Ad Group fields
    ad_group_id: Optional[int] = None
    ad_group_name: Optional[str] = Field(None, max_length=255)
    ad_group_status: Optional[str] = Field(None, max_length=50)
    
    # Ad fields
    ad_id: Optional[int] = None
    ad_name: Optional[str] = Field(None, max_length=255)
    ad_name_headline: Optional[str] = Field(None, max_length=500) #clear description for llm 
    ad_status: Optional[str] = Field(None, max_length=50)
    ad_score: Optional[int] = None
    
    # Campaign details
    advertising_channel: str = Field(max_length=100)
    campaign_objective: str = Field(max_length=100)
    daily_budget: Optional[float] = None
    target_audience: str = Field(max_length=255)
    
    # KPI Goals
    primary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_2: Optional[str] = Field(None, max_length=255)
    secondary_kpi_3: Optional[str] = Field(None, max_length=255)
    
    # Additional fields
    landing_page: Optional[str] = Field(None, max_length=500)


class KpiGoalUpdate(BaseModel):
    """Schema for updating a KPI Goal entry"""
    customer_id: Optional[int] = None
    campaign_id: Optional[str] = Field(None, max_length=50)
    campaign_name: Optional[str] = Field(None, max_length=255)
    campaign_status: Optional[str] = Field(None, max_length=50)
    
    # Ad Group fields
    ad_group_id: Optional[int] = None
    ad_group_name: Optional[str] = Field(None, max_length=255)
    ad_group_status: Optional[str] = Field(None, max_length=50)
    
    # Ad fields
    ad_id: Optional[int] = None
    ad_name: Optional[str] = Field(None, max_length=255)
    ad_name_headline: Optional[str] = Field(None, max_length=500)
    ad_status: Optional[str] = Field(None, max_length=50)
    ad_score: Optional[int] = None
    
    # Campaign details
    advertising_channel: Optional[str] = Field(None, max_length=100)
    campaign_objective: Optional[str] = Field(None, max_length=100)
    daily_budget: Optional[float] = None
    target_audience: Optional[str] = Field(None, max_length=255)
    
    # KPI Goals
    primary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_2: Optional[str] = Field(None, max_length=255)
    secondary_kpi_3: Optional[str] = Field(None, max_length=255)
    
    # Additional fields
    landing_page: Optional[str] = Field(None, max_length=500)


class DigitalAssetCreate(BaseModel):
    """Schema for creating a Digital Asset entry"""
    customer_id: int
    asset_type: str
    provider: str = Field(max_length=100)
    name: str = Field(max_length=255)
    handle: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    external_id: str = Field(max_length=255)
    meta: dict = Field(default_factory=dict)
    is_active: bool = True


class DigitalAssetUpdate(BaseModel):
    """Schema for updating a Digital Asset entry"""
    customer_id: Optional[int] = None
    asset_type: Optional[str] = None
    provider: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    handle: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    external_id: Optional[str] = Field(None, max_length=255)
    meta: Optional[dict] = None
    is_active: Optional[bool] = None


# ===== KPI Catalog Routes =====

@router.get("/catalog")
async def get_kpi_catalog(
    subtype: Optional[str] = Query(None, description="Filter by subtype"),
):
    """Get all KPI catalog entries (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(KpiCatalog)
            
            # Apply filters
            conditions = []
            if subtype:
                conditions.append(KpiCatalog.subtype == subtype)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(KpiCatalog.subtype, KpiCatalog.primary_metric)
            kpis = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(kpis),
                "kpis": [
                    {
                        "id": kpi.id,
                        "subtype": kpi.subtype,
                        "primary_metric": kpi.primary_metric,
                        "primary_submetrics": kpi.primary_submetrics,
                        "secondary_metric": kpi.secondary_metric,
                        "secondary_submetrics": kpi.secondary_submetrics,
                        "lite_primary_metric": kpi.lite_primary_metric,
                        "lite_primary_submetrics": kpi.lite_primary_submetrics,
                        "lite_secondary_metric": kpi.lite_secondary_metric,
                        "lite_secondary_submetrics": kpi.lite_secondary_submetrics,
                        "created_at": kpi.created_at.isoformat(),
                        "updated_at": kpi.updated_at.isoformat()
                    }
                    for kpi in kpis
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI catalog: {str(e)}"
        )


@router.get("/catalog/{kpi_id}")
async def get_kpi_catalog_item(
    kpi_id: int,
):
    """Get a specific KPI catalog entry"""
    try:
        with get_session() as session:
            kpi = session.get(KpiCatalog, kpi_id)
            
            if not kpi:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI not found"
                )
            
            return {
                "success": True,
                "kpi": {
                    "id": kpi.id,
                    "subtype": kpi.subtype,
                    "primary_metric": kpi.primary_metric,
                    "primary_submetrics": kpi.primary_submetrics,
                    "secondary_metric": kpi.secondary_metric,
                    "secondary_submetrics": kpi.secondary_submetrics,
                    "lite_primary_metric": kpi.lite_primary_metric,
                    "lite_primary_submetrics": kpi.lite_primary_submetrics,
                    "lite_secondary_metric": kpi.lite_secondary_metric,
                    "lite_secondary_submetrics": kpi.lite_secondary_submetrics,
                    "created_at": kpi.created_at.isoformat(),
                    "updated_at": kpi.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI: {str(e)}"
        )


@router.post("/catalog")
async def create_kpi_catalog(
    kpi_data: KpiCatalogCreate,
):
    """Create a new KPI catalog entry"""
    try:
        with get_session() as session:
            new_kpi = KpiCatalog(
                subtype=kpi_data.subtype,
                primary_metric=kpi_data.primary_metric,
                primary_submetrics=kpi_data.primary_submetrics,
                secondary_metric=kpi_data.secondary_metric,
                secondary_submetrics=kpi_data.secondary_submetrics,
                lite_primary_metric=kpi_data.lite_primary_metric,
                lite_primary_submetrics=kpi_data.lite_primary_submetrics,
                lite_secondary_metric=kpi_data.lite_secondary_metric,
                lite_secondary_submetrics=kpi_data.lite_secondary_submetrics,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_kpi)
            session.commit()
            session.refresh(new_kpi)
            
            return {
                "success": True,
                "message": "KPI created successfully",
                "kpi": {
                    "id": new_kpi.id,
                    "subtype": new_kpi.subtype,
                    "primary_metric": new_kpi.primary_metric,
                    "primary_submetrics": new_kpi.primary_submetrics,
                    "secondary_metric": new_kpi.secondary_metric,
                    "secondary_submetrics": new_kpi.secondary_submetrics,
                    "lite_primary_metric": new_kpi.lite_primary_metric,
                    "lite_primary_submetrics": new_kpi.lite_primary_submetrics,
                    "lite_secondary_metric": new_kpi.lite_secondary_metric,
                    "lite_secondary_submetrics": new_kpi.lite_secondary_submetrics,
                    "created_at": new_kpi.created_at.isoformat(),
                    "updated_at": new_kpi.updated_at.isoformat()
                }
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create KPI: {str(e)}"
        )


@router.put("/catalog/{kpi_id}")
async def update_kpi_catalog(
    kpi_id: int,
    kpi_data: KpiCatalogUpdate,
):
    """Update a KPI catalog entry"""
    try:
        with get_session() as session:
            kpi = session.get(KpiCatalog, kpi_id)
            
            if not kpi:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI not found"
                )
            
            # Update fields
            update_data = kpi_data.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(kpi, key, value)
            
            kpi.updated_at = datetime.utcnow()
            
            session.add(kpi)
            session.commit()
            session.refresh(kpi)
            
            return {
                "success": True,
                "message": "KPI updated successfully",
                "kpi": {
                    "id": kpi.id,
                    "subtype": kpi.subtype,
                    "primary_metric": kpi.primary_metric,
                    "primary_submetrics": kpi.primary_submetrics,
                    "secondary_metric": kpi.secondary_metric,
                    "secondary_submetrics": kpi.secondary_submetrics,
                    "lite_primary_metric": kpi.lite_primary_metric,
                    "lite_primary_submetrics": kpi.lite_primary_submetrics,
                    "lite_secondary_metric": kpi.lite_secondary_metric,
                    "lite_secondary_submetrics": kpi.lite_secondary_submetrics,
                    "created_at": kpi.created_at.isoformat(),
                    "updated_at": kpi.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KPI: {str(e)}"
        )


@router.delete("/catalog/{kpi_id}")
async def delete_kpi_catalog(
    kpi_id: int,
):
    """Delete a KPI catalog entry"""
    try:
        with get_session() as session:
            kpi = session.get(KpiCatalog, kpi_id)
            
            if not kpi:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI not found"
                )
            
            session.delete(kpi)
            session.commit()
            
            return {
                "success": True,
                "message": "KPI deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete KPI: {str(e)}"
        )


# ===== KPI Goals Routes =====

@router.get("/kpi-goals")
async def get_kpi_goals(
    customer_id: Optional[int] = Query(None, description="Filter by customer"),
    active_only: bool = Query(False, description="Return only active campaigns"),
    limit: int = Query(1000, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all KPI goals (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(KpiGoal)
            
            # Apply filters (no user filtering - this is admin tool)
            conditions = []
            if customer_id:
                conditions.append(KpiGoal.customer_id == customer_id)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(KpiGoal.created_at.desc()).offset(offset).limit(limit)
            campaigns = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(campaigns),
                "campaigns": [
                    {
                        "id": campaign.id,
                        "customer_id": campaign.customer_id,
                        "campaign_id": campaign.campaign_id,
                        "campaign_name": campaign.campaign_name,
                        "campaign_status": campaign.campaign_status,
                        "ad_group_id": campaign.ad_group_id,
                        "ad_group_name": campaign.ad_group_name,
                        "ad_group_status": campaign.ad_group_status,
                        "ad_id": campaign.ad_id,
                        "ad_name": campaign.ad_name,
                        "ad_name_headline": campaign.ad_name_headline,
                        "ad_status": campaign.ad_status,
                        "ad_score": campaign.ad_score,
                        "advertising_channel": campaign.advertising_channel,
                        "campaign_objective": campaign.campaign_objective,
                        "daily_budget": campaign.daily_budget,
                        "target_audience": campaign.target_audience,
                        "primary_kpi_1": campaign.primary_kpi_1,
                        "secondary_kpi_1": campaign.secondary_kpi_1,
                        "secondary_kpi_2": campaign.secondary_kpi_2,
                        "secondary_kpi_3": campaign.secondary_kpi_3,
                        "landing_page": campaign.landing_page,
                        "created_at": campaign.created_at.isoformat(),
                        "updated_at": campaign.updated_at.isoformat()
                    }
                    for campaign in campaigns
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI goals: {str(e)}"
        )


@router.get("/kpi-goals/{kpi_goal_id}")
async def get_kpi_goal(
    kpi_goal_id: int,
):
    """Get a specific KPI goal entry"""
    try:
        with get_session() as session:
            campaign = session.get(KpiGoal, kpi_goal_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI goal not found"
                )
            
            return {
                "success": True,
                "campaign": {
                    "id": campaign.id,
                    "customer_id": campaign.customer_id,
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "campaign_status": campaign.campaign_status,
                    "ad_group_id": campaign.ad_group_id,
                    "ad_group_name": campaign.ad_group_name,
                    "ad_group_status": campaign.ad_group_status,
                    "ad_id": campaign.ad_id,
                    "ad_name": campaign.ad_name,
                    "ad_name_headline": campaign.ad_name_headline,
                    "ad_status": campaign.ad_status,
                    "ad_score": campaign.ad_score,
                    "advertising_channel": campaign.advertising_channel,
                    "campaign_objective": campaign.campaign_objective,
                    "daily_budget": campaign.daily_budget,
                    "target_audience": campaign.target_audience,
                    "primary_kpi_1": campaign.primary_kpi_1,
                    "secondary_kpi_1": campaign.secondary_kpi_1,
                    "secondary_kpi_2": campaign.secondary_kpi_2,
                    "secondary_kpi_3": campaign.secondary_kpi_3,
                    "landing_page": campaign.landing_page,
                    "created_at": campaign.created_at.isoformat(),
                    "updated_at": campaign.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaign KPI: {str(e)}"
        )


@router.post("/kpi-goals")
async def create_kpi_goal(
    campaign_data: KpiGoalCreate,
):
    """Create a new campaign KPI entry"""
    try:
        with get_session() as session:
            new_campaign = KpiGoal(
                customer_id=campaign_data.customer_id,
                campaign_id=campaign_data.campaign_id,
                campaign_name=campaign_data.campaign_name,
                campaign_status=campaign_data.campaign_status,
                ad_group_id=campaign_data.ad_group_id,
                ad_group_name=campaign_data.ad_group_name,
                ad_group_status=campaign_data.ad_group_status,
                ad_id=campaign_data.ad_id,
                ad_name=campaign_data.ad_name,
                ad_name_headline=campaign_data.ad_name_headline,
                ad_status=campaign_data.ad_status,
                ad_score=campaign_data.ad_score,
                advertising_channel=campaign_data.advertising_channel,
                campaign_objective=campaign_data.campaign_objective,
                daily_budget=campaign_data.daily_budget,
                target_audience=campaign_data.target_audience,
                primary_kpi_1=campaign_data.primary_kpi_1,
                secondary_kpi_1=campaign_data.secondary_kpi_1,
                secondary_kpi_2=campaign_data.secondary_kpi_2,
                secondary_kpi_3=campaign_data.secondary_kpi_3,
                landing_page=campaign_data.landing_page,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_campaign)
            session.commit()
            session.refresh(new_campaign)
            
            # Auto-create corresponding KPI Values based on campaign objective
            try:
                # Get KPI Settings for this campaign objective
                kpi_settings = session.exec(
                    select(KpiSettings).where(KpiSettings.campaign_objective == new_campaign.campaign_objective)
                ).all()
                
                if kpi_settings:
                    # Create KPI Value entry with structured data from KPI Settings
                    new_kpi_value = KpiValue(
                        customer_id=new_campaign.customer_id,
                        campaign_id=new_campaign.campaign_id,
                        campaign_name=new_campaign.campaign_name,
                        campaign_status=new_campaign.campaign_status,
                        ad_group_id=new_campaign.ad_group_id,
                        ad_group_name=new_campaign.ad_group_name,
                        ad_group_status=new_campaign.ad_group_status,
                        ad_id=new_campaign.ad_id,
                        ad_name=new_campaign.ad_name,
                        ad_name_headline=new_campaign.ad_name_headline,
                        ad_status=new_campaign.ad_status,
                        ad_score=new_campaign.ad_score,
                        advertising_channel=new_campaign.advertising_channel,
                        campaign_objective=new_campaign.campaign_objective,
                        daily_budget=new_campaign.daily_budget,
                        target_audience=new_campaign.target_audience,
                        # Auto-populate KPI Values with structured data from KPI Settings
                        primary_kpi_1=_format_kpi_value(kpi_settings, "Primary", 1),
                        secondary_kpi_1=_format_kpi_value(kpi_settings, "Secondary", 1),
                        secondary_kpi_2=_format_kpi_value(kpi_settings, "Secondary", 2),
                        secondary_kpi_3=_format_kpi_value(kpi_settings, "Secondary", 3),
                        landing_page=new_campaign.landing_page,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    session.add(new_kpi_value)
                    session.commit()
                    logger.info(f"✅ Auto-created KPI Values for campaign {new_campaign.campaign_id}")
                else:
                    logger.warning(f"⚠️ No KPI Settings found for objective: {new_campaign.campaign_objective}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to auto-create KPI Values for campaign {new_campaign.campaign_id}: {str(e)}")
                # Don't fail the main operation if KPI Values creation fails
            
            return {
                "success": True,
                "message": "KPI goal created successfully",
                "campaign": {
                    "id": new_campaign.id,
                    "customer_id": new_campaign.customer_id,
                    "campaign_id": new_campaign.campaign_id,
                    "campaign_name": new_campaign.campaign_name,
                    "campaign_status": new_campaign.campaign_status,
                    "ad_group_id": new_campaign.ad_group_id,
                    "ad_group_name": new_campaign.ad_group_name,
                    "ad_group_status": new_campaign.ad_group_status,
                    "ad_id": new_campaign.ad_id,
                    "ad_name": new_campaign.ad_name,
                    "ad_name_headline": new_campaign.ad_name_headline,
                    "ad_status": new_campaign.ad_status,
                    "ad_score": new_campaign.ad_score,
                    "advertising_channel": new_campaign.advertising_channel,
                    "campaign_objective": new_campaign.campaign_objective,
                    "daily_budget": new_campaign.daily_budget,
                    "target_audience": new_campaign.target_audience,
                    "primary_kpi_1": new_campaign.primary_kpi_1,
                    "secondary_kpi_1": new_campaign.secondary_kpi_1,
                    "secondary_kpi_2": new_campaign.secondary_kpi_2,
                    "secondary_kpi_3": new_campaign.secondary_kpi_3,
                    "landing_page": new_campaign.landing_page,
                    "created_at": new_campaign.created_at.isoformat(),
                    "updated_at": new_campaign.updated_at.isoformat()
                }
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign KPI: {str(e)}"
        )


@router.put("/kpi-goals/{kpi_goal_id}")
async def update_kpi_goal(
    kpi_goal_id: int,
    campaign_data: KpiGoalUpdate,
):
    """Update a campaign KPI entry"""
    try:
        with get_session() as session:
            campaign = session.get(KpiGoal, kpi_goal_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI goal not found"
                )
            
            # Update fields
            update_data = campaign_data.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(campaign, key, value)
            
            campaign.updated_at = datetime.utcnow()
            
            session.add(campaign)
            session.commit()
            session.refresh(campaign)
            
            return {
                "success": True,
                "message": "KPI goal updated successfully",
                "campaign": {
                    "id": campaign.id,
                    "customer_id": campaign.customer_id,
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "campaign_status": campaign.campaign_status,
                    "ad_group_id": campaign.ad_group_id,
                    "ad_group_name": campaign.ad_group_name,
                    "ad_group_status": campaign.ad_group_status,
                    "ad_id": campaign.ad_id,
                    "ad_name": campaign.ad_name,
                    "ad_name_headline": campaign.ad_name_headline,
                    "ad_status": campaign.ad_status,
                    "ad_score": campaign.ad_score,
                    "advertising_channel": campaign.advertising_channel,
                    "campaign_objective": campaign.campaign_objective,
                    "daily_budget": campaign.daily_budget,
                    "target_audience": campaign.target_audience,
                    "primary_kpi_1": campaign.primary_kpi_1,
                    "secondary_kpi_1": campaign.secondary_kpi_1,
                    "secondary_kpi_2": campaign.secondary_kpi_2,
                    "secondary_kpi_3": campaign.secondary_kpi_3,
                    "landing_page": campaign.landing_page,
                    "created_at": campaign.created_at.isoformat(),
                    "updated_at": campaign.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign KPI: {str(e)}"
        )


@router.delete("/kpi-goals/{kpi_goal_id}")
async def delete_kpi_goal(
    kpi_goal_id: int,
):
    """Delete a campaign KPI entry"""
    try:
        with get_session() as session:
            campaign = session.get(KpiGoal, kpi_goal_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI goal not found"
                )
            
            # Auto-delete corresponding KPI Values
            try:
                # Find and delete KPI Values with matching campaign_id
                kpi_values = session.exec(
                    select(KpiValue).where(KpiValue.campaign_id == campaign.campaign_id)
                ).all()
                
                for kpi_value in kpi_values:
                    session.delete(kpi_value)
                
                logger.info(f"✅ Auto-deleted {len(kpi_values)} KPI Values for campaign {campaign.campaign_id}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to auto-delete KPI Values for campaign {campaign.campaign_id}: {str(e)}")
                # Don't fail the main operation if KPI Values deletion fails
            
            session.delete(campaign)
            session.commit()
            
            return {
                "success": True,
                "message": "KPI goal deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign KPI: {str(e)}"
        )


# ===== KPI Values Routes =====

@router.get("/kpi-values")
async def get_kpi_values(
    customer_id: Optional[int] = Query(None, description="Filter by customer"),
    active_only: bool = Query(False, description="Return only active campaigns"),
    limit: int = Query(1000, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all KPI values (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(KpiValue)
            
            # Apply filters
            conditions = []
            if active_only:
                conditions.append(KpiValue.is_active == True)
            if customer_id:
                conditions.append(KpiValue.customer_id == customer_id)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(KpiValue.created_at.desc()).offset(offset).limit(limit)
            campaigns = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(campaigns),
                "campaigns": [
                    {
                        "id": campaign.id,
                        "customer_id": campaign.customer_id,
                        "campaign_id": campaign.campaign_id,
                        "campaign_name": campaign.campaign_name,
                        "campaign_status": campaign.campaign_status,
                        "ad_group_id": campaign.ad_group_id,
                        "ad_group_name": campaign.ad_group_name,
                        "ad_group_status": campaign.ad_group_status,
                        "ad_id": campaign.ad_id,
                        "ad_name": campaign.ad_name,
                        "ad_name_headline": campaign.ad_name_headline,
                        "ad_status": campaign.ad_status,
                        "ad_score": campaign.ad_score,
                        "advertising_channel": campaign.advertising_channel,
                        "campaign_objective": campaign.campaign_objective,
                        "daily_budget": campaign.daily_budget,
                        "target_audience": campaign.target_audience,
                        "primary_kpi_1": campaign.primary_kpi_1,
                        "secondary_kpi_1": campaign.secondary_kpi_1,
                        "secondary_kpi_2": campaign.secondary_kpi_2,
                        "secondary_kpi_3": campaign.secondary_kpi_3,
                        "landing_page": campaign.landing_page,
                        "created_at": campaign.created_at.isoformat(),
                        "updated_at": campaign.updated_at.isoformat()
                    }
                    for campaign in campaigns
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI values: {str(e)}"
        )


@router.post("/kpi-values")
async def create_kpi_value(
    campaign_data: dict,
):
    """Create a new KPI value entry"""
    try:
        with get_session() as session:
            new_campaign = KpiValue(
                customer_id=campaign_data.get('customer_id'),
                campaign_id=campaign_data.get('campaign_id'),
                campaign_name=campaign_data.get('campaign_name'),
                campaign_status=campaign_data.get('campaign_status', 'ACTIVE'),
                ad_group_id=campaign_data.get('ad_group_id'),
                ad_group_name=campaign_data.get('ad_group_name'),
                ad_group_status=campaign_data.get('ad_group_status'),
                ad_id=campaign_data.get('ad_id'),
                ad_name=campaign_data.get('ad_name'),
                ad_name_headline=campaign_data.get('ad_name_headline'),
                ad_status=campaign_data.get('ad_status'),
                ad_score=campaign_data.get('ad_score'),
                advertising_channel=campaign_data.get('advertising_channel'),
                campaign_objective=campaign_data.get('campaign_objective'),
                daily_budget=campaign_data.get('daily_budget'),
                target_audience=campaign_data.get('target_audience'),
                primary_kpi_1=campaign_data.get('primary_kpi_1'),
                secondary_kpi_1=campaign_data.get('secondary_kpi_1'),
                secondary_kpi_2=campaign_data.get('secondary_kpi_2'),
                secondary_kpi_3=campaign_data.get('secondary_kpi_3'),
                landing_page=campaign_data.get('landing_page'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_campaign)
            session.commit()
            session.refresh(new_campaign)
            
            return {
                "success": True,
                "message": "KPI value created successfully",
                "campaign": {
                    "id": new_campaign.id,
                    "customer_id": new_campaign.customer_id,
                    "campaign_id": new_campaign.campaign_id,
                    "campaign_name": new_campaign.campaign_name,
                    "campaign_status": new_campaign.campaign_status,
                    "ad_group_id": new_campaign.ad_group_id,
                    "ad_group_name": new_campaign.ad_group_name,
                    "ad_group_status": new_campaign.ad_group_status,
                    "ad_id": new_campaign.ad_id,
                    "ad_name": new_campaign.ad_name,
                    "ad_name_headline": new_campaign.ad_name_headline,
                    "ad_status": new_campaign.ad_status,
                    "ad_score": new_campaign.ad_score,
                    "advertising_channel": new_campaign.advertising_channel,
                    "campaign_objective": new_campaign.campaign_objective,
                    "daily_budget": new_campaign.daily_budget,
                    "target_audience": new_campaign.target_audience,
                    "primary_kpi_1": new_campaign.primary_kpi_1,
                    "secondary_kpi_1": new_campaign.secondary_kpi_1,
                    "secondary_kpi_2": new_campaign.secondary_kpi_2,
                    "secondary_kpi_3": new_campaign.secondary_kpi_3,
                    "landing_page": new_campaign.landing_page,
                    "created_at": new_campaign.created_at.isoformat(),
                    "updated_at": new_campaign.updated_at.isoformat()
                }
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create KPI value: {str(e)}"
        )


@router.put("/kpi-values/{kpi_value_id}")
async def update_kpi_value(
    kpi_value_id: int,
    campaign_data: dict,
):
    """Update a KPI value entry"""
    try:
        with get_session() as session:
            campaign = session.get(KpiValue, kpi_value_id)
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI value not found"
                )
            
            # Update fields
            for field, value in campaign_data.items():
                if hasattr(campaign, field) and value is not None:
                    setattr(campaign, field, value)
            
            campaign.updated_at = datetime.utcnow()
            session.add(campaign)
            session.commit()
            session.refresh(campaign)
            
            return {
                "success": True,
                "message": "KPI value updated successfully",
                "campaign": {
                    "id": campaign.id,
                    "customer_id": campaign.customer_id,
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "campaign_status": campaign.campaign_status,
                    "ad_group_id": campaign.ad_group_id,
                    "ad_group_name": campaign.ad_group_name,
                    "ad_group_status": campaign.ad_group_status,
                    "ad_id": campaign.ad_id,
                    "ad_name": campaign.ad_name,
                    "ad_name_headline": campaign.ad_name_headline,
                    "ad_status": campaign.ad_status,
                    "ad_score": campaign.ad_score,
                    "advertising_channel": campaign.advertising_channel,
                    "campaign_objective": campaign.campaign_objective,
                    "daily_budget": campaign.daily_budget,
                    "target_audience": campaign.target_audience,
                    "primary_kpi_1": campaign.primary_kpi_1,
                    "secondary_kpi_1": campaign.secondary_kpi_1,
                    "secondary_kpi_2": campaign.secondary_kpi_2,
                    "secondary_kpi_3": campaign.secondary_kpi_3,
                    "landing_page": campaign.landing_page,
                    "created_at": campaign.created_at.isoformat(),
                    "updated_at": campaign.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KPI value: {str(e)}"
        )


@router.delete("/kpi-values/{kpi_value_id}")
async def delete_kpi_value(
    kpi_value_id: int,
):
    """Delete a KPI value entry"""
    try:
        with get_session() as session:
            campaign = session.get(KpiValue, kpi_value_id)
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI value not found"
                )
            
            session.delete(campaign)
            session.commit()
            
            return {
                "success": True,
                "message": "KPI value deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete KPI value: {str(e)}"
        )


# ===== Categories Route =====

@router.get("/catalog/subtypes/list")
async def get_kpi_subtypes(
):
    """Get all unique KPI subtypes"""
    try:
        with get_session() as session:
            statement = select(KpiCatalog.subtype).distinct()
            subtypes = session.exec(statement).all()
            
            return {
                "success": True,
                "subtypes": subtypes
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
        )


# ===== Agent Config Routes =====

@router.get("/agent-configs")
async def get_agent_configs(
    active_only: bool = Query(False, description="Return only active agents"),
):
    """Get all agent configurations (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(AgentConfig)
            
            if active_only:
                statement = statement.where(AgentConfig.is_active == True)
            
            statement = statement.order_by(AgentConfig.agent_type, AgentConfig.name)
            agents = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(agents),
                "agents": [
                    {
                        "id": agent.id,
                        "agent_type": agent.agent_type,
                        "name": agent.name,
                        "role": agent.role,
                        "goal": agent.goal,
                        "backstory": agent.backstory,
                        "task": agent.task,
                        "capabilities": agent.capabilities,
                        "tools": agent.tools,
                        "prompt_template": agent.prompt_template,
                        "output_schema": agent.output_schema,
                        "max_iterations": agent.max_iterations,
                        "allow_delegation": agent.allow_delegation,
                        "verbose": agent.verbose,
                        "is_active": agent.is_active,
                        "created_by_user_id": agent.created_by_user_id,
                        "created_at": agent.created_at.isoformat(),
                        "updated_at": agent.updated_at.isoformat()
                    }
                    for agent in agents
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch agent configs: {str(e)}"
        )


@router.get("/routing-rules")
async def get_routing_rules(
    active_only: bool = Query(False, description="Return only active rules"),
):
    """Get all routing rules (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(RoutingRule)
            
            if active_only:
                statement = statement.where(RoutingRule.is_active == True)
            
            statement = statement.order_by(RoutingRule.priority.desc(), RoutingRule.intent_pattern)
            rules = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(rules),
                "rules": [
                    {
                        "id": rule.id,
                        "intent_pattern": rule.intent_pattern,
                        "required_specialists": rule.required_specialists,
                        "conditions": rule.conditions,
                        "priority": rule.priority,
                        "is_active": rule.is_active,
                        "created_at": rule.created_at.isoformat(),
                        "updated_at": rule.updated_at.isoformat()
                    }
                    for rule in rules
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch routing rules: {str(e)}"
        )





# ===== User Management Routes =====

@router.get("/users")
async def get_users(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all users (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(Campaigner)
            statement = statement.order_by(Campaigner.created_at.desc()).offset(offset).limit(limit)
            users = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(users),
                "users": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                        "phone": user.phone,
                        "role": user.role,
                        "status": user.status,
                        "agency_id": user.agency_id,
                        "created_at": user.created_at.isoformat(),
                        "updated_at": user.updated_at.isoformat()
                    }
                    for user in users
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@router.get("/customers")
async def get_customers(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all customers (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(Customer)
            statement = statement.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
            customers = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(customers),
                "customers": [
                    {
                        "id": customer.id,
                        "name": customer.name,
                        "type": customer.type,
                        "status": customer.status,
                        "plan": customer.plan,
                        "billing_currency": customer.billing_currency,
                        "vat_id": customer.vat_id,
                        "address": customer.address,
                        "primary_contact_user_id": customer.primary_contact_user_id,
                        "domains": customer.domains,
                        "tags": customer.tags,
                        "notes": customer.notes,
                        "created_at": customer.created_at.isoformat(),
                        "updated_at": customer.updated_at.isoformat()
                    }
                    for customer in customers
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customers: {str(e)}"
        )


@router.get("/customers")
async def get_customers(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all customers (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(Customer)
            statement = statement.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
            customers = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(customers),
                "customers": [
                    {
                        "id": customer.id,
                        "agency_id": customer.agency_id,
                        "full_name": customer.full_name,
                        "contact_email": customer.contact_email,
                        "phone": customer.phone,
                        "address": customer.address,
                        "opening_hours": customer.opening_hours,
                        "narrative_report": customer.narrative_report,
                        "website_url": customer.website_url,
                        "facebook_page_url": customer.facebook_page_url,
                        "instagram_page_url": customer.instagram_page_url,
                        "llm_engine_preference": customer.llm_engine_preference,
                        "status": customer.status,
                        "is_active": customer.is_active,
                        "created_at": customer.created_at.isoformat(),
                        "updated_at": customer.updated_at.isoformat()
                    }
                    for customer in customers
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sub-customers: {str(e)}"
        )


@router.get("/digital-assets")
async def get_digital_assets(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    active_only: bool = Query(False, description="Return only active assets"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get digital assets with optional filtering by customer"""
    try:
        with get_session() as session:
            statement = select(DigitalAsset)
            
            # Apply filters
            conditions = []
            if customer_id:
                conditions.append(DigitalAsset.customer_id == customer_id)
            if active_only:
                conditions.append(DigitalAsset.is_active == True)
            if asset_type:
                conditions.append(DigitalAsset.asset_type == asset_type)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(DigitalAsset.created_at.desc()).offset(offset).limit(limit)
            assets = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(assets),
                "assets": [
                    {
                        "id": asset.id,
                        "customer_id": asset.customer_id,
                        "asset_type": asset.asset_type,
                        "provider": asset.provider,
                        "name": asset.name,
                        "handle": asset.handle,
                        "url": asset.url,
                        "external_id": asset.external_id,
                        "metadata": asset.meta,
                        "is_active": asset.is_active,
                        "created_at": asset.created_at.isoformat(),
                        "updated_at": asset.updated_at.isoformat()
                    }
                    for asset in assets
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch digital assets: {str(e)}"
        )


@router.get("/digital-assets/{asset_id}")
async def get_digital_asset(
    asset_id: int,
):
    """Get a specific digital asset"""
    try:
        with get_session() as session:
            asset = session.get(DigitalAsset, asset_id)
            
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Digital asset not found"
                )
            
            return {
                "success": True,
                "asset": {
                    "id": asset.id,
                    "customer_id": asset.customer_id,
                    "asset_type": asset.asset_type,
                    "provider": asset.provider,
                    "name": asset.name,
                    "handle": asset.handle,
                    "url": asset.url,
                    "external_id": asset.external_id,
                    "metadata": asset.meta,
                    "is_active": asset.is_active,
                    "created_at": asset.created_at.isoformat(),
                    "updated_at": asset.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch digital asset: {str(e)}"
        )


@router.post("/digital-assets")
async def create_digital_asset(
    asset_data: DigitalAssetCreate,
):
    """Create a new digital asset"""
    try:
        with get_session() as session:
            # Verify customer exists
            customer = session.get(Customer, asset_data.customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer with ID {asset_data.customer_id} not found"
                )
            
            new_asset = DigitalAsset(
                customer_id=asset_data.customer_id,
                asset_type=asset_data.asset_type,
                provider=asset_data.provider,
                name=asset_data.name,
                handle=asset_data.handle,
                url=asset_data.url,
                external_id=asset_data.external_id,
                meta=asset_data.meta,
                is_active=asset_data.is_active
            )
            
            session.add(new_asset)
            session.commit()
            session.refresh(new_asset)
            
            return {
                "success": True,
                "message": "Digital asset created successfully",
                "asset": {
                    "id": new_asset.id,
                    "customer_id": new_asset.customer_id,
                    "asset_type": new_asset.asset_type,
                    "provider": new_asset.provider,
                    "name": new_asset.name,
                    "handle": new_asset.handle,
                    "url": new_asset.url,
                    "external_id": new_asset.external_id,
                    "metadata": new_asset.meta,
                    "is_active": new_asset.is_active,
                    "created_at": new_asset.created_at.isoformat(),
                    "updated_at": new_asset.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create digital asset: {str(e)}"
        )


@router.put("/digital-assets/{asset_id}")
async def update_digital_asset(
    asset_id: int,
    asset_data: DigitalAssetUpdate,
):
    """Update a digital asset"""
    try:
        with get_session() as session:
            asset = session.get(DigitalAsset, asset_id)
            
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Digital asset not found"
                )
            
            # Update only provided fields
            update_data = asset_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(asset, field, value)
            
            asset.updated_at = datetime.utcnow()
            
            session.add(asset)
            session.commit()
            session.refresh(asset)
            
            return {
                "success": True,
                "message": "Digital asset updated successfully",
                "asset": {
                    "id": asset.id,
                    "customer_id": asset.customer_id,
                    "asset_type": asset.asset_type,
                    "provider": asset.provider,
                    "name": asset.name,
                    "handle": asset.handle,
                    "url": asset.url,
                    "external_id": asset.external_id,
                    "metadata": asset.meta,
                    "is_active": asset.is_active,
                    "created_at": asset.created_at.isoformat(),
                    "updated_at": asset.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update digital asset: {str(e)}"
        )


@router.delete("/digital-assets/{asset_id}")
async def delete_digital_asset(
    asset_id: int,
):
    """Delete a digital asset"""
    try:
        with get_session() as session:
            asset = session.get(DigitalAsset, asset_id)
            
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Digital asset not found"
                )
            
            session.delete(asset)
            session.commit()
            
            return {
                "success": True,
                "message": "Digital asset deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete digital asset: {str(e)}"
        )


@router.get("/connections")
async def get_connections(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all connections (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(Connection)
            statement = statement.order_by(Connection.created_at.desc()).offset(offset).limit(limit)
            connections = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(connections),
                "connections": [
                    {
                        "id": conn.id,
                        "digital_asset_id": conn.digital_asset_id,
                        "customer_id": conn.customer_id,
                        "campaigner_id": conn.campaigner_id,
                        "auth_type": conn.auth_type,
                        "account_email": conn.account_email,
                        "scopes": conn.scopes,
                        "expires_at": conn.expires_at.isoformat() if conn.expires_at else None,
                        "revoked": conn.revoked,
                        "rotated_at": conn.rotated_at.isoformat() if conn.rotated_at else None,
                        "last_used_at": conn.last_used_at.isoformat() if conn.last_used_at else None,
                        "created_at": conn.created_at.isoformat(),
                        "updated_at": conn.updated_at.isoformat()
                    }
                    for conn in connections
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch connections: {str(e)}"
        )


@router.get("/user-property-selections")
async def get_user_property_selections(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all user property selections (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(UserPropertySelection)
            statement = statement.order_by(UserPropertySelection.created_at.desc()).offset(offset).limit(limit)
            selections = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(selections),
                "selections": [
                    {
                        "id": sel.id,
                        "user_id": sel.user_id,
                        "customer_id": sel.customer_id,
                        "service": sel.service,
                        "selected_property_id": sel.selected_property_id,
                        "property_name": sel.property_name,
                        "is_active": sel.is_active,
                        "created_at": sel.created_at.isoformat(),
                        "updated_at": sel.updated_at.isoformat()
                    }
                    for sel in selections
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user property selections: {str(e)}"
        )




@router.get("/customer-logs")
async def get_customer_logs(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all customer logs (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(CustomerLog)
            statement = statement.order_by(CustomerLog.date_time.desc()).offset(offset).limit(limit)
            logs = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(logs),
                "logs": [
                    {
                        "id": log.id,
                        "session_id": log.session_id,
                        "date_time": log.date_time.isoformat(),
                        "user_intent": log.user_intent,
                        "original_query": log.original_query,
                        "crewai_input_prompt": log.crewai_input_prompt,
                        "master_answer": log.master_answer,
                        "crewai_log": log.crewai_log,
                        "total_execution_time_ms": log.total_execution_time_ms,
                        "timing_breakdown": log.timing_breakdown,
                        "campaigner_id": log.campaigner_id,
                        "analysis_id": log.analysis_id,
                        "success": log.success,
                        "error_message": log.error_message,
                        "agents_used": log.agents_used,
                        "tools_used": log.tools_used,
                        "created_at": log.created_at.isoformat(),
                        "updated_at": log.updated_at.isoformat()
                    }
                    for log in logs
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customer logs: {str(e)}"
        )


# Execution timings endpoint removed - functionality consolidated into customer_logs


@router.get("/detailed-execution-logs")
async def get_detailed_execution_logs(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all detailed execution logs (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(DetailedExecutionLog)
            statement = statement.order_by(DetailedExecutionLog.timestamp.desc()).offset(offset).limit(limit)
            logs = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(logs),
                "logs": [
                    {
                        "id": log.id,
                        "session_id": log.session_id,
                        "analysis_id": log.analysis_id,
                        "timestamp": log.timestamp.isoformat(),
                        "sequence_number": log.sequence_number,
                        "log_type": log.log_type,
                        "parent_log_id": log.parent_log_id,
                        "depth_level": log.depth_level,
                        "crew_id": log.crew_id,
                        "task_id": log.task_id,
                        "agent_name": log.agent_name,
                        "tool_name": log.tool_name,
                        "status": log.status,
                        "duration_ms": log.duration_ms,
                        "title": log.title,
                        "content": log.content,
                        "input_data": log.input_data,
                        "output_data": log.output_data,
                        "error_details": log.error_details,
                        "log_metadata": log.log_metadata,
                        "icon": log.icon,
                        "color": log.color,
                        "is_collapsible": log.is_collapsible,
                        "created_at": log.created_at.isoformat(),
                        "updated_at": log.updated_at.isoformat()
                    }
                    for log in logs
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch detailed execution logs: {str(e)}"
        )


# ===== KPI Settings Routes (Admin-only) =====

@router.get("/kpi-settings")
async def get_kpi_settings(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get all KPI settings (public read access)"""
    try:
        with get_session() as session:
            statement = select(KpiSettings).offset(offset).limit(limit)
            settings = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(settings),
                "settings": [
                    {
                        "id": setting.id,
                        "campaign_objective": setting.campaign_objective,
                        "kpi_name": setting.kpi_name,
                        "kpi_type": setting.kpi_type,
                        "direction": setting.direction,
                        "default_value": setting.default_value,
                        "unit": setting.unit,
                        "created_at": setting.created_at.isoformat(),
                        "updated_at": setting.updated_at.isoformat()
                    }
                    for setting in settings
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI settings: {str(e)}"
        )


@router.get("/kpi-settings/{setting_id}")
async def get_kpi_setting(setting_id: int):
    """Get a single KPI setting by ID (public read access)"""
    try:
        with get_session() as session:
            setting = session.get(KpiSettings, setting_id)
            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI setting not found"
                )
            
            return {
                "success": True,
                "setting": {
                    "id": setting.id,
                    "campaign_objective": setting.campaign_objective,
                    "kpi_name": setting.kpi_name,
                    "kpi_type": setting.kpi_type,
                    "direction": setting.direction,
                    "default_value": setting.default_value,
                    "unit": setting.unit,
                    "created_at": setting.created_at.isoformat(),
                    "updated_at": setting.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KPI setting: {str(e)}"
        )


@router.post("/kpi-settings")
async def create_kpi_setting(
    setting_data: KpiSettingsCreate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Create a new KPI setting"""
    try:
        with get_session() as session:
            new_setting = KpiSettings(
                campaign_objective=setting_data.campaign_objective,
                kpi_name=setting_data.kpi_name,
                kpi_type=setting_data.kpi_type,
                direction=setting_data.direction,
                default_value=setting_data.default_value,
                unit=setting_data.unit,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_setting)
            session.commit()
            session.refresh(new_setting)
            
            return {
                "success": True,
                "message": "KPI setting created successfully",
                "setting_id": new_setting.id
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create KPI setting: {str(e)}"
        )


@router.put("/kpi-settings/bulk")
async def bulk_update_kpi_settings(
    bulk_data: KpiSettingsBulkUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Bulk update multiple KPI settings"""
    try:
        print(f"DEBUG: Received bulk update request with {len(bulk_data.settings)} settings")
        print(f"DEBUG: First setting data: {bulk_data.settings[0] if bulk_data.settings else 'No settings'}")
        print(f"DEBUG: Full request data: {bulk_data.dict()}")
        print(f"DEBUG: Current user: {current_user.id if current_user else 'None'}")
        
        with get_session() as session:
            updated_count = 0
            errors = []
            
            for setting_data in bulk_data.settings:
                try:
                    # Get the existing setting
                    setting = session.get(KpiSettings, setting_data.id)
                    if not setting:
                        errors.append(f"Setting with ID {setting_data.id} not found")
                        continue
                    
                    # Update fields only if they are provided (not None)
                    if setting_data.campaign_objective is not None:
                        setting.campaign_objective = setting_data.campaign_objective
                    if setting_data.kpi_name is not None:
                        setting.kpi_name = setting_data.kpi_name
                    if setting_data.kpi_type is not None:
                        setting.kpi_type = setting_data.kpi_type
                    if setting_data.direction is not None:
                        setting.direction = setting_data.direction
                    if setting_data.default_value is not None:
                        setting.default_value = setting_data.default_value
                    if setting_data.unit is not None:
                        setting.unit = setting_data.unit
                    
                    setting.updated_at = datetime.utcnow()
                    session.add(setting)
                    updated_count += 1
                    
                except Exception as e:
                    errors.append(f"Error updating setting {setting_data.id}: {str(e)}")
            
            # Commit all changes
            session.commit()
            
            return {
                "success": True,
                "message": f"Successfully updated {updated_count} KPI settings",
                "updated_count": updated_count,
                "errors": errors if errors else None
            }
    
    except HTTPException:
        raise
    except ValidationError as e:
        print(f"DEBUG: Pydantic validation error: {e}")
        print(f"DEBUG: Error details: {e.errors()}")
        error_details = {
            "message": "Validation error in KPI settings data",
            "errors": e.errors()
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_details
        )
    except Exception as e:
        print(f"DEBUG: Exception in bulk update: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update KPI settings: {str(e)}"
        )


@router.put("/kpi-settings/{setting_id}")
async def update_kpi_setting(
    setting_id: int,
    setting_data: KpiSettingsUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update a KPI setting"""
    try:
        with get_session() as session:
            setting = session.get(KpiSettings, setting_id)
            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI setting not found"
                )
            
            # Update fields
            update_data = setting_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(setting, field, value)
            
            setting.updated_at = datetime.utcnow()
            
            session.add(setting)
            session.commit()
            session.refresh(setting)
            
            return {
                "success": True,
                "message": "KPI setting updated successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KPI setting: {str(e)}"
        )


@router.delete("/kpi-settings/{setting_id}")
async def delete_kpi_setting(
    setting_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """Delete a KPI setting"""
    try:
        with get_session() as session:
            setting = session.get(KpiSettings, setting_id)
            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI setting not found"
                )
            
            session.delete(setting)
            session.commit()
            
            return {
                "success": True,
                "message": "KPI setting deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete KPI setting: {str(e)}"
        )


# ===== Generic Table Metadata Route =====

@router.get("/tables")
async def get_available_tables(
):
    """Get list of all available tables for management"""
    return {
        "success": True,
        "tables": [
            # Core user and customer management
            {"name": "campaigners", "label": "Campaigners", "description": "System campaigners", "endpoint": "/api/v1/database/campaigners"},
            {"name": "customers", "label": "Customers", "description": "Customer organizations", "endpoint": "/api/v1/database/customers"},
            
            # Digital assets and connections
            {"name": "digital_assets", "label": "Digital Assets", "description": "Connected digital assets", "endpoint": "/api/v1/database/digital-assets"},
            {"name": "connections", "label": "Connections", "description": "OAuth connections", "endpoint": "/api/v1/database/connections"},
            
            # KPI and analytics
            {"name": "kpi_catalog", "label": "KPI Catalog", "description": "Standardized KPI definitions", "endpoint": "/api/v1/database/catalog"},
            {"name": "kpi_goals", "label": "KPI Goals", "description": "KPI goal metrics", "endpoint": "/api/v1/database/kpi-goals"},
            
            # Agent configurations
            {"name": "agent_configs", "label": "Agent Configurations", "description": "AI agent configurations", "endpoint": "/api/v1/database/agent-configs"},
            {"name": "routing_rules", "label": "Routing Rules", "description": "Intent routing rules", "endpoint": "/api/v1/database/routing-rules"},
            
            # Execution logs (2-table architecture for comprehensive logging)
            {"name": "customer_logs", "label": "Customer Logs", "description": "Customer execution logs (business-level with timing)", "endpoint": "/api/v1/database/customer-logs"},
            {"name": "detailed_execution_logs", "label": "Detailed Execution Logs", "description": "Detailed execution logs (debugging)", "endpoint": "/api/v1/database/detailed-execution-logs"},
            
            # REMOVED TABLES: The following tables have been deleted from the database (empty, unused)
            # - analysis_executions
            # - performance_metrics  
            # - analytics_cache
            # - chat_messages
            # - webhook_entries
            # - narrative_reports
        ]
    }

