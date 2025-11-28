"""
Metrics API routes for accessing ad performance data
Handles role-based access to metrics table
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_, or_, col

from app.core.auth import get_current_user
from app.models.users import Campaigner, UserRole, CustomerCampaignerAssignment
from app.models.analytics import Metrics, DigitalAsset
from app.models.users import Customer
from app.config.database import get_session
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics(
    current_user: Campaigner = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return (max 1000)"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    start_date: Optional[date] = Query(None, description="Filter metrics from this date (inclusive)"),
    end_date: Optional[date] = Query(None, description="Filter metrics to this date (inclusive)"),
    platform_id: Optional[int] = Query(None, description="Filter by specific platform/digital asset ID"),
    item_type: Optional[str] = Query(None, description="Filter by item type ('ad' or 'ad_group')"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID (admin/campaigner can only access their assigned customers)"),
):
    """
    Get metrics from the database with role-based access control.

    Access levels:
    - OWNER: Can access all metrics across all agencies
    - ADMIN: Can access metrics for all customers in their agency
    - CAMPAIGNER: Can access metrics only for customers assigned to them
    - VIEWER: Can access metrics only for customers assigned to them

    The metrics table contains the last 90 days of ad performance data.
    """
    try:
        with get_session() as session:
            # Start building the query
            conditions = []

            # Apply date filters
            if start_date:
                conditions.append(Metrics.metric_date >= start_date)
            if end_date:
                conditions.append(Metrics.metric_date <= end_date)

            # Apply item type filter
            if item_type:
                if item_type not in ['ad', 'ad_group']:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="item_type must be 'ad' or 'ad_group'"
                    )
                conditions.append(Metrics.item_type == item_type)

            # Role-based access control
            if current_user.role == UserRole.OWNER:
                # OWNER: Access all metrics, optionally filtered by platform_id or customer_id
                logger.info(f"[Metrics API] OWNER {current_user.id} accessing all metrics")

                if platform_id:
                    conditions.append(Metrics.platform_id == platform_id)
                elif customer_id:
                    # If customer_id is specified, filter by digital assets of that customer
                    customer_platform_ids = session.exec(
                        select(DigitalAsset.id).where(DigitalAsset.customer_id == customer_id)
                    ).all()
                    if customer_platform_ids:
                        conditions.append(Metrics.platform_id.in_(customer_platform_ids))
                    else:
                        # No platforms for this customer, return empty result
                        return {
                            "success": True,
                            "metrics": [],
                            "total": 0,
                            "limit": limit,
                            "offset": offset,
                            "filters_applied": {
                                "start_date": str(start_date) if start_date else None,
                                "end_date": str(end_date) if end_date else None,
                                "platform_id": platform_id,
                                "item_type": item_type,
                                "customer_id": customer_id
                            }
                        }

            elif current_user.role == UserRole.ADMIN:
                # ADMIN: Access metrics for all customers in their agency
                logger.info(f"[Metrics API] ADMIN {current_user.id} accessing agency {current_user.agency_id} metrics")

                # Get all customer IDs in the admin's agency
                customer_ids = session.exec(
                    select(Customer.id).where(Customer.agency_id == current_user.agency_id)
                ).all()

                if not customer_ids:
                    return {
                        "success": True,
                        "metrics": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "filters_applied": {
                            "start_date": str(start_date) if start_date else None,
                            "end_date": str(end_date) if end_date else None,
                            "platform_id": platform_id,
                            "item_type": item_type,
                            "customer_id": customer_id
                        }
                    }

                # If customer_id filter is provided, check if it's in the allowed list
                if customer_id:
                    if customer_id not in customer_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this customer's metrics"
                        )
                    customer_ids = [customer_id]

                # Get platform IDs for these customers
                platform_ids = session.exec(
                    select(DigitalAsset.id).where(DigitalAsset.customer_id.in_(customer_ids))
                ).all()

                if not platform_ids:
                    return {
                        "success": True,
                        "metrics": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "filters_applied": {
                            "start_date": str(start_date) if start_date else None,
                            "end_date": str(end_date) if end_date else None,
                            "platform_id": platform_id,
                            "item_type": item_type,
                            "customer_id": customer_id
                        }
                    }

                # Apply platform filter
                if platform_id:
                    if platform_id not in platform_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this platform's metrics"
                        )
                    conditions.append(Metrics.platform_id == platform_id)
                else:
                    conditions.append(Metrics.platform_id.in_(platform_ids))

            else:
                # CAMPAIGNER or VIEWER: Access only assigned customers' metrics
                logger.info(f"[Metrics API] {current_user.role.value} {current_user.id} accessing assigned metrics")

                # Get assigned customer IDs
                assigned_customer_ids = session.exec(
                    select(CustomerCampaignerAssignment.customer_id).where(
                        and_(
                            CustomerCampaignerAssignment.campaigner_id == current_user.id,
                            CustomerCampaignerAssignment.is_active == True
                        )
                    )
                ).all()

                if not assigned_customer_ids:
                    return {
                        "success": True,
                        "metrics": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "filters_applied": {
                            "start_date": str(start_date) if start_date else None,
                            "end_date": str(end_date) if end_date else None,
                            "platform_id": platform_id,
                            "item_type": item_type,
                            "customer_id": customer_id
                        }
                    }

                # If customer_id filter is provided, check if it's in the allowed list
                if customer_id:
                    if customer_id not in assigned_customer_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this customer's metrics"
                        )
                    assigned_customer_ids = [customer_id]

                # Get platform IDs for assigned customers
                platform_ids = session.exec(
                    select(DigitalAsset.id).where(DigitalAsset.customer_id.in_(assigned_customer_ids))
                ).all()

                if not platform_ids:
                    return {
                        "success": True,
                        "metrics": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "filters_applied": {
                            "start_date": str(start_date) if start_date else None,
                            "end_date": str(end_date) if end_date else None,
                            "platform_id": platform_id,
                            "item_type": item_type,
                            "customer_id": customer_id
                        }
                    }

                # Apply platform filter
                if platform_id:
                    if platform_id not in platform_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this platform's metrics"
                        )
                    conditions.append(Metrics.platform_id == platform_id)
                else:
                    conditions.append(Metrics.platform_id.in_(platform_ids))

            # Build the query with all conditions
            if conditions:
                statement = select(Metrics).where(and_(*conditions)).order_by(
                    Metrics.metric_date.desc(),
                    Metrics.platform_id,
                    Metrics.item_id
                ).offset(offset).limit(limit)
            else:
                statement = select(Metrics).order_by(
                    Metrics.metric_date.desc(),
                    Metrics.platform_id,
                    Metrics.item_id
                ).offset(offset).limit(limit)

            # Execute query
            metrics = session.exec(statement).all()

            # Count total matching records (for pagination)
            if conditions:
                count_statement = select(Metrics).where(and_(*conditions))
            else:
                count_statement = select(Metrics)
            total = len(session.exec(count_statement).all())

            logger.info(f"[Metrics API] Returning {len(metrics)} metrics (total: {total})")

            return {
                "success": True,
                "metrics": [
                    {
                        "metric_date": metric.metric_date.isoformat(),
                        "item_id": metric.item_id,
                        "platform_id": metric.platform_id,
                        "item_type": metric.item_type,
                        "cpa": metric.cpa,
                        "cvr": metric.cvr,
                        "conv_val": metric.conv_val,
                        "ctr": metric.ctr,
                        "cpc": metric.cpc,
                        "clicks": metric.clicks,
                        "cpm": metric.cpm,
                        "impressions": metric.impressions,
                        "reach": metric.reach,
                        "frequency": metric.frequency,
                        "cpl": metric.cpl,
                        "leads": metric.leads,
                        "spent": metric.spent,
                        "conversions": metric.conversions,
                    }
                    for metric in metrics
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
                "filters_applied": {
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                    "platform_id": platform_id,
                    "item_type": item_type,
                    "customer_id": customer_id
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Metrics API] Error fetching metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch metrics: {str(e)}"
        )
