"""
Google Analytics 4 tools for CrewAI agents
Provides GA4 data fetching capabilities using stored user credentials
"""

import json
import asyncio
from typing import Dict, Any, List, Optional, Type
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from app.services.google_analytics_service import GoogleAnalyticsService
from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from sqlmodel import select, and_


class GA4AnalyticsInput(BaseModel):
    """Input schema for GA4AnalyticsTool."""
    property_id: Optional[str] = Field(None, description="GA4 property ID (optional - will auto-detect if not provided)")
    metrics: Optional[List[str]] = Field(None, description="List of metrics to fetch")
    dimensions: Optional[List[str]] = Field(None, description="List of dimensions to fetch")
    start_date: str = Field("7daysAgo", description="Start date in YYYY-MM-DD format or relative")
    end_date: str = Field("today", description="End date in YYYY-MM-DD format or relative")
    limit: int = Field(1000, description="Maximum number of rows to return")
    analysis_type: Optional[str] = Field("basic", description="Type of analysis (optional)")


class GA4AnalyticsTool(BaseTool):
    """Tool for fetching Google Analytics 4 data using stored user credentials"""
    
    name: str = "GA4 Analytics Data Fetcher"
    description: str = """
    Fetch Google Analytics 4 data using stored user credentials.
    
    This tool can:
    - Fetch basic metrics (sessions, users, pageviews, bounce rate)
    - Get traffic sources and channels
    - Analyze user demographics and behavior
    - Track conversions and revenue
    - Generate custom reports with dimensions and metrics
    
    Use this tool when you need to analyze website performance, traffic patterns,
    user behavior, or marketing campaign effectiveness.
    """
    args_schema: Type[BaseModel] = GA4AnalyticsInput
    
    # Allow extra fields for Pydantic model
    class Config:
        extra = "allow"
    
    def __init__(self, user_id: int = None, customer_id: int = None):
        super().__init__()
        self.ga_service = GoogleAnalyticsService()
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'user_id', user_id)
        object.__setattr__(self, 'customer_id', customer_id)
    
    @property
    def ga_service(self):
        """Lazy initialization of GA service"""
        if not hasattr(self, '_ga_service'):
            self._ga_service = GoogleAnalyticsService()
        return self._ga_service
    
    @ga_service.setter
    def ga_service(self, value):
        self._ga_service = value
    
    def _run(
        self, 
        property_id: str = None,
        metrics: List[str] = None,
        dimensions: List[str] = None,
        start_date: str = "7daysAgo",
        end_date: str = "today",
        limit: int = 1000,
        analysis_type: str = "basic"
    ) -> Dict[str, Any]:
        """
        Fetch GA4 data using user's stored refresh token
        
        Args:
            property_id: GA4 property ID (e.g., "123456789") - if not provided, uses first available
            metrics: List of metrics to fetch (default: basic metrics)
            dimensions: List of dimensions to fetch (default: date)
            start_date: Start date in YYYY-MM-DD format or relative (e.g., "7daysAgo")
            end_date: End date in YYYY-MM-DD format or relative (e.g., "today")
            limit: Maximum number of rows to return
            analysis_type: Type of analysis (basic, traffic_sources, demographics, conversions)
        """
        
        try:
            # Use stored user_id and customer_id from initialization
            if not self.user_id or not self.customer_id:
                return {
                    'error': 'No user/customer context available for GA4 data fetching',
                    'suggestion': 'Tool needs to be initialized with user_id and customer_id'
                }
            
            # Get customer's GA4 connections (customer owns the connections)
            # Use asyncio.run() but handle the event loop properly
            import asyncio
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.ga_service.get_user_ga_connections(self.customer_id))
                    user_connections = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                user_connections = asyncio.run(self.ga_service.get_user_ga_connections(self.customer_id))
            
            if not user_connections:
                return {
                    'error': f'No GA4 connections found for customer {self.customer_id}',
                    'suggestion': 'Customer needs to connect their Google Analytics account first'
                }
            
            # Use provided property_id or first available connection
            if property_id and property_id not in ["YOUR_GA4_PROPERTY_ID", "YOUR_PROPERTY_ID", "PROPERTY_ID"]:
                # Find connection for specific property (only if it's a real property ID)
                connection_id = self._get_user_ga_connection(self.customer_id, property_id)
                if not connection_id:
                    return {
                        'error': f'No GA4 connection found for property {property_id}',
                        'suggestion': 'Check if the property ID is correct and connected'
                    }
            else:
                # Use first available connection (auto-detect)
                connection = user_connections[0]
                connection_id = connection["connection_id"]
                property_id = connection["property_id"]
            
            # Set default metrics and dimensions based on analysis type
            if not metrics:
                metrics = self._get_default_metrics(analysis_type)
            if not dimensions:
                dimensions = self._get_default_dimensions(analysis_type)
            
            # Fetch data using the service
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.ga_service.fetch_ga4_data(
                        connection_id=connection_id,
                        property_id=property_id,
                        metrics=metrics,
                        dimensions=dimensions,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit
                    ))
                    result = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                result = asyncio.run(self.ga_service.fetch_ga4_data(
                    connection_id=connection_id,
                    property_id=property_id,
                    metrics=metrics,
                    dimensions=dimensions,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                ))
            
            # Add analysis insights
            result['analysis_type'] = analysis_type
            result['insights'] = self._generate_insights(result, analysis_type)
            
            return result
            
        except Exception as e:
            return {
                'error': f'GA4 API error: {str(e)}',
                'suggestion': 'Check if the GA4 connection is valid and has proper permissions'
            }
    
    def _get_user_ga_connection(self, user_id: int, property_id: str) -> Optional[int]:
        """Get user's GA4 connection ID for the specified property"""
        
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == user_id,
                    DigitalAsset.asset_type == AssetType.ANALYTICS,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.external_id == property_id,
                    Connection.revoked == False
                )
            )
            
            result = session.exec(statement).first()
            return result[0].id if result else None
    
    def _get_default_metrics(self, analysis_type: str) -> List[str]:
        """Get default metrics based on analysis type"""
        
        metric_sets = {
            'basic': ['sessions', 'newUsers', 'screenPageViews', 'bounceRate', 'averageSessionDuration'],
            'traffic_sources': ['sessions', 'newUsers', 'bounceRate'],
            'demographics': ['sessions', 'newUsers', 'screenPageViews', 'bounceRate'],
            'conversions': ['sessions', 'conversions', 'totalRevenue', 'purchaseRevenue'],
            'content': ['screenPageViews', 'sessions', 'bounceRate'],
            'ecommerce': ['purchaseRevenue', 'totalRevenue', 'transactions', 'conversions']
        }
        
        return metric_sets.get(analysis_type, metric_sets['basic'])
    
    def _get_default_dimensions(self, analysis_type: str) -> List[str]:
        """Get default dimensions based on analysis type"""
        
        dimension_sets = {
            'basic': ['date'],
            'traffic_sources': ['date', 'channelGroup', 'source', 'medium'],
            'demographics': ['date', 'country', 'city', 'deviceCategory'],
            'conversions': ['date', 'eventName'],
            'content': ['date', 'pagePath', 'pageTitle'],
            'ecommerce': ['date', 'transactionId']
        }
        
        return dimension_sets.get(analysis_type, dimension_sets['basic'])
    
    def _generate_insights(self, data: Dict[str, Any], analysis_type: str) -> List[str]:
        """Generate insights based on the fetched data"""
        
        insights = []
        
        if not data.get('rows'):
            return ['No data available for the specified date range']
        
        # Basic insights
        total_sessions = self._get_metric_total(data, 'sessions')
        total_users = self._get_metric_total(data, 'users')
        bounce_rate = self._get_metric_average(data, 'bounceRate')
        
        if total_sessions:
            insights.append(f"Total sessions: {total_sessions:,}")
        if total_users:
            insights.append(f"Total users: {total_users:,}")
        if bounce_rate:
            insights.append(f"Average bounce rate: {bounce_rate:.1f}%")
        
        # Analysis-specific insights
        if analysis_type == 'traffic_sources':
            insights.extend(self._analyze_traffic_sources(data))
        elif analysis_type == 'demographics':
            insights.extend(self._analyze_demographics(data))
        elif analysis_type == 'conversions':
            insights.extend(self._analyze_conversions(data))
        elif analysis_type == 'content':
            insights.extend(self._analyze_content(data))
        
        return insights
    
    def _get_metric_total(self, data: Dict[str, Any], metric_name: str) -> Optional[float]:
        """Get total value for a specific metric"""
        
        try:
            metric_index = data['metric_headers'].index(metric_name)
            total = 0
            for row in data['rows']:
                value = float(row['metric_values'][metric_index])
                total += value
            return total
        except (ValueError, IndexError, TypeError):
            return None
    
    def _get_metric_average(self, data: Dict[str, Any], metric_name: str) -> Optional[float]:
        """Get average value for a specific metric"""
        
        try:
            metric_index = data['metric_headers'].index(metric_name)
            total = 0
            count = 0
            for row in data['rows']:
                value = float(row['metric_values'][metric_index])
                total += value
                count += 1
            return (total / count) * 100 if count > 0 else None  # Convert to percentage for bounce rate
        except (ValueError, IndexError, TypeError):
            return None
    
    def _analyze_traffic_sources(self, data: Dict[str, Any]) -> List[str]:
        """Analyze traffic sources data"""
        
        insights = []
        
        try:
            channel_index = data['dimension_headers'].index('channelGroup')
            sessions_index = data['metric_headers'].index('sessions')
            
            # Group by channel
            channel_data = {}
            for row in data['rows']:
                channel = row['dimension_values'][channel_index]
                sessions = float(row['metric_values'][sessions_index])
                channel_data[channel] = channel_data.get(channel, 0) + sessions
            
            # Find top channels
            if channel_data:
                sorted_channels = sorted(channel_data.items(), key=lambda x: x[1], reverse=True)
                top_channel = sorted_channels[0]
                insights.append(f"Top traffic source: {top_channel[0]} ({top_channel[1]:,.0f} sessions)")
                
                if len(sorted_channels) > 1:
                    second_channel = sorted_channels[1]
                    insights.append(f"Second highest: {second_channel[0]} ({second_channel[1]:,.0f} sessions)")
        
        except (ValueError, IndexError, TypeError):
            pass
        
        return insights
    
    def _analyze_demographics(self, data: Dict[str, Any]) -> List[str]:
        """Analyze demographics data"""
        
        insights = []
        
        try:
            country_index = data['dimension_headers'].index('country')
            sessions_index = data['metric_headers'].index('sessions')
            
            # Group by country
            country_data = {}
            for row in data['rows']:
                country = row['dimension_values'][country_index]
                sessions = float(row['metric_values'][sessions_index])
                country_data[country] = country_data.get(country, 0) + sessions
            
            # Find top countries
            if country_data:
                sorted_countries = sorted(country_data.items(), key=lambda x: x[1], reverse=True)
                top_country = sorted_countries[0]
                insights.append(f"Top country: {top_country[0]} ({top_country[1]:,.0f} sessions)")
        
        except (ValueError, IndexError, TypeError):
            pass
        
        return insights
    
    def _analyze_conversions(self, data: Dict[str, Any]) -> List[str]:
        """Analyze conversions data"""
        
        insights = []
        
        try:
            conversions_index = data['metric_headers'].index('conversions')
            revenue_index = data['metric_headers'].index('totalRevenue')
            
            total_conversions = self._get_metric_total(data, 'conversions')
            total_revenue = self._get_metric_total(data, 'totalRevenue')
            
            if total_conversions:
                insights.append(f"Total conversions: {total_conversions:,.0f}")
            if total_revenue:
                insights.append(f"Total revenue: ${total_revenue:,.2f}")
                if total_conversions and total_conversions > 0:
                    avg_revenue = total_revenue / total_conversions
                    insights.append(f"Average revenue per conversion: ${avg_revenue:.2f}")
        
        except (ValueError, IndexError, TypeError):
            pass
        
        return insights
    
    def _analyze_content(self, data: Dict[str, Any]) -> List[str]:
        """Analyze content performance data"""
        
        insights = []
        
        try:
            page_index = data['dimension_headers'].index('pagePath')
            pageviews_index = data['metric_headers'].index('pageviews')
            
            # Group by page
            page_data = {}
            for row in data['rows']:
                page = row['dimension_values'][page_index]
                pageviews = float(row['metric_values'][pageviews_index])
                page_data[page] = page_data.get(page, 0) + pageviews
            
            # Find top pages
            if page_data:
                sorted_pages = sorted(page_data.items(), key=lambda x: x[1], reverse=True)
                top_page = sorted_pages[0]
                insights.append(f"Top page: {top_page[0]} ({top_page[1]:,.0f} pageviews)")
        
        except (ValueError, IndexError, TypeError):
            pass
        
        return insights


class GA4ReportGenerator(BaseTool):
    """Tool for generating comprehensive GA4 reports"""
    
    name: str = "GA4 Report Generator"
    description: str = """
    Generate comprehensive Google Analytics 4 reports with multiple data points.
    
    This tool can create:
    - Executive summary reports
    - Marketing performance reports
    - User behavior analysis reports
    - Conversion funnel reports
    - Custom business reports
    
    Use this tool when you need detailed, multi-dimensional analysis of website performance.
    """
    
    def __init__(self):
        super().__init__()
        self.ga_tool = GA4AnalyticsTool()
    
    def _run(
        self,
        user_id: int,
        property_id: str,
        report_type: str = "executive_summary",
        start_date: str = "30daysAgo",
        end_date: str = "today"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive GA4 report
        
        Args:
            user_id: ID of the user requesting the report
            property_id: GA4 property ID
            report_type: Type of report to generate
            start_date: Start date for the report
            end_date: End date for the report
        """
        
        try:
            report_data = {
                'report_type': report_type,
                'date_range': f"{start_date} to {end_date}",
                'property_id': property_id,
                'sections': {}
            }
            
            if report_type == "executive_summary":
                report_data['sections'] = self._generate_executive_summary(
                    user_id, property_id, start_date, end_date
                )
            elif report_type == "marketing_performance":
                report_data['sections'] = self._generate_marketing_performance(
                    user_id, property_id, start_date, end_date
                )
            elif report_type == "user_behavior":
                report_data['sections'] = self._generate_user_behavior(
                    user_id, property_id, start_date, end_date
                )
            elif report_type == "conversion_funnel":
                report_data['sections'] = self._generate_conversion_funnel(
                    user_id, property_id, start_date, end_date
                )
            else:
                report_data['sections'] = self._generate_custom_report(
                    user_id, property_id, start_date, end_date
                )
            
            return report_data
            
        except Exception as e:
            return {
                'error': f'Report generation error: {str(e)}',
                'suggestion': 'Check if the GA4 connection is valid and has proper permissions'
            }
    
    def _generate_executive_summary(
        self, user_id: int, property_id: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate executive summary report"""
        
        # Basic metrics
        basic_data = self.ga_tool._run(
            user_id, property_id, 
            metrics=['sessions', 'users', 'pageviews', 'bounceRate', 'sessionDuration'],
            dimensions=['date'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='basic'
        )
        
        # Traffic sources
        traffic_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['sessions', 'users'],
            dimensions=['channelGroup'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='traffic_sources'
        )
        
        return {
            'overview': basic_data,
            'traffic_sources': traffic_data,
            'summary': {
                'total_sessions': self.ga_tool._get_metric_total(basic_data, 'sessions'),
                'total_users': self.ga_tool._get_metric_total(basic_data, 'users'),
                'avg_bounce_rate': self.ga_tool._get_metric_average(basic_data, 'bounceRate'),
                'insights': basic_data.get('insights', [])
            }
        }
    
    def _generate_marketing_performance(
        self, user_id: int, property_id: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate marketing performance report"""
        
        # Traffic sources analysis
        traffic_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['sessions', 'users', 'bounceRate'],
            dimensions=['channelGroup', 'source', 'medium'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='traffic_sources'
        )
        
        # Campaign performance
        campaign_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['sessions', 'users', 'conversions'],
            dimensions=['campaign', 'source', 'medium'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='traffic_sources'
        )
        
        return {
            'traffic_sources': traffic_data,
            'campaigns': campaign_data,
            'summary': {
                'top_channel': self._get_top_channel(traffic_data),
                'top_source': self._get_top_source(traffic_data),
                'insights': traffic_data.get('insights', [])
            }
        }
    
    def _generate_user_behavior(
        self, user_id: int, property_id: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate user behavior report"""
        
        # Demographics
        demo_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['sessions', 'users'],
            dimensions=['country', 'city', 'deviceCategory'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='demographics'
        )
        
        # Content performance
        content_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['pageviews', 'sessions', 'bounceRate'],
            dimensions=['pagePath', 'pageTitle'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='content'
        )
        
        return {
            'demographics': demo_data,
            'content': content_data,
            'summary': {
                'top_country': self._get_top_country(demo_data),
                'top_device': self._get_top_device(demo_data),
                'top_page': self._get_top_page(content_data),
                'insights': demo_data.get('insights', []) + content_data.get('insights', [])
            }
        }
    
    def _generate_conversion_funnel(
        self, user_id: int, property_id: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate conversion funnel report"""
        
        # Conversion data
        conversion_data = self.ga_tool._run(
            user_id, property_id,
            metrics=['sessions', 'conversions', 'totalRevenue', 'purchaseRevenue'],
            dimensions=['date'],
            start_date=start_date,
            end_date=end_date,
            analysis_type='conversions'
        )
        
        return {
            'conversions': conversion_data,
            'summary': {
                'conversion_rate': self._calculate_conversion_rate(conversion_data),
                'total_revenue': self.ga_tool._get_metric_total(conversion_data, 'totalRevenue'),
                'insights': conversion_data.get('insights', [])
            }
        }
    
    def _generate_custom_report(
        self, user_id: int, property_id: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate custom report with all available data"""
        
        # Get all available data types
        basic_data = self.ga_tool._run(user_id, property_id, start_date=start_date, end_date=end_date, analysis_type='basic')
        traffic_data = self.ga_tool._run(user_id, property_id, start_date=start_date, end_date=end_date, analysis_type='traffic_sources')
        demo_data = self.ga_tool._run(user_id, property_id, start_date=start_date, end_date=end_date, analysis_type='demographics')
        
        return {
            'basic_metrics': basic_data,
            'traffic_sources': traffic_data,
            'demographics': demo_data,
            'summary': {
                'comprehensive_analysis': True,
                'insights': basic_data.get('insights', []) + traffic_data.get('insights', []) + demo_data.get('insights', [])
            }
        }
    
    def _get_top_channel(self, data: Dict[str, Any]) -> Optional[str]:
        """Get top traffic channel"""
        try:
            channel_index = data['dimension_headers'].index('channelGroup')
            sessions_index = data['metric_headers'].index('sessions')
            
            max_sessions = 0
            top_channel = None
            
            for row in data['rows']:
                sessions = float(row['metric_values'][sessions_index])
                if sessions > max_sessions:
                    max_sessions = sessions
                    top_channel = row['dimension_values'][channel_index]
            
            return top_channel
        except (ValueError, IndexError, TypeError):
            return None
    
    def _get_top_source(self, data: Dict[str, Any]) -> Optional[str]:
        """Get top traffic source"""
        try:
            source_index = data['dimension_headers'].index('source')
            sessions_index = data['metric_headers'].index('sessions')
            
            max_sessions = 0
            top_source = None
            
            for row in data['rows']:
                sessions = float(row['metric_values'][sessions_index])
                if sessions > max_sessions:
                    max_sessions = sessions
                    top_source = row['dimension_values'][source_index]
            
            return top_source
        except (ValueError, IndexError, TypeError):
            return None
    
    def _get_top_country(self, data: Dict[str, Any]) -> Optional[str]:
        """Get top country"""
        try:
            country_index = data['dimension_headers'].index('country')
            sessions_index = data['metric_headers'].index('sessions')
            
            max_sessions = 0
            top_country = None
            
            for row in data['rows']:
                sessions = float(row['metric_values'][sessions_index])
                if sessions > max_sessions:
                    max_sessions = sessions
                    top_country = row['dimension_values'][country_index]
            
            return top_country
        except (ValueError, IndexError, TypeError):
            return None
    
    def _get_top_device(self, data: Dict[str, Any]) -> Optional[str]:
        """Get top device category"""
        try:
            device_index = data['dimension_headers'].index('deviceCategory')
            sessions_index = data['metric_headers'].index('sessions')
            
            max_sessions = 0
            top_device = None
            
            for row in data['rows']:
                sessions = float(row['metric_values'][sessions_index])
                if sessions > max_sessions:
                    max_sessions = sessions
                    top_device = row['dimension_values'][device_index]
            
            return top_device
        except (ValueError, IndexError, TypeError):
            return None
    
    def _get_top_page(self, data: Dict[str, Any]) -> Optional[str]:
        """Get top page"""
        try:
            page_index = data['dimension_headers'].index('pagePath')
            pageviews_index = data['metric_headers'].index('pageviews')
            
            max_pageviews = 0
            top_page = None
            
            for row in data['rows']:
                pageviews = float(row['metric_values'][pageviews_index])
                if pageviews > max_pageviews:
                    max_pageviews = pageviews
                    top_page = row['dimension_values'][page_index]
            
            return top_page
        except (ValueError, IndexError, TypeError):
            return None
    
    def _calculate_conversion_rate(self, data: Dict[str, Any]) -> Optional[float]:
        """Calculate conversion rate"""
        try:
            total_sessions = self.ga_tool._get_metric_total(data, 'sessions')
            total_conversions = self.ga_tool._get_metric_total(data, 'conversions')
            
            if total_sessions and total_sessions > 0:
                return (total_conversions / total_sessions) * 100
            return None
        except (TypeError, ZeroDivisionError):
            return None

