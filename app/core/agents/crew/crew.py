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
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
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
            temperature=0.1,
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
        from app.models.connections import (
            FacebookConnection,
            GoogleAdsConnection,
            GoogleAnalyticsConnection,
        )
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
        custom_mcp_selection: Optional[Dict[str, MCPServer]] = None,
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

    def _identify_mcp_service_type(self, server_param) -> str:
        """Identify the service type of an MCP server parameter."""
        # Check environment variables for service indicators
        env_vars = server_param.env or {}
        for env_key, env_value in env_vars.items():
            env_key_lower = env_key.lower()
            if "meta" in env_key_lower or "facebook" in env_key_lower:
                return "meta_ads"
            elif "google_analytics" in env_key_lower or "ga4" in env_key_lower:
                return "google_analytics"
            elif "google_ads" in env_key_lower:
                return "google_ads"

        # Check command/args for service indicators
        command_str = " ".join(server_param.args or []).lower()
        if "meta" in command_str or "facebook" in command_str:
            return "meta_ads"
        elif "analytics" in command_str or "ga4" in command_str:
            return "google_analytics"
        elif "google_ads" in command_str or "ads" in command_str:
            return "google_ads"

        # Default fallback
        return "unknown"

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
    
    ### ==================================================================
    def _create_context_str_from_task_details(self, task_details, credentials):
        # Build context information
        query = task_details.get("query", "")
        context = task_details.get("context", {})
        # metrics = ", ".join(task_details.get("metrics", []))
        # date_range = task_details.get("date_range", {})
        platforms = task_details.get("platforms", [])

        # Get all credentials
        fb_credentials = task_details.get("meta_ads_credentials", {}) or {}
        ga_credentials = task_details.get("google_analytics_credentials", {}) or {}
        gads_credentials = task_details.get("google_ads_credentials", {}) or {}

        ad_account_id = fb_credentials.get("ad_account_id", "NOT_PROVIDED")
        property_id = ga_credentials.get("property_id", "NOT_PROVIDED")
        customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")
        account_id = gads_credentials.get("account_id", "NOT_PROVIDED")

        context_info = f"User Question: {query}\n"
        if context:
            agency = context.get("agency", {})
            campaigner = context.get("campaigner", {})
            language = context.get("language", "english")

            if agency:
                context_info += f"\n\nAgency Context:\n- Name: {agency.get('name')}"
            if campaigner:
                context_info += f"\n\nCampaigner Context:\n- Name: {campaigner.get('full_name')}\n- Email: {campaigner.get('email')}"
            context_info += f"\n\nResponse User Language: {language}"

        # Add account information for all platforms
        if ad_account_id and ad_account_id != "NOT_PROVIDED":
            context_info += (
                f"\n\nFacebook Ads Account:\n- Ad Account ID: {ad_account_id}"
            )

        if property_id and property_id != "NOT_PROVIDED":
            context_info += (
                f"\n\nGoogle Analytics Property:\n- Property ID: {property_id}"
            )

        if account_id and account_id != "NOT_PROVIDED":
            context_info += f"\n\nGoogle Ads Account:\n- Account ID: {account_id}"
        if customer_id and customer_id != "NOT_PROVIDED":
            context_info += f"\n- Customer ID: {customer_id}"

        platforms_str = (
            ", ".join(platforms) if platforms else "all available platforms"
        )
        context_info += f"\n\nPlatforms to analyze: {platforms_str}"
        logger.info(f"📡 [AnalyticsCrew] Context: {context_info}")
        return context_info

    ### ==================================================================
    def _get_crew(self, task_details, credentials, platforms) -> Crew:
        """Get the crew for the task."""
        # Get the context information (IDs, user information, user request etc...)
        context_str = self._create_context_str_from_task_details(task_details, credentials)

        from crewai import Agent, Crew, Task, Process
        specialist_agents = []
        # Manager agent coordinates the team
        manager = Agent(
            role="Project Manager",
            goal="Coordinate team efforts and ensure project success. Receive a question from the user and intelligently transform user question and intents into specialist-specific, precise, actionable prompts that leverage each worker's expertise and tools effectively.",
            backstory="You are a master orchestrator with deep knowledge of your specialist team capabilities. You route questions between the Google Specialist and Facebook Marketing Specialist. You ensure each specialist receives clear instructions with all necessary parameters to execute their analysis effectively, critically evaluate their results, and iterate until acceptance criteria are met. Deliver one final, decision-ready answer plus structured data.",
            allow_delegation=True,
            verbose=True
        )
        logger.info(f"✅ Manager agent created")

        # Specialist agents
        if "facebook_ads" in platforms:
            facebook_specialist = Agent(
                role="Facebook Marketing Specialist",
                goal="Analyze Facebook Ads Manager and Meta Business Suite data. Extract performance metrics, audience insights, ad spend, conversions, and ROI calculations.",
                backstory="You are a Facebook Marketing expert with extensive experience using Meta's APIs. You handle campaign performance analysis, audience targeting, creative optimization, and ROI evaluation across Facebook and Instagram.",
                allow_delegation=False,  # Specialists focus on their expertise
                verbose=True,
                tools=self.facebook_tools
            )
            specialist_agents.append(facebook_specialist)
            logger.info(f"✅ Facebook Specialist created with {len(self.facebook_tools)} tools")

        if "google_analytics" in platforms or "google_ads" in platforms:
            google_specialist = Agent(
                role="Google Specialist", 
                goal="Extract, analyze, and provide deep insights from Google Analytics and Google Ads data. Generate comprehensive reports on traffic, conversions, user behavior, and performance metrics.",
                backstory="You are a Google Analytics and Google Ads expert with 8+ years of experience. You understand GA4 and Google Ads APIs, conversion tracking, attribution modeling, and user behavior analysis. You can access GA4 and Google Ads data programmatically and turn metrics into actionable business insights.",
                allow_delegation=False,
                verbose=True,
                tools=self.google_tools
            )
            specialist_agents.append(google_specialist)
            logger.info(f"✅ Google Specialist created with {len(self.google_tools)} tools")

        # Manager-led task
        project_task = Task(
            description=f"""{context_str}

Perform a comprehensive unified analysis across the platforms for the following:

IMPORTANT: Use the appropriate account/credential IDs provided above when querying each platform's data through MCP tools.

Your comprehensive tasks across all platforms:
1. Understand the user's question and what specific insights they need
2. For Facebook Ads: Use Ad Account ID to fetch campaign data, calculate KPIs, identify trends, and analyze audience engagement
3. For Google Analytics: Use Property ID to analyze user behavior, traffic patterns, conversion funnels, and demographics
4. For Google Ads: Use Customer/Account ID to analyze campaign performance, ad spend efficiency, and conversion tracking
5. Calculate unified key performance indicators across all platforms
6. Identify cross-platform patterns and correlations
7. Compare performance across different marketing channels
8. Analyze user journey from awareness (ads) to conversion (analytics)
9. Identify top-performing and under-performing campaigns/channels
10. Highlight anomalies and significant changes across platforms
11. Provide actionable insights that span multiple platforms
12. Answer the user's specific question with data from all relevant sources

Deliver a comprehensive unified analysis with:
- Direct answer to the user's question (first and foremost)
- Executive summary covering all platforms (2-3 paragraphs)
- Cross-platform performance comparison
- Unified metrics dashboard
- User journey analysis (ads → analytics)
- Channel attribution insights
- Actionable recommendations (at least 5, prioritized by impact)
- Specific optimization strategies for each platform
- Overall marketing health assessment
- Next steps and prioritized action items
IMPORTANT: Make sure your response is in the user's language.
""",
            # "Create a comprehensive market analysis report with recommendations",
            expected_output="""A comprehensive unified analytics report including:
- Executive summary covering all platforms
- Cross-platform performance metrics and comparisons
- User journey analysis from ads to conversions
- Channel attribution and ROI analysis
- 5+ prioritized actionable insights and recommendations
- Platform-specific optimization strategies
- Marketing performance scorecard
- Detailed action plan with timelines
""",   # "Executive summary, detailed analysis, and strategic recommendations",
            agent=google_specialist  # Manager will delegate to specialists
        )
        
        # Hierarchical crew
        crew = Crew(
            agents=[*specialist_agents],#, manager],
            tasks=[project_task],
            process=Process.hierarchical,  # Manager coordinates everything
            manager_llm=self.llm,  # Specify LLM for manager
            verbose=True
        )
        return crew
        ### ==================================================================
    
    def _execute_internal(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Internal execution logic with tracing context."""

        # Extract campaigner_id (for backwards compatibility, but credentials are now passed in)
        self.campaigner_id = task_details.get("campaigner_id")
        customer_id = task_details.get("customer_id")

        platforms = task_details.get("platforms", None)
        if platforms is None:
            from app.core.agents.customer_credentials import CustomerCredentialManager

            self.credential_manager = CustomerCredentialManager()
            credentials = self.credential_manager.fetch_all_credentials(
                customer_id, self.campaigner_id
            )
            platforms = credentials.get("platforms", [])
            google_analytics_credentials = credentials.get(
                "google_analytics"
            )
            google_ads_credentials = credentials.get("google_ads")
            meta_ads_credentials = credentials.get("meta_ads")
            task_details["platforms"] = platforms
            task_details["meta_ads_credentials"] = meta_ads_credentials
            task_details["google_analytics_credentials"] = google_analytics_credentials
            task_details["google_ads_credentials"] = google_ads_credentials
        else:
            google_analytics_credentials = task_details.get(
                "google_analytics_credentials"
            )
            google_ads_credentials = task_details.get("google_ads_credentials")
            meta_ads_credentials = task_details.get("meta_ads_credentials")
        logger.info(f"📡 [AnalyticsCrew] Platforms: {platforms}")

        # Get thread_id for ChatTraceService tracing
        thread_id = task_details.get("thread_id")
        level = task_details.get("level", 1)

        # Initialize ChatTraceService if thread_id is provided
        trace_service = None
        if thread_id:
            from app.services.chat_trace_service import ChatTraceService

            trace_service = ChatTraceService()
            logger.info(
                f"🔍 [AnalyticsCrew] ChatTraceService enabled for thread {thread_id}"
            )
        else:
            logger.warning(f"⚠️  [AnalyticsCrew] No thread_id provided, tracing disabled")

        # Generate session ID for tracking
        session_id = str(uuid.uuid4())
        logger.info(f"🎬 [AnalyticsCrew] Session started: {session_id}")

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
                        "progress_stage": "mcp_initialization",
                    },
                    level=level,
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  [AnalyticsCrew] Failed to trace MCP initialization: {e}"
                )

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
        facebook_tools = []
        google_tools = []

        if use_mcp_adapter:
            logger.info(f"🔧 Initializing {len(self.mcp_param_list)} MCP server(s)")

            # Split MCP servers by service type
            facebook_server_params = []
            google_analytics_server_params = []
            google_ads_server_params = []

            for param in self.mcp_param_list:
                # Determine service type from the server configuration
                # We can check the command args or env vars to identify the service
                service_type = self._identify_mcp_service_type(param)
                if service_type == "meta_ads":
                    facebook_server_params.append(param)
                elif service_type == "google_analytics":
                    google_analytics_server_params.append(param)
                elif service_type == "google_ads":
                    google_ads_server_params.append(param)

            # Create separate MCP adapters for each service type
            facebook_mcp_tools = []
            if facebook_server_params:
                fb_mcp_server = MCPServerAdapter(facebook_server_params)
                fb_tools = fb_mcp_server.tools
                facebook_mcp_tools = list(fb_tools) if fb_tools else []

            google_mcp_tools = []
            google_server_params = google_analytics_server_params + google_ads_server_params
            if google_server_params:
                ggl_mcp_server = MCPServerAdapter(google_server_params)
                g_tools = ggl_mcp_server.tools
                google_mcp_tools = list(g_tools) if g_tools else []

            # Add MCP tools to respective specialists
            facebook_tools.extend(facebook_mcp_tools)
            google_tools.extend(google_mcp_tools)

        else:
            # Fallback: Use custom MCP clients
            logger.warning("⚠️  No MCP servers configured, using custom MCP clients")
            # if "facebook_ads" in platforms or "facebook" in platforms or "both" in platforms:
            #     facebook_tools.extend(self._get_facebook_tools())
            # if "google_analytics" in platforms or "google_ads" in platforms or "google" in platforms or "both" in platforms:
            #     google_tools.extend(self._get_google_tools())

        # Store tools for use in specialist creation
        self.facebook_tools = facebook_tools
        self.google_tools = google_tools

        # Initialize calculator tool
        from app.core.agents.tools.calculator_tool import CalculatorTool
        calculator = CalculatorTool()
        if len(facebook_tools) > 0:
            facebook_tools.append(calculator)
        if len(google_tools) > 0:
            google_tools.append(calculator)

        # Log loaded tools
        logger.info(f"✅ Tools prepared: {len(self.facebook_tools)} Facebook + {len(self.google_tools)} Google (including calculator)")
        logger.info(f"🔧 Facebook tools: {[tool.name for tool in self.facebook_tools]}")
        logger.info(f"🔧 Google tools: {[tool.name for tool in self.google_tools]}")

        # Get LLM model name for tracing
        llm_model_name = (
            self.llm.model if hasattr(self.llm, "model") else str(self.llm)
        )

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
                            "llm_model": llm_model_name,
                        },
                        level=level,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️  [AnalyticsCrew] Failed to trace agent creation progress: {e}"
                    )


        ### ==================================================================
        # # Create agents
        # master_agent = self.agents_factory.create_master_agent()

        # # Trace master agent initialization
        # if trace_service and thread_id:
        #     try:
        #         trace_service.add_crew_agent_initialization(
        #             thread_id=thread_id,
        #             agent_name="master_agent",
        #             agent_role=master_agent.role,
        #             agent_goal=master_agent.goal,
        #             agent_backstory=master_agent.backstory,
        #             llm_model=llm_model_name,
        #             tools=[],  # Master agent doesn't have direct tools in hierarchical mode
        #             allow_delegation=True,
        #             metadata={
        #                 "max_iter": getattr(master_agent, "max_iter", None),
        #                 "reasoning": getattr(master_agent, "reasoning", False),
        #                 "verbose": getattr(master_agent, "verbose", False),
        #             },
        #             level=level,
        #         )
        #         logger.info(
        #             f"✅ [AnalyticsCrew] Traced master_agent initialization"
        #         )
        #     except Exception as e:
        #         logger.warning(
        #             f"⚠️  [AnalyticsCrew] Failed to trace master_agent initialization: {e}"
        #         )

        # agents = []
        # tasks = []
        # specialist_tasks = []

        # # Create Facebook specialist if needed
        # if (
        #     "facebook_ads" in platforms
        #     or "facebook" in platforms
        #     or "both" in platforms
        # ):
        #     facebook_agent = self.agents_factory.create_facebook_specialist(
        #         tools=self.facebook_tools
        #     )
        #     agents.append(facebook_agent)
        #     facebook_task = self.tasks_factory.create_facebook_analysis_task(
        #         agent=facebook_agent, task_details=task_details
        #     )
        #     tasks.append(facebook_task)
        #     specialist_tasks.append(facebook_task)

        # # Create Google specialist if needed
        # if (
        #     "google_analytics" in platforms
        #     or "google_ads" in platforms
        #     or "google" in platforms
        #     or "both" in platforms
        # ):
        #     google_agent = self.agents_factory.create_google_specialist(
        #         tools=self.google_tools
        #     )
        #     agents.append(google_agent)
        #     google_task = self.tasks_factory.create_google_analysis_task(
        #         agent=google_agent, task_details=task_details
        #     )
        #     tasks.append(google_task)
        #     specialist_tasks.append(google_task)

        #     # Trace Google specialist initialization
        #     if trace_service and thread_id:
        #         try:
        #             tool_names = [tool.name for tool in self.google_tools] if self.google_tools else []
        #             trace_service.add_crew_agent_initialization(
        #                 thread_id=thread_id,
        #                 agent_name="google_specialist",
        #                 agent_role=google_agent.role,
        #                 agent_goal=google_agent.goal,
        #                 agent_backstory=google_agent.backstory,
        #                 llm_model=llm_model_name,
        #                 tools=tool_names,
        #                 allow_delegation=False,
        #                 task_description=google_task.description
        #                 if hasattr(google_task, "description")
        #                 else None,
        #                 metadata={
        #                     "max_iter": getattr(google_agent, "max_iter", None),
        #                     "verbose": getattr(google_agent, "verbose", False),
        #                 },
        #                 level=level,
        #             )
        #             logger.info(
        #                 f"✅ [AnalyticsCrew] Traced google_specialist initialization with {len(tool_names)} tools"
        #             )
        #         except Exception as e:
        #             logger.warning(
        #                 f"⚠️  [AnalyticsCrew] Failed to trace google_specialist initialization: {e}"
        #             )

        # # Create synthesis task for master agent
        # synthesis_task = self.tasks_factory.create_synthesis_task(
        #     agent=master_agent,
        #     task_details=task_details,
        #     context=specialist_tasks  # Master agent gets specialist outputs
        # )
        # tasks.append(synthesis_task)

        # merged_task = self.tasks_factory.create_merged_task(
        #     agent=master_agent, task_details=task_details
        # )
        # tasks.append(merged_task)

        # # Create callbacks for ChatTraceService integration
        # callbacks = CrewCallbacks(thread_id=thread_id, level=level)

        # # Record task starts
        # for i, task in enumerate(tasks):
        #     agent = task.agent if hasattr(task, "agent") else master_agent
        #     callbacks.start_task(task, agent, i)

        # # Create and run crew with callbacks
        # logger.debug(
        #     f"Starting a crew with agents: {agents}, tasks: {tasks}, master_agent: {master_agent}"
        # )
        # crew = Crew(
        #     agents=agents,# + [master_agent],
        #     manager_agent=master_agent,
        #     manager_llm=self.llm,
        #     tasks=[merged_task],
        #     process=Process.hierarchical,
        #     verbose=True,
        #     planning=True,
        #     # Note: CrewAI callbacks - task_callback called after each task completes
        #     task_callback=callbacks.task_callback,
        #     step_callback=callbacks.step_callback,  # Enable step-by-step tracing
        # )
        ### ==================================================================
        crew = self._get_crew(task_details, credentials, platforms)
        # # Trace crew kickoff start
        # if trace_service and thread_id:
        #     try:
        #         trace_service.add_agent_step(
        #             thread_id=thread_id,
        #             step_type="crew_kickoff_start",
        #             content=f"Starting crew execution with {len(agents)} agents and {len(tasks)} tasks",
        #             agent_name="analytics_crew",
        #             metadata={
        #                 "num_agents": len(agents),
        #                 "num_tasks": len(tasks),
        #                 "platforms": platforms,
        #                 "session_id": session_id,
        #             },
        #             level=level,
        #         )
        #     except Exception as e:
        #         logger.warning(
        #             f"⚠️  [AnalyticsCrew] Failed to trace crew kickoff start: {e}"
        #         )
        try:
        #     logger.info(
        #         f"🚀 Starting crew execution with {len(agents)} agents and {len(tasks)} tasks"
        #     )

        #     # Trace: Starting crew execution
        #     if trace_service and thread_id:
        #         try:
        #             trace_service.add_agent_step(
        #                 thread_id=thread_id,
        #                 step_type="progress",
        #                 content=f"Executing crew with {len(agents)} agents and {len(tasks)} tasks - this may take a while...",
        #                 agent_name="analytics_crew",
        #                 metadata={
        #                     "progress_stage": "crew_execution",
        #                     "num_agents": len(agents),
        #                     "num_tasks": len(tasks),
        #                     "platforms": platforms,
        #                 },
        #                 level=level,
        #             )
        #         except Exception as e:
        #             logger.warning(
        #                     f"⚠️  [AnalyticsCrew] Failed to trace crew execution progress: {e}"
        #                 )

            # Execute crew - all tracing handled by ChatTraceService via callbacks
            try:
                    result = crew.kickoff()

                    # Validate crew result
                    if result is None:
                        error_msg = "Crew returned None result"
                        logger.error(f"❌ [AnalyticsCrew] {error_msg}")
                        raise LLMResponseError(error_msg)

                    # Check if result has content (CrewOutput has .raw attribute)
                    if hasattr(result, "raw"):
                        if not result.raw or not str(result.raw).strip():
                            error_msg = "Crew returned empty result"
                            logger.error(f"❌ [AnalyticsCrew] {error_msg}")
                            raise LLMResponseError(error_msg)
                        logger.debug(
                            f"✅ [AnalyticsCrew] Result validated: {len(str(result.raw))} chars"
                        )

                    logger.info("✅ Crew execution completed successfully")

            except LLMResponseError as e:
                    # LLM response error - log and re-raise for retry
                    logger.error(f"❌ [AnalyticsCrew] LLM response error: {e}")
                    raise
            except Exception as e:
                    # Other errors during crew execution
                    logger.error(
                        f"❌ [AnalyticsCrew] Crew execution failed: {e}", exc_info=True
                    )

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
                                    "platforms": platforms,
                                },
                                level=level,
                            )
                        except Exception as trace_error:
                            logger.warning(
                                f"⚠️  [AnalyticsCrew] Failed to trace crew error: {trace_error}"
                            )

                    # Return error result
                    return {
                        "success": False,
                        "error": str(e),
                        "platforms": platforms,
                        "task_details": task_details,
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
                            "platforms": platforms,
                        },
                        level=level,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️  [AnalyticsCrew] Failed to trace results processing: {e}"
                    )

            # Trace crew kickoff completion
            if trace_service and thread_id:
                try:
                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="crew_kickoff_complete",
                        content=f"✅ Crew execution completed successfully",
                        agent_name="analytics_crew",
                        metadata={"session_id": session_id, "platforms": platforms},
                        level=level,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️  [AnalyticsCrew] Failed to trace crew kickoff completion: {e}"
                    )

            return {
                "success": True,
                    "result": result,
                    "platforms": platforms,
                    "task_details": task_details,
                    "session_id": session_id,
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
                                "session_id": session_id,
                            },
                            level=level,
                        )
                    except Exception as trace_error:
                        logger.warning(
                            f"⚠️  [AnalyticsCrew] Failed to trace error: {trace_error}"
                        )

                return {
                    "success": False,
                    "error": str(e),
                    "platforms": platforms,
                    "task_details": task_details,
                    "session_id": session_id,
                }

        finally:
                # Cleanup MCP clients
                if self.facebook_client:
                    self.facebook_client.close()
                if self.google_client:
                    self.google_client.close()
