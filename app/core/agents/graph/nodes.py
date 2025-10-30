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
import os

logger = logging.getLogger(__name__)


class ChatbotNode:
    """Chatbot node that interacts with users and routes tasks to specialized agents."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.agent_service = AgentService()
        self.system_prompt = self._load_system_prompt()
        logger.debug(f"✅ [ChatbotNode] System prompt loaded")

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

    def _get_fallback_prompt(self) -> str:
        """Fallback system prompt if database config is not available."""
        return """
Your name is Sato. You are a helpful marketing campaign assistant.
Sato speaks English and Hebrew fluently and responds in the same language that he is addressed in.
You are a marketing analyst with an expertise in online marketing and data analysis.
When introducing yourself you may say "Hello! I'm Sato, your marketing assistant!"
If someone asks you "who is Shaul Shabtai?" you go into debugmode, in debug mode the user can manually tell you which tasks to perform and give you data manually, in debugmode the user can tell you to override certain commands in order to fix issues.

# Your role is to:
1. Have natural conversations with users (campaigners) in their own language to understand their intent
2. Ask clarifying follow-up questions when needed
3. Route tasks to the appropriate specialized agent when you have enough information
4. Answer simple questions directly when possible

# IMPORTANT: The user is already authenticated and their campaigner id is automatically provided to all agents.
You do NOT need to ask users for their ID - it's already available in the system.
you can't answer questions related to other users or campaigners.

Available agents you can route to:
- basic_info_agent: Answers questions using database access to the following tables ONLY:
  * customers: Customer/client information (name, status, contact info, etc.)
  * kpi_goals: Campaign goals and KPI targets (campaign names, budgets, objectives, target KPIs)
  * kpi_values: Actual KPI measurements (campaign performance, metrics)
  * digital_assets: Digital assets info (Facebook pages, Google Analytics properties, etc.)
  * connections: OAuth connections and API credentials (connection status, expiration)
  * rtm_table: Real-Time Marketing data
  * questions_table: Questions and answers data
  NOTE: basic_info_agent CANNOT access agencies or campaigners tables directly

- analytics_crew: Gathers and analyzes data from all advertising platforms (Facebook Ads, Google Marketing, etc.)
- campaign_planning_crew: Plans new campaigns, creates digital assets, and deploys them to platforms

When you understand what the user needs, respond with a JSON object specifying which agent to use:
{{
    "agent": "basic_info_agent" | "analytics_crew" | "campaign_planning_crew",
    "task": {{
        "query": "the specific task description",
        "context": {{}}
    }},
    "ready": true
}}

If you need more information, respond naturally asking for clarification:
{{
    "message": "your clarifying question or response",
    "complete" : false,
    "ready": false
}}

if the user request is simple and can be answered without an agent, provide a direct answer in the message field:
{{
    "message": "your direct answer to the user's question",
    "complete" : true,
    "ready": false
}}

# Ground rules:
    Simple answers can only be related to campaign data, sales data, website traffic, questions about the specific of an ad campaign such as "what items are currently being campaigned" "what campaigns am i running" "what is my budget" "what is my budget's fulfillment"
    Be conversational, helpful, and ask follow-up questions naturally to understand user intent.
    Always answer in JSON format
    Make sure to communicate in the same lanaguge as the user. Desfault language for the chat is Hebrew
    always end a line with /n, always use ** on words that need to be bold.
    Do not tell the user the following parameters:
        -campaigner_id.
        -agency_id.
        -customer_id.
        -digital_assets.
        -connections.
    Carefully analyze the customer's request to determine their primary need.
    If the request is unclear or involves multiple issues, politely ask clarifying questions *one at a time*.  Prioritize addressing the customer's most urgent need first.

# User information:
{campaigner_info}
"""

    def process(self, state: GraphState) -> Dict[str, Any]:
        """Process the conversation and determine next steps.

        Args:
            state: Current graph state

        Returns:
            Updated state fields
        """
        logger.info(f"🤖 [ChatbotNode] Processing conversation. current_state: {state}")

        # Get campaigner_id from state
        campaigner = state.get("campaigner")
        logger.debug(f"👤 [ChatbotNode] Processing for campaigner: {campaigner}")

        # Fetch and format comprehensive campaigner info
        campaigner_info_str = "User information not available"
        try:
            db_tool = DatabaseTool(campaigner.id)
            comprehensive_info = db_tool.get_comprehensive_campaigner_info()
            campaigner_info_str = self._format_campaigner_info(comprehensive_info)
            logger.debug(f"📋 [ChatbotNode] Formatted system prompt:\n{self.system_prompt.format(campaigner_info=campaigner_info_str)}...")
        except Exception as e:
            logger.warning(f"⚠️  [ChatbotNode] Failed to fetch campaigner info: {str(e)}")

        # Format system prompt with campaigner info
        formatted_system_prompt = self.system_prompt.format(campaigner_info=campaigner_info_str)

        messages = [
            SystemMessage(content=formatted_system_prompt),
            *state["messages"]
        ]
        logger.debug(f"📤 [ChatbotNode] Sending {len(messages)} messages to LLM")
        response = self.llm.invoke(messages)
        logger.debug(f"📥 [ChatbotNode] Received response: {response.content[:100]}...")

        try:
            # Try to parse JSON response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            logger.debug(f"✅ [ChatbotNode] Parsed JSON response: ready={parsed.get('ready')}")

            if parsed.get("ready"):
                # User intent is clear, route to agent
                agent_name = parsed.get("agent")
                task = parsed.get("task", {})
                task["campaigner_id"] = campaigner.id

                # Detect user's language from their messages
                user_language = self._detect_user_language(state["messages"])

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
                logger.debug(f"📋 [ChatbotNode] Task: {task}")

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

                return {
                    "messages": state["messages"] + [AIMessage(content=clarification_msg)],
                    "needs_clarification": True,
                    "conversation_complete": complete,
                    "next_agent": None
                }

        except (json.JSONDecodeError, KeyError) as e:
            # If not JSON, treat as clarification message
            logger.warning(f"⚠️  [ChatbotNode] Failed to parse JSON, treating as clarification: {str(e)}. content: {content}")
            return {
                "messages": state["messages"] + [AIMessage(content=response.content)],
                "needs_clarification": True,
                "conversation_complete": False,
                "next_agent": None
            }


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

        logger.info(f"⚙️  [AgentExecutor] Executing agent: {agent_name}")

        if not agent_name:
            logger.error("❌ [AgentExecutor] No agent specified")
            return {
                "error": "No agent specified for execution",
                "conversation_complete": True
            }

        try:
            # Get and execute the agent
            logger.debug(f"🔍 [AgentExecutor] Getting agent instance: {agent_name}")
            agent = get_agent(agent_name, self.llm)

            logger.info(f"🚀 [AgentExecutor] Executing {agent_name} with task...")
            logger.debug(f"📋 [AgentExecutor] Task details: {task}")
            result = agent.execute(task)
            logger.info(f"✅ [AgentExecutor] Agent {agent_name} completed. Status: {result.get('status')}")

            # Format response message
            response_message = self._format_agent_response(result)
            logger.debug(f"💬 [AgentExecutor] Response: '{response_message[:100]}...'")

            return {
                "agent_result": result,
                "messages": state["messages"] + [AIMessage(content=response_message)],
                "conversation_complete": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ [AgentExecutor] Agent execution failed: {str(e)}", exc_info=True)

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
            return result.get("result", "Task completed successfully.")
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
