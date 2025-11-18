"""
Unit tests for date utility functions
"""

import pytest
from datetime import datetime
from freezegun import freeze_time
from app.utils.date_utils import (
    extract_date_from_tool_result,
    is_iso_date_format,
    convert_relative_dates_to_iso,
    get_default_date_range,
    format_date_for_api,
)


class TestDateUtils:
    """Test cases for date utility functions"""

    def test_extract_date_from_tool_result(self):
        """Test extracting dates from tool results"""
        # Test with Start Date format
        result = "Start Date: 2024-01-15"
        assert extract_date_from_tool_result(result) == "2024-01-15"

        # Test with End Date format
        result = "End Date: 2024-01-20"
        assert extract_date_from_tool_result(result) == "2024-01-20"

        # Test with any YYYY-MM-DD pattern
        result = "Some text 2024-02-01 more text"
        assert extract_date_from_tool_result(result) == "2024-02-01"

        # Test fallback to today
        result = "No date here"
        with freeze_time("2024-01-15"):
            assert extract_date_from_tool_result(result) == "2024-01-15"

    def test_is_iso_date_format(self):
        """Test ISO date format validation"""
        # Valid ISO date formats (only checks format, not date validity)
        assert is_iso_date_format("2024-01-15") is True
        assert is_iso_date_format("2023-12-31") is True
        assert is_iso_date_format("2020-02-29") is True  # Leap year
        assert (
            is_iso_date_format("2024-13-01") is True
        )  # Invalid month but correct format
        assert (
            is_iso_date_format("2024-01-32") is True
        )  # Invalid day but correct format

        # Invalid formats
        assert is_iso_date_format("2024/01/15") is False
        assert is_iso_date_format("01-15-2024") is False
        assert is_iso_date_format("not a date") is False
        assert is_iso_date_format("") is False
        assert is_iso_date_format("2024-1-15") is False  # Missing leading zero
        assert is_iso_date_format("2024-01-5") is False  # Missing leading zero

    def test_get_default_date_range(self):
        """Test default date range generation"""
        with freeze_time("2024-01-15"):
            start_date, end_date = get_default_date_range(days_back=30)
            assert start_date == "2023-12-16"  # 30 days before 2024-01-15
            assert end_date == "2024-01-15"  # Today

        # Test with different days_back
        with freeze_time("2024-01-15"):
            start_date, end_date = get_default_date_range(days_back=7)
            assert start_date == "2024-01-08"  # 7 days before
            assert end_date == "2024-01-15"

    def test_format_date_for_api(self):
        """Test date formatting for different APIs"""
        # Google Ads - should return ISO format
        assert format_date_for_api("2024-01-15", "google_ads") == "2024-01-15"

        # GA4 - should accept relative dates
        assert format_date_for_api("yesterday", "ga4") == "yesterday"
        assert format_date_for_api("7daysAgo", "ga4") == "7daysAgo"

        # Facebook - should accept relative dates
        assert format_date_for_api("last_week", "facebook") == "last_week"

        # Default behavior
        assert format_date_for_api("2024-01-15", "unknown") == "2024-01-15"

    def test_convert_relative_dates_to_iso_placeholder(self):
        """Placeholder for testing relative date conversion"""
        # Full testing would require mocking DateConversionTool
        # This is a complex integration test that should be in integration/
        pass
