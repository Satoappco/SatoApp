"""
Facebook Analytics Tool for CrewAI - REAL DATA IMPLEMENTATION
Provides Facebook page insights, social media metrics, and content performance data
"""

from crewai.tools import BaseTool
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import asyncio
from datetime import datetime, timedelta
import os

from app.services.facebook_service import FacebookService
from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from sqlmodel import select, and_


class FacebookAnalyticsInput(BaseModel):
    """Input schema for FacebookAnalyticsTool."""
    data_type: str = Field("page_insights", description="Type of data to fetch: 'page_insights', 'page_posts', 'ad_insights'")
    metrics: Optional[List[str]] = Field(None, description="Specific metrics to retrieve (optional - will use defaults if not provided)")
    start_date: str = Field("7daysAgo", description="Start date in YYYY-MM-DD format or relative (e.g., '7daysAgo', '30daysAgo')")
    end_date: str = Field("today", description="End date in YYYY-MM-DD format or relative (e.g., 'today', 'yesterday')")
    limit: int = Field(100, description="Maximum number of results to return")
    page_id: Optional[str] = Field(None, description="Specific Facebook page ID (optional - will auto-detect if not provided)")


class FacebookAnalyticsTool(BaseTool):
    name: str = "Facebook Analytics Data Fetcher"
    description: str = (
        "Fetch Facebook page insights, social media metrics, and content performance data from Facebook API. "
        "This tool retrieves REAL data from Facebook pages including engagement metrics, reach, impressions, "
        "post performance, and social media analytics. Perfect for social media analysis and content performance tracking."
    )
    args_schema: Type[BaseModel] = FacebookAnalyticsInput

    # Allow extra fields for Pydantic model
    class Config:
        extra = "allow"

    def __init__(self, user_id: int = None, subclient_id: int = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'user_id', user_id)
        object.__setattr__(self, 'subclient_id', subclient_id)

    def _run(
        self, 
        data_type: str = "page_insights", 
        metrics: List[str] = None, 
        start_date: str = "7daysAgo", 
        end_date: str = "today", 
        limit: int = 100,
        page_id: str = None
    ) -> str:
        """Execute Facebook analytics data fetch with REAL DATA based on agent's specifications"""
        try:
            if not self.user_id or not self.subclient_id:
                return json.dumps({
                    "error": "User ID and Subclient ID are required for Facebook analytics",
                    "status": "error"
                })

            # Initialize Facebook service
            facebook_service = FacebookService()

            # Get Facebook connection with token refresh
            connection_info = asyncio.run(facebook_service.get_facebook_connection_for_user(
                user_id=self.user_id,
                subclient_id=self.subclient_id,
                asset_type="SOCIAL_MEDIA"
            ))
            
            if not connection_info:
                return json.dumps({
                    "error": "No active Facebook connection found. Please connect your Facebook account first.",
                    "status": "error",
                    "suggestion": "Use the Connections tab to connect your Facebook account"
                })
            
            if "error" in connection_info:
                return json.dumps({
                    "error": connection_info["error"],
                    "status": "error",
                    "requires_reauth": connection_info.get("requires_reauth", False),
                    "suggestion": "Please re-authenticate your Facebook account in the Connections tab"
                })

            # Fetch data based on type
            if data_type == "page_insights":
                result = asyncio.run(facebook_service.fetch_facebook_data(
                    connection_id=connection_info["connection_id"],
                    data_type="page_insights",
                    start_date=start_date,
                    end_date=end_date,
                    metrics=metrics,
                    limit=limit
                ))
            elif data_type == "page_posts":
                result = asyncio.run(facebook_service.fetch_facebook_data(
                    connection_id=connection_info["connection_id"],
                    data_type="page_posts",
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                ))
            elif data_type == "ad_insights":
                result = asyncio.run(facebook_service.fetch_facebook_data(
                    connection_id=connection_info["connection_id"],
                    data_type="ad_insights",
                    start_date=start_date,
                    end_date=end_date,
                    metrics=metrics,
                    limit=limit
                ))
            else:
                return json.dumps({
                    "error": f"Unsupported data type: {data_type}",
                    "status": "error",
                    "supported_types": ["page_insights", "page_posts", "ad_insights"]
                })

            # Format the response for the agent
            formatted_result = self._format_facebook_data(result, data_type)
            
            return json.dumps({
                "status": "success",
                "data_type": data_type,
                "source": "Facebook API",
                "date_range": f"{start_date} to {end_date}",
                "data": formatted_result,
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            error_msg = f"Facebook analytics data fetch failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            return json.dumps({
                "error": error_msg,
                "status": "error",
                "data_type": data_type,
                "source": "Facebook API"
            })

    def _get_facebook_connection(self) -> Optional[Connection]:
        """Get active Facebook connection for user/subclient"""
        with get_session() as session:
            # Look for Facebook social media connections
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == self.user_id,
                    DigitalAsset.subclient_id == self.subclient_id,
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                    Connection.revoked == False
                )
            )
            
            result = session.exec(statement).first()
            return result[0] if result else None

    def _format_facebook_data(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """Format Facebook data for agent consumption"""
        if data_type == "page_insights":
            return self._format_page_insights(data)
        elif data_type == "page_posts":
            return self._format_page_posts(data)
        elif data_type == "ad_insights":
            return self._format_ad_insights(data)
        else:
            return data

    def _format_page_insights(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format page insights data"""
        insights_data = data.get('data', [])
        
        if not insights_data:
            return {
                "message": "No page insights data available for the specified date range",
                "metrics_requested": data.get('metrics', []),
                "page_name": data.get('page_name', 'Unknown')
            }

        # Extract and format metrics
        formatted_metrics = {}
        for insight in insights_data:
            metric_name = insight.get('name', 'unknown_metric')
            values = insight.get('values', [])
            
            if values:
                # Get the most recent value
                latest_value = values[-1].get('value', 0)
                formatted_metrics[metric_name] = {
                    "value": latest_value,
                    "period": insight.get('period', 'day'),
                    "description": self._get_metric_description(metric_name)
                }

        return {
            "page_name": data.get('page_name', 'Unknown'),
            "page_id": data.get('page_id', 'Unknown'),
            "date_range": data.get('date_range', {}),
            "metrics": formatted_metrics,
            "summary": self._generate_insights_summary(formatted_metrics)
        }

    def _format_page_posts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format page posts data"""
        posts_data = data.get('data', [])
        
        if not posts_data:
            return {
                "message": "No page posts data available for the specified date range",
                "page_name": data.get('page_name', 'Unknown')
            }

        # Format posts with engagement metrics
        formatted_posts = []
        total_engagement = 0
        
        for post in posts_data:
            insights = post.get('insights', {}).get('data', [])
            engagement_metrics = {}
            
            for insight in insights:
                metric_name = insight.get('name', '')
                values = insight.get('values', [])
                if values:
                    engagement_metrics[metric_name] = values[0].get('value', 0)
            
            # Calculate total engagement
            post_engagement = (
                engagement_metrics.get('post_impressions', 0) +
                engagement_metrics.get('post_engaged_users', 0) +
                engagement_metrics.get('post_clicks', 0)
            )
            total_engagement += post_engagement
            
            formatted_posts.append({
                "post_id": post.get('id', ''),
                "message": post.get('message', '')[:200] + "..." if len(post.get('message', '')) > 200 else post.get('message', ''),
                "created_time": post.get('created_time', ''),
                "type": post.get('type', ''),
                "permalink_url": post.get('permalink_url', ''),
                "engagement_metrics": engagement_metrics,
                "total_engagement": post_engagement
            })

        # Sort by engagement
        formatted_posts.sort(key=lambda x: x['total_engagement'], reverse=True)

        return {
            "page_name": data.get('page_name', 'Unknown'),
            "page_id": data.get('page_id', 'Unknown'),
            "total_posts": len(formatted_posts),
            "total_engagement": total_engagement,
            "top_posts": formatted_posts[:10],  # Top 10 posts
            "date_range": data.get('date_range', {})
        }

    def _format_ad_insights(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format ad insights data"""
        insights_data = data.get('data', [])
        
        if not insights_data:
            return {
                "message": "No ad insights data available for the specified date range",
                "ad_account_name": data.get('ad_account_name', 'Unknown')
            }

        # Format ad performance metrics
        formatted_metrics = {}
        total_spend = 0
        total_impressions = 0
        total_clicks = 0
        
        for insight in insights_data:
            for metric_name, value in insight.items():
                if metric_name not in ['date_start', 'date_stop']:
                    if metric_name not in formatted_metrics:
                        formatted_metrics[metric_name] = 0
                    formatted_metrics[metric_name] += float(value) if value else 0
                    
                    # Track key metrics
                    if metric_name == 'spend':
                        total_spend += float(value) if value else 0
                    elif metric_name == 'impressions':
                        total_impressions += float(value) if value else 0
                    elif metric_name == 'clicks':
                        total_clicks += float(value) if value else 0

        return {
            "ad_account_name": data.get('ad_account_name', 'Unknown'),
            "ad_account_id": data.get('ad_account_id', 'Unknown'),
            "date_range": data.get('date_range', {}),
            "metrics": formatted_metrics,
            "summary": {
                "total_spend": total_spend,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "cpm": (total_spend / total_impressions * 1000) if total_impressions > 0 else 0,
                "cpc": (total_spend / total_clicks) if total_clicks > 0 else 0,
                "ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            }
        }

    def _get_metric_description(self, metric_name: str) -> str:
        """Get human-readable description for Facebook metrics"""
        descriptions = {
            'page_impressions': 'Total number of times your page content was displayed',
            'page_reach': 'Number of unique people who saw your page content',
            'page_engaged_users': 'Number of people who engaged with your page content',
            'page_post_engagements': 'Total engagements on your page posts',
            'page_video_views': 'Number of times your page videos were viewed',
            'page_fans': 'Number of people who like your page',
            'page_views': 'Number of times your page was viewed',
            'page_actions_post_reactions': 'Number of reactions on your page posts',
            'page_actions_post_comments': 'Number of comments on your page posts',
            'page_actions_post_shares': 'Number of shares of your page posts'
        }
        return descriptions.get(metric_name, f'Facebook metric: {metric_name}')

    def _generate_insights_summary(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of page insights"""
        summary = {
            "top_metrics": [],
            "performance_indicators": {}
        }
        
        # Sort metrics by value
        sorted_metrics = sorted(metrics.items(), key=lambda x: x[1].get('value', 0), reverse=True)
        summary["top_metrics"] = [
            {
                "metric": name,
                "value": data.get('value', 0),
                "description": data.get('description', '')
            }
            for name, data in sorted_metrics[:5]
        ]
        
        # Calculate performance indicators
        impressions = metrics.get('page_impressions', {}).get('value', 0)
        reach = metrics.get('page_reach', {}).get('value', 0)
        engaged_users = metrics.get('page_engaged_users', {}).get('value', 0)
        
        if impressions > 0:
            summary["performance_indicators"]["reach_rate"] = (reach / impressions) * 100
        if reach > 0:
            summary["performance_indicators"]["engagement_rate"] = (engaged_users / reach) * 100
        
        return summary
