"""Main CrewAI crew orchestration."""

from crewai import Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters # Needed for Stdio example

from typing import Dict, Any, List, Optional
# from langchain_openai import ChatOpenAI
from crewai.llm import LLM
import os
import logging

from .agents import AnalyticsAgents
from .tasks import AnalyticsTasks
from ..mcp_clients.facebook_client import FacebookMCPClient
from ..mcp_clients.google_client import GoogleMCPClient
from app.config.langfuse_config import LangfuseConfig
from app.core.observability import trace_context, get_current_trace

logger = logging.getLogger(__name__)


class DummyContext:
    """Dummy context manager for when tracing is disabled."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class AnalyticsCrew:
    """Analytics crew for processing marketing data requests."""

    def __init__(self):
        # Initialize LLM
        # self.llm = ChatOpenAI(
        #     model="gpt-4o",
        #     temperature=0.3,
        #     api_key=os.getenv("OPENAI_API_KEY")
        # )

        self.llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )

        # Initialize agent factory
        self.agents_factory = AnalyticsAgents(self.llm)

        # Initialize tasks factory
        self.tasks_factory = AnalyticsTasks()

        # Initialize MCP clients
        self.facebook_client: Optional[FacebookMCPClient] = None
        self.google_client: Optional[GoogleMCPClient] = None

        # Store user tokens for MCP tools
        self.campaigner_id: Optional[int] = None
        self.user_tokens: Dict[str, str] = {}
        self.mcp_param_list = []

    def _fetch_user_tokens(self, campaigner_id: int):
        """Fetch OAuth tokens for the user from database."""
        from app.config.database import get_session
        from app.models.connections import FacebookConnection, GoogleAdsConnection, GoogleAnalyticsConnection
        from sqlmodel import select

        try:
            with get_session() as session:
                # Fetch Facebook token
                fb_conn = session.exec(
                    select(FacebookConnection)
                    .where(FacebookConnection.campaigner_id == campaigner_id)
                    .where(FacebookConnection.is_active == True)
                ).first()
                if fb_conn:
                    self.user_tokens["facebook"] = fb_conn.access_token

                # Fetch Google Ads token
                google_ads_conn = session.exec(
                    select(GoogleAdsConnection)
                    .where(GoogleAdsConnection.campaigner_id == campaigner_id)
                    .where(GoogleAdsConnection.is_active == True)
                ).first()
                if google_ads_conn:
                    self.user_tokens["google_ads"] = google_ads_conn.access_token

                # Fetch Google Analytics token
                ga_conn = session.exec(
                    select(GoogleAnalyticsConnection)
                    .where(GoogleAnalyticsConnection.campaigner_id == campaigner_id)
                    .where(GoogleAnalyticsConnection.is_active == True)
                ).first()
                if ga_conn:
                    self.user_tokens["google_analytics"] = ga_conn.access_token

        except Exception as e:
            print(f"⚠️  Failed to fetch user tokens: {e}")

    def _initialize_mcp_clients(self, platforms: List[str]):
        """Initialize MCP clients for required platforms."""
        self.mcp_param_list.append(    
            StdioServerParameters(
                command="pipx",
                args=[
                    "run",
                    "analytics-mcp"
                ],
                env={
                    "UV_PYTHON": "3.12", 
                    **os.environ,
#         "GOOGLE_APPLICATION_CREDENTIALS": "PATH_TO_CREDENTIALS_JSON",
#         "GOOGLE_PROJECT_ID": "YOUR_PROJECT_ID"
                },
            )
        )
        
        # if "facebook" in platforms or "both" in platforms:
        #     if not self.facebook_client:
        #         # Pass Facebook token if available
        #         facebook_token = self.user_tokens.get("facebook")
        #         self.facebook_client = FacebookMCPClient(access_token=facebook_token)

        # if "google" in platforms or "both" in platforms:
        #     if not self.google_client:
        #         # Pass Google tokens if available
        #         google_ads_token = self.user_tokens.get("google_ads")
        #         google_analytics_token = self.user_tokens.get("google_analytics")
        #         self.google_client = GoogleMCPClient(
        #             google_ads_token=google_ads_token,
        #             google_analytics_token=google_analytics_token
        #         )

    # TODO: use?
    async def refresh_user_data_connections(self, campaigner_id: int, data_sources: List[str]):
        # REFRESH GA4 TOKENS BEFORE GETTING CONNECTIONS
        from app.services.google_analytics_service import GoogleAnalyticsService
        from app.api.v1.routes.webhooks import refresh_user_ga4_tokens, refresh_user_facebook_tokens
        ga_service = GoogleAnalyticsService()
        user_connections = []
        if "ga4" in data_sources:
            try:
                # STEP 1: Automatically refresh expired tokens before using them
                # logger.info(f"🔄 Checking and refreshing GA4 tokens for user {campaigner_id}...")
                await refresh_user_ga4_tokens(ga_service, campaigner_id)
                
                # STEP 2: Get user connections (should work now with fresh tokens)
                if hasattr(ga_service, 'get_user_connections'):
                    user_connections = await ga_service.get_user_connections(campaigner_id)
                    # logger.info(f"✅ Found {len(user_connections)} GA4 connections for user")
                else:
                    pass
                    # logger.info("get_user_connections method not implemented yet - continuing without user connections")
            except Exception as e:
                pass
                # logger.warning(f"Could not get user connections: {e}")
        
        # Also refresh Google Ads tokens if Google Ads is in data sources
        if "google_ads" in data_sources:
            try:
                from app.services.google_ads_service import GoogleAdsService
                google_ads_service = GoogleAdsService()
                # logger.info(f"🔄 Checking Google Ads connections for user {campaigner_id}...")
                # Google Ads tokens are refreshed automatically when needed
                # logger.info(f"✅ Google Ads service ready for user {campaigner_id}")
            except Exception as e:
                pass
                # logger.warning(f"Could not initialize Google Ads service: {e}")
        
        # Also refresh Facebook tokens if Facebook is in data sources
        if "facebook" in data_sources:
            try:
                from app.services.facebook_service import FacebookService
                facebook_service = FacebookService()
                # logger.info(f"🔄 Checking and refreshing Facebook tokens for user {campaigner_id}...")
                await refresh_user_facebook_tokens(facebook_service, campaigner_id)
                # logger.info(f"✅ Facebook service ready for user {campaigner_id}")
            except Exception as e:
                pass
                # logger.warning(f"Could not initialize Facebook service: {e}")
        

    def _get_facebook_tools(self) -> List:
        """Get Facebook MCP tools."""
        if not self.facebook_client:
            return []
        return self.facebook_client.get_tools()

    def _get_google_tools(self) -> List:
        """Get Google Analytics MCP tools."""
        if not self.google_client:
            return []
        return self.google_client.get_tools()

    def execute(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the analytics crew with the given task details."""
        logger.debug(f"🧑‍💼 [AnalyticsCrew] Received task: {task_details}...")
        # Get Langfuse client
        langfuse = LangfuseConfig.get_client()
        parent_trace = get_current_trace()

        # Create trace for crew execution if Langfuse is enabled
        if langfuse and parent_trace:
            trace = parent_trace.span(
                name="analytics_crew_execution",
                input={
                    "query": task_details.get("query"),
                    "platforms": task_details.get("platforms"),
                    "campaigner_id": task_details.get("campaigner_id"),
                },
                metadata={
                    "crew_type": "analytics",
                    "language": task_details.get("context", {}).get("language"),
                }
            )
        else:
            trace = None

        try:
            with trace_context(trace) if trace else DummyContext():
                return self._execute_internal(task_details)
        except Exception as e:
            if trace:
                trace.end(level="ERROR", status_message=str(e))
            raise
        finally:
            if trace:
                trace.end()

    def _execute_internal(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Internal execution logic with tracing context."""

        platforms = task_details.get("platforms", [])

        # Extract campaigner_id and fetch user tokens
        self.campaigner_id = task_details.get("campaigner_id")
        if self.campaigner_id:
            current_trace = get_current_trace()
            if current_trace:
                token_span = current_trace.span(name="fetch_user_tokens")

            self._fetch_user_tokens(self.campaigner_id)

            if current_trace:
                token_span.end()

        # Initialize MCP clients
        current_trace = get_current_trace()
        if current_trace:
            init_span = current_trace.span(name="initialize_mcp_clients", metadata={"platforms": platforms})

        self._initialize_mcp_clients(platforms)

        if current_trace:
            init_span.end()

        with MCPServerAdapter(self.mcp_param_list) as aggregated_tools:
            logger.debug(f"🔧 Aggregated MCP tools: {[tool.name for tool in aggregated_tools]}")
            # Create agents
            master_agent = self.agents_factory.create_master_agent()

            agents = []
            tasks = []
            specialist_tasks = []

            # Create Facebook specialist if needed
            # if "facebook" in platforms or "both" in platforms:
            #     facebook_tools = self._get_facebook_tools()
            #     facebook_agent = self.agents_factory.create_facebook_specialist(
            #         tools=facebook_tools
            #     )
            #     facebook_task = self.tasks_factory.create_facebook_analysis_task(
            #         agent=facebook_agent,
            #         task_details=task_details
            #     )
            #     agents.append(facebook_agent)
            #     tasks.append(facebook_task)
            #     specialist_tasks.append(facebook_task)

            # Create Google specialist if needed
            if "google" in platforms or "both" in platforms:
                google_tools = self._get_google_tools()
                google_agent = self.agents_factory.create_google_specialist(
                    tools=aggregated_tools #google_tools
                )
                google_task = self.tasks_factory.create_google_analysis_task(
                    agent=google_agent,
                    task_details=task_details
                )
                agents.append(google_agent)
                tasks.append(google_task)
                specialist_tasks.append(google_task)

            # Create synthesis task for master agent
            synthesis_task = self.tasks_factory.create_synthesis_task(
                agent=master_agent,
                task_details=task_details,
                context=specialist_tasks  # Master agent gets specialist outputs
            )
            tasks.append(synthesis_task)

            # Create and run crew
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=master_agent,
                verbose=True
            )

            # Track crew kickoff
            current_trace = get_current_trace()
            if current_trace:
                kickoff_span = current_trace.span(
                    name="crew_kickoff",
                    metadata={
                        "num_agents": len(agents),
                        "num_tasks": len(tasks),
                        "platforms": platforms
                    }
                )

            try:
                logger.info(f"🚀 Starting crew execution with {len(agents)} agents and {len(tasks)} tasks")
                result = crew.kickoff()
                logger.info("✅ Crew execution completed successfully")

                if current_trace:
                    kickoff_span.end(output={"success": True, "result_length": len(str(result))})

                return {
                    "success": True,
                    "result": result,
                    "platforms": platforms,
                    "task_details": task_details
                }

            except Exception as e:
                logger.error(f"❌ Crew execution failed: {e}")
                if current_trace:
                    kickoff_span.end(level="ERROR", status_message=str(e))

                return {
                    "success": False,
                    "error": str(e),
                    "platforms": platforms,
                    "task_details": task_details
                }

            finally:
                # Cleanup MCP clients
                if self.facebook_client:
                    self.facebook_client.close()
                if self.google_client:
                    self.google_client.close()
