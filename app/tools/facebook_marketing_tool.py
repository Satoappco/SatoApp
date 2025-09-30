"""
Facebook Marketing Tool for CrewAI - COMPREHENSIVE TOOL
Handles both Facebook analytics and advertising data in one unified tool
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


class FacebookMarketingInput(BaseModel):
    """Input schema for FacebookMarketingTool."""
    data_type: str = Field("auto", description="Type of data to fetch: 'auto', 'page_insights', 'page_posts', 'ad_insights', 'campaigns'")
    metrics: Optional[List[str]] = Field(None, description="Specific metrics to retrieve (optional - will use smart defaults)")
    start_date: str = Field("7daysAgo", description="Start date in YYYY-MM-DD format or relative")
    end_date: str = Field("today", description="End date in YYYY-MM-DD format or relative")
    level: str = Field("account", description="Level of data aggregation: 'account', 'campaign', 'adset', 'ad' (for ads data)")
    limit: int = Field(100, description="Maximum number of results to return")
    asset_id: Optional[str] = Field(None, description="Specific Facebook asset ID (optional - will auto-detect)")


class FacebookMarketingTool(BaseTool):
    name: str = "Facebook Marketing Data Fetcher"
    description: str = (
        "Comprehensive Facebook marketing tool that automatically determines and fetches the most relevant "
        "Facebook data based on your request. This tool can handle page insights, social media metrics, "
        "advertising performance, campaign data, and content analysis. It intelligently chooses between "
        "analytics and advertising data based on available connections and request context."
    )
    args_schema: Type[BaseModel] = FacebookMarketingInput

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
        data_type: str = "auto", 
        metrics: List[str] = None, 
        start_date: str = "7daysAgo", 
        end_date: str = "today", 
        level: str = "account",
        limit: int = 100,
        asset_id: str = None
    ) -> str:
        """Execute Facebook marketing data fetch with intelligent data type detection"""
        try:
            if not self.user_id or not self.subclient_id:
                return json.dumps({
                    "error": "User ID and Subclient ID are required for Facebook marketing data",
                    "status": "error"
                })

            # Initialize Facebook service
            facebook_service = FacebookService()

            # Get Facebook connections with token refresh
            social_connections = asyncio.run(facebook_service.get_facebook_connection_for_user(
                user_id=self.user_id,
                subclient_id=self.subclient_id,
                asset_type="SOCIAL_MEDIA"
            ))
            
            ad_connections = asyncio.run(facebook_service.get_facebook_connection_for_user(
                user_id=self.user_id,
                subclient_id=self.subclient_id,
                asset_type="ADVERTISING"
            ))
            
            connections = []
            if social_connections and "error" not in social_connections:
                connections.append(social_connections)
            if ad_connections and "error" not in ad_connections:
                connections.append(ad_connections)
            
            if not connections:
                return json.dumps({
                    "error": "No active Facebook connections found. Please connect your Facebook account first.",
                    "status": "error",
                    "suggestion": "Use the Connections tab to connect your Facebook account"
                })

            # Check for token errors
            for conn in [social_connections, ad_connections]:
                if conn and "error" in conn:
                    return json.dumps({
                        "error": conn["error"],
                        "status": "error",
                        "requires_reauth": conn.get("requires_reauth", False),
                        "suggestion": "Please re-authenticate your Facebook account in the Connections tab"
                    })

            # Determine data type if auto
            if data_type == "auto":
                data_type = self._determine_data_type(connections, metrics)
                print(f"🔍 Auto-detected data type: {data_type}")

            # Fetch data based on determined type
            results = []
            
            if data_type in ["page_insights", "page_posts"]:
                # Use social media connections
                for conn in connections:
                    if conn["asset_type"] == "SOCIAL_MEDIA":
                        if asset_id and conn["external_id"] != asset_id:
                            continue
                        
                        result = asyncio.run(facebook_service.fetch_facebook_data(
                            connection_id=conn["connection_id"],
                            data_type=data_type,
                            start_date=start_date,
                            end_date=end_date,
                            metrics=metrics,
                            limit=limit
                        ))
                        results.append(result)
                    
            elif data_type in ["ad_insights", "campaigns"]:
                # Use advertising connections
                for conn in connections:
                    if conn["asset_type"] == "ADVERTISING":
                        if asset_id and conn["external_id"] != asset_id:
                            continue
                        
                        result = asyncio.run(facebook_service.fetch_facebook_data(
                            connection_id=conn["connection_id"],
                            data_type="ad_insights",
                            start_date=start_date,
                            end_date=end_date,
                            metrics=metrics,
                            limit=limit
                        ))
                        results.append(result)
            
            else:
                return json.dumps({
                    "error": f"Unsupported data type: {data_type}",
                    "status": "error",
                    "supported_types": ["auto", "page_insights", "page_posts", "ad_insights", "campaigns"]
                })

            # Format and combine results
            formatted_result = self._format_combined_data(results, data_type, level)
            
            return json.dumps({
                "status": "success",
                "data_type": data_type,
                "source": "Facebook Marketing API",
                "date_range": f"{start_date} to {end_date}",
                "assets_analyzed": len(results),
                "data": formatted_result,
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            error_msg = f"Facebook marketing data fetch failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            return json.dumps({
                "error": error_msg,
                "status": "error",
                "data_type": data_type,
                "source": "Facebook Marketing API"
            })

    def _get_facebook_connections(self) -> List[tuple]:
        """Get all active Facebook connections for user/subclient"""
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == self.user_id,
                    DigitalAsset.subclient_id == self.subclient_id,
                    DigitalAsset.provider == "Facebook",
                    Connection.revoked == False
                )
            )
            
            results = session.exec(statement).all()
            return results

    def _determine_data_type(self, connections: List[dict], metrics: List[str] = None) -> str:
        """Intelligently determine the best data type based on available connections and metrics"""
        # Check what types of connections are available
        has_social = any(conn["asset_type"] == "SOCIAL_MEDIA" for conn in connections)
        has_advertising = any(conn["asset_type"] == "ADVERTISING" for conn in connections)
        
        # If metrics are specified, try to determine from metric names
        if metrics:
            ad_metrics = ['impressions', 'clicks', 'spend', 'conversions', 'cpm', 'cpc', 'ctr']
            social_metrics = ['page_impressions', 'page_reach', 'page_engaged_users', 'page_fans']
            
            has_ad_metrics = any(metric in ad_metrics for metric in metrics)
            has_social_metrics = any(metric in social_metrics for metric in metrics)
            
            if has_ad_metrics and has_advertising:
                return "ad_insights"
            elif has_social_metrics and has_social:
                return "page_insights"
        
        # Default priority: advertising first (more valuable for marketing), then social
        if has_advertising:
            return "ad_insights"
        elif has_social:
            return "page_insights"
        else:
            return "page_insights"  # Fallback

    def _format_combined_data(self, results: List[Dict[str, Any]], data_type: str, level: str) -> Dict[str, Any]:
        """Format and combine data from multiple Facebook assets"""
        if not results:
            return {
                "message": "No data available for the specified criteria",
                "data_type": data_type
            }

        if data_type in ["page_insights", "page_posts"]:
            return self._format_social_data(results, data_type)
        elif data_type in ["ad_insights", "campaigns"]:
            return self._format_advertising_data(results, level)
        else:
            return {"raw_data": results}

    def _format_social_data(self, results: List[Dict[str, Any]], data_type: str) -> Dict[str, Any]:
        """Format social media data from multiple pages"""
        combined_data = {
            "data_type": data_type,
            "total_assets": len(results),
            "assets": [],
            "summary": {
                "total_impressions": 0,
                "total_reach": 0,
                "total_engagement": 0,
                "total_posts": 0
            }
        }

        for result in results:
            asset_data = {
                "asset_name": result.get('page_name', 'Unknown'),
                "asset_id": result.get('page_id', 'Unknown'),
                "data": result.get('data', []),
                "metrics": result.get('metrics', [])
            }
            combined_data["assets"].append(asset_data)

            # Aggregate summary metrics
            if data_type == "page_insights":
                for insight in result.get('data', []):
                    if insight.get('name') == 'page_impressions':
                        combined_data["summary"]["total_impressions"] += sum(
                            val.get('value', 0) for val in insight.get('values', [])
                        )
                    elif insight.get('name') == 'page_reach':
                        combined_data["summary"]["total_reach"] += sum(
                            val.get('value', 0) for val in insight.get('values', [])
                        )
            elif data_type == "page_posts":
                combined_data["summary"]["total_posts"] += len(result.get('data', []))

        return combined_data

    def _format_advertising_data(self, results: List[Dict[str, Any]], level: str) -> Dict[str, Any]:
        """Format advertising data from multiple ad accounts"""
        combined_data = {
            "data_type": "ad_insights",
            "level": level,
            "total_accounts": len(results),
            "accounts": [],
            "summary": {
                "total_impressions": 0,
                "total_clicks": 0,
                "total_spend": 0,
                "total_conversions": 0,
                "overall_ctr": 0,
                "overall_cpm": 0,
                "overall_cpc": 0
            }
        }

        total_impressions = 0
        total_clicks = 0
        total_spend = 0
        total_conversions = 0

        for result in results:
            account_data = {
                "account_name": result.get('ad_account_name', 'Unknown'),
                "account_id": result.get('ad_account_id', 'Unknown'),
                "data": result.get('data', []),
                "metrics": result.get('metrics', [])
            }
            combined_data["accounts"].append(account_data)

            # Aggregate metrics
            for insight in result.get('data', []):
                total_impressions += float(insight.get('impressions', 0))
                total_clicks += float(insight.get('clicks', 0))
                total_spend += float(insight.get('spend', 0))
                total_conversions += float(insight.get('conversions', 0))

        # Calculate summary metrics
        combined_data["summary"]["total_impressions"] = total_impressions
        combined_data["summary"]["total_clicks"] = total_clicks
        combined_data["summary"]["total_spend"] = total_spend
        combined_data["summary"]["total_conversions"] = total_conversions
        
        if total_impressions > 0:
            combined_data["summary"]["overall_ctr"] = (total_clicks / total_impressions) * 100
            combined_data["summary"]["overall_cpm"] = (total_spend / total_impressions) * 1000
        
        if total_clicks > 0:
            combined_data["summary"]["overall_cpc"] = total_spend / total_clicks

        return combined_data
