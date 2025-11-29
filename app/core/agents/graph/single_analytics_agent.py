
from typing import Dict, Any, List, Optional
import logging
import asyncio
from langchain_core.language_models import BaseChatModel
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient as MCPClient
from ..customer_credentials import CustomerCredentialManager
from ..mcp_clients.mcp_registry import MCPSelector
from app.services.chat_trace_service import ChatTraceService
import time

logger = logging.getLogger(__name__)

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

        self.mcp_client: Optional[MCPClient] = None
        self.credential_manager = CustomerCredentialManager()

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

    async def _initialize_mcp_clients(self, task_details: Dict[str, Any], thread_id: Optional[str] = None, level: int = 1):
        """Initialize and connect MultiServerMCPClient using MCP Client Manager.

        Args:
            task_details: Task details containing platforms and credentials
            thread_id: Optional thread ID for logging
            level: Hierarchy level for logging (default: 1)
        """
        from app.core.agents.mcp_clients.mcp_client_manager import MCPClientManager

        platforms = task_details.get("platforms", [])
        ga_credentials = task_details.get("google_analytics_credentials")
        gads_credentials = task_details.get("google_ads_credentials")
        meta_credentials = task_details.get("meta_ads_credentials")
        campaigner_id = task_details.get("campaigner_id")

        if not campaigner_id:
            logger.warning("⚠️  [SingleAnalyticsAgent] No campaigner_id provided, skipping MCP initialization")
            return

        # 🆕 Use centralized MCP Client Manager
        # This automatically handles: token refresh → initialization → validation
        self.mcp_manager = MCPClientManager(
            campaigner_id=campaigner_id,
            platforms=platforms,
            credentials={
                'google_analytics': ga_credentials,
                'google_ads': gads_credentials,
                'facebook': meta_credentials
            }
        )

        # Initialize (includes token refresh and validation)
        success = await self.mcp_manager.initialize()

        if success:
            self.mcp_client = self.mcp_manager.get_clients()
            self.mcp_validation_results = self.mcp_manager.get_validation_results()

            logger.info(f"✅ [SingleAnalyticsAgent] MCP clients initialized successfully")

            # Store MCP details for later logging
            self._mcp_servers_info = {
                "platforms": platforms,
                "thread_id": thread_id,
                "level": level,
                "validation_results": self.mcp_validation_results
            }
        else:
            logger.error(f"❌ [SingleAnalyticsAgent] Failed to initialize MCP clients")
            self.mcp_client = None

    async def _disconnect_mcp_clients(self):
        """Disconnect MultiServerMCPClient."""
        if hasattr(self, 'mcp_manager') and self.mcp_manager:
            try:
                await self.mcp_manager.cleanup()
                logger.info("✅ [SingleAnalyticsAgent] MCP client cleanup complete")
            except Exception as e:
                logger.error(f"❌ [SingleAnalyticsAgent] Error during MCP cleanup: {e}")
            finally:
                self.mcp_client = None
                self.mcp_manager = None
        elif self.mcp_client:
            # Fallback for old initialization method
            try:
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

        # Add calculator tool to the tools list
        from app.core.agents.tools.calculator_tool import CalculatorTool
        # Note: thread_id will be set via the tool's pydantic fields if needed
        calculator = CalculatorTool()
        tools.append(calculator)
        logger.info(f"🧮 [SingleAnalyticsAgent] Added calculator tool (total tools: {len(tools)})")

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
        thread_id = task.get("thread_id")  # Extract thread_id for tracing
        level = task.get("level", 1)  # Extract level for hierarchy tracking

        # Initialize trace service if thread_id is available
        trace_service = ChatTraceService() if thread_id else None

        if customer_id:
            credentials = self.credential_manager.fetch_all_credentials(customer_id, campaigner_id)
        else:
            logger.warning("⚠️  [SingleAnalyticsAgent] No customer_id provided")
            credentials = {
                "platforms": task.get("platforms", []),
                "google_analytics": None,
                "google_ads": None,
                "meta_ads": None
            }

        # Build task details
        task_details = {
            "query": query,
            "context": context,
            "campaigner_id": campaigner_id,
            "customer_id": customer_id,
            "platforms": credentials["platforms"],
            "metrics": task.get("metrics", ["impressions", "clicks", "conversions", "spend"]),
            # "date_range": task.get("date_range", {"start": "last_30_days", "end": "today"}),
            "google_analytics_credentials": credentials["google_analytics"],
            "google_ads_credentials": credentials["google_ads"],
            "meta_ads_credentials": credentials["meta_ads"],
        }

        # Initialize and connect MCP clients
        await self._initialize_mcp_clients(task_details, thread_id=thread_id, level=level)

        # Check if MCP client was initialized successfully
        if not self.mcp_client:
            error_msg = "Failed to initialize MCP servers. Please check server configurations and credentials."
            logger.error(f"❌ [SingleAnalyticsAgent] {error_msg}")
            return {
                "status": "error",
                "result": f"I encountered a configuration error: {error_msg}",
                "message": error_msg,
                "agent": "single_analytics_agent",
                "platforms": credentials["platforms"],
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
                    "platforms": credentials["platforms"],
                    "task_received": task
                }

            logger.info(f"🚀 [SingleAnalyticsAgent] Executing with {len(tools)} tools from platforms: {credentials['platforms']}")

            # Log MCP initialization with tools list and validation results
            if trace_service and thread_id:
                mcp_info = getattr(self, '_mcp_servers_info', None)

                # Build tools list content
                tools_list = "\n".join([f"  - {getattr(tool, 'name', f'tool_{i}')}" for i, tool in enumerate(tools)])
                content = f"**Loaded {len(tools)} Tools:**\n{tools_list}"

                # Add validation results if available
                if mcp_info and 'validation_results' in mcp_info:
                    validation_results = mcp_info['validation_results']
                    if validation_results:
                        content += "\n\n**MCP Validation Results:**\n"
                        for result in validation_results:
                            status_emoji = "✅" if result.status.value == "success" else "❌"
                            content += f"{status_emoji} {result.server}: {result.status.value}"
                            if result.message:
                                content += f" - {result.message}"
                            if result.duration_ms:
                                content += f" ({result.duration_ms}ms)"
                            content += "\n"

                metadata = {
                    "num_tools": len(tools),
                    "tool_names": [getattr(tool, 'name', f'tool_{i}') for i, tool in enumerate(tools)]
                }

                if mcp_info:
                    metadata["platforms"] = mcp_info.get('platforms', [])

                    # Add validation results to metadata
                    if 'validation_results' in mcp_info:
                        metadata["validation_results"] = [
                            {
                                "server": r.server,
                                "status": r.status.value,
                                "message": r.message,
                                "duration_ms": r.duration_ms
                            }
                            for r in mcp_info['validation_results']
                        ]

                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="mcp_initialization",
                    content=content,
                    agent_name="single_analytics_agent",
                    metadata=metadata,
                    level=level
                )

            # Build context for the agent
            context_str = self._build_context_string(task_details)

            # Get current date and time
            from datetime import datetime
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Build system prompt
            system_prompt = f"""You are an expert marketing analytics agent with direct access to multiple advertising platforms.

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
**Google Analytics API** accepts ONLY these date formats:
- YYYY-MM-DD format: 2024-01-15
- Relative formats: today, yesterday, 7daysAgo, 30daysAgo
- NEVER use formats like this_week_mon_today or this_week_monday - these are INVALID
- For this week queries, use 7daysAgo as start_date and today as end_date
- For last week queries, use 14daysAgo as start_date and 7daysAgo as end_date

**Google Ads API (GAQL queries)** accepts ONLY:
- YYYY-MM-DD format: '2024-01-15' (must be in quotes)
- DO NOT use relative formats like '30daysAgo', 'yesterday', 'today'
- For date ranges, calculate the actual dates from current date
- Example: For last 30 days, if today is 2024-11-19, use dates.date BETWEEN '2024-10-20' AND '2024-11-19'
- ALWAYS calculate actual YYYY-MM-DD dates before making Google Ads GAQL queries

ERROR HANDLING - THIS IS CRITICAL FOR SUCCESS:
When a tool call fails with an error, you MUST analyze the error and retry with corrected parameters.
You have up to 15 iterations - use them to debug and fix issues!

Common error patterns and how to fix them:
1. Google Ads date format errors:
   - Error: "BETWEEN operator must have exactly two values...in 'YYYY-MM-DD' format"
   - Fix: Calculate actual dates (e.g., convert "30daysAgo" to actual date like '2024-10-20')
   - Example correction: segments.date BETWEEN '2024-10-20' AND '2024-11-19'

2. Google Analytics dimension errors:
   - Error: "Field campaign is not valid. Did you mean campaignId?"
   - Fix: Use sessionCampaignName instead of campaign
   - Error: "Field source is not valid"
   - Fix: Use sessionSource instead of source

3. Missing required parameters:
   - Error: "Field required: dimensions"
   - Fix: Add dimensions=["date"] to your run_report call

4. Date format errors:
   - Error: "Invalid startDate: this_week_mon_today"
   - Fix: Use 7daysAgo or calculate actual YYYY-MM-DD date

IMPORTANT: After ANY tool error, read the error message carefully, understand what went wrong,
fix the specific issue, and retry immediately. Don't give up after the first error!

Remember: Use the tools available to you to fetch real data before providing insights."""

            # Log agent initialization with LLM and system prompt
            if trace_service and thread_id:
                # Get LLM model name
                llm_model_name = "unknown"
                if hasattr(self.llm, 'model_name'):
                    llm_model_name = self.llm.model_name
                elif hasattr(self.llm, 'model'):
                    llm_model_name = self.llm.model

                trace_service.add_chatbot_initialization(
                    thread_id=thread_id,
                    chatbot_name="single_analytics_agent",
                    llm_model=llm_model_name,
                    system_prompt=system_prompt,
                    metadata={
                        "platforms": credentials["platforms"],
                        "num_tools": len(tools),
                        "customer_id": customer_id,
                        "language": language,
                        "query": query
                    },
                    level=level
                )

            # Log agent start with key parameters
            if trace_service and thread_id:
                params_summary = f"""**Query:** {query}

**Platforms:** {', '.join(credentials['platforms'])}

**Customer ID:** {customer_id}

**Language:** {language}

**Available Tools:** {len(tools)} MCP tools loaded"""

                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="agent_start",
                    content=f"Starting Analytics Agent execution\n\n{params_summary}",
                    agent_name="single_analytics_agent",
                    metadata={
                        "platforms": credentials["platforms"],
                        "num_tools": len(tools),
                        "query": query,
                        "customer_id": customer_id,
                        "language": language,
                        "system_prompt": system_prompt  # Full prompt in metadata for reference
                    },
                    level=level
                )

            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])

            # Create agent with tools
            agent = create_tool_calling_agent(self.llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=15,  # Allow up to 15 tool calls (includes retries)
                handle_parsing_errors=True,
                handle_tool_error=True,  # Pass tool errors back to agent as observations for retry
                return_intermediate_steps=True,  # Return steps for debugging
                max_execution_time=180,  # 3 minute timeout (increased for retries)
                early_stopping_method="generate"  # Generate final answer
            )

            # Execute agent
            try:
                result = await agent_executor.ainvoke({"input": query})

                # Log tool calls from intermediate_steps
                if trace_service and thread_id and "intermediate_steps" in result:
                    for i, (action, observation) in enumerate(result["intermediate_steps"]):
                        tool_start_time = time.time()

                        # Extract tool information
                        tool_name = action.tool if hasattr(action, 'tool') else str(action)
                        tool_input = action.tool_input if hasattr(action, 'tool_input') else {}

                        # Check if observation contains an error
                        observation_str = str(observation)
                        is_error = isinstance(observation, Exception) or observation_str.startswith("Error:")

                        # Log tool usage
                        trace_service.add_tool_usage(
                            thread_id=thread_id,
                            tool_name=tool_name,
                            tool_input=str(tool_input),
                            tool_output=observation_str[:5000],  # Limit output size
                            success=not is_error,
                            error=observation_str if is_error else None,
                            latency_ms=int((time.time() - tool_start_time) * 1000),
                            metadata={
                                "step_index": i,
                                "action_type": type(action).__name__,
                                "retry_attempt": i  # Track which attempt this was
                            },
                            level=level
                        )

            except Exception as e:
                # Log any tool calls that were made before the exception
                if trace_service and thread_id:
                    # Try to extract intermediate_steps from the exception context
                    import sys
                    exc_info = sys.exc_info()

                    # Log the exception with full traceback
                    import traceback
                    traceback_str = traceback.format_exc()

                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="agent_exception",
                        content=f"Exception during agent execution: {str(e)}",
                        agent_name="single_analytics_agent",
                        metadata={
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "traceback": traceback_str
                        },
                        level=level
                    )

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
                                handle_tool_error=True,  # Pass tool errors back to agent as observations for retry
                                return_intermediate_steps=True,
                                max_execution_time=180,
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
                "platforms": credentials["platforms"],
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

            # Log error with traceback to traces
            if trace_service and thread_id:
                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="agent_error",
                    content=f"Agent execution failed: {error_str}",
                    agent_name="single_analytics_agent",
                    metadata={
                        "error_type": error_type,
                        "error_message": error_str,
                        "traceback": traceback_str
                    },
                    level=level
                )

            return {
                "status": "error",
                "result": user_message,
                "message": f"Single analytics agent execution failed: {str(e)}",
                "error_type": error_type,
                "traceback": traceback_str,  # Include traceback in response
                "agent": "single_analytics_agent",
                "platforms": credentials["platforms"],
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
            ga_credentials = task_details.get("google_analytics_credentials", {}) or {}
            property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

            gads_credentials = task_details.get("google_ads_credentials", {}) or {}
            customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")

            if property_id != "NOT_PROVIDED":
                context_parts.append(f"Google Analytics Property ID: {property_id}")
            if customer_id != "NOT_PROVIDED":
                context_parts.append(f"Google Ads Customer ID: {customer_id}")

        if "facebook" in platforms:
            fb_credentials = task_details.get("meta_ads_credentials", {}) or {}
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