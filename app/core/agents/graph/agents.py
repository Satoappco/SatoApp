"""Specialized agents for handling specific tasks."""

from typing import Dict, Any, List, Optional
import logging
import asyncio
from langchain_core.language_models import BaseChatModel
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient as MCPClient
from ..crew.crew import AnalyticsCrew
from .sql_agent import SQLBasicInfoAgent
from .single_analytics_agent import SingleAnalyticsAgent
from ..customer_credentials import CustomerCredentialManager
from ..mcp_clients.mcp_registry import MCPSelector
from app.services.chat_trace_service import ChatTraceService

import time

logger = logging.getLogger(__name__)

class AnalyticsCrewPlaceholder:
    """Wrapper for the Analytics Crew.

    This crew gathers information from all campaigns across multiple platforms
    (Facebook Ads, Google Marketing, etc.) and generate insights.
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.analytics_crew = AnalyticsCrew()
        self.credential_manager = CustomerCredentialManager()

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an analytics task using the AnalyticsCrew.

        Args:
            task: Dictionary containing the analytics request with keys:
                - query: The analytics question/request
                - context: Additional context (optional)
                - customer_id: Customer ID (required for fetching platforms and tokens)
                - campaigner_id: Campaigner ID (optional)
                - platforms: List of platforms to analyze (optional, will be auto-fetched)
                - metrics: List of metrics to analyze (optional)
                - date_range: Dict with 'start' and 'end' dates (optional)

        Returns:
            Dictionary containing the analytics results
        """
        # Extract task details
        query = task.get("query", "")
        customer_id = task.get("customer_id")
        campaigner_id = task.get("campaigner_id")

        if customer_id:
            logger.info(f"🔍 [AnalyticsCrew] Auto-fetching data for customer {customer_id}")
            # Fetch customer's platforms and credentials from digital_assets table
            credentials = self.credential_manager.fetch_all_credentials(customer_id, campaigner_id)
            platforms = credentials.get("platforms", [])
            logger.info(f"✅ [AnalyticsCrew] Fetched platforms: {platforms}")
        else:
            logger.warning("⚠️  [AnalyticsCrew] No customer_id provided, using NO platforms")
            platforms = task.get("platforms", [])

        # Build task details for AnalyticsCrew
        task_details = {
            "query": query,
            "context": task.get("context"),  # Pass through the context (agency, campaigner, language)
            "campaigner_id": campaigner_id,  # Pass through campaigner_id
            "customer_id": customer_id,  # Pass customer_id
            "thread_id" : task.get("thread_id"),
            "platforms": platforms,  # Use auto-fetched platforms
            "metrics": task.get("metrics", ["impressions", "clicks", "conversions", "spend"]),
            # "date_range": task.get("date_range", {"start": "last_30_days", "end": "today"}),
            "specific_campaigns": task.get("specific_campaigns", None),
            # Pass credentials for MCP configuration
            "google_analytics_credentials": credentials["google_analytics"],
            "google_ads_credentials": credentials["google_ads"],
            "meta_ads_credentials": credentials["meta_ads"],
        }

        logger.info(f"🚀 [AnalyticsCrew] Executing with platforms: {platforms}")

        # Execute the analytics crew with trace context
        crew_result = self.analytics_crew.execute(task_details)

        # Format the response
        if crew_result.get("success"):
            return {
                "status": "completed",
                "result": crew_result.get("result"),
                "agent": "analytics_crew",
                "platforms": crew_result.get("platforms"),
                "task_details": task_details
            }
        else:
            return {
                "status": "error",
                "message": f"Analytics crew execution failed: {crew_result.get('error')}",
                "agent": "analytics_crew",
                "task_received": task
            }


class CampaignPlanningCrewPlaceholder:
    """Placeholder for the Campaign Planning Crew.

    This crew will plan new campaigns, create digital assets,
    and distribute them to advertising platforms.
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a campaign planning task.

        Args:
            task: Dictionary containing the campaign planning request

        Returns:
            Dictionary containing the campaign plan
        """
        # TODO: Implement CrewAI crew for campaign planning
        # This crew should:
        # 1. Plan new marketing campaigns based on goals
        # 2. Create digital assets (copy, images, etc.)
        # 3. Format and send campaigns to advertising platforms

        return {
            "status": "placeholder",
            "message": "Campaign planning crew not yet implemented",
            "agent": "campaign_planning_crew",
            "task_received": task
        }


def get_agent(agent_name: str, llm: BaseChatModel):
    """Get an agent instance by name.

    Args:
        agent_name: Name of the agent to retrieve
        llm: Language model instance

    Returns:
        Agent instance

    Raises:
        ValueError: If agent_name is not recognized
    """
    from app.config.settings import get_settings
    settings = get_settings()

    agents = {
        "basic_info_agent": SQLBasicInfoAgent,  # Using SQL-based agent
        # "basic_info_agent_legacy": BasicInfoAgent,  # Legacy version kept for reference
        "analytics_crew": AnalyticsCrewPlaceholder,
        "single_analytics_agent": SingleAnalyticsAgent,
        "campaign_planning_crew": CampaignPlanningCrewPlaceholder
    }

    # Handle analytics agent routing based on configuration
    if agent_name == "analytics_crew":
        analytics_type = settings.analytics_agent_type
        logger.info(f"🔧 [get_agent] Using analytics agent type: {analytics_type}")

        if analytics_type == "single":
            agent_name = "single_analytics_agent"
        elif analytics_type == "crew":
            agent_name = "analytics_crew"
        else:
            logger.warning(f"⚠️  [get_agent] Unknown analytics_agent_type: {analytics_type}, defaulting to crew")
            agent_name = "analytics_crew"

    if agent_name not in agents:
        raise ValueError(f"Unknown agent: {agent_name}")

    return agents[agent_name](llm)
