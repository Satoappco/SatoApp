"""Main CrewAI crew orchestration."""

from crewai import Crew, Process
from crewai_tools import MCPServerAdapter

from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from crewai.llm import LLM
import os
import logging

from .agents import AnalyticsAgents
from .tasks import AnalyticsTasks
from .mcp_registry import MCPSelector, MCPServer
from .session_recorder import SessionRecorder, CrewCallbacks
from ..mcp_clients.facebook_client import FacebookMCPClient
from ..mcp_clients.google_client import GoogleMCPClient
from app.config.langfuse_config import LangfuseConfig
import uuid

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
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )

        # self.llm = LLM(
        #     model="gemini/gemini-2.5-flash",
        #     api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        #     temperature=0.1
        # )

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

    def _initialize_mcp_clients(
        self,
        platforms: List[str],
        google_analytics_credentials: Optional[Dict[str, str]] = None,
        google_ads_credentials: Optional[Dict[str, str]] = None,
        meta_ads_credentials: Optional[Dict[str, str]] = None,
        custom_mcp_selection: Optional[Dict[str, MCPServer]] = None
    ):
        """Initialize MCP clients for required platforms.

        Args:
            platforms: List of platforms to initialize
            google_analytics_credentials: Dict with 'refresh_token' and 'property_id' for GA MCP
            google_ads_credentials: Dict with Google Ads credentials
            meta_ads_credentials: Dict with Meta/Facebook Ads credentials
            custom_mcp_selection: Custom selection of which MCP servers to use per service
                Example: {"google_analytics": MCPServer.GOOGLE_ANALYTICS_SURENDRANB}
        """
        # Use the MCP registry and selector system
        self.mcp_param_list = MCPSelector.build_all_server_params(
            platforms=platforms,
            google_analytics_credentials=google_analytics_credentials,
            google_ads_credentials=google_ads_credentials,
            meta_ads_credentials=meta_ads_credentials,
            custom_selection=custom_mcp_selection,
        )

        if not self.mcp_param_list:
            logger.warning("⚠️  No MCP servers configured")

        # Legacy MCP clients (kept for backwards compatibility if needed)
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

        # Get the parent trace from task_details if provided
        parent_trace = task_details.get("trace")

        # Get Langfuse client
        langfuse = LangfuseConfig.get_client()

        # Use the parent trace if provided, otherwise create a new trace
        if parent_trace:
            logger.info("✅ [AnalyticsCrew] Using parent trace from session")
            # Create a span within the parent trace
            trace_context_manager = parent_trace.span(
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
        elif langfuse:
            logger.warning("⚠️  [AnalyticsCrew] No parent trace provided, creating standalone trace")
            # Fallback: create standalone trace (shouldn't happen with new implementation)
            trace_context_manager = langfuse.start_as_current_span(
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
            trace_context_manager = DummyContext()

        try:
            with trace_context_manager as span:
                result = self._execute_internal(task_details)

                # Update span with output
                if span and hasattr(span, 'update'):
                    span.update(
                        output={"success": result.get("success"), "platforms": result.get("platforms")},
                        metadata={"session_id": result.get("session_id")}
                    )

                return result
        except Exception as e:
            logger.error(f"❌ Analytics crew execution error: {e}")

            # Update span with error
            if hasattr(trace_context_manager, '__enter__'):
                try:
                    span = trace_context_manager.__enter__()
                    if span and hasattr(span, 'update'):
                        span.update(
                            output={"error": str(e)},
                            level="ERROR",
                            status_message=str(e)
                        )
                except Exception:
                    pass

            raise

    def _execute_internal(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Internal execution logic with tracing context."""

        platforms = task_details.get("platforms", [])
        google_analytics_credentials = task_details.get("google_analytics_credentials")
        google_ads_credentials = task_details.get("google_ads_credentials")
        meta_ads_credentials = task_details.get("meta_ads_credentials")

        # Extract campaigner_id (for backwards compatibility, but credentials are now passed in)
        self.campaigner_id = task_details.get("campaigner_id")
        customer_id = task_details.get("customer_id")

        # Initialize session recorder
        session_id = str(uuid.uuid4())
        recorder = SessionRecorder(session_id=session_id, customer_id=customer_id)
        recorder.set_metadata("query", task_details.get("query"))
        recorder.set_metadata("platforms", platforms)
        recorder.set_metadata("campaigner_id", self.campaigner_id)
        logger.info(f"🎬 [AnalyticsCrew] Session recording started: {session_id}")

        # Log credential info
        cred_count = 0
        if google_analytics_credentials:
            logger.info(f"🔑 [AnalyticsCrew] Received Google Analytics credentials")
            logger.debug(f"   Property ID: {google_analytics_credentials.get('property_id')}")
            cred_count += 1
        if google_ads_credentials:
            logger.info(f"🔑 [AnalyticsCrew] Received Google Ads credentials")
            cred_count += 1
        if meta_ads_credentials:
            logger.info(f"🔑 [AnalyticsCrew] Received Meta Ads credentials")
            cred_count += 1

        if cred_count == 0:
            logger.warning(f"⚠️  [AnalyticsCrew] No credentials provided")

        # Initialize MCP clients with customer credentials
        # The instrumentation will automatically trace this
        self._initialize_mcp_clients(
            platforms,
            google_analytics_credentials,
            google_ads_credentials,
            meta_ads_credentials
        )

        # Check if MCP servers are configured
        use_mcp_adapter = bool(self.mcp_param_list)

        if use_mcp_adapter:
            logger.info(f"🔧 Initializing {len(self.mcp_param_list)} MCP server(s)")

            # Use CrewAI's official multi-server approach: pass list of server params
            # MCPServerAdapter accepts either a single dict or a list of dicts
            context_manager = MCPServerAdapter(self.mcp_param_list)
        else:
            # Fallback: Use custom MCP clients or no tools
            logger.warning("⚠️  No MCP servers configured, using custom MCP clients")
            from contextlib import nullcontext
            context_manager = nullcontext(enter_result=[])

        with context_manager as aggregated_tools:
            # Log loaded tools
            if aggregated_tools:
                logger.info(f"✅ Total tools loaded: {len(aggregated_tools)}")
                logger.debug(f"🔧 Available tools: {[tool.name for tool in aggregated_tools]}")
            else:
                logger.warning("⚠️  No tools available")

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
                # Use aggregated_tools if available, otherwise use custom Google tools
                tools = aggregated_tools if use_mcp_adapter else self._get_google_tools()
                google_agent = self.agents_factory.create_google_specialist(
                    tools=tools
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

            # Create callbacks for session recording
            callbacks = CrewCallbacks(recorder)

            # Record task starts
            for i, task in enumerate(tasks):
                agent = task.agent if hasattr(task, 'agent') else master_agent
                callbacks.start_task(task, agent, i)

            # Create and run crew with callbacks
            logger.debug(f"Starting a crew with agents: {agents}, tasks: {tasks}, master_agent: {master_agent}")
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=master_agent,
                verbose=True,
                # Note: CrewAI callbacks - task_callback called after each task completes
                task_callback=callbacks.task_callback,
                # step_callback=callbacks.step_callback,  # Uncomment if needed (can be verbose)
            )

            # Get Langfuse client for tracing
            langfuse = LangfuseConfig.get_client()

            # Use start_as_current_span as per Langfuse docs for CrewAI
            # This enables automatic instrumentation to capture all crew operations
            if langfuse:
                span_context = langfuse.start_as_current_span(
                    name="crew_kickoff",
                    input={
                        "num_agents": len(agents),
                        "num_tasks": len(tasks),
                        "platforms": platforms,
                        "session_id": session_id
                    }
                )
            else:
                span_context = DummyContext()

            try:
                logger.info(f"🚀 Starting crew execution with {len(agents)} agents and {len(tasks)} tasks")

                # Execute crew within Langfuse span - instrumentation captures everything
                with span_context:
                    result = crew.kickoff()

                logger.info("✅ Crew execution completed successfully")

                # Save session recording
                session_file = recorder.save_to_file()
                session_summary = recorder.get_summary()

                logger.info(f"📊 [AnalyticsCrew] Session summary: {session_summary['total_tasks']} tasks, "
                           f"{session_summary['total_steps']} steps, {session_summary['duration_seconds']:.2f}s")

                # Flush Langfuse to ensure traces are sent
                if langfuse:
                    try:
                        langfuse.flush()
                    except Exception:
                        pass

                return {
                    "success": True,
                    "result": result,
                    "platforms": platforms,
                    "task_details": task_details,
                    "session_id": session_id,
                    "session_summary": session_summary,
                    "session_file": session_file
                }

            except Exception as e:
                logger.error(f"❌ Crew execution failed: {e}")
                recorder.record_error(str(e), {"platforms": platforms})
                recorder.save_to_file()

                return {
                    "success": False,
                    "error": str(e),
                    "platforms": platforms,
                    "task_details": task_details,
                    "session_id": session_id
                }

            finally:
                # Cleanup MCP clients
                if self.facebook_client:
                    self.facebook_client.close()
                if self.google_client:
                    self.google_client.close()
