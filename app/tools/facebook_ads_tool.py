"""
Facebook Ads Tool for CrewAI - REAL DATA IMPLEMENTATION
Provides Facebook advertising data, campaign performance, and ad insights
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


class FacebookAdsInput(BaseModel):
    """Input schema for FacebookAdsTool."""
    metrics: List[str] = Field(..., description="Specific metrics to retrieve (e.g., ['impressions', 'clicks', 'spend', 'conversions', 'cpm', 'cpc', 'ctr'])")
    dimensions: List[str] = Field(default=[], description="Dimensions to group by (e.g., ['campaign.name', 'adset.name', 'ad.name'])")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    level: str = Field("account", description="Level of data aggregation: 'account', 'campaign', 'adset', 'ad'")
    limit: int = Field(100, description="Maximum number of results to return")
    ad_account_id: Optional[str] = Field(None, description="Specific Facebook ad account ID (optional - will auto-detect if not provided)")


class FacebookAdsTool(BaseTool):
    name: str = "Facebook Ads Data Fetcher"
    description: str = (
        "Fetch Facebook advertising performance data from the Facebook Ads API. "
        "This tool retrieves REAL data from Facebook ad accounts including campaign performance, "
        "ad spend, impressions, clicks, conversions, and detailed advertising metrics. "
        "Perfect for advertising analysis, campaign optimization, and ROI tracking."
    )
    args_schema: Type[BaseModel] = FacebookAdsInput

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
        metrics: List[str], 
        dimensions: List[str] = None, 
        start_date: str = None, 
        end_date: str = None, 
        level: str = "account",
        limit: int = 100,
        ad_account_id: str = None
    ) -> str:
        """Execute Facebook ads data fetch with REAL DATA based on agent's specifications"""
        try:
            if not self.user_id or not self.subclient_id:
                return json.dumps({
                    "error": "User ID and Subclient ID are required for Facebook ads",
                    "status": "error"
                })

            if dimensions is None:
                dimensions = []

            # Master agent should provide ISO dates via DateConversionTool
            # No date conversion needed here - master agent handles it

            # Initialize Facebook service
            facebook_service = FacebookService()

            # Get Facebook ad account connection with token refresh
            # Use ThreadPoolExecutor to handle async operations properly
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, facebook_service.get_facebook_connection_for_user(
                        user_id=self.user_id,
                        subclient_id=self.subclient_id,
                        asset_type="ADVERTISING"
                    ))
                    connection_info = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                connection_info = asyncio.run(facebook_service.get_facebook_connection_for_user(
                    user_id=self.user_id,
                    subclient_id=self.subclient_id,
                    asset_type="ADVERTISING"
                ))
            
            if not connection_info:
                return json.dumps({
                    "error": "No active Facebook ad account connection found. Please connect your Facebook account first.",
                    "status": "error",
                    "suggestion": "Use the Connections tab to connect your Facebook account with ad account access"
                })
            
            if "error" in connection_info:
                # If refresh failed, try to use the connection anyway - maybe the token is still valid
                print(f"⚠️ Facebook token refresh failed: {connection_info['error']}")
                print(f"🔄 Attempting to use existing token for API call...")
                
                # Try to get the connection ID and use it directly
                if "connection_id" in connection_info:
                    connection_id = connection_info["connection_id"]
                else:
                    return json.dumps({
                        "error": connection_info["error"],
                        "status": "error",
                        "requires_reauth": connection_info.get("requires_reauth", False),
                        "suggestion": "Please re-authenticate your Facebook account in the Connections tab"
                    })
            else:
                connection_id = connection_info["connection_id"]

            # Fetch ad insights data
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, facebook_service.fetch_facebook_data(
                        connection_id=connection_info["connection_id"],
                        data_type="ad_insights",
                        start_date=start_date,
                        end_date=end_date,
                        metrics=metrics,
                        limit=limit
                    ))
                    result = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                result = asyncio.run(facebook_service.fetch_facebook_data(
                    connection_id=connection_info["connection_id"],
                    data_type="ad_insights",
                    start_date=start_date,
                    end_date=end_date,
                    metrics=metrics,
                    limit=limit
                ))

            # Format the response for the agent
            formatted_result = self._format_ads_data(result, metrics, dimensions, level)
            
            return json.dumps({
                "status": "success",
                "data_type": "ad_insights",
                "source": "Facebook Ads API",
                "level": level,
                "date_range": f"{start_date} to {end_date}",
                "data": formatted_result,
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            error_msg = f"Facebook ads data fetch failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            return json.dumps({
                "error": error_msg,
                "status": "error",
                "data_type": "ad_insights",
                "source": "Facebook Ads API"
            })

    def _get_facebook_ad_connection(self, ad_account_id: str = None) -> Optional[Connection]:
        """Get active Facebook ad account connection for user/subclient"""
        with get_session() as session:
            # Look for Facebook advertising connections
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == self.user_id,
                    DigitalAsset.subclient_id == self.subclient_id,
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.ADVERTISING,
                    Connection.revoked == False
                )
            )
            
            if ad_account_id:
                statement = statement.where(DigitalAsset.external_id == ad_account_id)
            
            result = session.exec(statement).first()
            return result[0] if result else None


    def _format_ads_data(self, data: Dict[str, Any], metrics: List[str], dimensions: List[str], level: str) -> Dict[str, Any]:
        """Format Facebook ads data for agent consumption"""
        insights_data = data.get('data', [])
        
        if not insights_data:
            return {
                "message": "No ad insights data available for the specified date range",
                "ad_account_name": data.get('ad_account_name', 'Unknown'),
                "metrics_requested": metrics,
                "level": level
            }

        # Format ad performance data
        formatted_campaigns = []
        total_metrics = {}
        
        for insight in insights_data:
            campaign_data = {
                "date_start": insight.get('date_start', ''),
                "date_stop": insight.get('date_stop', ''),
                "metrics": {},
                "performance_indicators": {}
            }
            
            # Extract metrics
            for metric in metrics:
                value = insight.get(metric, 0)
                campaign_data["metrics"][metric] = {
                    "value": float(value) if value else 0,
                    "description": self._get_ads_metric_description(metric)
                }
                
                # Accumulate totals
                if metric not in total_metrics:
                    total_metrics[metric] = 0
                total_metrics[metric] += float(value) if value else 0
            
            # Calculate performance indicators
            impressions = float(insight.get('impressions', 0))
            clicks = float(insight.get('clicks', 0))
            spend = float(insight.get('spend', 0))
            conversions = float(insight.get('conversions', 0))
            
            if impressions > 0:
                campaign_data["performance_indicators"]["ctr"] = (clicks / impressions) * 100
                campaign_data["performance_indicators"]["cpm"] = (spend / impressions) * 1000
            
            if clicks > 0:
                campaign_data["performance_indicators"]["cpc"] = spend / clicks
            
            if conversions > 0:
                campaign_data["performance_indicators"]["cost_per_conversion"] = spend / conversions
                campaign_data["performance_indicators"]["conversion_rate"] = (conversions / clicks) * 100
            
            formatted_campaigns.append(campaign_data)

        # Calculate overall performance summary
        total_impressions = total_metrics.get('impressions', 0)
        total_clicks = total_metrics.get('clicks', 0)
        total_spend = total_metrics.get('spend', 0)
        total_conversions = total_metrics.get('conversions', 0)

        summary = {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": total_spend,
            "total_conversions": total_conversions,
            "overall_ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
            "overall_cpm": (total_spend / total_impressions * 1000) if total_impressions > 0 else 0,
            "overall_cpc": (total_spend / total_clicks) if total_clicks > 0 else 0,
            "cost_per_conversion": (total_spend / total_conversions) if total_conversions > 0 else 0,
            "conversion_rate": (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        }

        return {
            "ad_account_name": data.get('ad_account_name', 'Unknown'),
            "ad_account_id": data.get('ad_account_id', 'Unknown'),
            "level": level,
            "date_range": data.get('date_range', {}),
            "campaigns": formatted_campaigns,
            "summary": summary,
            "metrics_breakdown": self._format_metrics_breakdown(total_metrics, metrics)
        }

    def _format_metrics_breakdown(self, total_metrics: Dict[str, float], requested_metrics: List[str]) -> Dict[str, Any]:
        """Format detailed metrics breakdown"""
        breakdown = {}
        
        for metric in requested_metrics:
            value = total_metrics.get(metric, 0)
            breakdown[metric] = {
                "total_value": value,
                "description": self._get_ads_metric_description(metric),
                "formatted_value": self._format_metric_value(metric, value)
            }
        
        return breakdown

    def _format_metric_value(self, metric: str, value: float) -> str:
        """Format metric value with appropriate units"""
        if metric in ['spend', 'cost_per_conversion', 'cpc']:
            return f"${value:.2f}"
        elif metric in ['ctr', 'conversion_rate']:
            return f"{value:.2f}%"
        elif metric in ['cpm']:
            return f"${value:.2f}"
        elif metric in ['impressions', 'clicks', 'conversions']:
            return f"{int(value):,}"
        else:
            return f"{value:.2f}"

    def _get_ads_metric_description(self, metric_name: str) -> str:
        """Get human-readable description for Facebook ads metrics"""
        descriptions = {
            'impressions': 'Number of times your ads were displayed',
            'clicks': 'Number of clicks on your ads',
            'spend': 'Total amount spent on ads (in USD)',
            'conversions': 'Number of conversions from ads',
            'cpm': 'Cost per 1,000 impressions',
            'cpc': 'Cost per click',
            'ctr': 'Click-through rate (clicks/impressions)',
            'reach': 'Number of unique people who saw your ads',
            'frequency': 'Average number of times each person saw your ads',
            'cost_per_conversion': 'Average cost per conversion',
            'conversion_rate': 'Percentage of clicks that resulted in conversions',
            'video_views': 'Number of times your video ads were viewed',
            'video_view_rate': 'Percentage of impressions that resulted in video views',
            'link_clicks': 'Number of clicks on links in your ads',
            'post_engagements': 'Total engagements on your ad posts',
            'page_likes': 'Number of new page likes from ads',
            'post_likes': 'Number of likes on your ad posts',
            'post_comments': 'Number of comments on your ad posts',
            'post_shares': 'Number of shares of your ad posts'
        }
        return descriptions.get(metric_name, f'Facebook ads metric: {metric_name}')
