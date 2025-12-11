"""
Data formatting and processing utilities
Centralizes common data transformation operations
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def format_analytics_data(
    data: Dict[str, Any], data_type: str, metrics: List[str] = None
) -> Dict[str, Any]:
    """
    Format analytics data for agent consumption

    Args:
        data: Raw data from API
        data_type: Type of data (page_insights, page_posts, ad_insights, etc.)
        metrics: List of requested metrics

    Returns:
        Formatted data dictionary
    """
    if not data or "data" not in data:
        return {"error": "No data available", "status": "error", "data_type": data_type}

    raw_data = data.get("data", [])

    if data_type == "page_insights":
        return _format_page_insights(raw_data, metrics)
    elif data_type == "page_posts":
        return _format_page_posts(raw_data, metrics)
    elif data_type == "ad_insights":
        return _format_ad_insights(raw_data, metrics)
    elif data_type == "campaigns":
        return _format_campaigns(raw_data, metrics)
    else:
        return {"raw_data": raw_data, "data_type": data_type, "status": "success"}


def _format_page_insights(
    data: List[Dict], metrics: List[str] = None
) -> Dict[str, Any]:
    """Format Facebook page insights data"""
    if not data:
        return {"error": "No page insights data available", "status": "error"}

    formatted_data = {
        "data_type": "page_insights",
        "status": "success",
        "insights": [],
        "summary": {
            "total_impressions": 0,
            "total_engagements": 0,
            "total_video_views": 0,
            "total_fans": 0,
        },
    }

    for insight in data:
        insight_name = insight.get("name", "")
        values = insight.get("values", [])

        if values:
            value = values[0].get("value", 0)
            formatted_insight = {
                "metric": insight_name,
                "value": value,
                "period": insight.get("period", "day"),
            }
            formatted_data["insights"].append(formatted_insight)

            # Update summary
            if insight_name == "page_impressions":
                formatted_data["summary"]["total_impressions"] += value
            elif insight_name == "page_post_engagements":
                formatted_data["summary"]["total_engagements"] += value
            elif insight_name == "page_video_views":
                formatted_data["summary"]["total_video_views"] += value
            elif insight_name == "page_fans":
                formatted_data["summary"]["total_fans"] = (
                    value  # Current count, not cumulative
                )

    return formatted_data


def _format_page_posts(data: List[Dict], metrics: List[str] = None) -> Dict[str, Any]:
    """Format Facebook page posts data"""
    if not data:
        return {"error": "No page posts data available", "status": "error"}

    formatted_data = {
        "data_type": "page_posts",
        "status": "success",
        "posts": [],
        "summary": {
            "total_posts": len(data),
            "total_impressions": 0,
            "total_engagements": 0,
        },
    }

    for post in data:
        formatted_post = {
            "id": post.get("id", ""),
            "message": post.get("message", ""),
            "created_time": post.get("created_time", ""),
            "insights": {},
        }

        # Extract insights if available
        if "insights" in post:
            for insight in post["insights"].get("data", []):
                insight_name = insight.get("name", "")
                values = insight.get("values", [])
                if values:
                    formatted_post["insights"][insight_name] = values[0].get("value", 0)

        formatted_data["posts"].append(formatted_post)

    return formatted_data


def _format_ad_insights(data: List[Dict], metrics: List[str] = None) -> Dict[str, Any]:
    """Format Facebook ad insights data"""
    if not data:
        return {"error": "No ad insights data available", "status": "error"}

    formatted_data = {
        "data_type": "ad_insights",
        "status": "success",
        "insights": [],
        "summary": {
            "total_impressions": 0,
            "total_clicks": 0,
            "total_spend": 0.0,
            "total_conversions": 0,
        },
    }

    for insight in data:
        # Safely convert string values to appropriate types
        try:
            impressions = int(insight.get("impressions", 0))
            clicks = int(insight.get("clicks", 0))
            spend = float(insight.get("spend", 0))
            conversions = int(insight.get("conversions", 0))
            cpm = float(insight.get("cpm", 0))
            cpc = float(insight.get("cpc", 0))
            ctr = float(insight.get("ctr", 0))
        except (ValueError, TypeError):
            impressions = clicks = conversions = 0
            spend = cpm = cpc = ctr = 0.0

        formatted_insight = {
            "campaign_id": insight.get("campaign_id", ""),
            "campaign_name": insight.get("campaign_name", ""),
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": conversions,
            "cpm": cpm,
            "cpc": cpc,
            "ctr": ctr,
        }

        formatted_data["insights"].append(formatted_insight)

        # Update summary
        formatted_data["summary"]["total_impressions"] += impressions
        formatted_data["summary"]["total_clicks"] += clicks
        formatted_data["summary"]["total_spend"] += spend
        formatted_data["summary"]["total_conversions"] += conversions

    return formatted_data


def _format_campaigns(data: List[Dict], metrics: List[str] = None) -> Dict[str, Any]:
    """Format campaign data"""
    if not data:
        return {"error": "No campaign data available", "status": "error"}

    formatted_data = {
        "data_type": "campaigns",
        "status": "success",
        "campaigns": [],
        "summary": {
            "total_campaigns": len(data),
            "active_campaigns": 0,
            "paused_campaigns": 0,
        },
    }

    for campaign in data:
        status = campaign.get("status", "").lower()
        formatted_campaign = {
            "id": campaign.get("id", ""),
            "name": campaign.get("name", ""),
            "status": status,
            "objective": campaign.get("objective", ""),
            "created_time": campaign.get("created_time", ""),
            "updated_time": campaign.get("updated_time", ""),
        }

        formatted_data["campaigns"].append(formatted_campaign)

        # Update summary
        if status == "active":
            formatted_data["summary"]["active_campaigns"] += 1
        elif status == "paused":
            formatted_data["summary"]["paused_campaigns"] += 1

    return formatted_data


def combine_multiple_data_sources(data_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine data from multiple sources into a unified format

    Args:
        data_sources: List of data dictionaries from different sources

    Returns:
        Combined data dictionary
    """
    combined_data = {
        "status": "success",
        "sources": len(data_sources),
        "data": [],
        "summary": {
            "total_impressions": 0,
            "total_engagements": 0,
            "total_spend": 0.0,
            "total_clicks": 0,
        },
    }

    for source_data in data_sources:
        if source_data.get("status") == "success":
            combined_data["data"].append(source_data)

            # Aggregate summary metrics
            summary = source_data.get("summary", {})
            combined_data["summary"]["total_impressions"] += summary.get(
                "total_impressions", 0
            )
            combined_data["summary"]["total_engagements"] += summary.get(
                "total_engagements", 0
            )
            combined_data["summary"]["total_spend"] += summary.get("total_spend", 0.0)
            combined_data["summary"]["total_clicks"] += summary.get("total_clicks", 0)

    return combined_data
