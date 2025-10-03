"""
Standardized constants for Sato AI Platform
Ensures consistency across frontend, backend, and database
"""

from enum import Enum
from typing import List, Dict, Any


class AgentType(str, Enum):
    """Standardized agent types used across the platform"""
    
    # Master Agents
    MASTER = "master"
    SEO_CAMPAIGN_MANAGER = "seo_campaign_manager"
    
    # Google Specialists
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_DATABASE_ANALYSIS_EXPERT = "google_database_analysis_expert"
    GOOGLE_ADS_EXPERT = "google_ads_expert"
    
    # Facebook/Meta Specialists
    FACEBOOK_ADS = "facebook_ads"
    FACEBOOK_DATABASE_ANALYSIS_EXPERT = "facebook_database_analysis_expert"
    SOCIAL_MEDIA_EXPERT = "social_media_expert"
    META_ADS_EXPERT = "meta_ads_expert"
    
    # Advertising Specialists
    ADVERTISING_ANALYSIS_EXPERT = "advertising_analysis_expert"
    CAMPAIGN_ANALYSIS_EXPERT = "campaign_analysis_expert"
    PAID_MEDIA_EXPERT = "paid_media_expert"
    
    # Content & SEO Specialists
    SEO_EXPERT = "seo_expert"
    CONTENT_EXPERT = "content_expert"
    
    # Data Specialists
    DATA_ANALYSIS_AGENT = "data_analysis_agent"
    DATA_REPORTING_AGENT = "data_reporting_agent"
    DATA_INSIGHTS_AGENT = "data_insights_agent"
    DATA_VISUALIZATION_AGENT = "data_visualization_agent"
    
    # Platform-Specific Agents
    YOUTUBE_GA4_AGENT = "youtube_GA4_agent"
    LINKEDIN_GA4_AGENT = "linkedin_GA4_agent"
    TWITTER_GA4_AGENT = "twitter_GA4_agent"
    PINTEREST_GA4_AGENT = "pinterest_GA4_agent"
    TIKTOK_GA4_AGENT = "tiktok_GA4_agent"


class DataSource(str, Enum):
    """Standardized data sources used across the platform"""
    
    # Google Sources
    GA4 = "ga4"
    GOOGLE_ANALYTICS = "google_analytics"  # Alias for GA4
    GOOGLE_ADS = "google_ads"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    
    # Facebook/Meta Sources
    FACEBOOK = "facebook"
    FB = "fb"  # Alias for Facebook
    FACEBOOK_ADS = "facebook_ads"  # Alias for Facebook
    
    # Other Advertising Platforms
    BING_ADS = "bing_ads"
    LINKEDIN_ADS = "linkedin_ads"
    TWITTER_ADS = "twitter_ads"
    TIKTOK_ADS = "tiktok_ads"


class ToolName(str, Enum):
    """Standardized tool names used across the platform"""
    
    # Google Tools
    GA4_ANALYTICS_TOOL = "GA4AnalyticsTool"
    GOOGLE_ADS_ANALYTICS_TOOL = "GoogleAdsAnalyticsTool"
    
    # Facebook Tools
    FACEBOOK_ANALYTICS_TOOL = "FacebookAnalyticsTool"
    FACEBOOK_ADS_TOOL = "FacebookAdsTool"
    FACEBOOK_MARKETING_TOOL = "FacebookMarketingTool"
    
    # User Tools
    USER_PROFILE_TOOL = "UserProfileTool"
    
    # Master Agent Tools
    DELEGATE_WORK_TO_COWORKER = "DelegateWorkToCoworker"


class AgentDisplayName(str, Enum):
    """Human-readable display names for agent types"""
    
    # Master Agents
    MASTER = "Master Agent"
    SEO_CAMPAIGN_MANAGER = "SEO Campaign Manager"
    
    # Google Specialists
    GOOGLE_ANALYTICS = "Google Analytics Specialist"
    GOOGLE_DATABASE_ANALYSIS_EXPERT = "Google Database Analysis Expert"
    GOOGLE_ADS_EXPERT = "Google Ads Expert"
    
    # Facebook/Meta Specialists
    FACEBOOK_ADS = "Facebook Ads Specialist"
    FACEBOOK_DATABASE_ANALYSIS_EXPERT = "Facebook Database Analysis Expert"
    SOCIAL_MEDIA_EXPERT = "Social Media Expert"
    META_ADS_EXPERT = "Meta Ads Expert"
    
    # Advertising Specialists
    ADVERTISING_ANALYSIS_EXPERT = "Advertising Analysis Expert"
    CAMPAIGN_ANALYSIS_EXPERT = "Campaign Analysis Expert"
    PAID_MEDIA_EXPERT = "Paid Media Expert"
    
    # Content & SEO Specialists
    SEO_EXPERT = "SEO Expert"
    CONTENT_EXPERT = "Content Expert"
    
    # Data Specialists
    DATA_ANALYSIS_AGENT = "Data Analysis Agent"
    DATA_REPORTING_AGENT = "Data Reporting Agent"
    DATA_INSIGHTS_AGENT = "Data Insights Agent"
    DATA_VISUALIZATION_AGENT = "Data Visualization Agent"
    
    # Platform-Specific Agents
    YOUTUBE_GA4_AGENT = "YouTube GA4 Agent"
    LINKEDIN_GA4_AGENT = "LinkedIn GA4 Agent"
    TWITTER_GA4_AGENT = "Twitter GA4 Agent"
    PINTEREST_GA4_AGENT = "Pinterest GA4 Agent"
    TIKTOK_GA4_AGENT = "TikTok GA4 Agent"


# Tool Mapping Configuration
AGENT_TOOL_MAPPING: Dict[str, List[str]] = {
    # Master agent - gets delegation tools only
    AgentType.MASTER: [ToolName.DELEGATE_WORK_TO_COWORKER],
    
    # Google specialists - ONLY Google tools
    AgentType.GOOGLE_DATABASE_ANALYSIS_EXPERT: [ToolName.GA4_ANALYTICS_TOOL, ToolName.GOOGLE_ADS_ANALYTICS_TOOL],
    AgentType.GOOGLE_ANALYTICS: [ToolName.GA4_ANALYTICS_TOOL],
    AgentType.GOOGLE_ADS_EXPERT: [ToolName.GOOGLE_ADS_ANALYTICS_TOOL],
    
    # Facebook specialists - ONLY Facebook tools
    AgentType.FACEBOOK_DATABASE_ANALYSIS_EXPERT: [ToolName.FACEBOOK_MARKETING_TOOL, ToolName.FACEBOOK_ANALYTICS_TOOL, ToolName.FACEBOOK_ADS_TOOL],
    AgentType.FACEBOOK_ADS: [ToolName.FACEBOOK_MARKETING_TOOL, ToolName.FACEBOOK_ANALYTICS_TOOL, ToolName.FACEBOOK_ADS_TOOL],
    AgentType.SOCIAL_MEDIA_EXPERT: [ToolName.FACEBOOK_MARKETING_TOOL, ToolName.FACEBOOK_ANALYTICS_TOOL],
    AgentType.META_ADS_EXPERT: [ToolName.FACEBOOK_MARKETING_TOOL, ToolName.FACEBOOK_ADS_TOOL],
    
    # Future specialists (tools to be added)
    AgentType.ADVERTISING_ANALYSIS_EXPERT: [],
    AgentType.CAMPAIGN_ANALYSIS_EXPERT: [],
    AgentType.PAID_MEDIA_EXPERT: [],
    
    # Content & SEO specialists (tools to be added)
    AgentType.SEO_EXPERT: [],
    AgentType.CONTENT_EXPERT: [],
    
    # Data specialists (tools to be added)
    AgentType.DATA_ANALYSIS_AGENT: [],
    AgentType.DATA_REPORTING_AGENT: [],
    AgentType.DATA_INSIGHTS_AGENT: [],
    AgentType.DATA_VISUALIZATION_AGENT: [],
    
    # Platform-specific agents (tools to be added)
    AgentType.YOUTUBE_GA4_AGENT: [],
    AgentType.LINKEDIN_GA4_AGENT: [],
    AgentType.TWITTER_GA4_AGENT: [],
    AgentType.PINTEREST_GA4_AGENT: [],
    AgentType.TIKTOK_GA4_AGENT: [],
}


# Data Source Mapping for Agent Inclusion
AGENT_DATA_SOURCE_MAPPING: Dict[str, List[str]] = {
    # Master agent - can work with any data source
    AgentType.MASTER: [DataSource.GA4, DataSource.GOOGLE_ADS, DataSource.FACEBOOK, DataSource.FB],
    
    # Date specialist - works with ANY data source (needed for all timeframe requests)
    "date_timeframe_specialist": [DataSource.GA4, DataSource.GOOGLE_ADS, DataSource.FACEBOOK, DataSource.FB],
    
    # Google specialists - ONLY Google data sources
    AgentType.GOOGLE_DATABASE_ANALYSIS_EXPERT: [DataSource.GA4, DataSource.GOOGLE_ADS],
    AgentType.GOOGLE_ANALYTICS: [DataSource.GA4],
    AgentType.GOOGLE_ADS_EXPERT: [DataSource.GOOGLE_ADS],
    
    # Facebook specialists - ONLY Facebook data sources
    AgentType.FACEBOOK_DATABASE_ANALYSIS_EXPERT: [DataSource.FACEBOOK, DataSource.FB],
    AgentType.FACEBOOK_ADS: [DataSource.FACEBOOK, DataSource.FB],
    AgentType.SOCIAL_MEDIA_EXPERT: [DataSource.FACEBOOK, DataSource.FB],
    AgentType.META_ADS_EXPERT: [DataSource.FACEBOOK, DataSource.FB],
    
    # Future specialists (data sources to be defined)
    AgentType.ADVERTISING_ANALYSIS_EXPERT: [],
    AgentType.CAMPAIGN_ANALYSIS_EXPERT: [],
    AgentType.PAID_MEDIA_EXPERT: [],
    
    # Content & SEO specialists (data sources to be defined)
    AgentType.SEO_EXPERT: [],
    AgentType.CONTENT_EXPERT: [],
    
    # Data specialists (data sources to be defined)
    AgentType.DATA_ANALYSIS_AGENT: [],
    AgentType.DATA_REPORTING_AGENT: [],
    AgentType.DATA_INSIGHTS_AGENT: [],
    AgentType.DATA_VISUALIZATION_AGENT: [],
    
    # Platform-specific agents (data sources to be defined)
    AgentType.YOUTUBE_GA4_AGENT: [],
    AgentType.LINKEDIN_GA4_AGENT: [],
    AgentType.TWITTER_GA4_AGENT: [],
    AgentType.PINTEREST_GA4_AGENT: [],
    AgentType.TIKTOK_GA4_AGENT: [],
}


# Valid data sources for validation
VALID_DATA_SOURCES: List[str] = [
    DataSource.GA4,
    DataSource.GOOGLE_ANALYTICS,
    DataSource.GOOGLE_ADS,
    DataSource.FACEBOOK,
    DataSource.FB,
    DataSource.GOOGLE_SEARCH_CONSOLE,
    DataSource.BING_ADS,
    DataSource.LINKEDIN_ADS,
    DataSource.TWITTER_ADS,
    DataSource.TIKTOK_ADS,
]


# Agent type aliases for backward compatibility
AGENT_TYPE_ALIASES: Dict[str, str] = {
    # Database aliases to standard types
    "google_analytics": AgentType.GOOGLE_ANALYTICS,
    "facebook_ads": AgentType.FACEBOOK_ADS,
    "master": AgentType.MASTER,
    
    # Frontend aliases to standard types
    "facebook_database_analysis_expert": AgentType.FACEBOOK_DATABASE_ANALYSIS_EXPERT,
    "google_database_analysis_expert": AgentType.GOOGLE_DATABASE_ANALYSIS_EXPERT,
}


# Data source aliases for backward compatibility
DATA_SOURCE_ALIASES: Dict[str, str] = {
    # Frontend aliases to standard sources
    "facebook_ads": DataSource.FACEBOOK,
    "google_analytics": DataSource.GA4,
}


def get_standard_agent_type(agent_type: str) -> str:
    """Convert any agent type to the standard format"""
    return AGENT_TYPE_ALIASES.get(agent_type, agent_type)


def get_standard_data_source(data_source: str) -> str:
    """Convert any data source to the standard format"""
    return DATA_SOURCE_ALIASES.get(data_source, data_source)


def get_agent_display_name(agent_type: str) -> str:
    """Get human-readable display name for agent type"""
    standard_type = get_standard_agent_type(agent_type)
    return AgentDisplayName.get(standard_type, standard_type)


def get_tools_for_agent(agent_type: str) -> List[str]:
    """Get tools for a given agent type"""
    standard_type = get_standard_agent_type(agent_type)
    return AGENT_TOOL_MAPPING.get(standard_type, [])


def get_data_sources_for_agent(agent_type: str) -> List[str]:
    """Get data sources for a given agent type"""
    standard_type = get_standard_agent_type(agent_type)
    return AGENT_DATA_SOURCE_MAPPING.get(standard_type, [])


def should_include_agent(agent_type: str, data_sources: List[str], user_question: str = "") -> bool:
    """Determine if an agent should be included based on data sources and question"""
    standard_type = get_standard_agent_type(agent_type)
    agent_data_sources = get_data_sources_for_agent(standard_type)
    
    # Check if any of the agent's data sources match the requested data sources
    standard_data_sources = [get_standard_data_source(ds) for ds in data_sources]
    
    # Debug logging
    print(f"🔍 Agent inclusion check: {agent_type} -> {standard_type}")
    print(f"   Agent data sources: {agent_data_sources}")
    print(f"   Requested data sources: {standard_data_sources}")
    
    # Include agent if ANY of its data sources match the request
    # This allows multiple specialists to work together on multi-source requests
    result = any(ds in standard_data_sources for ds in agent_data_sources)
    print(f"   Agent included: {result} (ANY data source match)")

    
    # If data source matching worked, return the result
    if result:
        return result
    
    # If data sources were explicitly provided, trust them - don't use keyword fallback
    if standard_data_sources:
        print(f"   Explicitly provided data sources don't match - NOT including agent")
        return False
    
    # Keyword-based matching ONLY when no data sources are provided (backward compatibility)
    question_lower = user_question.lower()
    
    if standard_type in [AgentType.GOOGLE_DATABASE_ANALYSIS_EXPERT, AgentType.GOOGLE_ANALYTICS]:
        return (
            "google" in question_lower or
            "analytics" in question_lower or
            "ga4" in question_lower or
            "google ads" in question_lower or
            "google advertising" in question_lower or
            "roas" in question_lower or
            "cpc" in question_lower or
            "ctr" in question_lower
        )
    
    if standard_type in [AgentType.FACEBOOK_DATABASE_ANALYSIS_EXPERT, AgentType.FACEBOOK_ADS, AgentType.SOCIAL_MEDIA_EXPERT, AgentType.META_ADS_EXPERT]:
        return (
            "facebook" in question_lower or
            "fb" in question_lower or
            "social" in question_lower or
            "meta" in question_lower or
            "instagram" in question_lower or
            "social media" in question_lower
        )
    
    return False
