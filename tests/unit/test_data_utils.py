"""
Tests for data formatting utilities
"""

import pytest
from app.utils.data_utils import (
    format_analytics_data,
    _format_page_insights,
    _format_page_posts,
    _format_ad_insights,
    _format_campaigns,
    combine_multiple_data_sources,
)


class TestFormatAnalyticsData:
    """Test format_analytics_data function"""

    def test_format_analytics_data_no_data(self):
        """Test formatting with no data"""
        result = format_analytics_data({}, "page_insights")
        assert result["status"] == "error"
        assert result["error"] == "No data available"
        assert result["data_type"] == "page_insights"

    def test_format_analytics_data_empty_data(self):
        """Test formatting with empty data"""
        result = format_analytics_data({"data": []}, "page_insights")
        assert result["status"] == "error"
        assert "No page insights data available" in result["error"]

    def test_format_analytics_data_page_insights(self):
        """Test formatting page insights data"""
        data = {
            "data": [
                {
                    "name": "page_impressions",
                    "values": [{"value": 1000}],
                    "period": "day",
                },
                {
                    "name": "page_post_engagements",
                    "values": [{"value": 50}],
                    "period": "day",
                },
            ]
        }
        result = format_analytics_data(data, "page_insights")

        assert result["status"] == "success"
        assert result["data_type"] == "page_insights"
        assert len(result["insights"]) == 2
        assert result["summary"]["total_impressions"] == 1000
        assert result["summary"]["total_engagements"] == 50

    def test_format_analytics_data_page_posts(self):
        """Test formatting page posts data"""
        data = {
            "data": [
                {
                    "id": "post_123",
                    "message": "Test post",
                    "created_time": "2023-01-01T12:00:00Z",
                    "insights": {
                        "data": [
                            {"name": "post_impressions", "values": [{"value": 500}]}
                        ]
                    },
                }
            ]
        }
        result = format_analytics_data(data, "page_posts")

        assert result["status"] == "success"
        assert result["data_type"] == "page_posts"
        assert len(result["posts"]) == 1
        assert result["posts"][0]["id"] == "post_123"
        assert result["posts"][0]["insights"]["post_impressions"] == 500

    def test_format_analytics_data_ad_insights(self):
        """Test formatting ad insights data"""
        data = {
            "data": [
                {
                    "campaign_id": "camp_123",
                    "campaign_name": "Test Campaign",
                    "impressions": "1000",
                    "clicks": "50",
                    "spend": "25.50",
                    "conversions": "5",
                    "cpm": "25.50",
                    "cpc": "0.51",
                    "ctr": "5.0",
                }
            ]
        }
        result = format_analytics_data(data, "ad_insights")

        assert result["status"] == "success"
        assert result["data_type"] == "ad_insights"
        assert len(result["insights"]) == 1
        assert result["insights"][0]["campaign_id"] == "camp_123"
        assert result["summary"]["total_impressions"] == 1000
        assert result["summary"]["total_clicks"] == 50
        assert result["summary"]["total_spend"] == 25.5

    def test_format_analytics_data_campaigns(self):
        """Test formatting campaigns data"""
        data = {
            "data": [
                {
                    "id": "camp_123",
                    "name": "Test Campaign",
                    "status": "ACTIVE",
                    "objective": "CONVERSIONS",
                    "created_time": "2023-01-01T12:00:00Z",
                },
                {
                    "id": "camp_456",
                    "name": "Paused Campaign",
                    "status": "PAUSED",
                    "objective": "AWARENESS",
                },
            ]
        }
        result = format_analytics_data(data, "campaigns")

        assert result["status"] == "success"
        assert result["data_type"] == "campaigns"
        assert len(result["campaigns"]) == 2
        assert result["summary"]["total_campaigns"] == 2
        assert result["summary"]["active_campaigns"] == 1
        assert result["summary"]["paused_campaigns"] == 1

    def test_format_analytics_data_unknown_type(self):
        """Test formatting unknown data type"""
        data = {"data": [{"key": "value"}]}
        result = format_analytics_data(data, "unknown_type")

        assert result["status"] == "success"
        assert result["data_type"] == "unknown_type"
        assert result["raw_data"] == [{"key": "value"}]


class TestFormatPageInsights:
    """Test _format_page_insights function"""

    def test_format_page_insights_empty(self):
        """Test formatting empty page insights"""
        result = _format_page_insights([])
        assert result["status"] == "error"
        assert "No page insights data available" in result["error"]

    def test_format_page_insights_with_data(self):
        """Test formatting page insights with data"""
        data = [
            {"name": "page_impressions", "values": [{"value": 1000}], "period": "day"},
            {"name": "page_fans", "values": [{"value": 500}], "period": "lifetime"},
        ]
        result = _format_page_insights(data)

        assert result["status"] == "success"
        assert len(result["insights"]) == 2
        assert result["insights"][0]["metric"] == "page_impressions"
        assert result["insights"][0]["value"] == 1000
        assert result["summary"]["total_impressions"] == 1000
        assert result["summary"]["total_fans"] == 500


class TestFormatPagePosts:
    """Test _format_page_posts function"""

    def test_format_page_posts_empty(self):
        """Test formatting empty page posts"""
        result = _format_page_posts([])
        assert result["status"] == "error"
        assert "No page posts data available" in result["error"]

    def test_format_page_posts_with_data(self):
        """Test formatting page posts with data"""
        data = [
            {
                "id": "post_123",
                "message": "Test message",
                "created_time": "2023-01-01T12:00:00Z",
                "insights": {
                    "data": [{"name": "post_impressions", "values": [{"value": 200}]}]
                },
            }
        ]
        result = _format_page_posts(data)

        assert result["status"] == "success"
        assert len(result["posts"]) == 1
        assert result["posts"][0]["id"] == "post_123"
        assert result["posts"][0]["insights"]["post_impressions"] == 200
        assert result["summary"]["total_posts"] == 1


class TestFormatAdInsights:
    """Test _format_ad_insights function"""

    def test_format_ad_insights_empty(self):
        """Test formatting empty ad insights"""
        result = _format_ad_insights([])
        assert result["status"] == "error"
        assert "No ad insights data available" in result["error"]

    def test_format_ad_insights_with_data(self):
        """Test formatting ad insights with data"""
        data = [
            {
                "campaign_id": "camp_123",
                "campaign_name": "Test Campaign",
                "impressions": "1000",
                "clicks": "50",
                "spend": "25.50",
                "conversions": "5",
            }
        ]
        result = _format_ad_insights(data)

        assert result["status"] == "success"
        assert len(result["insights"]) == 1
        assert result["insights"][0]["campaign_id"] == "camp_123"
        assert result["insights"][0]["impressions"] == 1000
        assert result["insights"][0]["spend"] == 25.5
        assert result["summary"]["total_impressions"] == 1000
        assert result["summary"]["total_clicks"] == 50
        assert result["summary"]["total_spend"] == 25.5


class TestFormatCampaigns:
    """Test _format_campaigns function"""

    def test_format_campaigns_empty(self):
        """Test formatting empty campaigns"""
        result = _format_campaigns([])
        assert result["status"] == "error"
        assert "No campaign data available" in result["error"]

    def test_format_campaigns_with_data(self):
        """Test formatting campaigns with data"""
        data = [
            {
                "id": "camp_123",
                "name": "Active Campaign",
                "status": "ACTIVE",
                "objective": "CONVERSIONS",
            },
            {
                "id": "camp_456",
                "name": "Paused Campaign",
                "status": "PAUSED",
                "objective": "AWARENESS",
            },
        ]
        result = _format_campaigns(data)

        assert result["status"] == "success"
        assert len(result["campaigns"]) == 2
        assert result["campaigns"][0]["status"] == "active"
        assert result["campaigns"][1]["status"] == "paused"
        assert result["summary"]["total_campaigns"] == 2
        assert result["summary"]["active_campaigns"] == 1
        assert result["summary"]["paused_campaigns"] == 1


class TestCombineMultipleDataSources:
    """Test combine_multiple_data_sources function"""

    def test_combine_multiple_data_sources_empty(self):
        """Test combining empty data sources"""
        result = combine_multiple_data_sources([])
        assert result["status"] == "success"
        assert result["sources"] == 0
        assert result["data"] == []
        assert result["summary"]["total_impressions"] == 0

    def test_combine_multiple_data_sources_with_data(self):
        """Test combining multiple data sources"""
        data_sources = [
            {
                "status": "success",
                "data_type": "page_insights",
                "summary": {"total_impressions": 1000, "total_engagements": 50},
            },
            {
                "status": "success",
                "data_type": "ad_insights",
                "summary": {
                    "total_impressions": 500,
                    "total_clicks": 25,
                    "total_spend": 12.50,
                },
            },
            {"status": "error", "data_type": "failed_source"},
        ]
        result = combine_multiple_data_sources(data_sources)

        assert result["status"] == "success"
        assert result["sources"] == 3
        assert len(result["data"]) == 2  # Only successful sources
        assert result["summary"]["total_impressions"] == 1500
        assert result["summary"]["total_engagements"] == 50
        assert result["summary"]["total_clicks"] == 25
        assert result["summary"]["total_spend"] == 12.5
