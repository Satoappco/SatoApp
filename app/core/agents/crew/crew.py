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
from app.services.chat_trace_service import CrewCallbacks
from ..mcp_clients.mcp_registry import MCPSelector, MCPServer
from langchain_mcp_adapters.client import MultiServerMCPClient as MCPClient
from ..mcp_clients.facebook_client import FacebookMCPClient
from ..mcp_clients.google_client import GoogleMCPClient
from app.utils.llm_retry import LLMResponseError, validate_llm_response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uuid

logger = logging.getLogger(__name__)


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

        # Convert StdioServerParameters to MultiServerMCPClient format
        # servers = {}
        # for idx, params in enumerate(self.mcp_param_list):
        #     # Use service name as key (extract from working directory or use index)
        #     server_name = f"server_{idx}"
        #     if params.cwd:
        #         # Extract service name from working directory path
        #         # e.g., /path/to/mcps/google_ads_mcp -> google_ads
        #         from pathlib import Path
        #         cwd_path = Path(params.cwd)
        #         server_name = cwd_path.name.replace("-", "_")

        #     servers[server_name] = {
        #         "command": params.command,
        #         "args": params.args,
        #         "env": params.env or {},
        #         "transport": "stdio"  # All MCP servers use stdio transport
        #     }

        # # Create MultiServerMCPClient (initializes on creation, no connect() needed)
        # if servers:
        #     try:
        #         self.mcp_client = MCPClient(servers)
        #         logger.info(f"✅ [AnalyticsCrew] Initialized {len(servers)} MCP servers: {list(servers.keys())}")

        #         # Store MCP details for later logging (will be logged with tools)
        #         self._mcp_servers_info = {
        #             "servers": servers,
        #             "platforms": platforms
        #         }

        #     except Exception as e:
        #         logger.error(f"❌ [AnalyticsCrew] Failed to initialize MCP client: {e}")
        #         import traceback
        #         logger.error(f"   Traceback: {traceback.format_exc()}")
        #         self.mcp_client = None
        # else:
        #     logger.warning("⚠️  [AnalyticsCrew] No MCP servers configured")


    # # TODO: use?
    # async def refresh_user_data_connections(self, campaigner_id: int, data_sources: List[str]):
    #     # REFRESH GA4 TOKENS BEFORE GETTING CONNECTIONS
    #     from app.services.google_analytics_service import GoogleAnalyticsService
    #     from app.api.v1.routes.webhooks import refresh_user_ga4_tokens, refresh_user_facebook_tokens
    #     ga_service = GoogleAnalyticsService()
    #     user_connections = []
    #     if "ga4" in data_sources:
    #         try:
    #             # STEP 1: Automatically refresh expired tokens before using them
    #             # logger.info(f"🔄 Checking and refreshing GA4 tokens for user {campaigner_id}...")
    #             await refresh_user_ga4_tokens(ga_service, campaigner_id)
                
    #             # STEP 2: Get user connections (should work now with fresh tokens)
    #             if hasattr(ga_service, 'get_user_connections'):
    #                 user_connections = await ga_service.get_user_connections(campaigner_id)
    #                 # logger.info(f"✅ Found {len(user_connections)} GA4 connections for user")
    #             else:
    #                 pass
    #                 # logger.info("get_user_connections method not implemented yet - continuing without user connections")
    #         except Exception as e:
    #             pass
    #             # logger.warning(f"Could not get user connections: {e}")
        
    #     # Also refresh Google Ads tokens if Google Ads is in data sources
    #     if "google_ads" in data_sources:
    #         try:
    #             from app.services.google_ads_service import GoogleAdsService
    #             google_ads_service = GoogleAdsService()
    #             # logger.info(f"🔄 Checking Google Ads connections for user {campaigner_id}...")
    #             # Google Ads tokens are refreshed automatically when needed
    #             # logger.info(f"✅ Google Ads service ready for user {campaigner_id}")
    #         except Exception as e:
    #             pass
    #             # logger.warning(f"Could not initialize Google Ads service: {e}")
        
    #     # Also refresh Facebook tokens if Facebook is in data sources
    #     if "facebook" in data_sources:
    #         try:
    #             from app.services.facebook_service import FacebookService
    #             facebook_service = FacebookService()
    #             # logger.info(f"🔄 Checking and refreshing Facebook tokens for user {campaigner_id}...")
    #             await refresh_user_facebook_tokens(facebook_service, campaigner_id)
    #             # logger.info(f"✅ Facebook service ready for user {campaigner_id}")
    #         except Exception as e:
    #             pass
    #             # logger.warning(f"Could not initialize Facebook service: {e}")
        

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
        """Execute the analytics crew with the given task details.

        All tracing (including Langfuse) is handled by ChatTraceService.
        """
        logger.debug(f"🧑‍💼 [AnalyticsCrew] Received task: {task_details}...")

        try:
            result = self._execute_internal(task_details)
            return result
        except Exception as e:
            logger.error(f"❌ Analytics crew execution error: {e}")
            raise

    def _execute_internal(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Internal execution logic with tracing context."""

        # Extract campaigner_id (for backwards compatibility, but credentials are now passed in)
        self.campaigner_id = task_details.get("campaigner_id")
        customer_id = task_details.get("customer_id")

        platforms = task_details.get("platforms", [])
        if platforms is None:
            from app.core.agents.customer_credentials import CustomerCredentialManager
            self.credential_manager = CustomerCredentialManager()
            credentials = self.credential_manager.fetch_all_credentials(customer_id, self.campaigner_id)
            platforms = credentials.get("platforms", [])
            google_analytics_credentials = credentials.get("google_analytics_credentials")
            google_ads_credentials = credentials.get("google_ads_credentials")
            meta_ads_credentials = credentials.get("meta_ads_credentials")
        else:
            google_analytics_credentials = task_details.get("google_analytics_credentials")
            google_ads_credentials = task_details.get("google_ads_credentials")
            meta_ads_credentials = task_details.get("meta_ads_credentials")


        # Get thread_id for ChatTraceService tracing
        thread_id = task_details.get("thread_id")
        level = task_details.get("level", 1)

        # Initialize ChatTraceService if thread_id is provided
        trace_service = None
        if thread_id:
            from app.services.chat_trace_service import ChatTraceService
            trace_service = ChatTraceService()
            logger.info(f"🔍 [AnalyticsCrew] ChatTraceService enabled for thread {thread_id}")

        # Generate session ID for tracking
        session_id = str(uuid.uuid4())
        logger.info(f"🎬 [AnalyticsCrew] Session started: {session_id}")

        # # Log credential info
        # cred_count = 0
        # if google_analytics_credentials:
        #     logger.info(f"🔑 [AnalyticsCrew] Received Google Analytics credentials")
        #     logger.debug(f"   Property ID: {google_analytics_credentials.get('property_id')}")
        #     cred_count += 1
        # if google_ads_credentials:
        #     logger.info(f"🔑 [AnalyticsCrew] Received Google Ads credentials")
        #     cred_count += 1
        # if meta_ads_credentials:
        #     logger.info(f"🔑 [AnalyticsCrew] Received Meta Ads credentials")
        #     cred_count += 1
        # if cred_count == 0:
        #     logger.warning(f"⚠️  [AnalyticsCrew] No credentials provided")

        # Trace: Initializing MCP clients
        if trace_service and thread_id:
            try:
                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="progress",
                    content=f"Initializing MCP clients for platforms: {platforms}",
                    agent_name="analytics_crew",
                    metadata={
                        "platforms": platforms,
                        "progress_stage": "mcp_initialization"
                    },
                    level=level
                )
            except Exception as e:
                logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace MCP initialization: {e}")

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
            # Add calculator tool to aggregated tools
            from app.core.agents.tools.calculator_tool import CalculatorTool
            calculator = CalculatorTool()

            # Ensure aggregated_tools is a list
            if aggregated_tools is None:
                aggregated_tools = []
            elif not isinstance(aggregated_tools, list):
                aggregated_tools = list(aggregated_tools)

            # Add calculator to the tools list
            aggregated_tools.append(calculator)

            # Log loaded tools
            if aggregated_tools:
                logger.info(f"✅ Total tools loaded: {len(aggregated_tools)} (including calculator)")
                logger.debug(f"🔧 Available tools: {[tool.name for tool in aggregated_tools]}")
            else:
                logger.warning("⚠️  No tools available")

            # Get LLM model name for tracing
            llm_model_name = self.llm.model if hasattr(self.llm, 'model') else str(self.llm)

            # Trace: Creating agents
            if trace_service and thread_id:
                try:
                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="progress",
                        content=f"Creating analytics agents for platforms: {', '.join(platforms)}",
                        agent_name="analytics_crew",
                        metadata={
                            "progress_stage": "agent_creation",
                            "platforms": platforms,
                            "llm_model": llm_model_name
                        },
                        level=level
                    )
                except Exception as e:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace agent creation progress: {e}")

            # Create agents
            master_agent = self.agents_factory.create_master_agent()

            # Trace master agent initialization
            if trace_service and thread_id:
                try:
                    trace_service.add_crew_agent_initialization(
                        thread_id=thread_id,
                        agent_name="master_agent",
                        agent_role=master_agent.role,
                        agent_goal=master_agent.goal,
                        agent_backstory=master_agent.backstory,
                        llm_model=llm_model_name,
                        tools=[],  # Master agent doesn't have direct tools in hierarchical mode
                        allow_delegation=True,
                        metadata={
                            "max_iter": getattr(master_agent, 'max_iter', None),
                            "reasoning": getattr(master_agent, 'reasoning', False),
                            "verbose": getattr(master_agent, 'verbose', False)
                        },
                        level=level
                    )
                    logger.info(f"✅ [AnalyticsCrew] Traced master_agent initialization")
                except Exception as e:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace master_agent initialization: {e}")

            agents = []
            tasks = []
            specialist_tasks = []

            # Create Facebook specialist if needed
            if "facebook_ads" in platforms or "facebook" in platforms or "both" in platforms:
                facebook_tools = self._get_facebook_tools()
                facebook_agent = self.agents_factory.create_facebook_specialist(
                    tools=facebook_tools
                )
                facebook_task = self.tasks_factory.create_facebook_analysis_task(
                    agent=facebook_agent,
                    task_details=task_details
                )
                agents.append(facebook_agent)
                tasks.append(facebook_task)
                specialist_tasks.append(facebook_task)

            # Create Google specialist if needed
            if "google_analytics" in platforms or "google_ads" in platforms or "google" in platforms or "both" in platforms:
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

                # Trace Google specialist initialization
                if trace_service and thread_id:
                    try:
                        tool_names = [tool.name for tool in tools] if tools else []
                        trace_service.add_crew_agent_initialization(
                            thread_id=thread_id,
                            agent_name="google_specialist",
                            agent_role=google_agent.role,
                            agent_goal=google_agent.goal,
                            agent_backstory=google_agent.backstory,
                            llm_model=llm_model_name,
                            tools=tool_names,
                            allow_delegation=False,
                            task_description=google_task.description if hasattr(google_task, 'description') else None,
                            metadata={
                                "max_iter": getattr(google_agent, 'max_iter', None),
                                "verbose": getattr(google_agent, 'verbose', False)
                            },
                            level=level
                        )
                        logger.info(f"✅ [AnalyticsCrew] Traced google_specialist initialization with {len(tool_names)} tools")
                    except Exception as e:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace google_specialist initialization: {e}")

            # # Create synthesis task for master agent
            # synthesis_task = self.tasks_factory.create_synthesis_task(
            #     agent=master_agent,
            #     task_details=task_details,
            #     context=specialist_tasks  # Master agent gets specialist outputs
            # )
            # tasks.append(synthesis_task)

            # Create callbacks for ChatTraceService integration
            callbacks = CrewCallbacks(thread_id=thread_id, level=level)

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
                planning=True,
                # Note: CrewAI callbacks - task_callback called after each task completes
                task_callback=callbacks.task_callback,
                step_callback=callbacks.step_callback,  # Enable step-by-step tracing
            )

            # Trace crew kickoff start
            if trace_service and thread_id:
                try:
                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="crew_kickoff_start",
                        content=f"Starting crew execution with {len(agents)} agents and {len(tasks)} tasks",
                        agent_name="analytics_crew",
                        metadata={
                            "num_agents": len(agents),
                            "num_tasks": len(tasks),
                            "platforms": platforms,
                            "session_id": session_id
                        },
                        level=level
                    )
                except Exception as e:
                    logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace crew kickoff start: {e}")

            try:
                logger.info(f"🚀 Starting crew execution with {len(agents)} agents and {len(tasks)} tasks")

                # Trace: Starting crew execution
                if trace_service and thread_id:
                    try:
                        trace_service.add_agent_step(
                            thread_id=thread_id,
                            step_type="progress",
                            content=f"Executing crew with {len(agents)} agents and {len(tasks)} tasks - this may take a while...",
                            agent_name="analytics_crew",
                            metadata={
                                "progress_stage": "crew_execution",
                                "num_agents": len(agents),
                                "num_tasks": len(tasks),
                                "platforms": platforms
                            },
                            level=level
                        )
                    except Exception as e:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace crew execution progress: {e}")

                # Execute crew - all tracing handled by ChatTraceService via callbacks
                try:
                    result = crew.kickoff()

                    # Validate crew result
                    if result is None:
                        error_msg = "Crew returned None result"
                        logger.error(f"❌ [AnalyticsCrew] {error_msg}")
                        raise LLMResponseError(error_msg)

                    # Check if result has content (CrewOutput has .raw attribute)
                    if hasattr(result, 'raw'):
                        if not result.raw or not str(result.raw).strip():
                            error_msg = "Crew returned empty result"
                            logger.error(f"❌ [AnalyticsCrew] {error_msg}")
                            raise LLMResponseError(error_msg)
                        logger.debug(f"✅ [AnalyticsCrew] Result validated: {len(str(result.raw))} chars")

                    logger.info("✅ Crew execution completed successfully")

                except LLMResponseError as e:
                    # LLM response error - log and re-raise for retry
                    logger.error(f"❌ [AnalyticsCrew] LLM response error: {e}")
                    raise
                except Exception as e:
                    # Other errors during crew execution
                    logger.error(f"❌ [AnalyticsCrew] Crew execution failed: {e}", exc_info=True)

                    # Trace error if available
                    if trace_service and thread_id:
                        try:
                            trace_service.add_agent_step(
                                thread_id=thread_id,
                                step_type="crew_error",
                                content=f"Crew execution failed: {str(e)}",
                                agent_name="analytics_crew",
                                metadata={
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                    "platforms": platforms
                                },
                                level=level
                            )
                        except Exception as trace_error:
                            logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace crew error: {trace_error}")

                    # Return error result
                    return {
                        "success": False,
                        "error": str(e),
                        "platforms": platforms,
                        "task_details": task_details
                    }

                # Trace: Processing results
                if trace_service and thread_id:
                    try:
                        trace_service.add_agent_step(
                            thread_id=thread_id,
                            step_type="progress",
                            content=f"Processing crew results and finalizing response...",
                            agent_name="analytics_crew",
                            metadata={
                                "progress_stage": "results_processing",
                                "platforms": platforms
                            },
                            level=level
                        )
                    except Exception as e:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace results processing: {e}")

                # Trace crew kickoff completion
                if trace_service and thread_id:
                    try:
                        trace_service.add_agent_step(
                            thread_id=thread_id,
                            step_type="crew_kickoff_complete",
                            content=f"✅ Crew execution completed successfully",
                            agent_name="analytics_crew",
                            metadata={
                                "session_id": session_id,
                                "platforms": platforms
                            },
                            level=level
                        )
                    except Exception as e:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace crew kickoff completion: {e}")

                return {
                    "success": True,
                    "result": result,
                    "platforms": platforms,
                    "task_details": task_details,
                    "session_id": session_id
                }

            except Exception as e:
                logger.error(f"❌ Crew execution failed: {e}")

                # Trace error
                if trace_service and thread_id:
                    try:
                        trace_service.add_agent_step(
                            thread_id=thread_id,
                            step_type="error",
                            content=f"Crew execution failed: {str(e)}",
                            agent_name="analytics_crew",
                            metadata={
                                "error_type": type(e).__name__,
                                "platforms": platforms,
                                "session_id": session_id
                            },
                            level=level
                        )
                    except Exception as trace_error:
                        logger.warning(f"⚠️  [AnalyticsCrew] Failed to trace error: {trace_error}")

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
