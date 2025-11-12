# server.py
import sys
import os
import json
from typing import Dict, List, Optional, Any, Union
import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import AnyUrl

# Create an MCP server
mcp = FastMCP("Google Analytics MCP")

# Environment variables for Google Analytics configuration
GOOGLE_ANALYTICS_CLIENT_ID = os.environ.get("GOOGLE_ANALYTICS_CLIENT_ID")
GOOGLE_ANALYTICS_CLIENT_SECRET = os.environ.get("GOOGLE_ANALYTICS_CLIENT_SECRET")
GOOGLE_ANALYTICS_REFRESH_TOKEN = os.environ.get("GOOGLE_ANALYTICS_REFRESH_TOKEN")
GOOGLE_ANALYTICS_PROPERTY_ID = os.environ.get("GOOGLE_ANALYTICS_PROPERTY_ID")

# API endpoints
GA_DATA_API = "https://analyticsdata.googleapis.com/v1beta"
GA_ADMIN_API = "https://analyticsadmin.googleapis.com/v1alpha"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Check if environment variables are set
if not all([GOOGLE_ANALYTICS_CLIENT_ID, GOOGLE_ANALYTICS_CLIENT_SECRET, GOOGLE_ANALYTICS_REFRESH_TOKEN]):
    print("Warning: Google Analytics environment variables not fully configured. Set GOOGLE_ANALYTICS_CLIENT_ID, GOOGLE_ANALYTICS_CLIENT_SECRET, and GOOGLE_ANALYTICS_REFRESH_TOKEN.", file=sys.stderr)

async def get_access_token() -> str:
    """Get a fresh access token using the refresh token."""
    data = {
        'client_id': GOOGLE_ANALYTICS_CLIENT_ID,
        'client_secret': GOOGLE_ANALYTICS_CLIENT_SECRET,
        'refresh_token': GOOGLE_ANALYTICS_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data)
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            print(f"Error getting access token: {response.text}", file=sys.stderr)
            return ""

# Helper function for API requests
async def make_google_analytics_request(method: str, endpoint: str, api_base: str = GA_DATA_API, data: Dict = None) -> Dict:
    """
    Make a request to the Google Analytics API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (without base URL)
        api_base: Base API URL (defaults to GA_DATA_API)
        data: Data to send (for POST/PUT)
    
    Returns:
        Response from Google Analytics API as dictionary
    """
    url = f"{api_base}{endpoint}"
    
    # Get access token
    access_token = await get_access_token()
    if not access_token:
        return {
            "error": True,
            "message": "Failed to obtain access token. Check your credentials."
        }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code >= 400:
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "message": response.text
                }
                
            return response.json()
        except Exception as e:
            return {
                "error": True,
                "message": f"API request failed: {str(e)}"
            }

# === TOOLS ===

@mcp.tool()
async def run_report(metrics: List[str], dimensions: Optional[List[str]] = None, date_range_start: str = "7daysAgo", date_range_end: str = "today", row_limit: int = 10) -> str:
    """
    Run a basic Google Analytics report with specified metrics and dimensions.
    
    Args:
        metrics: List of metrics to include (e.g., ['activeUsers', 'sessions'])
        dimensions: Optional list of dimensions (e.g., ['date', 'deviceCategory'])
        date_range_start: Start date in YYYY-MM-DD format or NdaysAgo format (default: 7daysAgo)
        date_range_end: End date in YYYY-MM-DD format or 'today' (default: today)
        row_limit: Maximum number of rows to return (default: 10)
    """
    if not GOOGLE_ANALYTICS_PROPERTY_ID:
        return "Error: GOOGLE_ANALYTICS_PROPERTY_ID environment variable is not set."
    
    # Format metrics and dimensions
    formatted_metrics = [{"name": m} for m in metrics]
    formatted_dimensions = [{"name": d} for d in dimensions] if dimensions else []
    
    # Prepare report request
    request_data = {
        "dateRanges": [
            {
                "startDate": date_range_start,
                "endDate": date_range_end
            }
        ],
        "metrics": formatted_metrics,
        "dimensions": formatted_dimensions,
        "limit": row_limit
    }
    
    result = await make_google_analytics_request(
        "POST", 
        f"/properties/{GOOGLE_ANALYTICS_PROPERTY_ID}:runReport",
        data=request_data
    )
    
    if "error" in result:
        return f"Error running report: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_accounts() -> str:
    """
    Get a list of all Google Analytics accounts that the authenticated user has access to.
    """
    result = await make_google_analytics_request(
        "GET", 
        "/accounts", 
        api_base=GA_ADMIN_API
    )
    
    if "error" in result:
        return f"Error retrieving accounts: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_properties(account_id: str) -> str:
    """
    Get a list of all properties within a Google Analytics account.
    
    Args:
        account_id: The Google Analytics account ID
    """
    result = await make_google_analytics_request(
        "GET", 
        f"/accounts/{account_id}/properties", 
        api_base=GA_ADMIN_API
    )
    
    if "error" in result:
        return f"Error retrieving properties: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_metadata() -> str:
    """
    Get metadata about available metrics and dimensions in Google Analytics.
    """
    if not GOOGLE_ANALYTICS_PROPERTY_ID:
        return "Error: GOOGLE_ANALYTICS_PROPERTY_ID environment variable is not set."
    
    result = await make_google_analytics_request(
        "GET", 
        f"/properties/{GOOGLE_ANALYTICS_PROPERTY_ID}/metadata"
    )
    
    if "error" in result:
        return f"Error retrieving metadata: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

# === RESOURCES ===

@mcp.resource("https://google-analytics/accounts")
async def get_accounts_resource() -> str:
    """Get a list of all Google Analytics accounts."""
    result = await make_google_analytics_request(
        "GET", 
        "/accounts", 
        api_base=GA_ADMIN_API
    )
    
    if "error" in result:
        return f"Error retrieving accounts: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.resource("https://google-analytics/properties/{account_id}")
async def get_properties_resource(account_id: str) -> str:
    """
    Get a list of all properties for a specific Google Analytics account.
    
    Args:
        account_id: The Google Analytics account ID
    """
    result = await make_google_analytics_request(
        "GET", 
        f"/accounts/{account_id}/properties", 
        api_base=GA_ADMIN_API
    )
    
    if "error" in result:
        return f"Error retrieving properties: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.resource("https://google-analytics/metadata")
async def get_metadata_resource() -> str:
    """Get metadata about available metrics and dimensions."""
    if not GOOGLE_ANALYTICS_PROPERTY_ID:
        return "Error: GOOGLE_ANALYTICS_PROPERTY_ID environment variable is not set."
    
    result = await make_google_analytics_request(
        "GET", 
        f"/properties/{GOOGLE_ANALYTICS_PROPERTY_ID}/metadata"
    )
    
    if "error" in result:
        return f"Error retrieving metadata: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

# === PROMPTS ===

@mcp.prompt("create_basic_report")
def create_basic_report_prompt(metrics: str = None, dimensions: str = None) -> str:
    """
    A prompt template for creating a basic Google Analytics report.
    
    Args:
        metrics: Comma-separated metrics (e.g., 'activeUsers,sessions')
        dimensions: Comma-separated dimensions (e.g., 'date,deviceCategory')
    """
    metrics_text = f"Metrics: {metrics}" if metrics else "You'll need to specify metrics for your report."
    dimensions_text = f"Dimensions: {dimensions}" if dimensions else "You can optionally specify dimensions to segment your data."
    
    return f"Please help me create a Google Analytics report with these specifications:\n\n{metrics_text}\n{dimensions_text}\n\nI'd like to analyze this data over the past 7 days."

@mcp.prompt("analyze_traffic_sources")
def analyze_traffic_sources_prompt(property_id: str = None) -> str:
    """
    A prompt template for analyzing traffic sources in Google Analytics.
    
    Args:
        property_id: The Google Analytics property ID
    """
    property_text = f"Property ID: {property_id}" if property_id else "You'll need to specify which Google Analytics property you want to analyze."
    
    return f"Please help me analyze traffic sources for my website using Google Analytics.\n\n{property_text}\n\nI'd like to understand where my visitors are coming from and which sources drive the most engagement."

@mcp.prompt("track_conversions")
def track_conversions_prompt(conversion_goal: str = None) -> str:
    """
    A prompt template for tracking conversions in Google Analytics.
    
    Args:
        conversion_goal: Description of the conversion goal to track
    """
    goal_text = f"Conversion Goal: {conversion_goal}" if conversion_goal else "You'll need to specify what conversion goal you want to track."
    
    return f"Please help me track and analyze conversions in Google Analytics.\n\n{goal_text}\n\nI want to understand my conversion rates, which user segments convert best, and how to improve my conversion funnel."

if __name__ == "__main__":
    print("Starting Google Analytics MCP server...", file=sys.stderr)
    mcp.run()
