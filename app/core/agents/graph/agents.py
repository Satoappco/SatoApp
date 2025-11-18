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
from ..customer_credentials import CustomerCredentialManager
from ..mcp_clients.mcp_registry import MCPSelector

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
        self.credential_manager = CustomerCredentialManager()

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
        return self.credential_manager.fetch_customer_platforms(customer_id)

    def _fetch_google_analytics_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID.

        Args:
            customer_id: Customer ID

        Returns:
            Dictionary with 'refresh_token', 'property_id', 'client_id', 'client_secret' or None
        """
        return self.credential_manager.fetch_google_analytics_credentials(customer_id, campaigner_id)

    def _fetch_google_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Ads credentials.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'refresh_token', 'customer_id', 'client_id', 'client_secret' or None
        """
        return self.credential_manager.fetch_google_ads_credentials(customer_id, campaigner_id)

    def _fetch_meta_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Facebook/Meta Ads access token.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'access_token', 'ad_account_id' or None
        """
        return self.credential_manager.fetch_meta_ads_credentials(customer_id, campaigner_id)

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
        self.llm_class = type(llm)  # Store the LLM class for recreation in worker thread

        # Extract LLM configuration for recreation
        # Try multiple methods to get the model name and other params
        self.llm_kwargs = {}
        if hasattr(llm, 'model_name'):
            self.llm_kwargs['model'] = llm.model_name
        elif hasattr(llm, 'model'):
            self.llm_kwargs['model'] = llm.model

        # Get other kwargs if available
        if hasattr(llm, '_lc_kwargs'):
            self.llm_kwargs.update(llm._lc_kwargs)

        self.trace = None  # Will be set by AgentExecutorNode
        self.mcp_client: Optional[MCPClient] = None
        self.credential_manager = CustomerCredentialManager()

    def set_trace(self, trace):
        """Set the LangFuse trace for this agent."""
        self.trace = trace

    def _fetch_customer_platforms(self, customer_id: int) -> List[str]:
        """Fetch customer's enabled platforms from digital_assets table."""
        return self.credential_manager.fetch_customer_platforms(customer_id)

    def _fetch_google_analytics_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID."""
        return self.credential_manager.fetch_google_analytics_credentials(customer_id, campaigner_id)

    def _fetch_google_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Ads credentials."""
        return self.credential_manager.fetch_google_ads_credentials(customer_id, campaigner_id)

    def _fetch_meta_ads_token(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Facebook/Meta Ads access token."""
        return self.credential_manager.fetch_meta_ads_credentials(customer_id, campaigner_id)

    async def _initialize_mcp_clients(self, task_details: Dict[str, Any]):
        """Initialize and connect MultiServerMCPClient using MCP registry.

        Args:
            task_details: Task details containing platforms and credentials
        """
        platforms = task_details.get("platforms", [])
        ga_credentials = task_details.get("google_analytics_credentials")
        gads_credentials = task_details.get("google_ads_credentials")
        meta_credentials = task_details.get("meta_ads_credentials")

        # Build server parameters using MCP registry
        server_params_list = MCPSelector.build_all_server_params(
            platforms=platforms,
            google_analytics_credentials=ga_credentials,
            google_ads_credentials=gads_credentials,
            meta_ads_credentials=meta_credentials
        )

        if not server_params_list:
            logger.warning("⚠️  [SingleAnalyticsAgent] No MCP servers configured")
            return

        # Convert StdioServerParameters to MultiServerMCPClient format
        servers = {}
        for idx, params in enumerate(server_params_list):
            # Use service name as key (extract from working directory or use index)
            server_name = f"server_{idx}"
            if params.cwd:
                # Extract service name from working directory path
                # e.g., /path/to/mcps/google_ads_mcp -> google_ads
                from pathlib import Path
                cwd_path = Path(params.cwd)
                server_name = cwd_path.name.replace("-", "_")

            servers[server_name] = {
                "command": params.command,
                "args": params.args,
                "env": params.env or {},
                "transport": "stdio"  # All MCP servers use stdio transport
            }

        # Create MultiServerMCPClient (initializes on creation, no connect() needed)
        if servers:
            try:
                self.mcp_client = MCPClient(servers)
                logger.info(f"✅ [SingleAnalyticsAgent] Initialized {len(servers)} MCP servers: {list(servers.keys())}")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Failed to initialize MCP client: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                self.mcp_client = None
        else:
            logger.warning("⚠️  [SingleAnalyticsAgent] No MCP servers configured")

    async def _disconnect_mcp_clients(self):
        """Disconnect MultiServerMCPClient."""
        if self.mcp_client:
            try:
                # MultiServerMCPClient doesn't have disconnect(), cleanup happens automatically
                logger.info("✅ [SingleAnalyticsAgent] MCP client cleanup complete")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Error during MCP cleanup: {e}")
            finally:
                self.mcp_client = None

    def _wrap_tool_with_type_coercion(self, tool, schema_dict: dict):
        """Wrap a tool to automatically coerce float parameters to int based on common parameter names.

        Args:
            tool: The original tool to wrap
            schema_dict: The tool's JSON schema (may be None for MCP tools)

        Returns:
            Wrapped tool with type coercion
        """
        tool_name = getattr(tool, 'name', 'unknown')

        # Common parameter names that should be integers
        # These are based on Google Analytics, Google Ads, and Facebook Ads APIs
        KNOWN_INTEGER_PARAMS = {
            'match_type',      # Google Analytics filter match type
            'limit',           # Pagination limit
            'offset',          # Pagination offset
            'page_size',       # Page size
            'max_results',     # Max results
            'comparison_type', # Comparison operators
            'operator',        # Numeric operators
            'level',           # Ad level (campaign, adset, ad)
            'time_increment',  # Time increment for reports
        }

        logger.debug(f"🔧 [TypeCoercion] Wrapping tool '{tool_name}' with integer param coercion")

        # Store original coroutine (this is what actually gets called)
        original_coroutine = tool.coroutine if hasattr(tool, 'coroutine') else None

        if not original_coroutine:
            logger.debug(f"⚠️  Tool '{getattr(tool, 'name', 'unknown')}' has no coroutine attribute")
            return tool

        def coerce_value(value, param_path="", parent_path=""):
            """Recursively coerce floats to ints in nested structures."""
            if isinstance(value, dict):
                # Recursively coerce dict values
                result = {}
                for k, v in value.items():
                    # Build the full path for nested parameters
                    full_path = f"{parent_path}.{k}" if parent_path else k
                    result[k] = coerce_value(v, k, full_path)
                return result
            elif isinstance(value, list):
                # Recursively coerce list items
                return [coerce_value(item, param_path, parent_path) for item in value]
            elif isinstance(value, float) and param_path in KNOWN_INTEGER_PARAMS:
                # Coerce float to int if this parameter name is a known integer param
                int_value = int(value)
                full_path = f"{parent_path}.{param_path}" if parent_path else param_path
                logger.info(f"🔧 [TypeCoercion] Coerced {full_path}: {value} (float) -> {int_value} (int)")
                return int_value
            else:
                return value

        # Wrap the coroutine method (this is what arun actually calls)
        async def wrapped_coroutine(*args, **kwargs):
            """Wrapped coroutine that coerces types and logs MCP calls."""
            import time

            # Sanitize arguments for logging (redact sensitive data)
            def sanitize_for_logging(data, max_length=500):
                """Sanitize data for logging."""
                sensitive_keys = {"token", "password", "secret", "key", "api_key", "access_token", "refresh_token"}

                if isinstance(data, dict):
                    sanitized = {}
                    for k, v in data.items():
                        if isinstance(k, str) and any(sens in k.lower() for sens in sensitive_keys):
                            sanitized[k] = "***REDACTED***"
                        elif isinstance(v, str) and len(v) > max_length:
                            sanitized[k] = v[:max_length] + "..."
                        elif isinstance(v, (dict, list)):
                            sanitized[k] = sanitize_for_logging(v, max_length)
                        else:
                            sanitized[k] = v
                    return sanitized
                elif isinstance(data, list):
                    return [sanitize_for_logging(item, max_length) for item in data]
                elif isinstance(data, str) and len(data) > max_length:
                    return data[:max_length] + "..."
                else:
                    return data

            # Debug print for MCP call
            sanitized_kwargs = sanitize_for_logging(kwargs)
            logger.info(f"\n{'='*80}")
            logger.info(f"🔧 [MCP CALL] Tool: {tool_name}")
            logger.info(f"📦 [MCP CALL] Client: MultiServerMCPClient (SingleAnalyticsAgent)")
            logger.info(f"📋 [MCP CALL] Arguments:")
            for key, value in sanitized_kwargs.items():
                logger.info(f"   - {key}: {value}")
            logger.info(f"{'='*80}\n")

            # Coerce all kwargs recursively
            coerced_kwargs = {}
            for key, value in kwargs.items():
                coerced_value = coerce_value(value, key)
                if coerced_value != value:
                    logger.info(f"🔧 [TypeCoercion] Coerced {key}: {type(value).__name__} -> {type(coerced_value).__name__}")
                coerced_kwargs[key] = coerced_value

            # Call original coroutine with coerced kwargs and track time
            start_time = time.time()
            try:
                result = await original_coroutine(*args, **coerced_kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Debug print for MCP response
                logger.info(f"\n{'='*80}")
                logger.info(f"✅ [MCP RESPONSE] Tool: {tool_name}")
                logger.info(f"⏱️  [MCP RESPONSE] Duration: {duration_ms:.2f}ms")
                logger.info(f"📊 [MCP RESPONSE] Result type: {type(result).__name__}")

                # Log the content of the response
                if hasattr(result, 'content'):
                    logger.info(f"📄 [MCP RESPONSE] Content:")
                    if isinstance(result.content, list):
                        for idx, item in enumerate(result.content):
                            logger.info(f"   [{idx}] Type: {type(item).__name__}")
                            if hasattr(item, 'text'):
                                text = item.text
                                if len(text) > 500:
                                    logger.info(f"   [{idx}] Text (first 500 chars): {text[:500]}...")
                                else:
                                    logger.info(f"   [{idx}] Text: {text}")
                            elif hasattr(item, '__dict__'):
                                logger.info(f"   [{idx}] Data: {item.__dict__}")
                            else:
                                logger.info(f"   [{idx}] Value: {item}")
                    else:
                        logger.info(f"   {result.content}")
                elif isinstance(result, str):
                    # String response
                    if len(result) > 500:
                        logger.info(f"📄 [MCP RESPONSE] Result (first 500 chars): {result[:500]}...")
                    else:
                        logger.info(f"📄 [MCP RESPONSE] Result: {result}")
                elif hasattr(result, '__dict__'):
                    logger.info(f"📄 [MCP RESPONSE] Result dict: {result.__dict__}")
                else:
                    logger.info(f"📄 [MCP RESPONSE] Result: {result}")

                logger.info(f"{'='*80}\n")

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # Debug print for MCP error
                logger.error(f"\n{'='*80}")
                logger.error(f"❌ [MCP ERROR] Tool: {tool_name}")
                logger.error(f"⏱️  [MCP ERROR] Duration: {duration_ms:.2f}ms")
                logger.error(f"🚫 [MCP ERROR] Error type: {type(e).__name__}")
                logger.error(f"💬 [MCP ERROR] Error message: {str(e)}")
                logger.error(f"{'='*80}\n")

                raise

        tool.coroutine = wrapped_coroutine
        logger.info(f"✅ [TypeCoercion] Wrapped coroutine for tool '{getattr(tool, 'name', 'unknown')}'")

        return tool

    async def _get_all_tools(self) -> List:
        """Get all available MCP tools from MultiServerMCPClient."""
        tools = []

        if self.mcp_client:
            try:
                raw_tools = await self.mcp_client.get_tools()
                logger.info(f"✅ [SingleAnalyticsAgent] Loaded {len(raw_tools)} tools from MCP servers")

                # Filter out tools with invalid schemas that would cause Gemini errors
                # Specifically, tools with array parameters missing 'items' field
                for idx, tool in enumerate(raw_tools):
                    try:
                        valid = True
                        tool_name = getattr(tool, 'name', f'tool_{idx}')

                        # Try to get the schema from the tool
                        schema_dict = None
                        if hasattr(tool, 'args_schema') and tool.args_schema:
                            try:
                                if hasattr(tool.args_schema, 'model_json_schema'):
                                    schema_dict = tool.args_schema.model_json_schema()
                                elif hasattr(tool.args_schema, 'schema'):
                                    # Fallback for older Pydantic versions (suppress deprecation)
                                    import warnings
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore", DeprecationWarning)
                                        schema_dict = tool.args_schema.schema()

                                # Log schema extraction for run_report
                                if tool_name == 'run_report':
                                    logger.info(f"📋 [Schema] Extracted schema for {tool_name}: has schema = {schema_dict is not None}")
                            except Exception as e:
                                logger.debug(f"Could not get schema for tool '{tool_name}': {e}")
                        else:
                            if tool_name == 'run_report':
                                logger.info(f"⚠️  [Schema] Tool {tool_name} has no args_schema")

                        # Validate schema recursively
                        if schema_dict:
                            def check_schema_recursive(schema_obj, path=""):
                                """Recursively check schema for invalid array definitions."""
                                if isinstance(schema_obj, dict):
                                    # Check if this is an array type without items
                                    if schema_obj.get('type') == 'array' and 'items' not in schema_obj:
                                        logger.warning(f"⚠️  [SingleAnalyticsAgent] Tool '{tool_name}' - invalid array at {path}: missing 'items' field")
                                        return False

                                    # Check nested objects
                                    for key, value in schema_obj.items():
                                        if not check_schema_recursive(value, f"{path}.{key}" if path else key):
                                            return False
                                elif isinstance(schema_obj, list):
                                    for i, item in enumerate(schema_obj):
                                        if not check_schema_recursive(item, f"{path}[{i}]"):
                                            return False
                                return True

                            valid = check_schema_recursive(schema_dict)

                        if valid:
                            # Wrap tool to handle type coercion (float -> int)
                            wrapped_tool = self._wrap_tool_with_type_coercion(tool, schema_dict)
                            tools.append(wrapped_tool)
                        else:
                            logger.warning(f"⚠️  [SingleAnalyticsAgent] Excluding tool '{tool_name}' (index {idx}) due to invalid schema")
                    except Exception as e:
                        logger.warning(f"⚠️  [SingleAnalyticsAgent] Error validating tool at index {idx}: {e}")
                        # Don't include tools we can't validate
                        logger.debug(f"   Tool details: {getattr(tool, 'name', 'unknown')}")

                logger.info(f"✅ [SingleAnalyticsAgent] Using {len(tools)} valid tools (filtered out {len(raw_tools) - len(tools)} invalid)")

                # Debug: Log tool names to identify problematic ones
                if logger.isEnabledFor(logging.DEBUG):
                    for i, tool in enumerate(tools):
                        tool_name = getattr(tool, 'name', f'unknown_{i}')
                        logger.debug(f"   Tool {i}: {tool_name}")

            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Failed to get tools from MCP client: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")

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

        # Check if MCP client was initialized successfully
        if not self.mcp_client:
            error_msg = "Failed to initialize MCP servers. Please check server configurations and credentials."
            logger.error(f"❌ [SingleAnalyticsAgent] {error_msg}")
            return {
                "status": "error",
                "result": f"I encountered a configuration error: {error_msg}",
                "message": error_msg,
                "agent": "single_analytics_agent",
                "platforms": platforms,
                "task_received": task
            }

        try:
            # Get all available tools
            tools = await self._get_all_tools()

            if not tools:
                error_msg = "No MCP tools are currently available. This could be due to server startup issues or missing dependencies."
                logger.error(f"❌ [SingleAnalyticsAgent] {error_msg}")
                return {
                    "status": "error",
                    "result": f"I'm unable to access the analytics tools right now: {error_msg}",
                    "message": error_msg,
                    "agent": "single_analytics_agent",
                    "platforms": platforms,
                    "task_received": task
                }

            logger.info(f"🚀 [SingleAnalyticsAgent] Executing with {len(tools)} tools from platforms: {platforms}")

            # Build context for the agent
            context_str = self._build_context_string(task_details)

            # Get current date and time
            from datetime import datetime
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create prompt template with context
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert marketing analytics agent with direct access to multiple advertising platforms.

Current Date and Time: {current_datetime}

{context_str}

Your tasks:
1. Analyze the user's question to understand what data they need
2. Use the appropriate MCP tools to fetch data from the relevant platforms
3. Always include the correct property/account IDs in your tool calls
4. Analyze the data and identify trends, patterns, and insights
5. Provide a comprehensive answer with actionable recommendations
6. Format your response in {language} language

IMPORTANT Tool Usage Guidelines:
- Google Analytics run_report REQUIRES both 'dimensions' and 'metrics' parameters
  Example: run_report(property_id="123", metrics=["sessions"], dimensions=["date"], date_ranges=[...])
- If dimensions are not specified in the query, use common defaults like ["date"] or ["country"]
- Always check tool schemas before calling - all required parameters must be provided
- CRITICAL: Integer parameters MUST be passed as integers, not floats
  Example: match_type=1 (CORRECT) not match_type=1.0 (WRONG)
  Common integer parameters: match_type, limit, offset, page_size

COMMON DIMENSION NAMES (Google Analytics 4):
- For campaigns: use sessionCampaignName or sessionCampaignId (NOT campaign or campaignId)
- For source: use sessionSource or firstUserSource (NOT source)
- For medium: use sessionMedium (NOT medium)
- For combined source/medium: use sessionSourceMedium
- For date: use date
- For country: use country
When you get a "Field X is not valid" error, the API usually suggests the correct field name - use it!

IMPORTANT FILTERING TIPS:
- For paid/CPC campaigns from Google: filter by sessionSourceMedium EQUALS "google / cpc" (exact match)
- For all Google traffic (paid + organic): filter by sessionSource EQUALS "google"
- For organic Google only: filter by sessionSourceMedium EQUALS "google / organic"
- match_type=1 means EXACT match, match_type=2 means CONTAINS

DATE FORMATS - CRITICAL:
Google Analytics API accepts ONLY these date formats:
- YYYY-MM-DD format: 2024-01-15
- Relative formats: today, yesterday, 7daysAgo, 30daysAgo
- NEVER use formats like this_week_mon_today or this_week_monday - these are INVALID
- For this week queries, use 7daysAgo as start_date and today as end_date
- For last week queries, use 14daysAgo as start_date and 7daysAgo as end_date

ERROR HANDLING - This is CRITICAL:
If a tool call fails with a validation error:
1. Read the error message carefully to identify the issue
2. Fix the parameter with the correct value based on the error
3. Retry the tool call immediately with the corrected parameters
4. Do NOT give up after one failed attempt - you have multiple iterations to get it right

Common error examples and fixes:
- "Field required: dimensions" → Add dimensions=["date"] and retry
- "Invalid startDate: this_week_mon_today" → Use 7daysAgo instead and retry
- "Field campaign is not a valid dimension. Did you mean campaignId?" → Use sessionCampaignName instead and retry
- "Field source is not a valid dimension" → Use sessionSource instead and retry
- "'float' object cannot be interpreted as an integer" → Already handled automatically

The agent MUST retry with corrected parameters when receiving validation errors!
You have 15 iterations to get it right - USE THEM!

Remember: Use the tools available to you to fetch real data before providing insights."""),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])

            # Create agent with tools
            agent = create_tool_calling_agent(self.llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=15,  # Increased to allow retries
                handle_parsing_errors=True,
                return_intermediate_steps=True,  # Return steps for debugging
                max_execution_time=120,  # 2 minute timeout
                early_stopping_method="generate"  # Generate final answer even on errors
            )

            # Execute agent
            try:
                result = await agent_executor.ainvoke({"input": query})
            except Exception as e:
                # Check if this is a tool schema error
                error_str = str(e)
                if "GenerateContentRequest.tools" in error_str and "missing field" in error_str:
                    # Extract tool index from error message
                    import re
                    match = re.search(r'function_declarations\[(\d+)\]', error_str)
                    if match:
                        bad_tool_idx = int(match.group(1))
                        logger.warning(f"⚠️  [SingleAnalyticsAgent] Tool schema error at index {bad_tool_idx}: {error_str}")
                        logger.warning(f"⚠️  [SingleAnalyticsAgent] Problematic tool: {getattr(tools[bad_tool_idx], 'name', 'unknown') if bad_tool_idx < len(tools) else 'index out of range'}")

                        # Retry without the problematic tool
                        if bad_tool_idx < len(tools):
                            logger.info(f"🔄 [SingleAnalyticsAgent] Retrying without tool at index {bad_tool_idx}")
                            tools_filtered = tools[:bad_tool_idx] + tools[bad_tool_idx + 1:]
                            agent = create_tool_calling_agent(self.llm, tools_filtered, prompt)
                            agent_executor = AgentExecutor(
                                agent=agent,
                                tools=tools_filtered,
                                verbose=True,
                                max_iterations=15,
                                handle_parsing_errors=True,
                                return_intermediate_steps=True,
                                max_execution_time=120,
                                early_stopping_method="generate"
                            )
                            result = await agent_executor.ainvoke({"input": query})
                        else:
                            raise
                    else:
                        raise
                else:
                    raise

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
            traceback_str = traceback.format_exc()
            logger.error(f"   Traceback: {traceback_str}")

            # Create user-friendly error message
            error_type = type(e).__name__
            error_str = str(e)
            user_message = f"I encountered an error while analyzing your data: {error_str}"
            logger.debug(f"   Error type: {error_type}")
            # Provide context-specific error messages
            if "MCP" in error_str or "Connection closed" in error_str:
                user_message = "I'm having trouble connecting to the analytics services. Please try again in a moment."
            elif "http2" in error_str.lower() or "h2" in error_str.lower():
                user_message = "There's a configuration issue with one of the analytics services. The technical team has been notified."
            elif "validation error" in error_str.lower() and "Field required" in error_str:
                # Extract the missing field name if possible
                if "dimensions" in error_str:
                    user_message = "I attempted to fetch analytics data but encountered a technical issue with the required parameters. I need to include dimensions when querying the data. Let me try a different approach."
                else:
                    user_message = f"I encountered a parameter validation issue while trying to fetch the data: {error_str}"
            elif "ToolException" in error_type:
                user_message = f"I ran into an issue using the analytics tools: {error_str}"

            return {
                "status": "error",
                "result": user_message,
                "message": f"Single analytics agent execution failed: {str(e)}",
                "error_type": error_type,
                "agent": "single_analytics_agent",
                "platforms": platforms,
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
            ga_credentials = ga_credentials or {}
            property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

            gads_credentials = task_details.get("google_ads_credentials", {})
            gads_credentials = gads_credentials or {}
            customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")

            if property_id != "NOT_PROVIDED":
                context_parts.append(f"Google Analytics Property ID: {property_id}")
            if customer_id != "NOT_PROVIDED":
                context_parts.append(f"Google Ads Customer ID: {customer_id}")

        if "facebook" in platforms:
            fb_credentials = task_details.get("meta_ads_credentials", {})
            if not fb_credentials:
                fb_credentials = {}
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
        # Check if there's already a running event loop
        try:
            asyncio.get_running_loop()
            # We're in an async context - run in a new thread to avoid conflicts
            # This is necessary because:
            # 1. asyncio.run() cannot be called from a running loop
            # 2. nest_asyncio doesn't support uvloop (which FastAPI/uvicorn uses)
            # 3. We need a completely separate event loop for MCP operations
            import concurrent.futures

            def run_in_new_loop():
                # Create a completely fresh asyncio event loop for this thread
                # This prevents gRPC from trying to use the parent uvloop
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    # Create a fresh LLM instance in this thread to avoid gRPC issues
                    # The original LLM has gRPC connections bound to the parent uvloop
                    try:
                        fresh_llm = self.llm_class(**self.llm_kwargs)
                    except Exception as e:
                        logger.warning(f"⚠️  Could not recreate LLM, using original: {e}")
                        fresh_llm = self.llm

                    # Temporarily replace self.llm for this execution
                    original_llm = self.llm
                    self.llm = fresh_llm
                    try:
                        return new_loop.run_until_complete(self._execute_async(task))
                    finally:
                        self.llm = original_llm
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_new_loop)
                return future.result()
        except RuntimeError as e:
            # No running event loop - create a new one
            return {
                "status": "error",
                "result": "There was internal error in the analytics agent execution.",
                "message": f"Single analytics agent execution failed: {str(e)}",
                "error_type": type(e).__name__,
                "agent": "single_analytics_agent",
                "platforms": [],
                "task_received": task
            }
            # return asyncio.run(self._execute_async(task))


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
