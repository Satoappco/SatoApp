"""
Database Management API routes
Handles CRUD operations for all database tables:
- KPI Catalog & Campaign KPIs
- Agent Config & Routing Rules
- Analysis Executions
- Performance Metrics
- Analytics Cache
- Narrative Reports
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.users import User, Customer, SubCustomer
from app.models.analytics import KpiCatalog, CampaignKPI, PerformanceMetric, DigitalAsset, Connection
from app.models.agents import AgentConfig, RoutingRule, AnalysisExecution, CustomerLog, ExecutionTiming, DetailedExecutionLog
from app.models.conversations import NarrativeReport
from app.config.database import get_session

# REMOVED IMPORTS (tables deleted):
# - UserSession (from app.models.users)
# - AnalyticsCache, UserPropertySelection (from app.models.analytics)
# - ChatMessage, WebhookEntry (from app.models.conversations)

router = APIRouter(prefix="/database", tags=["database-management"])


# ===== Pydantic Schemas =====

class KpiCatalogCreate(BaseModel):
    """Schema for creating a KPI Catalog entry"""
    kpi_name: str = Field(max_length=100)
    kpi_description: str
    calculation_method: str
    data_sources: str
    category: str = Field(max_length=100)
    is_active: bool = True


class KpiCatalogUpdate(BaseModel):
    """Schema for updating a KPI Catalog entry"""
    kpi_name: Optional[str] = Field(None, max_length=100)
    kpi_description: Optional[str] = None
    calculation_method: Optional[str] = None
    data_sources: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class CampaignKPICreate(BaseModel):
    """Schema for creating a Campaign KPI entry"""
    subcustomer_id: int
    date: datetime
    campaign_num: int
    campaign_id: str = Field(max_length=50)
    advertising_channel: str = Field(max_length=100)
    campaign_name: str = Field(max_length=255)
    campaign_objective: str = Field(max_length=100)
    daily_budget: Optional[float] = None
    weekly_budget: Optional[float] = None
    target_audience: str = Field(max_length=255)
    primary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_2: Optional[str] = Field(None, max_length=255)
    secondary_kpi_3: Optional[str] = Field(None, max_length=255)
    landing_page: Optional[str] = Field(None, max_length=500)
    summary_text: Optional[str] = None
    is_active: bool = True


class CampaignKPIUpdate(BaseModel):
    """Schema for updating a Campaign KPI entry"""
    subcustomer_id: Optional[int] = None
    date: Optional[datetime] = None
    campaign_num: Optional[int] = None
    campaign_id: Optional[str] = Field(None, max_length=50)
    advertising_channel: Optional[str] = Field(None, max_length=100)
    campaign_name: Optional[str] = Field(None, max_length=255)
    campaign_objective: Optional[str] = Field(None, max_length=100)
    daily_budget: Optional[float] = None
    weekly_budget: Optional[float] = None
    target_audience: Optional[str] = Field(None, max_length=255)
    primary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_1: Optional[str] = Field(None, max_length=255)
    secondary_kpi_2: Optional[str] = Field(None, max_length=255)
    secondary_kpi_3: Optional[str] = Field(None, max_length=255)
    landing_page: Optional[str] = Field(None, max_length=500)
    summary_text: Optional[str] = None
    is_active: Optional[bool] = None


# ===== KPI Catalog Routes =====

@router.get("/catalog")
async def get_kpi_catalog(
    active_only: bool = Query(False, description="Return only active KPIs"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Get all KPI catalog entries (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(KpiCatalog)
            
            # Apply filters
            conditions = []
            if active_only:
                conditions.append(KpiCatalog.is_active == True)
            if category:
                conditions.append(KpiCatalog.category == category)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(KpiCatalog.category, KpiCatalog.kpi_name)
            kpis = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(kpis),
                "kpis": [
                    {
                        "id": kpi.id,
                        "kpi_name": kpi.kpi_name,
                        "kpi_description": kpi.kpi_description,
                        "calculation_method": kpi.calculation_method,
                        "data_sources": kpi.data_sources,
                        "category": kpi.category,
                        "is_active": kpi.is_active,
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
                    "kpi_name": kpi.kpi_name,
                    "kpi_description": kpi.kpi_description,
                    "calculation_method": kpi.calculation_method,
                    "data_sources": kpi.data_sources,
                    "category": kpi.category,
                    "is_active": kpi.is_active,
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
                kpi_name=kpi_data.kpi_name,
                kpi_description=kpi_data.kpi_description,
                calculation_method=kpi_data.calculation_method,
                data_sources=kpi_data.data_sources,
                category=kpi_data.category,
                is_active=kpi_data.is_active,
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
                    "kpi_name": new_kpi.kpi_name,
                    "kpi_description": new_kpi.kpi_description,
                    "calculation_method": new_kpi.calculation_method,
                    "data_sources": new_kpi.data_sources,
                    "category": new_kpi.category,
                    "is_active": new_kpi.is_active,
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
                    "kpi_name": kpi.kpi_name,
                    "kpi_description": kpi.kpi_description,
                    "calculation_method": kpi.calculation_method,
                    "data_sources": kpi.data_sources,
                    "category": kpi.category,
                    "is_active": kpi.is_active,
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


# ===== Campaign KPI Routes =====

@router.get("/campaigns")
async def get_campaign_kpis(
    subcustomer_id: Optional[int] = Query(None, description="Filter by subcustomer"),
    active_only: bool = Query(False, description="Return only active campaigns"),
    limit: int = Query(1000, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all campaign KPIs (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(CampaignKPI)
            
            # Apply filters (no user filtering - this is admin tool)
            conditions = []
            if active_only:
                conditions.append(CampaignKPI.is_active == True)
            if subcustomer_id:
                conditions.append(CampaignKPI.subcustomer_id == subcustomer_id)
            
            if conditions:
                statement = statement.where(and_(*conditions))
            
            statement = statement.order_by(CampaignKPI.date.desc()).offset(offset).limit(limit)
            campaigns = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(campaigns),
                "campaigns": [
                    {
                        "id": campaign.id,
                        "subcustomer_id": campaign.subcustomer_id,
                        "date": campaign.date.isoformat(),
                        "campaign_num": campaign.campaign_num,
                        "campaign_id": campaign.campaign_id,
                        "advertising_channel": campaign.advertising_channel,
                        "campaign_name": campaign.campaign_name,
                        "campaign_objective": campaign.campaign_objective,
                        "daily_budget": campaign.daily_budget,
                        "weekly_budget": campaign.weekly_budget,
                        "target_audience": campaign.target_audience,
                        "primary_kpi_1": campaign.primary_kpi_1,
                        "secondary_kpi_1": campaign.secondary_kpi_1,
                        "secondary_kpi_2": campaign.secondary_kpi_2,
                        "secondary_kpi_3": campaign.secondary_kpi_3,
                        "landing_page": campaign.landing_page,
                        "summary_text": campaign.summary_text,
                        "is_active": campaign.is_active,
                        "created_at": campaign.created_at.isoformat(),
                        "updated_at": campaign.updated_at.isoformat()
                    }
                    for campaign in campaigns
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaign KPIs: {str(e)}"
        )


@router.get("/campaigns/{campaign_kpi_id}")
async def get_campaign_kpi(
    campaign_kpi_id: int,
):
    """Get a specific campaign KPI entry"""
    try:
        with get_session() as session:
            campaign = session.get(CampaignKPI, campaign_kpi_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign KPI not found"
                )
            
            return {
                "success": True,
                "campaign": {
                    "id": campaign.id,
                    "subcustomer_id": campaign.subcustomer_id,
                    "date": campaign.date.isoformat(),
                    "campaign_num": campaign.campaign_num,
                    "campaign_id": campaign.campaign_id,
                    "advertising_channel": campaign.advertising_channel,
                    "campaign_name": campaign.campaign_name,
                    "campaign_objective": campaign.campaign_objective,
                    "daily_budget": campaign.daily_budget,
                    "weekly_budget": campaign.weekly_budget,
                    "target_audience": campaign.target_audience,
                    "primary_kpi_1": campaign.primary_kpi_1,
                    "secondary_kpi_1": campaign.secondary_kpi_1,
                    "secondary_kpi_2": campaign.secondary_kpi_2,
                    "secondary_kpi_3": campaign.secondary_kpi_3,
                    "landing_page": campaign.landing_page,
                    "summary_text": campaign.summary_text,
                    "is_active": campaign.is_active,
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


@router.post("/campaigns")
async def create_campaign_kpi(
    campaign_data: CampaignKPICreate,
):
    """Create a new campaign KPI entry"""
    try:
        with get_session() as session:
            new_campaign = CampaignKPI(
                subcustomer_id=campaign_data.subcustomer_id,
                date=campaign_data.date,
                campaign_num=campaign_data.campaign_num,
                campaign_id=campaign_data.campaign_id,
                advertising_channel=campaign_data.advertising_channel,
                campaign_name=campaign_data.campaign_name,
                campaign_objective=campaign_data.campaign_objective,
                daily_budget=campaign_data.daily_budget,
                weekly_budget=campaign_data.weekly_budget,
                target_audience=campaign_data.target_audience,
                primary_kpi_1=campaign_data.primary_kpi_1,
                secondary_kpi_1=campaign_data.secondary_kpi_1,
                secondary_kpi_2=campaign_data.secondary_kpi_2,
                secondary_kpi_3=campaign_data.secondary_kpi_3,
                landing_page=campaign_data.landing_page,
                summary_text=campaign_data.summary_text,
                is_active=campaign_data.is_active,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_campaign)
            session.commit()
            session.refresh(new_campaign)
            
            return {
                "success": True,
                "message": "Campaign KPI created successfully",
                "campaign": {
                    "id": new_campaign.id,
                    "subcustomer_id": new_campaign.subcustomer_id,
                    "date": new_campaign.date.isoformat(),
                    "campaign_num": new_campaign.campaign_num,
                    "campaign_id": new_campaign.campaign_id,
                    "advertising_channel": new_campaign.advertising_channel,
                    "campaign_name": new_campaign.campaign_name,
                    "campaign_objective": new_campaign.campaign_objective,
                    "daily_budget": new_campaign.daily_budget,
                    "weekly_budget": new_campaign.weekly_budget,
                    "target_audience": new_campaign.target_audience,
                    "primary_kpi_1": new_campaign.primary_kpi_1,
                    "secondary_kpi_1": new_campaign.secondary_kpi_1,
                    "secondary_kpi_2": new_campaign.secondary_kpi_2,
                    "secondary_kpi_3": new_campaign.secondary_kpi_3,
                    "landing_page": new_campaign.landing_page,
                    "summary_text": new_campaign.summary_text,
                    "is_active": new_campaign.is_active,
                    "created_at": new_campaign.created_at.isoformat(),
                    "updated_at": new_campaign.updated_at.isoformat()
                }
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign KPI: {str(e)}"
        )


@router.put("/campaigns/{campaign_kpi_id}")
async def update_campaign_kpi(
    campaign_kpi_id: int,
    campaign_data: CampaignKPIUpdate,
):
    """Update a campaign KPI entry"""
    try:
        with get_session() as session:
            campaign = session.get(CampaignKPI, campaign_kpi_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign KPI not found"
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
                "message": "Campaign KPI updated successfully",
                "campaign": {
                    "id": campaign.id,
                    "subcustomer_id": campaign.subcustomer_id,
                    "date": campaign.date.isoformat(),
                    "campaign_num": campaign.campaign_num,
                    "campaign_id": campaign.campaign_id,
                    "advertising_channel": campaign.advertising_channel,
                    "campaign_name": campaign.campaign_name,
                    "campaign_objective": campaign.campaign_objective,
                    "daily_budget": campaign.daily_budget,
                    "weekly_budget": campaign.weekly_budget,
                    "target_audience": campaign.target_audience,
                    "primary_kpi_1": campaign.primary_kpi_1,
                    "secondary_kpi_1": campaign.secondary_kpi_1,
                    "secondary_kpi_2": campaign.secondary_kpi_2,
                    "secondary_kpi_3": campaign.secondary_kpi_3,
                    "landing_page": campaign.landing_page,
                    "summary_text": campaign.summary_text,
                    "is_active": campaign.is_active,
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


@router.delete("/campaigns/{campaign_kpi_id}")
async def delete_campaign_kpi(
    campaign_kpi_id: int,
):
    """Delete a campaign KPI entry"""
    try:
        with get_session() as session:
            campaign = session.get(CampaignKPI, campaign_kpi_id)
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign KPI not found"
                )
            
            session.delete(campaign)
            session.commit()
            
            return {
                "success": True,
                "message": "Campaign KPI deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign KPI: {str(e)}"
        )


# ===== Categories Route =====

@router.get("/catalog/categories/list")
async def get_kpi_categories(
):
    """Get all unique KPI categories"""
    try:
        with get_session() as session:
            statement = select(KpiCatalog.category).distinct()
            categories = session.exec(statement).all()
            
            return {
                "success": True,
                "categories": categories
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


@router.get("/analysis-executions")
async def get_analysis_executions(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all analysis executions (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(AnalysisExecution)
            statement = statement.order_by(AnalysisExecution.created_at.desc()).offset(offset).limit(limit)
            executions = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(executions),
                "executions": [
                    {
                        "id": exec.id,
                        "user_id": exec.user_id,
                        "session_id": exec.session_id,
                        "master_agent_id": exec.master_agent_id,
                        "specialists_used": exec.specialists_used,
                        "iterations": exec.iterations,
                        "execution_time_ms": exec.execution_time_ms,
                        "validation_results": exec.validation_results,
                        "final_result": exec.final_result,
                        "created_at": exec.created_at.isoformat(),
                        "updated_at": exec.updated_at.isoformat()
                    }
                    for exec in executions
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analysis executions: {str(e)}"
        )


@router.get("/performance-metrics")
async def get_performance_metrics(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all performance metrics (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(PerformanceMetric)
            statement = statement.order_by(PerformanceMetric.created_at.desc()).offset(offset).limit(limit)
            metrics = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(metrics),
                "metrics": [
                    {
                        "id": metric.id,
                        "metric_name": metric.metric_name,
                        "metric_value": metric.metric_value,
                        "metric_unit": metric.metric_unit,
                        "agent_type": metric.agent_type,
                        "session_id": metric.session_id,
                        "user_id": metric.user_id,
                        "metric_metadata": metric.metric_metadata,
                        "created_at": metric.created_at.isoformat(),
                        "updated_at": metric.updated_at.isoformat()
                    }
                    for metric in metrics
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch performance metrics: {str(e)}"
        )


@router.get("/analytics-cache")
async def get_analytics_cache(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all analytics cache entries (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(AnalyticsCache)
            statement = statement.order_by(AnalyticsCache.expires_at.desc()).offset(offset).limit(limit)
            cache_entries = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(cache_entries),
                "cache_entries": [
                    {
                        "id": entry.id,
                        "cache_key": entry.cache_key,
                        "cache_data": entry.cache_data,
                        "expires_at": entry.expires_at.isoformat(),
                        "user_id": entry.user_id,
                        "asset_id": entry.asset_id,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat()
                    }
                    for entry in cache_entries
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics cache: {str(e)}"
        )


@router.get("/narrative-reports")
async def get_narrative_reports(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all narrative reports (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(NarrativeReport)
            statement = statement.order_by(NarrativeReport.created_at.desc()).offset(offset).limit(limit)
            reports = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(reports),
                "reports": [
                    {
                        "id": report.id,
                        "user_id": report.user_id,
                        "report_title": report.report_title,
                        "report_content": report.report_content,
                        "report_type": report.report_type,
                        "data_sources": report.data_sources,
                        "generated_by_agent": report.generated_by_agent,
                        "metrics_included": report.metrics_included,
                        "date_range_start": report.date_range_start.isoformat() if report.date_range_start else None,
                        "date_range_end": report.date_range_end.isoformat() if report.date_range_end else None,
                        "is_published": report.is_published,
                        "created_at": report.created_at.isoformat(),
                        "updated_at": report.updated_at.isoformat()
                    }
                    for report in reports
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch narrative reports: {str(e)}"
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
            statement = select(User)
            statement = statement.order_by(User.created_at.desc()).offset(offset).limit(limit)
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
                        "primary_customer_id": user.primary_customer_id,
                        "additional_customer_ids": user.additional_customer_ids,
                        "locale": user.locale,
                        "timezone": user.timezone,
                        "google_id": user.google_id,
                        "avatar_url": user.avatar_url,
                        "email_verified": user.email_verified,
                        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
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


@router.get("/sub-customers")
async def get_sub_customers(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all sub-customers (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(SubCustomer)
            statement = statement.order_by(SubCustomer.created_at.desc()).offset(offset).limit(limit)
            sub_customers = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(sub_customers),
                "sub_customers": [
                    {
                        "id": sub.id,
                        "customer_id": sub.customer_id,
                        "name": sub.name,
                        "subtype": sub.subtype,
                        "status": sub.status,
                        "external_ids": sub.external_ids,
                        "timezone": sub.timezone,
                        "markets": sub.markets,
                        "budget_monthly": sub.budget_monthly,
                        "tags": sub.tags,
                        "created_at": sub.created_at.isoformat(),
                        "updated_at": sub.updated_at.isoformat()
                    }
                    for sub in sub_customers
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sub-customers: {str(e)}"
        )


@router.get("/digital-assets")
async def get_digital_assets(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all digital assets (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(DigitalAsset)
            statement = statement.order_by(DigitalAsset.created_at.desc()).offset(offset).limit(limit)
            assets = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(assets),
                "assets": [
                    {
                        "id": asset.id,
                        "subclient_id": asset.subclient_id,
                        "asset_type": asset.asset_type,
                        "provider": asset.provider,
                        "name": asset.name,
                        "external_id": asset.external_id,
                        "metadata": asset.metadata,
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
                        "user_id": conn.user_id,
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
                        "subclient_id": sel.subclient_id,
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


@router.get("/chat-messages")
async def get_chat_messages(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all chat messages (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(ChatMessage)
            statement = statement.order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit)
            messages = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(messages),
                "messages": [
                    {
                        "id": msg.id,
                        "user_name": msg.user_name,
                        "message": msg.message,
                        "session_id": msg.session_id,
                        "intent": msg.intent,
                        "confidence": msg.confidence,
                        "response": msg.response,
                        "agent_type": msg.agent_type,
                        "execution_time": msg.execution_time,
                        "raw_data": msg.raw_data,
                        "created_at": msg.created_at.isoformat(),
                        "updated_at": msg.updated_at.isoformat()
                    }
                    for msg in messages
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat messages: {str(e)}"
        )


@router.get("/webhook-entries")
async def get_webhook_entries(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all webhook entries (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(WebhookEntry)
            statement = statement.order_by(WebhookEntry.created_at.desc()).offset(offset).limit(limit)
            entries = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(entries),
                "entries": [
                    {
                        "id": entry.id,
                        "user_name": entry.user_name,
                        "user_choice": entry.user_choice,
                        "raw_payload": entry.raw_payload,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat()
                    }
                    for entry in entries
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch webhook entries: {str(e)}"
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
                        "user_id": log.user_id,
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


@router.get("/execution-timings")
async def get_execution_timings(
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all execution timings (admin view - shows all data)"""
    try:
        with get_session() as session:
            statement = select(ExecutionTiming)
            statement = statement.order_by(ExecutionTiming.start_time.desc()).offset(offset).limit(limit)
            timings = session.exec(statement).all()
            
            return {
                "success": True,
                "count": len(timings),
                "timings": [
                    {
                        "id": timing.id,
                        "session_id": timing.session_id,
                        "analysis_id": timing.analysis_id,
                        "component_type": timing.component_type,
                        "component_name": timing.component_name,
                        "start_time": timing.start_time.isoformat(),
                        "end_time": timing.end_time.isoformat() if timing.end_time else None,
                        "duration_ms": timing.duration_ms,
                        "status": timing.status,
                        "input_data": timing.input_data,
                        "output_data": timing.output_data,
                        "error_message": timing.error_message,
                        "parent_session_id": timing.parent_session_id,
                        "created_at": timing.created_at.isoformat(),
                        "updated_at": timing.updated_at.isoformat()
                    }
                    for timing in timings
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch execution timings: {str(e)}"
        )


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


# ===== Generic Table Metadata Route =====

@router.get("/tables")
async def get_available_tables(
):
    """Get list of all available tables for management"""
    return {
        "success": True,
        "tables": [
            # Core user and customer management
            {"name": "users", "label": "Users", "description": "System users", "endpoint": "/api/v1/database/users"},
            {"name": "customers", "label": "Customers", "description": "Customer organizations", "endpoint": "/api/v1/database/customers"},
            {"name": "sub_customers", "label": "Sub-Customers", "description": "Customer sub-organizations", "endpoint": "/api/v1/database/sub-customers"},
            
            # Digital assets and connections
            {"name": "digital_assets", "label": "Digital Assets", "description": "Connected digital assets", "endpoint": "/api/v1/database/digital-assets"},
            {"name": "connections", "label": "Connections", "description": "OAuth connections", "endpoint": "/api/v1/database/connections"},
            
            # KPI and analytics
            {"name": "kpi_catalog", "label": "KPI Catalog", "description": "Standardized KPI definitions", "endpoint": "/api/v1/database/catalog"},
            {"name": "campaign_kpis", "label": "Campaign KPIs", "description": "Campaign performance metrics", "endpoint": "/api/v1/database/campaigns"},
            {"name": "performance_metrics", "label": "Performance Metrics", "description": "System performance metrics", "endpoint": "/api/v1/database/performance-metrics"},
            
            # Agent configurations
            {"name": "agent_configs", "label": "Agent Configurations", "description": "AI agent configurations", "endpoint": "/api/v1/database/agent-configs"},
            {"name": "routing_rules", "label": "Routing Rules", "description": "Intent routing rules", "endpoint": "/api/v1/database/routing-rules"},
            
            # Execution logs (4-table architecture for comprehensive logging)
            {"name": "analysis_executions", "label": "Analysis Executions", "description": "Analysis execution logs", "endpoint": "/api/v1/database/analysis-executions"},
            {"name": "customer_logs", "label": "Customer Logs", "description": "Customer execution logs (business-level)", "endpoint": "/api/v1/database/customer-logs"},
            {"name": "execution_timings", "label": "Execution Timings", "description": "Execution timing data (performance)", "endpoint": "/api/v1/database/execution-timings"},
            {"name": "detailed_execution_logs", "label": "Detailed Execution Logs", "description": "Detailed execution logs (debugging)", "endpoint": "/api/v1/database/detailed-execution-logs"},
            
            # Reports
            {"name": "narrative_reports", "label": "Narrative Reports", "description": "Generated reports", "endpoint": "/api/v1/database/narrative-reports"},
            
            # REMOVED: The following tables have been deleted from the database (empty, unused)
            # - analytics_cache
            # - user_property_selections
            # - user_sessions
            # - chat_messages
            # - webhook_entries
        ]
    }

