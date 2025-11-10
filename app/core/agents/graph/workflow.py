"""Main LangGraph workflow for chatbot routing."""

from typing import Literal
from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_community.chat_message_histories import PostgresChatMessageHistory
import os
import logging

from .state import GraphState
from .nodes import ChatbotNode, AgentExecutorNode, ErrorHandlerNode
from app.core.agents.database.connection import get_database_url
from app.models.users import Campaigner

logger = logging.getLogger(__name__)


class ConversationWorkflow:
    """LangGraph workflow for chatbot-based agent routing.

    This workflow implements a conversational interface where a chatbot:
    1. Interacts with users to understand their intent
    2. Asks follow-up questions when needed
    3. Routes tasks to specialized agents when ready
    """

    def __init__(self, campaigner: Campaigner, thread_id: str = "default", customer_id: int = None, trace=None):
        logger.info(f"🏗️  [Workflow] Initializing ConversationWorkflow for thread: {thread_id[:8]}...")

        # Store campaigner id, customer_id, thread_id, and trace for this workflow
        self.campaigner = campaigner
        self.customer_id = customer_id
        self.thread_id = thread_id
        self.trace = trace  # LangFuse trace for the entire session
        logger.debug(f"👤 [Workflow] Campaigner ID: {campaigner.id} | Customer ID: {customer_id} | Thread ID: {thread_id[:8]}... | Trace: {trace is not None}")

        # Initialize PostgreSQL chat message history
        try:
            connection_string = get_database_url()
            # Use a unique session_id combining campaigner id and thread_id
            session_id = f"campaigner_{campaigner.id}_thread_{thread_id}"
            self.message_history = PostgresChatMessageHistory(
                connection_string=connection_string,
                session_id=session_id
            )
            logger.info(f"✅ [Workflow] PostgreSQL chat history initialized for session: {session_id[:30]}...")
        except Exception as e:
            logger.error(f"❌ [Workflow] Failed to initialize PostgreSQL chat history: {e}")
            raise

        # Initialize conversation state (persistent across messages)
        # Load existing messages from database
        existing_messages = self.message_history.messages
        logger.debug(f"📜 [Workflow] Loaded {len(existing_messages)} existing messages from database")

        self.conversation_state = {
            "messages": existing_messages,  # Load from PostgreSQL
            "next_agent": None,
            "agent_task": None,
            "agent_result": None,
            "needs_clarification": False,
            "conversation_complete": False,
            "error": None,
            "campaigner": campaigner,
            "customer_id": customer_id,
            "trace": trace  # Pass trace through state for nodes to use
        }

        # Initialize LLM
        # self.llm = ChatOpenAI(
        #     model="gpt-4o-mini",
        #     temperature=0.7,
        #     api_key=os.getenv("OPENAI_API_KEY")
        # )
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        logger.debug(f"🤖 [Workflow] LLM initialized: gpt-4o-mini")

        # Initialize nodes
        self.chatbot_node = ChatbotNode(self.llm)
        self.agent_executor_node = AgentExecutorNode(self.llm)
        self.error_handler_node = ErrorHandlerNode()
        logger.debug("📦 [Workflow] Nodes initialized")

        # Build and compile graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        logger.debug("✅ [Workflow] Graph compiled and ready")

    def _build_graph(self) -> StateGraph:
        """Build the chatbot routing graph."""

        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("chatbot", self.chatbot_node.process)
        workflow.add_node("execute_agent", self.agent_executor_node.execute)
        workflow.add_node("handle_error", self.error_handler_node.handle)

        # Set entry point
        workflow.set_entry_point("chatbot")

        # Add conditional edges
        workflow.add_conditional_edges(
            "chatbot",
            self._route_from_chatbot,
            {
                "execute_agent": "execute_agent",
                "clarify": END,
                "error": "handle_error"
            }
        )

        workflow.add_edge("execute_agent", END)
        workflow.add_edge("handle_error", END)

        return workflow

    def _route_from_chatbot(
        self, state: GraphState
    ) -> Literal["execute_agent", "clarify", "error"]:
        """Route from chatbot node based on state.

        Args:
            state: Current graph state

        Returns:
            Next node to execute
        """
        if state.get("error"):
            logger.error("🔀 [Workflow] Routing to: error handler")
            return "error"

        if state.get("needs_clarification"):
            logger.info("🔀 [Workflow] Routing to: clarify (END)")
            return "clarify"

        if state.get("next_agent"):
            agent_name = state.get("next_agent")
            logger.info(f"🔀 [Workflow] Routing to: execute_agent ({agent_name})")
            return "execute_agent"

        logger.info("🔀 [Workflow] Routing to: clarify (default)")
        return "clarify"

    def process_message(self, message: str) -> dict:
        """Process a user message and return the updated state.

        Args:
            message: User's message

        Returns:
            Updated state after processing
        """
        logger.info(f"🔄 [Workflow] Processing message: '{message[:50]}...'")
        logger.debug(f"♻️  [Workflow] Continuing with {len(self.conversation_state.get('messages', []))} existing messages")

        # Add user message to PostgreSQL history
        try:
            self.message_history.add_user_message(message)
            logger.debug(f"💾 [Workflow] User message saved to PostgreSQL")
        except Exception as e:
            logger.error(f"❌ [Workflow] Failed to save user message to PostgreSQL: {e}")

        # Add user message to state for processing
        self.conversation_state["messages"].append(HumanMessage(content=message))

        # Reset flags for this turn
        self.conversation_state["next_agent"] = None
        self.conversation_state["agent_task"] = None
        self.conversation_state["agent_result"] = None
        self.conversation_state["needs_clarification"] = False
        self.conversation_state["error"] = None

        # Run the graph with persistent state
        logger.debug("⚙️  [Workflow] Invoking graph...")
        result = self.app.invoke(self.conversation_state)

        # Update persistent state with result
        self.conversation_state.update(result)

        # Save AI response to PostgreSQL
        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                try:
                    # Only save if it's an AI message (not user message)
                    if last_message.type == "ai":
                        self.message_history.add_ai_message(last_message.content)
                        logger.debug(f"💾 [Workflow] AI message saved to PostgreSQL")
                except Exception as e:
                    logger.error(f"❌ [Workflow] Failed to save AI message to PostgreSQL: {e}")

        logger.info(
            f"✅ [Workflow] Graph completed | "
            f"Agent: {result.get('next_agent', 'None')} | "
            f"Complete: {result.get('conversation_complete', False)} | "
            f"Total messages: {len(self.conversation_state['messages'])}"
        )

        return self.conversation_state


# Module-level function to build and return the compiled graph
#TODO: Review why it is needed if already in ConversationWorkflow
def build_graph():
    """Build and return the compiled chatbot routing graph.

    This function is used by LangGraph CLI and for module-level exports.

    Returns:
        Compiled graph application
    """
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    # llm = ChatOpenAI(
    #     model="gpt-4o-mini",
    #     temperature=0.7,
    #     api_key=os.getenv("OPENAI_API_KEY")
    # )

    # Initialize nodes
    chatbot_node = ChatbotNode(llm)
    agent_executor_node = AgentExecutorNode(llm)
    error_handler_node = ErrorHandlerNode()

    # Create graph
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("chatbot", chatbot_node.process)
    workflow.add_node("execute_agent", agent_executor_node.execute)
    workflow.add_node("handle_error", error_handler_node.handle)

    # Set entry point
    workflow.set_entry_point("chatbot")

    # Routing function
    def route_from_chatbot(
        state: GraphState
    ) -> Literal["execute_agent", "clarify", "error"]:
        """Route from chatbot node based on state."""
        if state.get("error"):
            return "error"
        if state.get("needs_clarification"):
            return "clarify"
        if state.get("next_agent"):
            return "execute_agent"
        return "clarify"

    # Add edges
    workflow.add_conditional_edges(
        "chatbot",
        route_from_chatbot,
        {
            "execute_agent": "execute_agent",
            "clarify": END,
            "error": "handle_error"
        }
    )

    workflow.add_edge("execute_agent", END)
    workflow.add_edge("handle_error", END)

    # Compile and return
    return workflow.compile()


# Lazy graph initialization
_graph = None


def get_graph():
    """Get or create the graph instance.

    Returns:
        Compiled graph application
    """
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# Export the graph for LangGraph CLI
try:
    graph = build_graph()
except Exception as e:
    # During testing, graph will be built lazily
    # if not os.getenv("OPENAI_API_KEY"):
    #     graph = None
    # else:
        raise
