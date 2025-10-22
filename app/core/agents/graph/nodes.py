"""Node implementations for the chatbot routing workflow."""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
import json
import logging

from .state import GraphState
from .agents import get_agent
from ..database.tools import DatabaseTool

logger = logging.getLogger(__name__)


class ChatbotNode:
    """Chatbot node that interacts with users and routes tasks to specialized agents."""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = """You are a helpful marketing campaign assistant chatbot.

Your role is to:
1. Have natural conversations with users (campaigners) to understand their intent
2. Ask clarifying follow-up questions when needed
3. Route tasks to the appropriate specialized agent when you have enough information

IMPORTANT: The user is already authenticated and their campaigner_id is automatically provided to all agents.
You do NOT need to ask users for their ID - it's already available in the system.

Available agents you can route to:
- basic_info_agent: Answers questions about agency info, user info, campaigns, and KPIs using database access
- analytics_crew: Gathers and analyzes data from all advertising platforms (Facebook Ads, Google Marketing, etc.)
- campaign_planning_crew: Plans new campaigns, creates digital assets, and deploys them to platforms

When you understand what the user needs, respond with a JSON object specifying which agent to use:
{
    "agent": "basic_info_agent" | "analytics_crew" | "campaign_planning_crew",
    "task": {
        "query": "the specific task description",
        "context": {}
    },
    "ready": true
}

If you need more information, respond naturally asking for clarification:
{
    "message": "your clarifying question or response",
    "ready": false
}

Be conversational, helpful, and ask follow-up questions naturally to understand user intent.
Remember: You have access to the user's identity through the system - never ask them for their campaigner ID.
"""

    def process(self, state: GraphState) -> Dict[str, Any]:
        """Process the conversation and determine next steps.

        Args:
            state: Current graph state

        Returns:
            Updated state fields
        """
        logger.info("🤖 [ChatbotNode] Processing conversation")

        # Get campaigner_id from state
        campaigner_id = state.get("campaigner_id", 1)
        logger.debug(f"👤 [ChatbotNode] Processing for campaigner: {campaigner_id}")

        messages = [
            SystemMessage(content=self.system_prompt),
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

                # Add campaigner_id and context for authorization and personalization
                campaigner_id = state.get("campaigner_id")
                if campaigner_id:
                    task["campaigner_id"] = campaigner_id
                    logger.debug(f"🔐 [ChatbotNode] Added campaigner_id to task: {campaigner_id}")

                    # Gather agency and campaigner context for agents
                    try:
                        db_tool = DatabaseTool(campaigner_id)
                        agency_info = db_tool.get_agency_info()
                        campaigner_info = db_tool.get_campaigner_info()

                        task["context"] = {
                            "agency": agency_info,
                            "campaigner": campaigner_info
                        }
                        logger.debug(f"📊 [ChatbotNode] Added context to task: agency={agency_info.get('name') if agency_info else None}")
                    except Exception as e:
                        logger.warning(f"⚠️  [ChatbotNode] Failed to gather context: {str(e)}")
                        task["context"] = {}

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
                logger.info(f"❓ [ChatbotNode] Need clarification: '{clarification_msg[:100]}...'")
                return {
                    "messages": state["messages"] + [AIMessage(content=clarification_msg)],
                    "needs_clarification": True,
                    "conversation_complete": False,
                    "next_agent": None
                }

        except (json.JSONDecodeError, KeyError) as e:
            # If not JSON, treat as clarification message
            logger.warning(f"⚠️  [ChatbotNode] Failed to parse JSON, treating as clarification: {str(e)}")
            return {
                "messages": state["messages"] + [AIMessage(content=response.content)],
                "needs_clarification": True,
                "conversation_complete": False,
                "next_agent": None
            }


class AgentExecutorNode:
    """Node that executes the appropriate specialized agent."""

    def __init__(self, llm: ChatOpenAI):
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
