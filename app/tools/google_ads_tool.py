"""
Google Ads Analytics Tool for CrewAI - REAL DATA IMPLEMENTATION
"""

from crewai.tools import BaseTool
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field
import json
from datetime import datetime, timedelta
import os

from app.services.google_analytics_service import GoogleAnalyticsService


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

    def __init__(self, user_id: int = None, customer_id: int = None):
        super().__init__()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'user_id', user_id)
        object.__setattr__(self, 'customer_id', customer_id)

    def _run(self, metrics: List[str], dimensions: List[str] = None, start_date: str = None, end_date: str = None, limit: int = 100) -> str:
        """Execute Google Ads data fetch with REAL DATA based on agent's specifications"""
        try:
            if dimensions is None:
                dimensions = []
            
            # Use stored user_id and customer_id from initialization
            if not self.user_id or not self.customer_id:
                return json.dumps({
                    "status": "error",
                    "message": "No user/customer context available for Google Ads data fetching. Tool needs to be initialized with user_id and customer_id."
                }, indent=2)
            
            # Initialize Google Analytics service (which now includes Google Ads)
            ga_service = GoogleAnalyticsService()
            
            # Get customer's Google connections (customer owns the connections)
            # Use asyncio.run() but handle the event loop properly
            import asyncio
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, ga_service.get_user_ga_connections(self.customer_id))
                    user_connections = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                user_connections = asyncio.run(ga_service.get_user_ga_connections(self.customer_id))
            
            if not user_connections:
                return json.dumps({
                    "status": "error",
                    "message": f"No Google Ads connections found for customer {self.customer_id}. Please connect your Google Ads account first."
                }, indent=2)
            
            # Use the first available connection
            connection = user_connections[0]
            connection_id = connection["connection_id"]
            
            # Get Google Ads accounts
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, ga_service.get_google_ads_accounts(connection_id))
                    accounts = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                accounts = asyncio.run(ga_service.get_google_ads_accounts(connection_id))
            
            if not accounts:
                return json.dumps({
                    "status": "error",
                    "message": "No Google Ads accounts found. Please ensure your Google Ads account is properly connected."
                }, indent=2)
            
            # Use the first account
            account = accounts[0]
            customer_id = account["customer_id"]
            
            # Fetch real Google Ads data with agent-specified parameters
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, ga_service.fetch_google_ads_data(
                        connection_id=connection_id,
                        customer_id=customer_id,
                        metrics=metrics,
                        dimensions=dimensions,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit
                    ))
                    ads_data = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                ads_data = asyncio.run(ga_service.fetch_google_ads_data(
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
                "data": ads_data.get("rows", []),
                "metadata": {
                    "metrics_requested": metrics,
                    "dimensions_requested": dimensions,
                    "date_range": f"{start_date} to {end_date}",
                    "row_count": ads_data.get("row_count", 0),
                    "account": {
                        "customer_id": customer_id,
                        "descriptive_name": account.get("descriptive_name", "Unknown"),
                        "currency_code": account.get("currency_code", "USD")
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
