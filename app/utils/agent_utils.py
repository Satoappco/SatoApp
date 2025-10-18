"""
Agent utilities for tool management and agent operations
Follows single responsibility principle and DRY principles
"""

from typing import List, Dict, Any, Optional
import logging
from app.core.constants import get_tools_for_agent

logger = logging.getLogger(__name__)


def get_tools_for_agent(agent_type: str, campaigner_connections: List[Dict], campaigner_id: int = None, agency_id: int = None, customer_id: int = None) -> List:
    """
    AUTO-DISCOVERY: Dynamically assign tools based on agent type naming conventions
    
    Args:
        agent_type: Type of agent (e.g., 'seo_campaign_manager', 'google_analytics')
        campaigner_connections: List of campaigner's data source connections
        campaigner_id: Campaigner ID for tool initialization
        agency_id: Agency ID (optional)
        customer_id: Customer ID for tool initialization
        
    Returns:
        List of initialized tool instances
    """
    tools = []
    
    # Use the provided customer_id directly - NO FALLBACK MAPPING!
    # If customer_id is not provided, tools will fail with clear error messages
    
    # Get tools using standardized constants
    from app.core.constants import get_tools_for_agent as get_standard_tools
    tool_names = get_standard_tools(agent_type)
    
    for tool_name in tool_names:
        try:
            tool_instance = _create_tool_instance(tool_name, campaigner_id, customer_id)
            if tool_instance:
                tools.append(tool_instance)
                logger.info(f"✅ Added {tool_name} for {agent_type} (customer_id={customer_id})")
                
        except ImportError as e:
            logger.warning(f"⚠️ Could not import {tool_name}: {e}")
        except Exception as e:
            logger.error(f"❌ Error creating {tool_name}: {e}")
    
    logger.info(f"🔧 Agent '{agent_type}' assigned {len(tools)} tools: {[tool.__class__.__name__ for tool in tools]}")
    return tools


def _create_tool_instance(tool_name: str, campaigner_id: int, customer_id: int):
    """
    Create a tool instance based on tool name
    
    Args:
        tool_name: Name of the tool to create
        campaigner_id: User ID for tool initialization
        customer_id: Subclient ID for tool initialization
        
    Returns:
        Initialized tool instance or None if creation fails
    """
    tool_creators = {
        "GA4AnalyticsTool": _create_ga4_tool,
        "GoogleAdsAnalyticsTool": _create_google_ads_tool,
        "FacebookAnalyticsTool": _create_facebook_analytics_tool,
        "FacebookAdsTool": _create_facebook_ads_tool,
        "DateConversionTool": _create_date_conversion_tool,
    }
    
    creator = tool_creators.get(tool_name)
    if creator:
        return creator(campaigner_id, customer_id)
    else:
        logger.warning(f"⚠️ Unknown tool: {tool_name}")
        return None


def _create_ga4_tool(campaigner_id: int, customer_id: int):
    """Create GA4AnalyticsTool instance"""
    from app.tools.ga4_analytics_tool import GA4AnalyticsTool
    return GA4AnalyticsTool(campaigner_id=campaigner_id, customer_id=customer_id)


def _create_google_ads_tool(campaigner_id: int, customer_id: int):
    """Create GoogleAdsAnalyticsTool instance"""
    from app.tools.google_ads_tool import GoogleAdsAnalyticsTool
    return GoogleAdsAnalyticsTool(campaigner_id=campaigner_id, customer_id=customer_id)


def _create_facebook_analytics_tool(campaigner_id: int, customer_id: int):
    """Create FacebookAnalyticsTool instance"""
    from app.tools.facebook_analytics_tool import FacebookAnalyticsTool
    return FacebookAnalyticsTool(campaigner_id=campaigner_id, customer_id=customer_id)


def _create_facebook_ads_tool(campaigner_id: int, customer_id: int):
    """Create FacebookAdsTool instance"""
    from app.tools.facebook_ads_tool import FacebookAdsTool
    return FacebookAdsTool(campaigner_id=campaigner_id, customer_id=customer_id)


def _create_date_conversion_tool(campaigner_id: int, customer_id: int):
    """Create DateConversionTool instance"""
    from app.tools.date_conversion_tool import DateConversionTool
    return DateConversionTool()
