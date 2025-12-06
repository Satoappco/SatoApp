"""
Metrics API routes for accessing ad performance data
Handles role-based access to metrics table
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_, or_, col, func

from app.core.auth import get_current_user
from app.models.users import Campaigner, UserRole, CustomerCampaignerAssignment
from app.models.analytics import Metrics, DigitalAsset
from app.models.users import Customer
from app.models.settings import AppSettings
from app.config.database import get_session
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _get_metric_weights_and_normalizer(session):
    """
    Load metric weights and normalizer from app settings.
    Returns dict with weights and normalizer value.
    """
    default_weights = {
        "cpa": 0.25,
        "cvr": 0.20,
        "ctr": 0.15,
        "cpc": 0.15,
        "cpm": 0.10,
        "cpl": 0.15,
    }
    default_normalizer = 1.0

    try:
        # Load settings from database
        settings = session.exec(select(AppSettings)).all()
        settings_dict = {s.key: s.value for s in settings}

        weights = {}
        for metric in ["cpa", "cvr", "ctr", "cpc", "cpm", "cpl"]:
            key = f"metric_weight_{metric}"
            weights[metric] = float(settings_dict.get(key, default_weights[metric]))

        normalizer = float(settings_dict.get("metric_score_normalizer", default_normalizer))

        return {"weights": weights, "normalizer": normalizer}
    except Exception as e:
        logger.warning(f"Failed to load metric weights from settings, using defaults: {e}")
        return {"weights": default_weights, "normalizer": default_normalizer}


def _calculate_metric_score(metrics_dict, weights, normalizer):
    """
    Calculate a weighted score for the given metrics.

    For "higher is better" metrics (CVR, CTR): use value directly (normalized to 0-100 scale)
    For "lower is better" metrics (CPA, CPC, CPM, CPL): invert using (100 - normalized_value)

    Args:
        metrics_dict: Dict with metric values (cpa, cvr, ctr, cpc, cpm, cpl)
        weights: Dict with weight for each metric
        normalizer: Divider to normalize the final score

    Returns:
        float: Weighted score (0-100 scale)
    """
    score = 0.0
    total_weight = 0.0

    # Higher is better metrics (already in % or can be used directly)
    if metrics_dict.get("cvr") is not None:
        # CVR is already 0-100 (percentage)
        score += weights["cvr"] * min(metrics_dict["cvr"], 100)
        total_weight += weights["cvr"]

    if metrics_dict.get("ctr") is not None:
        # CTR is already 0-100 (percentage)
        score += weights["ctr"] * min(metrics_dict["ctr"], 100)
        total_weight += weights["ctr"]

    # Lower is better metrics (cost metrics) - invert them
    # We'll use a simple inversion: if value exists, contribute to score based on how low it is
    # For costs, we'll normalize using: 100 / (1 + value) which gives higher scores for lower costs
    if metrics_dict.get("cpa") is not None and metrics_dict["cpa"] > 0:
        normalized_cpa = 100 / (1 + metrics_dict["cpa"])
        score += weights["cpa"] * normalized_cpa
        total_weight += weights["cpa"]

    if metrics_dict.get("cpc") is not None and metrics_dict["cpc"] > 0:
        normalized_cpc = 100 / (1 + metrics_dict["cpc"])
        score += weights["cpc"] * normalized_cpc
        total_weight += weights["cpc"]

    if metrics_dict.get("cpm") is not None and metrics_dict["cpm"] > 0:
        normalized_cpm = 100 / (1 + metrics_dict["cpm"])
        score += weights["cpm"] * normalized_cpm
        total_weight += weights["cpm"]

    if metrics_dict.get("cpl") is not None and metrics_dict["cpl"] > 0:
        normalized_cpl = 100 / (1 + metrics_dict["cpl"])
        score += weights["cpl"] * normalized_cpl
        total_weight += weights["cpl"]

    # Calculate weighted average and apply normalizer
    if total_weight > 0:
        final_score = (score / total_weight) / normalizer
        return round(final_score, 2)
    else:
        return None


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


@router.get("/aggregated")
async def get_aggregated_metrics(
    current_user: Campaigner = Depends(get_current_user),
    start_date: date = Query(..., description="Start date for aggregation (inclusive)"),
    end_date: date = Query(..., description="End date for aggregation (inclusive)"),
    platform_id: Optional[int] = Query(None, description="Filter by specific platform/digital asset ID"),
    item_type: Optional[str] = Query(None, description="Filter by item type ('ad' or 'ad_group')"),
    item_id: Optional[str] = Query(None, description="Filter by specific item ID (ad or ad_group)"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID (admin/campaigner can only access their assigned customers)"),
    group_by: Optional[str] = Query("item_id", description="Group results by 'item_id' (default), 'platform_id', 'item_type', or 'none' for total aggregation"),
):
    """
    Get aggregated metrics for a time range.

    By default, metrics are aggregated per ad/ad_group (group_by='item_id').
    Use group_by='none' to get a single total across all items.

    This endpoint aggregates daily metrics over the specified date range and calculates:
    - Sum metrics: clicks, impressions, leads, spent, conversions, conv_val
    - Calculated metrics: cpa, cvr, ctr, cpc, cpm, cpl
    - Reach bounds: reach_min (highest single day), reach_max (sum, assumes zero overlap)
    - Frequency bounds: frequency_min and frequency_max (calculated from reach bounds)
    - Performance score: weighted score (0-100) based on metric weights from settings

    The score is calculated using configurable weights for each metric (default weights sum to 1.0):
    - CPA (0.25), CVR (0.20), CTR (0.15), CPC (0.15), CPM (0.10), CPL (0.15)
    - Higher scores indicate better performance
    - Can be adjusted via app_settings: metric_weight_* and metric_score_normalizer

    Note: Exact reach and frequency cannot be calculated from daily metrics due to user overlap.
    The bounds provide an approximate range. For exact values, query the platform API directly.

    Access levels: Same as /metrics endpoint
    """
    try:
        with get_session() as session:
            # Load metric weights and normalizer from settings
            scoring_config = _get_metric_weights_and_normalizer(session)
            weights = scoring_config["weights"]
            normalizer = scoring_config["normalizer"]

            # Build base conditions
            conditions = [
                Metrics.metric_date >= start_date,
                Metrics.metric_date <= end_date
            ]

            # Apply item type filter
            if item_type:
                if item_type not in ['ad', 'ad_group']:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="item_type must be 'ad' or 'ad_group'"
                    )
                conditions.append(Metrics.item_type == item_type)

            # Apply item_id filter
            if item_id:
                conditions.append(Metrics.item_id == item_id)

            # Role-based access control (same logic as get_metrics)
            if current_user.role == UserRole.OWNER:
                logger.info(f"[Aggregated Metrics API] OWNER {current_user.id} accessing aggregated metrics")

                if platform_id:
                    conditions.append(Metrics.platform_id == platform_id)
                elif customer_id:
                    customer_platform_ids = session.exec(
                        select(DigitalAsset.id).where(DigitalAsset.customer_id == customer_id)
                    ).all()
                    if customer_platform_ids:
                        conditions.append(Metrics.platform_id.in_(customer_platform_ids))
                    else:
                        return _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights, normalizer)

            elif current_user.role == UserRole.ADMIN:
                logger.info(f"[Aggregated Metrics API] ADMIN {current_user.id} accessing aggregated metrics")

                customer_ids = session.exec(
                    select(Customer.id).where(Customer.agency_id == current_user.agency_id)
                ).all()

                if not customer_ids:
                    return _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights, normalizer)

                if customer_id:
                    if customer_id not in customer_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this customer's metrics"
                        )
                    customer_ids = [customer_id]

                platform_ids = session.exec(
                    select(DigitalAsset.id).where(DigitalAsset.customer_id.in_(customer_ids))
                ).all()

                if not platform_ids:
                    return _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights, normalizer)

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
                logger.info(f"[Aggregated Metrics API] {current_user.role.value} {current_user.id} accessing aggregated metrics")

                assigned_customer_ids = session.exec(
                    select(CustomerCampaignerAssignment.customer_id).where(
                        and_(
                            CustomerCampaignerAssignment.campaigner_id == current_user.id,
                            CustomerCampaignerAssignment.is_active == True
                        )
                    )
                ).all()

                if not assigned_customer_ids:
                    return _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights, normalizer)

                if customer_id:
                    if customer_id not in assigned_customer_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this customer's metrics"
                        )
                    assigned_customer_ids = [customer_id]

                platform_ids = session.exec(
                    select(DigitalAsset.id).where(DigitalAsset.customer_id.in_(assigned_customer_ids))
                ).all()

                if not platform_ids:
                    return _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights, normalizer)

                if platform_id:
                    if platform_id not in platform_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this platform's metrics"
                        )
                    conditions.append(Metrics.platform_id == platform_id)
                else:
                    conditions.append(Metrics.platform_id.in_(platform_ids))

            # Build aggregation query
            group_by_cols = []
            if group_by and group_by != "none":
                if group_by == "item_id":
                    group_by_cols = [Metrics.item_id, Metrics.platform_id, Metrics.item_type]
                elif group_by == "platform_id":
                    group_by_cols = [Metrics.platform_id]
                elif group_by == "item_type":
                    group_by_cols = [Metrics.item_type]
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="group_by must be 'item_id', 'platform_id', 'item_type', or 'none'"
                    )

            # Select aggregated fields (use COALESCE to convert NULL to 0 for sum operations)
            select_cols = [
                func.coalesce(func.sum(Metrics.clicks), 0).label("total_clicks"),
                func.coalesce(func.sum(Metrics.impressions), 0).label("total_impressions"),
                func.coalesce(func.sum(Metrics.leads), 0).label("total_leads"),
                func.coalesce(func.sum(Metrics.spent), 0).label("total_spent"),
                func.coalesce(func.sum(Metrics.conversions), 0).label("total_conversions"),
                func.coalesce(func.sum(Metrics.conv_val), 0).label("total_conv_val"),
                # Reach bounds - min is the highest single day, max is the sum (assumes no overlap)
                # Note: MAX can still return NULL if all values are NULL, which is okay
                func.max(Metrics.reach).label("reach_min"),
                func.coalesce(func.sum(Metrics.reach), 0).label("reach_max"),
            ]

            if group_by_cols:
                select_cols = group_by_cols + select_cols

            statement = select(*select_cols).where(and_(*conditions))

            if group_by_cols:
                statement = statement.group_by(*group_by_cols)

            results = session.exec(statement).all()

            # Process results and calculate derived metrics
            aggregated_metrics = []
            for row in results:
                if group_by and group_by != "none":
                    if group_by == "item_id":
                        group_info = {
                            "item_id": row[0],
                            "platform_id": row[1],
                            "item_type": row[2]
                        }
                        total_clicks = row[3]
                        total_impressions = row[4]
                        total_leads = row[5]
                        total_spent = row[6]
                        total_conversions = row[7]
                        total_conv_val = row[8]
                        reach_min = row[9]
                        reach_max = row[10]
                    elif group_by == "platform_id":
                        group_info = {"platform_id": row[0]}
                        total_clicks = row[1]
                        total_impressions = row[2]
                        total_leads = row[3]
                        total_spent = row[4]
                        total_conversions = row[5]
                        total_conv_val = row[6]
                        reach_min = row[7]
                        reach_max = row[8]
                    else:  # item_type
                        group_info = {"item_type": row[0]}
                        total_clicks = row[1]
                        total_impressions = row[2]
                        total_leads = row[3]
                        total_spent = row[4]
                        total_conversions = row[5]
                        total_conv_val = row[6]
                        reach_min = row[7]
                        reach_max = row[8]
                else:
                    group_info = {}
                    total_clicks = row[0]
                    total_impressions = row[1]
                    total_leads = row[2]
                    total_spent = row[3]
                    total_conversions = row[4]
                    total_conv_val = row[5]
                    reach_min = row[6]
                    reach_max = row[7]

                # Calculate derived metrics
                cpa = round(total_spent / total_conversions, 2) if total_conversions and total_conversions > 0 else None
                cvr = round((total_conversions / total_clicks) * 100, 2) if total_clicks and total_clicks > 0 else None
                ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions and total_impressions > 0 else None
                cpc = round(total_spent / total_clicks, 2) if total_clicks and total_clicks > 0 else None
                cpm = round((total_spent / total_impressions) * 1000, 2) if total_impressions and total_impressions > 0 else None
                cpl = round(total_spent / total_leads, 2) if total_leads and total_leads > 0 else None

                # Calculate score
                score = _calculate_metric_score(
                    {"cpa": cpa, "cvr": cvr, "ctr": ctr, "cpc": cpc, "cpm": cpm, "cpl": cpl},
                    weights,
                    normalizer
                )

                metric = {
                    **group_info,
                    "clicks": total_clicks,
                    "impressions": total_impressions,
                    "leads": total_leads,
                    "spent": total_spent,
                    "conversions": total_conversions,
                    "conv_val": total_conv_val,
                    # Calculated metrics
                    "cpa": cpa,
                    "cvr": cvr,
                    "ctr": ctr,
                    "cpc": cpc,
                    "cpm": cpm,
                    "cpl": cpl,
                    # Reach bounds (approximate)
                    "reach_min": reach_min,  # At minimum, equals the highest single day reach
                    "reach_max": reach_max,  # At maximum, if there's zero user overlap across days
                    # Frequency bounds (calculated from reach bounds)
                    "frequency_min": round(total_impressions / reach_max, 2) if reach_max and reach_max > 0 else None,
                    "frequency_max": round(total_impressions / reach_min, 2) if reach_min and reach_min > 0 else None,
                    # Performance score
                    "score": score,
                }

                aggregated_metrics.append(metric)

            logger.info(f"[Aggregated Metrics API] Returning {len(aggregated_metrics)} aggregated metric(s)")

            return {
                "success": True,
                "aggregated_metrics": aggregated_metrics,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "filters_applied": {
                    "platform_id": platform_id,
                    "item_type": item_type,
                    "item_id": item_id,
                    "customer_id": customer_id,
                    "group_by": group_by
                },
                "notes": {
                    "reach_bounds": "reach_min = highest single day reach, reach_max = sum of daily reach (assumes zero overlap). Actual unique reach is between these values.",
                    "frequency_bounds": "frequency_min and frequency_max calculated from reach bounds. Actual frequency is between these values.",
                    "accuracy": "For exact reach/frequency, fetch aggregated data directly from the advertising platform API for the entire date range.",
                    "score": f"Performance score (0-100) calculated using weighted metrics. Weights: CPA={weights['cpa']}, CVR={weights['cvr']}, CTR={weights['ctr']}, CPC={weights['cpc']}, CPM={weights['cpm']}, CPL={weights['cpl']}. Normalizer={normalizer}. Higher scores indicate better performance."
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Aggregated Metrics API] Error fetching aggregated metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aggregated metrics: {str(e)}"
        )


def _empty_aggregated_response(start_date, end_date, platform_id, item_type, item_id, customer_id, group_by, weights=None, normalizer=None):
    """Helper function to return empty aggregated metrics response"""
    notes = {
        "reach_bounds": "reach_min = highest single day reach, reach_max = sum of daily reach (assumes zero overlap). Actual unique reach is between these values.",
        "frequency_bounds": "frequency_min and frequency_max calculated from reach bounds. Actual frequency is between these values.",
        "accuracy": "For exact reach/frequency, fetch aggregated data directly from the advertising platform API for the entire date range."
    }

    if weights and normalizer:
        notes["score"] = f"Performance score (0-100) calculated using weighted metrics. Weights: CPA={weights['cpa']}, CVR={weights['cvr']}, CTR={weights['ctr']}, CPC={weights['cpc']}, CPM={weights['cpm']}, CPL={weights['cpl']}. Normalizer={normalizer}. Higher scores indicate better performance."

    return {
        "success": True,
        "aggregated_metrics": [],
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "filters_applied": {
            "platform_id": platform_id,
            "item_type": item_type,
            "item_id": item_id,
            "customer_id": customer_id,
            "group_by": group_by
        },
        "notes": notes
    }
