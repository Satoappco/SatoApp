"""Node implementations for the chatbot routing workflow."""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessage
import json
import logging

from .state import GraphState
from .agents import get_agent
from ..database.tools import DatabaseTool
from app.services.agent_service import AgentService
from app.config.langfuse_config import LangfuseConfig
from app.core.observability import trace_context
import os

logger = logging.getLogger(__name__)


class DummyContext:
    """Dummy context manager for when tracing is disabled."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class ChatbotNode:
    """Chatbot node that interacts with users and routes tasks to specialized agents."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.agent_service = AgentService()
        self.system_prompt = self._load_system_prompt()
        logger.debug(f"✅ [ChatbotNode] System prompt loaded: {self.system_prompt}")
        self.num_retries = 5
        # Check if LLM supports streaming
        self.supports_streaming = False #TODO: hasattr(self.llm, 'astream') or hasattr(self.llm, 'stream')
        logger.debug(f"🔄 [ChatbotNode] LLM streaming support: {self.supports_streaming}")

    def _load_system_prompt(self) -> str:
        """Load chatbot system prompt from database or use fallback."""
        try:
            # Try to get chatbot orchestrator config from database
            chatbot_config = self.agent_service.get_agent_config("chatbot_orchestrator") if os.getenv("USE_DATABASE_CONFIG", "false") == "true" else None

            if chatbot_config:
                logger.info("✅ Loaded chatbot orchestrator config from database")

                # Build system prompt from database config
                role = chatbot_config.get('role', 'Marketing Campaign Assistant Chatbot')
                goal = chatbot_config.get('goal', '')
                backstory = chatbot_config.get('backstory', '')
                task_template = chatbot_config.get('task', '')

                # Combine into a system prompt
                prompt_parts = []
                if role:
                    prompt_parts.append(f"{role}.")
                if backstory:
                    prompt_parts.append(f"\n{backstory}")
                if goal:
                    prompt_parts.append(f"\nYour goal: {goal}")
                if task_template:
                    prompt_parts.append(f"\nTask instructions:\n{task_template}")

                return "\n".join(prompt_parts)
            else:
                logger.warning("⚠️  Chatbot orchestrator config not found in database, using fallback")
                return self._get_fallback_prompt()

        except Exception as e:
            logger.error(f"❌ Failed to load chatbot config from database: {e}")
            return self._get_fallback_prompt()

    def _detect_user_language(self, messages: list) -> str:
        """Detect the user's language from their messages.

        Args:
            messages: List of conversation messages

        Returns:
            Language code ('hebrew', 'english', 'unknown')
        """
        # Get the last user message
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content.lower()

                # Simple heuristic: check for Hebrew characters
                hebrew_chars = sum(1 for char in content if '\u0590' <= char <= '\u05FF')
                total_chars = sum(1 for char in content if char.isalpha())

                if total_chars == 0:
                    continue

                # If more than 30% Hebrew characters, it's Hebrew
                if hebrew_chars / total_chars > 0.3:
                    return "hebrew"
                else:
                    return "english"

        # Default to hebrew as specified in system prompt
        return "hebrew"

    def _format_campaigner_info(self, info: Dict[str, Any]) -> str:
        """Format comprehensive campaigner information for system prompt.

        Args:
            info: Dictionary containing campaigner, agency, and customers data

        Returns:
            Formatted string with campaigner information
        """
        if not info:
            return "User information not available"

        lines = []

        # User Profile
        campaigner = info.get('campaigner', {})
        if campaigner:
            lines.append(f"- User Profile: {campaigner.get('name', 'N/A')} ({campaigner.get('email', 'N/A')}) - Role: {campaigner.get('role', 'N/A')}")

        # Agency
        agency = info.get('agency', {})
        if agency:
            lines.append(f"- Agency: {agency.get('name', 'N/A')}")

        # Total customers
        total_customers = info.get('total_customers', 0)
        lines.append(f"- Total Customers: {total_customers}")

        # Customers with campaign statistics
        customers = info.get('customers', [])
        if customers:
            lines.append(f"- First {len(customers)} Customers:")
            for customer in customers:
                customer_line = f"  • {customer.get('name', 'N/A')}: {customer.get('active_campaigns', 0)} active campaigns / {customer.get('total_campaigns', 0)} total campaigns"
                lines.append(customer_line)

        return "\n".join(lines) if lines else "No detailed information available"

    def _format_customer_info(self, customer_id: int, campaigner_id: int) -> str:
        """Format customer information for system prompt.

        Args:
            customer_id: Customer ID to get information for
            campaigner_id: Campaigner ID for authorization

        Returns:
            Formatted string with customer information
        """
        if not customer_id:
            return "No specific customer selected. Information shown is for all customers under your management."

        try:
            db_tool = DatabaseTool(campaigner_id)

            # Get customer details
            customer = db_tool.get_customer_info(customer_id)
            if not customer:
                return f"Customer ID {customer_id} not found or not accessible."

            # Get campaign summary
            campaigns = db_tool.get_campaigns_summary(customer_id)

            lines = [
                f"Selected Customer: {customer.get('full_name', 'N/A')} (ID: {customer_id})",
                f"- Status: {customer.get('status', 'N/A')}",
                f"- Contact: {customer.get('contact_email', 'N/A')}",
            ]

            # Add campaign statistics
            if campaigns:
                lines.append(f"- Active Campaigns: {campaigns.get('active_campaigns', 0)}")
                lines.append(f"- Total Campaigns: {campaigns.get('total_campaigns', 0)}")
                lines.append(f"- Paused Campaigns: {campaigns.get('paused_campaigns', 0)}")

                total_budget = campaigns.get('total_daily_budget', 0)
                if total_budget:
                    lines.append(f"- Total Daily Budget: {total_budget:.2f}")

            # Add website and social info if available
            if customer.get('website_url'):
                lines.append(f"- Website: {customer.get('website_url')}")
            if customer.get('facebook_page_url'):
                lines.append(f"- Facebook: {customer.get('facebook_page_url')}")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch customer info: {str(e)}")
            return f"Unable to retrieve information for customer ID {customer_id}"

    def _get_fallback_prompt(self) -> str:
        """Fallback system prompt if database config is not available."""
        return """
Your name is Sato. You are a helpful marketing campaign assistant.
Sato speaks English and Hebrew fluently and responds in the same language that he is addressed in.
You are a marketing analyst with an expertise in online marketing and data analysis.
When introducing yourself you may say "Hello! I'm Sato, your marketing assistant!"

If someone asks you "who is Shaul Shabtai?" you go into **debug mode**.  
In debug mode, the user can manually tell you which tasks to perform, provide data manually, and override certain commands to fix issues.

# Your role is to:
1. Have natural conversations with users (campaigners) in their own language to understand their intent.
2. Ask clarifying follow-up questions when needed.
3. Route tasks to the appropriate specialized agent when you have enough information.
4. Answer simple questions directly when possible.

# IMPORTANT: 
The user is already authenticated, and their campaigner ID is automatically provided to all agents.  
You do **not** need to ask for IDs — they are already available.  
You cannot answer questions related to other users or campaigners.

---

### Available agents you can route to:
- **basic_info_agent** - Answers questions using database access to the following tables ONLY:
  * customers: Customer/client information (name, status, contact info, etc.)
  * kpi_goals: Campaign goals and KPI targets (campaign names, budgets, objectives, target KPIs)
  * kpi_values: Actual KPI measurements (campaign performance, metrics)
  * digital_assets: Digital assets info (Facebook pages, Google Analytics properties, etc.)
  * connections: OAuth connections and API credentials (connection status, expiration)
  * rtm_table: Real-Time Marketing data
  * questions_table: Questions and answers data
  *(Note: this agent cannot access agencies or campaigners tables directly.)*

- **analytics_crew** — gathers and analyzes data from all advertising platforms (Facebook Ads, Google Marketing, etc.)
- **campaign_planning_crew** — plans new campaigns, creates digital assets, and deploys them to platforms

---

### Output Format Rules
You **must always** respond in **valid JSON only**, never plain text.  
No explanations, greetings, or extra text outside the JSON.  
All keys must be enclosed in double quotes.  
No trailing commas are allowed.  

#### When you know which agent to call:
```json
{{
    "agent": "basic_info_agent" | "analytics_crew" | "campaign_planning_crew",
    "task": {{
        "query": "the specific task description",
        "context": {{}}
    }},
    "ready": true,
    "complete" : true
}}
```

#### When you need clarification:
```json
{{
    "complete" : false,
    "ready": false,
    "message": "your clarifying question or response"
}}
```

#### When the request is simple and you can answer directly:
```json
if the user request is simple and can be answered without an agent, provide a direct answer in the message field:
{{
    "complete" : true,
    "ready": false,
    "message": "your direct answer to the user's question"
}}
```

# Ground rules:
    - Simple answers may only relate to campaign data, sales data, website traffic, or campaign details such as:
        - “What campaigns am I running?”
        - “What is my budget?”
        - “Which items are being campaigned?”
    - Be conversational, helpful, and ask follow-up questions naturally to understand user intent.
    - Always answer in JSON format only. no other text outside of JSON.
    - User is always talking about the selected customer/client unless they specify otherwise. no need to ask him about it.
    - Make sure to communicate in the same lanaguge as the user. Desfault language for the chat is Hebrew
    - always end a line with \n, always use ** on words that need to be bold.
    - Do not tell the user the following parameters:
        - campaigner_id.
        - agency_id.
        - customer_id.
        - digital_assets.
        - connections.
    - Analyze the customer's request carefully to determine their main intent.
    - If unclear or multi-part, ask clarifying questions one by one, prioritizing the most urgent issue.

# User information:
{campaigner_info}

# Selected customer/client information:
{customer_info}
"""


    def _process(self, state: GraphState) -> Dict[str, Any]:
        """Process the conversation and determine next steps.

        Args:
            state: Current graph state

        Returns:
            Updated state fields
        """
        logger.info(f"🤖 [ChatbotNode] Processing conversation. current_state: {state}")

        # Create Langfuse trace for this conversation turn
        langfuse = LangfuseConfig.get_client()
        if langfuse:
            # Get session_id from state or generate one
            session_id = state.get("session_id", "unknown")
            trace_context_manager = langfuse.start_as_current_span(
                name="chatbot_conversation_turn",
                input={
                    "session_id": session_id,
                    "user_id": str(state.get("campaigner").id),
                    "customer_id": state.get("customer_id"),
                }
            )
        else:
            trace_context_manager = DummyContext()

        ################## TODO: Move to init ##################
        # Get campaigner_id and customer_id from state
        campaigner = state.get("campaigner")
        customer_id = state.get("customer_id")
        logger.debug(f"👤 [ChatbotNode] Processing for campaigner: {campaigner} | Customer: {customer_id}")

        # Fetch and format comprehensive campaigner info
        campaigner_info_str = "User information not available"
        try:
            db_tool = DatabaseTool(campaigner.id)
            comprehensive_info = db_tool.get_comprehensive_campaigner_info()
            campaigner_info_str = self._format_campaigner_info(comprehensive_info)
        except Exception as e:
            logger.warning(f"⚠️  [ChatbotNode] Failed to fetch campaigner info: {str(e)}")

        # Fetch and format customer info
        customer_info_str = self._format_customer_info(customer_id, campaigner.id)
        logger.debug(f"🏪 [ChatbotNode] Customer info: {customer_info_str[:100]}...")

        # Format system prompt with campaigner and customer info
        self.formatted_system_prompt = self.system_prompt.format(
            campaigner_info=campaigner_info_str,
            customer_info=customer_info_str
        )
        ################## TODO: Move to init ##################

        messages = [
            SystemMessage(content=self.formatted_system_prompt),
            *state["messages"]
        ]
        logger.debug(f"📤 [ChatbotNode] Sending {len(messages)} messages to LLM")

        # Track LLM call with Langfuse - keep entire logic inside context manager
        with trace_context_manager:
            if langfuse:
                try:
                    llm_span = langfuse.start_span(
                        name="llm_routing_decision",
                        input={"messages": [{"role": m.type, "content": m.content[:200]} for m in messages[-3:]]}  # Last 3 messages
                    )
                except Exception as e:
                    logger.debug(f"⚠️  [ChatbotNode] Could not create LangFuse span: {e}")
                    llm_span = None

            response = self.llm.invoke(messages)
            logger.debug(f"📥 [ChatbotNode] Received response: {response.content[:100]}...")

            if langfuse and llm_span:
                try:
                    langfuse.update_current_span(output={"response": response.content[:500]})
                except Exception:
                    pass  # Span update is optional

            # Parse JSON and make routing decision INSIDE trace context
            try:
                # Try to parse JSON response
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                content = content.strip()
                if content.endswith(','):
                    content = content[:-1]
                parsed = json.loads(content)
                logger.debug(f"✅ [ChatbotNode] Parsed JSON response: ready={parsed.get('ready')}")

                if parsed.get("ready"):
                    # User intent is clear, route to agent
                    agent_name = parsed.get("agent")
                    task = parsed.get("task", {})
                    task["campaigner_id"] = campaigner.id

                    # Detect user's language from their messages
                    user_language = self._detect_user_language(state["messages"])

                    # Add customer_id and campaigner_id to task (hardcoded, not LLM-controlled)
                    task["customer_id"] = state.get("customer_id")
                    task["campaigner_id"] = campaigner.id

                    # Add trace to task for proper trace propagation to agents
                    task["trace"] = state.get("trace")

                    # Gather agency and campaigner context for agents
                    try:
                        db_tool = DatabaseTool(campaigner.id)
                        agency_info = db_tool.get_agency_info()
                        campaigner_info = db_tool.get_campaigner_info()

                        task["context"] = {
                            "agency": agency_info,
                            "campaigner": campaigner_info,
                            "language": user_language
                        }
                        logger.debug(f"📊 [ChatbotNode] Added context to task: agency={agency_info.get('name') if agency_info else None}, language={user_language}")
                    except Exception as e:
                        logger.warning(f"⚠️  [ChatbotNode] Failed to gather context: {str(e)}")
                        task["context"] = {"language": user_language}

                    logger.info(f"✅ [ChatbotNode] Intent ready! Routing to agent: {agent_name}")
                    logger.debug(f"📋 [ChatbotNode] Task: customer_id={task.get('customer_id')}, campaigner_id={task.get('campaigner_id')}")
                    logger.debug(f"📋 [ChatbotNode] Full task: {task}")

                    # Track routing decision (now inside trace context)
                    if langfuse:
                        try:
                            langfuse.update_current_trace(
                                output={
                                    "agent": agent_name,
                                    "query": task.get("query", "")[:200],
                                    "routed": True
                                },
                                metadata={
                                    "agent_name": agent_name,
                                    "language": user_language
                                }
                            )
                        except Exception:
                            pass  # Trace update is optional

                    return {
                        "next_agent": agent_name,
                        "agent_task": task,
                        "needs_clarification": False,
                        "conversation_complete": False
                    }
                else:
                    # Need more clarification
                    clarification_msg = parsed.get("message", response.content)
                    complete = parsed.get("complete", "false") == True
                    if not complete:
                        logger.debug(f"❓ [ChatbotNode] Need clarification: '{clarification_msg[:100]}...'")
                    else:
                        logger.debug(f"❓ [ChatbotNode] Answered the user: '{clarification_msg[:100]}...'")

                    # Track clarification/direct answer (now inside trace context)
                    if langfuse:
                        try:
                            langfuse.update_current_trace(
                                output={"message": clarification_msg[:500], "complete": complete},
                                metadata={"needs_clarification": True, "complete": complete}
                            )
                        except Exception:
                            pass  # Trace update is optional

                    return {
                        "messages": state["messages"] + [AIMessage(content=clarification_msg)],
                        "needs_clarification": True,
                        "conversation_complete": complete,
                        "next_agent": None
                    }

            except (json.JSONDecodeError, KeyError) as e:
                # JSON parsing failed - retry with explicit error message
                logger.warning(f"⚠️  [ChatbotNode] Failed to parse JSON: {str(e)}. content: {content}")

                # Track parse error (now inside trace context)
                if langfuse:
                    try:
                        langfuse.update_current_trace(
                            output={"raw_response": response.content[:500], "error": f"JSON parse error: {str(e)}", "retry": "will_retry"},
                            metadata={"level": "WARNING", "error_type": "json_parse_error", "attempt": 1}
                        )
                    except Exception:
                        pass  # Trace update is optional

                state["messages"].append(AIMessage(content=response.content))
                raise e
        

    def process(self, state: GraphState) -> Dict[str, Any]:
        for i in range(self.num_retries + 1):
            try:
                ret = self._process(state)
                if i > 0:
                    ret["messages"] = ret["messages"][:(-2*i-1)] + [ret["messages"][-1]]
                return ret
            except (json.JSONDecodeError, KeyError) as e:        
                # Retry: Send error message to LLM asking for properly formatted JSON
                response = state["messages"][-1]  # Last AIMessage
                error_message = SystemMessage(content=f"""
CRITICAL ERROR: Your previous response could not be parsed as valid JSON.

Error details: {str(e)}

Your response was:
{response.content[:500]}

You MUST follow the exact JSON format specified in the instructions.
- The response must be valid JSON
- Do not include any text before or after the JSON
- If you use markdown code blocks, use ```json
- Ensure all JSON keys are in double quotes
- Ensure proper comma placement

Please provide your response again in the EXACT format required, with valid JSON only.
""")

                state["messages"].append(error_message)
                logger.info(f"🔄 [ChatbotNode] Retry number ({i}) with JSON format error message")
                continue

        return {
            "messages": state["messages"] + [AIMessage(content=response.content)],
            "needs_clarification": True,
            "conversation_complete": False,
            "next_agent": None
        }

    async def stream_process(self, state: GraphState):
        """Stream process user input and yield response chunks as they arrive.

        Args:
            state: Current graph state

        Yields:
            Chunks of content and final state
        """
        campaigner = state.get("campaigner")
        if not campaigner:
            logger.error("❌ [ChatbotNode] No campaigner in state")
            yield {"state": {"error": "No campaigner found", "needs_clarification": False}}
            return

        logger.debug(f"📝 [ChatbotNode Stream] Processing for campaigner: {campaigner.full_name} (ID: {campaigner.id})")

        # Build messages for LLM
        formatted_system_prompt = self.system_prompt.replace("{campaigner_name}", campaigner.full_name)
        messages = [SystemMessage(content=formatted_system_prompt)] + state["messages"]

        if not self.supports_streaming:
            # Fallback to non-streaming if LLM doesn't support it
            logger.warning("⚠️  [ChatbotNode Stream] LLM doesn't support streaming, falling back to invoke")
            response = self.llm.invoke(messages)
            for char in response.content:
                yield {"content": char}
            # Parse and yield final state (simplified - no JSON retry in streaming mode)
            yield {"state": {
                "messages": state["messages"] + [AIMessage(content=response.content)],
                "needs_clarification": True,
                "conversation_complete": False,
                "next_agent": None
            }}
            return

        # TODO: Fix
        # # Stream from LLM
        # logger.debug("📡 [ChatbotNode Stream] Starting LLM stream...")
        # full_response = ""

        # try:
        #     # First, collect the full response (we need to parse JSON to know what to stream)
        #     async for chunk in self.llm.astream(messages):
        #         if hasattr(chunk, 'content') and chunk.content:
        #             content = chunk.content
        #             full_response += content

        #     logger.debug(f"✅ [ChatbotNode Stream] Received complete response: {len(full_response)} chars")

        #     # Try to parse JSON response
        #     try:
        #         content = full_response
        #         if "```json" in content:
        #             content = content.split("```json")[1].split("```")[0].strip()
        #         elif "```" in content:
        #             content = content.split("```")[1].split("```")[0].strip()

        #         parsed = json.loads(content)
        #         logger.debug(f"✅ [ChatbotNode Stream] Parsed JSON: ready={parsed.get('ready')}")

        #         if parsed.get("ready"):
        #             # User intent is clear, route to agent - NO MESSAGE TO STREAM
        #             agent_name = parsed.get("agent")
        #             task = parsed.get("task", {})
        #             task["campaigner_id"] = campaigner.id

        #             # Detect user's language
        #             user_language = self._detect_user_language(state["messages"])

        #             # Add customer_id and context
        #             task["customer_id"] = state.get("customer_id")
        #             task["campaigner_id"] = campaigner.id

        #             try:
        #                 db_tool = DatabaseTool(campaigner.id)
        #                 agency_info = db_tool.get_agency_info()
        #                 campaigner_info = db_tool.get_campaigner_info()
        #                 task["context"] = {
        #                     "agency": agency_info,
        #                     "campaigner": campaigner_info,
        #                     "language": user_language
        #                 }
        #             except Exception as e:
        #                 logger.warning(f"⚠️  [ChatbotNode Stream] Failed to gather context: {str(e)}")
        #                 task["context"] = {"language": user_language}

        #             logger.info(f"✅ [ChatbotNode Stream] Intent ready! Routing to: {agent_name} - NO streaming to user")

        #             # Don't add message to history yet - agent will add its response
        #             yield {"state": {
        #                 "messages": state["messages"],  # Don't add JSON response
        #                 "next_agent": agent_name,
        #                 "agent_task": task,
        #                 "needs_clarification": False,
        #                 "conversation_complete": False,
        #                 "ready_for_crew": True,
        #                 "platforms": task.get("platforms", []),
        #                 "metrics": task.get("metrics", []),
        #                 "date_range_start": task.get("date_range", {}).get("start"),
        #                 "date_range_end": task.get("date_range", {}).get("end"),
        #             }}
        #         else:
        #             # Clarification needed - extract and stream the MESSAGE only
        #             clarification_msg = parsed.get("message", "")
        #             if not clarification_msg:
        #                 logger.warning("⚠️  [ChatbotNode Stream] No message in JSON, using full response")
        #                 clarification_msg = full_response

        #             complete = parsed.get("complete", "false") == True
        #             logger.debug(f"❓ [ChatbotNode Stream] Clarification message: '{clarification_msg[:100]}...'")

        #             # Stream the clarification message character by character
        #             for char in clarification_msg:
        #                 yield {"content": char}

        #             # Then yield final state
        #             yield {"state": {
        #                 "messages": state["messages"] + [AIMessage(content=clarification_msg)],
        #                 "needs_clarification": True,
        #                 "conversation_complete": complete,
        #                 "clarification_question": clarification_msg,
        #                 "next_agent": None
        #             }}

        #     except (json.JSONDecodeError, KeyError) as e:
        #         # Failed to parse JSON - treat as clarification and stream the full response
        #         logger.warning(f"⚠️  [ChatbotNode Stream] Failed to parse JSON: {str(e)}, treating as text")

        #         # Stream the full response character by character
        #         for char in full_response:
        #             yield {"content": char}

        #         # Then yield final state
        #         yield {"state": {
        #             "messages": state["messages"] + [AIMessage(content=full_response)],
        #             "needs_clarification": True,
        #             "conversation_complete": False,
        #             "clarification_question": full_response,
        #             "next_agent": None
        #         }}

        # except Exception as e:
        #     logger.error(f"❌ [ChatbotNode Stream] Error during streaming: {str(e)}")
        #     yield {"state": {
        #         "error": str(e),
        #         "needs_clarification": False
        #     }}


class AgentExecutorNode:
    """Node that executes the appropriate specialized agent."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def execute(self, state: GraphState) -> Dict[str, Any]:
        """Execute the selected agent with the given task.

        Args:
            state: Current graph state

        Returns:
            Updated state fields with agent results
        """
        agent_name = state.get("next_agent")
        task = state.get("agent_task", {})
        trace = state.get("trace")  # Get session trace from state

        logger.info(f"⚙️  [AgentExecutor] Executing agent: {agent_name}")

        if not agent_name:
            logger.error("❌ [AgentExecutor] No agent specified")
            return {
                "error": "No agent specified for execution",
                "conversation_complete": True
            }

        try:
            # Get LangFuse client for creating generation within trace
            langfuse = LangfuseConfig.get_client()

            # Create a generation span within the session trace
            generation = None
            if langfuse and trace:
                generation = trace.generation(
                    name=f"agent_execution_{agent_name}",
                    input=task,
                    metadata={
                        "agent_name": agent_name,
                        "task_type": task.get("type", "unknown")
                    }
                )

            # Get and execute the agent
            logger.debug(f"🔍 [AgentExecutor] Getting agent instance: {agent_name}")
            agent = get_agent(agent_name, self.llm)

            # Pass the trace/generation to the agent if it supports it
            if hasattr(agent, 'set_trace'):
                agent.set_trace(trace)

            logger.info(f"🚀 [AgentExecutor] Executing {agent_name} with task...")
            logger.debug(f"📋 [AgentExecutor] Task details: {task}")
            result = agent.execute(task)
            logger.info(f"✅ [AgentExecutor] Agent {agent_name} completed. Status: {result.get('status')}")

            # Format response message
            response_message = self._format_agent_response(result)

            # Safe preview of response (handle both string and CrewOutput)
            try:
                preview = str(response_message)[:100] if response_message else "No response"
                logger.debug(f"💬 [AgentExecutor] Response: '{preview}...'")
            except Exception:
                logger.debug(f"💬 [AgentExecutor] Response: (non-string type: {type(response_message)})")

            # Update generation with output
            if generation:
                generation.update(
                    output={"response": str(response_message)[:1000], "status": result.get("status")},
                    metadata={"agent_completed": True}
                )

            return {
                "agent_result": result,
                "messages": state["messages"] + [AIMessage(content=str(response_message))],
                "conversation_complete": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ [AgentExecutor] Agent execution failed: {str(e)}", exc_info=True)

            # Update generation with error
            if generation:
                generation.update(
                    output={"error": str(e)},
                    level="ERROR",
                    status_message=str(e)
                )

            # Create user-friendly error message
            error_message = f"I encountered an error while processing your request: {str(e)}"

            return {
                "error": str(e),
                "messages": state["messages"] + [AIMessage(content=error_message)],
                "conversation_complete": True
            }

    def _format_agent_response(self, result: Dict[str, Any]) -> str:
        """Format the agent result as a user-friendly message.

        Args:
            result: Agent execution result

        Returns:
            Formatted message string
        """
        status = result.get("status")
        agent = result.get("agent", "Unknown agent")

        if status == "completed":
            crew_result = result.get("result", "Task completed successfully.")

            # Handle CrewOutput object from CrewAI
            # CrewOutput has multiple attributes: raw, pydantic, json_dict, tasks_output, token_usage
            if hasattr(crew_result, "raw"):
                # Use the raw string output from CrewAI
                return str(crew_result.raw)
            elif hasattr(crew_result, "__str__"):
                # Fallback to string representation
                return str(crew_result)
            else:
                # Already a string
                return crew_result

        elif status == "placeholder":
            message = result.get("message", "")
            return f"{message}\n\nThis feature is coming soon!"
        else:
            return f"Task processed by {agent}."


class ErrorHandlerNode:
    """Node for handling errors in the workflow."""

    def handle(self, state: GraphState) -> Dict[str, Any]:
        """Handle errors and provide user feedback.

        Args:
            state: Current graph state

        Returns:
            Updated state fields
        """
        error_msg = state.get("error", "An unknown error occurred")

        return {
            "messages": state["messages"] + [
                AIMessage(content=f"I encountered an issue: {error_msg}. Please try again.")
            ],
            "error": None,
            "conversation_complete": True
        }



#             logger.info("🔄 [ChatbotNode] Retrying with JSON format error message")

#             try:
#                 # Second attempt with error context
#                 retry_response = self.llm.invoke(retry_messages)
#                 logger.debug(f"📥 [ChatbotNode] Retry response: {retry_response.content[:100]}...")

#                 # Try to parse retry response
#                 retry_content = retry_response.content
#                 if "```json" in retry_content:
#                     retry_content = retry_content.split("```json")[1].split("```")[0].strip()
#                 elif "```" in retry_content:
#                     retry_content = retry_content.split("```")[1].split("```")[0].strip()

#                 parsed = json.loads(retry_content)
#                 logger.info(f"✅ [ChatbotNode] Successfully parsed JSON on retry: ready={parsed.get('ready')}")

#                 # Track successful retry
#                 if langfuse:
#                     try:
#                         langfuse.update_current_trace(
#                             output={"retry_success": True, "parsed": parsed.get('ready')},
#                             metadata={"level": "INFO", "attempt": 2}
#                         )
#                     except Exception:
#                         pass

#                 # Process the parsed response (same logic as above)
#                 if parsed.get("ready"):
#                     agent_name = parsed.get("agent")
#                     task = parsed.get("task", {})
#                     task["campaigner_id"] = campaigner.id
#                     user_language = self._detect_user_language(state["messages"])
#                     task["customer_id"] = state.get("customer_id")
#                     task["campaigner_id"] = campaigner.id

#                     try:
#                         db_tool = DatabaseTool(campaigner.id)
#                         agency_info = db_tool.get_agency_info()
#                         campaigner_info = db_tool.get_campaigner_info()
#                         task["context"] = {
#                             "agency": agency_info,
#                             "campaigner": campaigner_info,
#                             "language": user_language
#                         }
#                     except Exception as e:
#                         logger.warning(f"⚠️  [ChatbotNode] Failed to gather context on retry: {str(e)}")
#                         task["context"] = {"language": user_language}

#                     logger.info(f"✅ [ChatbotNode] Intent ready on retry! Routing to: {agent_name}")
#                     return {
#                         "next_agent": agent_name,
#                         "agent_task": task,
#                         "needs_clarification": False,
#                         "conversation_complete": False
#                     }
#                 else:
#                     clarification_msg = parsed.get("message", retry_response.content)
#                     complete = parsed.get("complete", "false") == True
#                     logger.debug(f"❓ [ChatbotNode] Clarification on retry: '{clarification_msg[:100]}...'")
#                     return {
#                         "messages": state["messages"] + [AIMessage(content=clarification_msg)],
#                         "needs_clarification": True,
#                         "conversation_complete": complete,
#                         "next_agent": None
#                     }

#             except (json.JSONDecodeError, KeyError) as retry_error:
#                 # Second attempt also failed
#                 logger.error(f"❌ [ChatbotNode] JSON parsing failed on retry: {str(retry_error)}. Giving up and treating as text.")

#                 # Track retry failure
#                 if langfuse:
#                     try:
#                         langfuse.update_current_trace(
#                             output={"retry_failed": True, "error": str(retry_error), "raw_response": retry_response.content[:500]},
#                             metadata={"level": "ERROR", "error_type": "json_parse_error_retry_failed", "attempt": 2}
#                         )
#                     except Exception:
#                         pass

#                 # Fall back to treating as clarification message
#                 return {
#                     "messages": state["messages"] + [AIMessage(content=retry_response.content)],
#                     "needs_clarification": True,
#                     "conversation_complete": False,
#                     "next_agent": None
#                 }
#             except Exception as retry_error:
#                 # Unexpected error on retry
#                 logger.error(f"❌ [ChatbotNode] Unexpected error on retry: {str(retry_error)}")

#                 # Fall back to original response
#                 return {
#                     "messages": state["messages"] + [AIMessage(content=response.content)],
#                     "needs_clarification": True,
#                     "conversation_complete": False,
#                     "next_agent": None
#                 }
