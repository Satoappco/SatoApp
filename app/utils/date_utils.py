"""
Centralized date utility functions for the Sato AI platform
Handles date conversion and extraction across all tools and services
"""

import re
from datetime import datetime, timedelta
from typing import Optional


def extract_date_from_tool_result(tool_result: str) -> str:
    """
    Extract YYYY-MM-DD date from DateConversionTool result
    
    Args:
        tool_result: Result string from DateConversionTool
        
    Returns:
        Date string in YYYY-MM-DD format, or today's date as fallback
    """
    # Look for "Start Date: YYYY-MM-DD" or "End Date: YYYY-MM-DD" pattern
    date_match = re.search(r'(?:Start Date|End Date):\s*(\d{4}-\d{2}-\d{2})', tool_result)
    if date_match:
        return date_match.group(1)
    
    # Fallback: look for any YYYY-MM-DD pattern
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', tool_result)
    if date_match:
        return date_match.group(1)
    
    # If no date found, return today's date as fallback
    return datetime.now().strftime("%Y-%m-%d")


def is_iso_date_format(date_string: str) -> bool:
    """
    Check if a date string is already in YYYY-MM-DD format
    
    Args:
        date_string: Date string to check
        
    Returns:
        True if the string is in YYYY-MM-DD format, False otherwise
    """
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', date_string))


def convert_relative_dates_to_iso(
    start_date: str, 
    end_date: str, 
    date_tool=None
) -> tuple[str, str]:
    """
    Convert relative dates to YYYY-MM-DD format if needed
    
    Args:
        start_date: Start date (relative or ISO format)
        end_date: End date (relative or ISO format)
        date_tool: DateConversionTool instance (optional, will create if not provided)
        
    Returns:
        Tuple of (start_date_iso, end_date_iso) in YYYY-MM-DD format
    """
    # Check if dates are already in YYYY-MM-DD format
    if is_iso_date_format(start_date) and is_iso_date_format(end_date):
        return start_date, end_date
    
    # Import here to avoid circular imports
    if date_tool is None:
        from app.tools.date_conversion_tool import DateConversionTool
        date_tool = DateConversionTool()
    
    # Convert relative dates using the date conversion tool
    start_result = date_tool._run(start_date)
    end_result = date_tool._run(end_date)
    
    # Extract dates from tool results
    start_date_iso = extract_date_from_tool_result(start_result)
    end_date_iso = extract_date_from_tool_result(end_result)
    
    return start_date_iso, end_date_iso


def get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """
    Get default date range for the last N days
    
    Args:
        days_back: Number of days to go back from today
        
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    end_date_iso = datetime.now().strftime("%Y-%m-%d")
    start_date_iso = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    return start_date_iso, end_date_iso


def format_date_for_api(date_string: str, api_type: str = "google_ads") -> str:
    """
    Format date string for specific API requirements
    
    Args:
        date_string: Date string to format
        api_type: Type of API ("google_ads", "ga4", "facebook")
        
    Returns:
        Formatted date string for the specific API
    """
    if api_type == "google_ads":
        # Google Ads requires YYYY-MM-DD format
        if not is_iso_date_format(date_string):
            # Convert relative dates
            start_iso, _ = convert_relative_dates_to_iso(date_string, "today")
            return start_iso
        return date_string
    elif api_type in ["ga4", "facebook"]:
        # GA4 and Facebook accept relative dates
        return date_string
    else:
        # Default to ISO format
        if not is_iso_date_format(date_string):
            start_iso, _ = convert_relative_dates_to_iso(date_string, "today")
            return start_iso
        return date_string
