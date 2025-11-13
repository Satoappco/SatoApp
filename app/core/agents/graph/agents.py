"""Specialized agents for handling specific tasks."""

from typing import Dict, Any, List, Optional
import logging
import asyncio
from langchain_core.language_models import BaseChatModel
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from sqlmodel import select
from ..crew.crew import AnalyticsCrew
from .sql_agent import SQLBasicInfoAgent
from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType
# from app.core.base.encryption_service import BaseEncryptionService
from app.services.google_ads_service import GoogleAdsService
from ..mcp_clients.google_client import GoogleMCPClient
from ..mcp_clients.facebook_client import FacebookMCPClient

google_ads_service = GoogleAdsService()
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

        return platforms

    def _fetch_google_analytics_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID.

        Args:
            customer_id: Customer ID

        Returns:
            Dictionary with 'refresh_token', 'property_id', 'client_id', 'client_secret' or None
        """
        try:
            # encryption_service = BaseEncryptionService()

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
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked == False
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [AnalyticsCrew] No active connection or refresh token found for GA4 asset {ga_asset.id}")
                    return None

                # Decrypt the tokens
                try:
                    refresh_token = google_ads_service._decrypt_token(connection.refresh_token_enc) #encryption_service.decrypt_token(connection.refresh_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to decrypt refresh_token: {decrypt_error}")
                    # Try using the token as-is (might be plain text or need re-encryption)
                    refresh_token = connection.refresh_token_enc
                    if isinstance(refresh_token, bytes):
                        try:
                            # Try decoding bytes to string
                            refresh_token = refresh_token.decode('utf-8')
                        except Exception:
                            logger.error(f"❌ [AnalyticsCrew] Cannot decode refresh_token bytes")
                            return None

                access_token = None
                if connection.access_token_enc:
                    try:
                        access_token = google_ads_service._decrypt_token(connection.access_token_enc)
                    except Exception as decrypt_error:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to decrypt access_token: {decrypt_error}")
                        # Access token is optional, can continue without it
                        access_token = None

                # Extract property_id from digital asset meta field
                property_id = ga_asset.meta.get("property_id") if ga_asset.meta else None

                if not property_id:
                    logger.warning(f"⚠️  [AnalyticsCrew] No property_id found in GA4 asset meta for customer {customer_id}")
                    return None

                # Get OAuth client credentials from environment
                # These are the same for all Google API connections
                import os
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

                if not client_id or not client_secret:
                    logger.warning(f"⚠️  [AnalyticsCrew] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in environment")

                logger.info(f"✅ [AnalyticsCrew] Found GA4 credentials for customer {customer_id}, property: {property_id}")

                return {
                    "refresh_token": refresh_token,
                    "property_id": property_id,
                    "access_token": access_token,
                    "client_id": client_id,
                    "client_secret": client_secret
                }

        except Exception as e:
            logger.warning(f"⚠️  [AnalyticsCrew] Failed to fetch GA token for customer {customer_id}: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

    def _fetch_google_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Ads credentials.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'refresh_token', 'customer_id', 'client_id', 'client_secret' or None
        """
        try:
            with get_session() as session:
                # Get Google Ads digital asset for this customer
                gads_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not gads_asset:
                    logger.warning(f"⚠️  [AnalyticsCrew] No Google Ads digital asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == gads_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked == False
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [AnalyticsCrew] No active connection for Google Ads asset")
                    return None

                # Decrypt the tokens
                try:
                    refresh_token = google_ads_service._decrypt_token(connection.refresh_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to decrypt refresh_token: {decrypt_error}")
                    return None

                # Extract customer_id from digital asset meta field
                gads_customer_id = gads_asset.meta.get("customer_id") if gads_asset.meta else None

                if not gads_customer_id:
                    logger.warning(f"⚠️  [AnalyticsCrew] No customer_id in Google Ads asset meta")
                    return None

                # Get OAuth client credentials from environment
                import os
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")

                if not client_id or not client_secret or not developer_token:
                    logger.warning(f"⚠️  [AnalyticsCrew] Missing Google Ads environment credentials")

                logger.info(f"✅ [AnalyticsCrew] Found Google Ads credentials, customer: {gads_customer_id}")

                return {
                    "refresh_token": refresh_token,
                    "customer_id": gads_customer_id,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "developer_token": developer_token
                }

        except Exception as e:
            logger.warning(f"⚠️  [AnalyticsCrew] Failed to fetch Google Ads token: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

    def _fetch_meta_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Facebook/Meta Ads access token.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'access_token', 'ad_account_id' or None
        """
        try:
            with get_session() as session:
                # Get Facebook Ads digital asset for this customer
                fb_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.FACEBOOK_ADS,
                        Connection.campaigner_id == campaigner_id,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not fb_asset:
                    logger.warning(f"⚠️  [AnalyticsCrew] No Facebook Ads digital asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == fb_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked == False
                    )
                ).first()

                if not connection or not connection.access_token_enc:
                    logger.warning(f"⚠️  [AnalyticsCrew] No active connection for Facebook Ads asset")
                    return None

                # Decrypt the access token
                try:
                    access_token = google_ads_service._decrypt_token(connection.access_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to decrypt access_token: {decrypt_error}")
                    return None

                # Extract ad_account_id from digital asset meta field
                ad_account_id = fb_asset.meta.get("ad_account_id") if fb_asset.meta else None

                if not ad_account_id:
                    logger.warning(f"⚠️  [AnalyticsCrew] No ad_account_id in Facebook Ads asset meta")
                    return None

                logger.info(f"✅ [AnalyticsCrew] Found Facebook Ads credentials, account: {ad_account_id}")

                return {
                    "access_token": access_token,
                    "ad_account_id": ad_account_id
                }

        except Exception as e:
            logger.warning(f"⚠️  [AnalyticsCrew] Failed to fetch Facebook Ads token: {e}")
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
        campaigner_id = task.get("campaigner_id")

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
                google_analytics_credentials = self._fetch_google_analytics_token(customer_id, campaigner_id)
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
            "campaigner_id": campaigner_id,  # Pass through campaigner_id
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


class SingleAnalyticsAgent:
    """Single analytics agent with direct access to all MCP tools.

    This agent can query Google Analytics, Google Ads, and Facebook Ads
    directly through MCP tools without delegating to specialist agents.
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.trace = None  # Will be set by AgentExecutorNode
        self.google_client: Optional[GoogleMCPClient] = None
        self.facebook_client: Optional[FacebookMCPClient] = None

    def set_trace(self, trace):
        """Set the LangFuse trace for this agent."""
        self.trace = trace

    def _fetch_customer_platforms(self, customer_id: int) -> List[str]:
        """Fetch customer's enabled platforms from digital_assets table."""
        platforms = []
        try:
            with get_session() as session:
                digital_assets = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.is_active == True
                    )
                ).all()

                platform_set = set()
                for asset in digital_assets:
                    asset_type_str = asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type)
                    provider = asset.provider.lower() if asset.provider else ""

                    if asset_type_str in ["GA4", "GOOGLE_ADS", "GOOGLE_ADS_CAPS"]:
                        platform_set.add("google")
                    elif asset_type_str in ["FACEBOOK_ADS", "FACEBOOK_ADS_CAPS"] or "facebook" in provider or "meta" in provider:
                        platform_set.add("facebook")

                platforms = list(platform_set)
                logger.info(f"📊 [SingleAnalyticsAgent] Customer {customer_id} platforms: {platforms}")

        except Exception as e:
            logger.warning(f"⚠️  [SingleAnalyticsAgent] Failed to fetch platforms for customer {customer_id}: {e}")
            platforms = ["google"]

        return platforms

    def _fetch_google_analytics_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID."""
        try:
            with get_session() as session:
                ga_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.GA4,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not ga_asset:
                    logger.warning(f"⚠️  [SingleAnalyticsAgent] No GA4 asset found for customer {customer_id}")
                    return None

                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == ga_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked == False
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [SingleAnalyticsAgent] No active connection for GA4 asset")
                    return None

                try:
                    refresh_token = google_ads_service._decrypt_token(connection.refresh_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [SingleAnalyticsAgent] Failed to decrypt refresh_token: {decrypt_error}")
                    return None

                property_id = ga_asset.meta.get("property_id") if ga_asset.meta else None
                if not property_id:
                    logger.warning(f"⚠️  [SingleAnalyticsAgent] No property_id in GA4 asset meta")
                    return None

                import os
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

                if not client_id or not client_secret:
                    logger.warning(f"⚠️  [SingleAnalyticsAgent] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")

                logger.info(f"✅ [SingleAnalyticsAgent] Found GA4 credentials, property: {property_id}")

                return {
                    "refresh_token": refresh_token,
                    "property_id": property_id,
                    "client_id": client_id,
                    "client_secret": client_secret
                }

        except Exception as e:
            logger.warning(f"⚠️  [SingleAnalyticsAgent] Failed to fetch GA token: {e}")

        return None

    async def _initialize_mcp_clients(self, task_details: Dict[str, Any]):
        """Initialize and connect MCP clients for enabled platforms.

        Args:
            task_details: Task details containing platforms and credentials
        """
        platforms = task_details.get("platforms", [])

        # Initialize Google MCP client if Google platform is enabled
        if "google" in platforms:
            ga_credentials = task_details.get("google_analytics_credentials")
            gads_credentials = task_details.get("google_ads_credentials")

            if ga_credentials or gads_credentials:
                try:
                    # Extract tokens from credentials
                    google_analytics_token = ga_credentials.get("refresh_token") if ga_credentials else None
                    google_ads_token = gads_credentials.get("refresh_token") if gads_credentials else None

                    self.google_client = GoogleMCPClient(
                        google_ads_token=google_ads_token,
                        google_analytics_token=google_analytics_token
                    )

                    # Connect to MCP server
                    await self.google_client.connect()
                    logger.info("✅ [SingleAnalyticsAgent] Connected to Google MCP client")

                except Exception as e:
                    logger.error(f"❌ [SingleAnalyticsAgent] Failed to initialize Google MCP: {e}")
                    self.google_client = None

        # Initialize Facebook MCP client if Facebook platform is enabled
        if "facebook" in platforms:
            fb_credentials = task_details.get("meta_ads_credentials")

            if fb_credentials:
                try:
                    access_token = fb_credentials.get("access_token")

                    self.facebook_client = FacebookMCPClient(access_token=access_token)

                    # Connect to MCP server
                    await self.facebook_client.connect()
                    logger.info("✅ [SingleAnalyticsAgent] Connected to Facebook MCP client")

                except Exception as e:
                    logger.error(f"❌ [SingleAnalyticsAgent] Failed to initialize Facebook MCP: {e}")
                    self.facebook_client = None

    async def _disconnect_mcp_clients(self):
        """Disconnect all MCP clients."""
        if self.google_client:
            try:
                await self.google_client.disconnect()
                logger.info("✅ [SingleAnalyticsAgent] Disconnected Google MCP client")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Error disconnecting Google MCP: {e}")

        if self.facebook_client:
            try:
                await self.facebook_client.disconnect()
                logger.info("✅ [SingleAnalyticsAgent] Disconnected Facebook MCP client")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Error disconnecting Facebook MCP: {e}")

    def _get_all_tools(self) -> List:
        """Get all available MCP tools from connected clients."""
        tools = []

        if self.google_client:
            try:
                google_tools = self.google_client.get_tools()
                tools.extend(google_tools)
                logger.info(f"✅ [SingleAnalyticsAgent] Loaded {len(google_tools)} Google tools")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Failed to get Google tools: {e}")

        if self.facebook_client:
            try:
                facebook_tools = self.facebook_client.get_tools()
                tools.extend(facebook_tools)
                logger.info(f"✅ [SingleAnalyticsAgent] Loaded {len(facebook_tools)} Facebook tools")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Failed to get Facebook tools: {e}")

        return tools

    async def _execute_async(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Async execution method with MCP client management.

        Args:
            task: Dictionary containing the analytics request

        Returns:
            Dictionary containing the analytics results
        """
        query = task.get("query", "")
        customer_id = task.get("customer_id")
        campaigner_id = task.get("campaigner_id")
        context = task.get("context", {})
        language = context.get("language", "english")

        # Auto-fetch customer platforms and credentials
        platforms = []
        google_analytics_credentials = None
        google_ads_credentials = None
        meta_ads_credentials = None

        if customer_id:
            logger.info(f"🔍 [SingleAnalyticsAgent] Auto-fetching data for customer {customer_id}")
            platforms = self._fetch_customer_platforms(customer_id)
            logger.info(f"✅ [SingleAnalyticsAgent] Fetched platforms: {platforms}")

            if "google" in platforms:
                google_analytics_credentials = self._fetch_google_analytics_token(customer_id, campaigner_id)
                if google_analytics_credentials:
                    logger.info(f"✅ [SingleAnalyticsAgent] Fetched Google Analytics credentials")

                google_ads_credentials = self._fetch_google_ads_token(customer_id, campaigner_id)
                if google_ads_credentials:
                    logger.info(f"✅ [SingleAnalyticsAgent] Fetched Google Ads credentials")

            if "facebook" in platforms:
                meta_ads_credentials = self._fetch_meta_ads_token(customer_id, campaigner_id)
                if meta_ads_credentials:
                    logger.info(f"✅ [SingleAnalyticsAgent] Fetched Facebook Ads credentials")
        else:
            logger.warning("⚠️  [SingleAnalyticsAgent] No customer_id provided")
            platforms = task.get("platforms", ["google"])

        # Build task details
        task_details = {
            "query": query,
            "context": context,
            "campaigner_id": campaigner_id,
            "customer_id": customer_id,
            "platforms": platforms,
            "metrics": task.get("metrics", ["impressions", "clicks", "conversions", "spend"]),
            "date_range": task.get("date_range", {"start": "last_30_days", "end": "today"}),
            "google_analytics_credentials": google_analytics_credentials,
            "google_ads_credentials": google_ads_credentials,
            "meta_ads_credentials": meta_ads_credentials,
        }

        # Initialize and connect MCP clients
        await self._initialize_mcp_clients(task_details)

        try:
            # Get all available tools
            tools = self._get_all_tools()

            if not tools:
                return {
                    "status": "error",
                    "message": "No MCP tools available for enabled platforms",
                    "agent": "single_analytics_agent",
                    "task_received": task
                }

            logger.info(f"🚀 [SingleAnalyticsAgent] Executing with {len(tools)} tools from platforms: {platforms}")

            # Build context for the agent
            context_str = self._build_context_string(task_details)

            # Create prompt template with context
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert marketing analytics agent with direct access to multiple advertising platforms.

{context_str}

Your tasks:
1. Analyze the user's question to understand what data they need
2. Use the appropriate MCP tools to fetch data from the relevant platforms
3. Always include the correct property/account IDs in your tool calls
4. Analyze the data and identify trends, patterns, and insights
5. Provide a comprehensive answer with actionable recommendations
6. Format your response in {language} language

Important: Use the tools available to you to fetch real data before providing insights."""),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])

            # Create agent with tools
            agent = create_tool_calling_agent(self.llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=10,
                handle_parsing_errors=True
            )

            # Execute agent
            result = await agent_executor.ainvoke({"input": query})

            return {
                "status": "completed",
                "result": result.get("output"),
                "agent": "single_analytics_agent",
                "platforms": platforms,
                "task_details": task_details
            }

        except Exception as e:
            logger.error(f"❌ [SingleAnalyticsAgent] Execution failed: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")

            return {
                "status": "error",
                "message": f"Single analytics agent execution failed: {str(e)}",
                "agent": "single_analytics_agent",
                "task_received": task
            }

        finally:
            # Always disconnect MCP clients
            await self._disconnect_mcp_clients()

    def _build_context_string(self, task_details: Dict[str, Any]) -> str:
        """Build context string with credentials and account IDs."""
        context = task_details.get("context", {})
        platforms = task_details.get("platforms", [])

        context_parts = []

        # Add platform-specific credentials
        if "google" in platforms:
            ga_credentials = task_details.get("google_analytics_credentials", {})
            property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

            gads_credentials = task_details.get("google_ads_credentials", {})
            customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")

            if property_id != "NOT_PROVIDED":
                context_parts.append(f"Google Analytics Property ID: {property_id}")
            if customer_id != "NOT_PROVIDED":
                context_parts.append(f"Google Ads Customer ID: {customer_id}")

        if "facebook" in platforms:
            fb_credentials = task_details.get("meta_ads_credentials", {})
            ad_account_id = fb_credentials.get("ad_account_id", "NOT_PROVIDED")
            if ad_account_id != "NOT_PROVIDED":
                context_parts.append(f"Facebook Ads Account ID: {ad_account_id}")

        # Add user context
        if context:
            agency = context.get("agency", {})
            campaigner = context.get("campaigner", {})

            if agency:
                context_parts.append(f"Agency: {agency.get('name')}")
            if campaigner:
                context_parts.append(f"Campaigner: {campaigner.get('full_name')}")

        return "\n".join(context_parts)

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an analytics task using direct MCP tool access.

        Args:
            task: Dictionary containing the analytics request

        Returns:
            Dictionary containing the analytics results
        """
        # Run async execution in event loop
        return asyncio.run(self._execute_async(task))


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
