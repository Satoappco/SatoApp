"""Specialized agents for handling specific tasks."""

from typing import Dict, Any, List, Optional
import logging
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from sqlmodel import select
from ..crew.crew import AnalyticsCrew
from .sql_agent import SQLBasicInfoAgent
from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.core.base.encryption_service import BaseEncryptionService

logger = logging.getLogger(__name__)

class AnalyticsCrewPlaceholder:
    """Wrapper for the Analytics Crew.

    This crew gathers information from all campaigns across multiple platforms
    (Facebook Ads, Google Marketing, etc.) and generate insights.
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.analytics_crew = AnalyticsCrew()
        self.trace = None  # Will be set by AgentExecutorNode

    def set_trace(self, trace):
        """Set the LangFuse trace for this agent."""
        self.trace = trace

    def _fetch_customer_platforms(self, customer_id: int) -> List[str]:
        """Fetch customer's enabled platforms from digital_assets table.

        Args:
            customer_id: Customer ID

        Returns:
            List of platform names (e.g., ["google", "facebook"])
        """
        platforms = []
        try:
            with get_session() as session:
                # Get digital assets for this customer
                digital_assets = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.is_active == True
                    )
                ).all()

                # Extract unique platforms from asset_type and provider
                platform_set = set()
                for asset in digital_assets:
                    # Check asset type to determine platform
                    asset_type_str = asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type)
                    provider = asset.provider.lower() if asset.provider else ""

                    # Map asset types to platforms
                    if asset_type_str in ["GA4", "GOOGLE_ADS", "GOOGLE_ADS_CAPS"]:
                        platform_set.add("google")
                    elif asset_type_str in ["FACEBOOK_ADS", "FACEBOOK_ADS_CAPS"] or "facebook" in provider or "meta" in provider:
                        platform_set.add("facebook")

                platforms = list(platform_set)
                logger.info(f"📊 [AnalyticsCrew] Customer {customer_id} platforms: {platforms}")

        except Exception as e:
            logger.warning(f"⚠️  [AnalyticsCrew] Failed to fetch platforms for customer {customer_id}: {e}")
            # Fallback to default platforms
            platforms = ["google"]

        return platforms if platforms else ["google"]

    def _fetch_google_analytics_token(self, customer_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID.

        Args:
            customer_id: Customer ID

        Returns:
            Dictionary with 'refresh_token' and 'property_id' or None
        """
        try:
            encryption_service = BaseEncryptionService()

            with get_session() as session:
                # First, get Google Analytics digital asset for this customer
                ga_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.GA4,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not ga_asset:
                    logger.warning(f"⚠️  [AnalyticsCrew] No GA4 digital asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == ga_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.revoked == False
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [AnalyticsCrew] No active connection or refresh token found for GA4 asset {ga_asset.id}")
                    return None

                # Decrypt the tokens
                refresh_token = encryption_service.decrypt_token(connection.refresh_token_enc)
                access_token = None
                if connection.access_token_enc:
                    access_token = encryption_service.decrypt_token(connection.access_token_enc)

                # Extract property_id from digital asset meta field
                property_id = ga_asset.meta.get("property_id") if ga_asset.meta else None

                if not property_id:
                    logger.warning(f"⚠️  [AnalyticsCrew] No property_id found in GA4 asset meta for customer {customer_id}")
                    return None

                logger.info(f"✅ [AnalyticsCrew] Found GA4 credentials for customer {customer_id}, property: {property_id}")

                return {
                    "refresh_token": refresh_token,
                    "property_id": property_id,
                    "access_token": access_token
                }

        except Exception as e:
            logger.warning(f"⚠️  [AnalyticsCrew] Failed to fetch GA token for customer {customer_id}: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

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

        # IMPORTANT: Auto-fetch customer platforms and tokens from database
        # This is hardcoded logic that LLM cannot control
        platforms = []
        google_analytics_credentials = None

        if customer_id:
            logger.info(f"🔍 [AnalyticsCrew] Auto-fetching data for customer {customer_id}")

            # Fetch customer's platforms from digital_assets table
            platforms = self._fetch_customer_platforms(customer_id)
            logger.info(f"✅ [AnalyticsCrew] Fetched platforms: {platforms}")

            # Fetch Google Analytics credentials if Google platform is enabled
            if "google" in platforms:
                google_analytics_credentials = self._fetch_google_analytics_token(customer_id)
                if google_analytics_credentials:
                    logger.info(f"✅ [AnalyticsCrew] Fetched Google Analytics credentials")
                    logger.debug(f"   Property ID: {google_analytics_credentials.get('property_id')}")
                else:
                    logger.warning(f"⚠️  [AnalyticsCrew] No Google Analytics credentials found for customer {customer_id}")
        else:
            logger.warning("⚠️  [AnalyticsCrew] No customer_id provided, using fallback platforms")
            platforms = task.get("platforms", ["google"])

        # Build task details for AnalyticsCrew
        task_details = {
            "query": query,
            "context": task.get("context"),  # Pass through the context (agency, campaigner, language)
            "campaigner_id": task.get("campaigner_id"),  # Pass through campaigner_id
            "customer_id": customer_id,  # Pass customer_id
            "platforms": platforms,  # Use auto-fetched platforms
            "metrics": task.get("metrics", ["impressions", "clicks", "conversions", "spend"]),
            "date_range": task.get("date_range", {"start": "last_30_days", "end": "today"}),
            "specific_campaigns": task.get("specific_campaigns", None),
            # Pass credentials for MCP configuration
            "google_analytics_credentials": google_analytics_credentials,
            # Pass the LangFuse trace
            "trace": self.trace
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
    agents = {
        "basic_info_agent": SQLBasicInfoAgent,  # Using SQL-based agent
        # "basic_info_agent_legacy": BasicInfoAgent,  # Legacy version kept for reference
        "analytics_crew": AnalyticsCrewPlaceholder,
        "campaign_planning_crew": CampaignPlanningCrewPlaceholder
    }

    if agent_name not in agents:
        raise ValueError(f"Unknown agent: {agent_name}")

    return agents[agent_name](llm)
