"""
Google Ads Analytics Tool for CrewAI - REAL DATA IMPLEMENTATION
"""

from crewai.tools import BaseTool
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field
import json
from datetime import datetime, timedelta
import os

from app.services.google_ads_service import GoogleAdsService
from app.utils.async_utils import run_async_in_thread
from app.utils.date_utils import convert_relative_dates_to_iso


class GoogleAdsAnalyticsInput(BaseModel):
    """Input schema for GoogleAdsAnalyticsTool."""
    metrics: List[str] = Field(..., description="Specific metrics to retrieve (e.g., ['clicks', 'impressions', 'cost', 'conversions'])")
    dimensions: List[str] = Field(default=[], description="Dimensions to group by (e.g., ['campaign.name', 'campaign.status'])")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    limit: int = Field(default=100, description="Maximum number of rows to return")


class GoogleAdsAnalyticsTool(BaseTool):
    name: str = "Google Ads Data Fetcher"
    description: str = (
        "Fetch Google Ads performance data from the Google Ads API. "
        "This tool retrieves REAL data based on the metrics, dimensions, and date range you specify. "
        "You must provide specific metrics you want to analyze and the date range for the analysis."
    )
    args_schema: Type[BaseModel] = GoogleAdsAnalyticsInput

    # Allow extra fields for Pydantic model
    class Config:
        extra = "allow"

    def __init__(self, user_id: int = None, subclient_id: int = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'user_id', user_id)
        object.__setattr__(self, 'subclient_id', subclient_id)
    

    def _run(self, metrics: List[str], dimensions: List[str] = None, start_date: str = None, end_date: str = None, limit: int = 100) -> str:
        """Execute Google Ads data fetch with REAL DATA based on agent's specifications"""
        try:
            if dimensions is None:
                dimensions = []
            
            # Use stored user_id and subclient_id from initialization
            if not self.user_id or not self.subclient_id:
                return json.dumps({
                    "status": "error",
                    "message": "No user/subclient context available for Google Ads data fetching. Tool needs to be initialized with user_id and subclient_id."
                }, indent=2)
            
            # Convert relative dates to YYYY-MM-DD format if needed (Google Ads API requires ISO format)
            if start_date and end_date:
                start_date, end_date = convert_relative_dates_to_iso(start_date, end_date)
                print(f"🔄 Converted dates for Google Ads API: {start_date} to {end_date}")
            
            # Initialize Google Ads service
            google_ads_service = GoogleAdsService()
            
            # Get subclient's Google Ads connections
            user_connections = run_async_in_thread(google_ads_service.get_user_google_ads_connections(self.user_id, self.subclient_id))
            
            if not user_connections:
                return json.dumps({
                    "status": "error",
                    "message": f"No Google Ads connections found for subclient {self.subclient_id}. Please connect your Google Ads account first."
                }, indent=2)
            
            # Use the first available connection
            connection = user_connections[0]
            connection_id = connection["connection_id"]
            customer_id = connection["customer_id"]
            
            # Fetch real Google Ads data with agent-specified parameters
            ads_data = run_async_in_thread(google_ads_service.get_google_ads_data(
                connection_id=connection_id,
                customer_id=customer_id,
                metrics=metrics,
                dimensions=dimensions,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            ))
            
            if not ads_data.get("success"):
                return json.dumps({
                    "status": "error",
                    "message": f"Failed to fetch Google Ads data: {ads_data.get('error', 'Unknown error')}"
                }, indent=2)
            
            # Return the raw data for the agent to analyze
            result = {
                "status": "success",
                "data": ads_data.get("data", []),  # Fixed: service returns "data", not "rows"
                "metadata": {
                    "metrics_requested": metrics,
                    "dimensions_requested": dimensions,
                    "date_range": f"{start_date} to {end_date}",
                    "row_count": ads_data.get("total_rows", 0),  # Fixed: service returns "total_rows", not "row_count"
                    "account": {
                        "customer_id": customer_id,
                        "descriptive_name": connection.get("account_name", "Unknown"),
                        "currency_code": "USD"  # Default currency, could be enhanced to get from connection
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Google Ads data fetch failed: {str(e)}"
            }, indent=2)
