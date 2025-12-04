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
from .nodes import AgentExecutorNode, ErrorHandlerNode
from .chatbot_agent import ChatbotNode
from app.core.agents.database.connection import get_database_url
from app.models.users import Campaigner
from app.services.chat_trace_service import ChatTraceService

logger = logging.getLogger(__name__)


class ConversationWorkflow:
    """LangGraph workflow for chatbot-based agent routing.

    This workflow implements a conversational interface where a chatbot:
    1. Interacts with users to understand their intent
    2. Asks follow-up questions when needed
    3. Routes tasks to specialized agents when ready
    """

    def __init__(self, campaigner: Campaigner, thread_id: str = "default", customer_id: int = None):
        logger.info(f"🏗️  [Workflow] Initializing ConversationWorkflow for thread: {thread_id[:8]}...")

        # Store campaigner id, customer_id, and thread_id for this workflow
        self.campaigner = campaigner
        self.customer_id = customer_id
        self.thread_id = thread_id
        logger.debug(f"👤 [Workflow] Campaigner ID: {campaigner.id} | Customer ID: {customer_id} | Thread ID: {thread_id[:8]}...")

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
            "thread_id": thread_id  # Pass thread_id for tracing
        }

        # Initialize LLM
        # self.llm = ChatOpenAI(
        #     model="gpt-4o-mini",
        #     temperature=0.7,
        #     api_key=os.getenv("OPENAI_API_KEY")
        # )
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        llm_model_name = "gemini-2.5-flash"  # Extract model name
        logger.debug(f"🤖 [Workflow] LLM initialized: {llm_model_name}")

        # Initialize nodes
        self.chatbot_node = ChatbotNode(self.llm, self.conversation_state)
        self.agent_executor_node = AgentExecutorNode(self.llm)
        self.error_handler_node = ErrorHandlerNode()
        logger.debug("📦 [Workflow] Nodes initialized")

        # Trace chatbot initialization with system prompt
        try:
            trace_service = ChatTraceService()
            trace_service.add_chatbot_initialization(
                thread_id=thread_id,
                chatbot_name="chatbot_orchestrator",
                llm_model=llm_model_name,
                system_prompt=self.chatbot_node.formatted_system_prompt,
                metadata={
                    "campaigner_id": campaigner.id,
                    "customer_id": customer_id,
                    "supports_streaming": self.chatbot_node.supports_streaming
                },
                level=0
            )
            logger.debug("✅ [Workflow] Chatbot initialization traced")
        except Exception as e:
            logger.warning(f"⚠️  [Workflow] Failed to trace chatbot initialization: {e}")

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

        # Add conditional routing from execute_agent
        workflow.add_conditional_edges(
            "execute_agent",
            self._route_from_agent,
            {
                "chatbot": "chatbot",  # Route back to chatbot if agent had error
                "end": END  # End if agent completed successfully
            }
        )

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

    def _route_from_agent(
        self, state: GraphState
    ) -> Literal["chatbot", "end"]:
        """Route from agent executor node based on state.

        Args:
            state: Current graph state

        Returns:
            Next node to execute
        """
        # Check if agent returned an error
        if state.get("agent_error"):
            logger.warning("🔀 [Workflow] Agent error detected, routing back to: chatbot")
            return "chatbot"

        # Normal completion - end workflow
        logger.info("🔀 [Workflow] Agent completed successfully, routing to: END")
        return "end"

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

    async def stream_message(self, message: str):
        """Stream a user message response in real-time.

        Args:
            message: User's message

        Yields:
            Chunks of the assistant's response as they are generated
        """

        # Yield progress: Starting workflow
        try:
            trace_service = ChatTraceService()
            trace_service.add_agent_step(
                thread_id=self.thread_id,
                step_type="progress",
                content="Analyzing your request with conversational AI...",
                agent_name="workflow",
                metadata={
                    "progress_stage": "workflow_start",
                    "message_length": len(message)
                },
                level=0
            )
            yield {"type": "progress", "message": "Analyzing your request..."}
        except Exception as e:
            logger.warning(f"⚠️  [Workflow] Failed to trace workflow start: {e}")

        #TODO: fix
        result = self.process_message(message)

        # Yield progress: Workflow completed
        try:
            trace_service = ChatTraceService()
            trace_service.add_agent_step(
                thread_id=self.thread_id,
                step_type="progress",
                content="Request analysis complete, preparing response...",
                agent_name="workflow",
                metadata={
                    "progress_stage": "workflow_complete",
                    "needs_clarification": result.get("needs_clarification", False),
                    "ready_for_crew": result.get("ready_for_crew", False)
                },
                level=0
            )
            yield {"type": "progress", "message": "Preparing your response..."}
        except Exception as e:
            logger.warning(f"⚠️  [Workflow] Failed to trace workflow completion: {e}")

        # Extract response message
        messages = result.get("messages", [])
        assistant_message = ""

        logger.debug(f"📋 [Stream] Total messages in result: {len(messages)}")
        if messages:
            last_message = messages[-1]
            logger.debug(f"📋 [Stream] Last message type: {last_message.type if hasattr(last_message, 'type') else type(last_message)}")
            if hasattr(last_message, "content"):
                assistant_message = last_message.content
                logger.info(f"📋 [Stream] Extracted message content: {len(assistant_message)} chars")
            else:
                logger.warning(f"⚠️  [Stream] Last message has no content attribute")
        else:
            logger.warning(f"⚠️  [Stream] No messages in result!")

        # If clarification question exists, use that
        if result.get("clarification_question"):
            assistant_message = result["clarification_question"]
            logger.debug(f"📋 [Stream] Using clarification question instead")

        if not assistant_message:
            logger.error(f"❌ [Stream] No assistant message to stream! Result keys: {list(result.keys())}")
            logger.error(f"❌ [Stream] Messages: {[(m.type if hasattr(m, 'type') else type(m), len(m.content) if hasattr(m, 'content') else 0) for m in messages]}")

        # Limit response length to prevent massive responses
        MAX_RESPONSE_LENGTH = 50000  # 50KB max
        if len(assistant_message) > MAX_RESPONSE_LENGTH:
            logger.warning(f"⚠️  [Stream] Response too large ({len(assistant_message)} chars), truncating to {MAX_RESPONSE_LENGTH}")
            assistant_message = assistant_message[:MAX_RESPONSE_LENGTH] + "\n\n[Response truncated due to length]"

        logger.info(f"📤 [Stream] Streaming {len(assistant_message.split()) if assistant_message else 0} words ({len(assistant_message)} chars)")

        #TODO: Why is that needed?
        yield {
            "type": "metadata",
            # "state": final_state,
            "needs_clarification": self.conversation_state.get("needs_clarification", False),
            "ready_for_crew": self.conversation_state.get("ready_for_crew", False),
            "platforms": self.conversation_state.get("platforms", []),
            "metrics": self.conversation_state.get("metrics", []),
            "date_range_start": self.conversation_state.get("date_range_start"),
            "date_range_end": self.conversation_state.get("date_range_end"),
        }

        # Yield content word-by-word for better streaming performance
        # This is faster than character-by-character while still providing smooth display
        # Words are natural boundaries that won't break frontend display logic
        words = assistant_message.split('\n')
        len_words = len(words)
        for i, word in enumerate(words):
            # Add space after word (except for last word)
            chunk = word + ('\n' if i < len_words else '')
            yield {"type": "content", "chunk": chunk}


        # logger.info(f"📡 [Workflow] Streaming message: '{message[:50]}...'")
        # logger.debug(f"♻️  [Workflow] Continuing with {len(self.conversation_state.get('messages', []))} existing messages")

        # # Add user message to PostgreSQL history
        # try:
        #     self.message_history.add_user_message(message)
        #     logger.debug(f"💾 [Workflow] User message saved to PostgreSQL")
        # except Exception as e:
        #     logger.error(f"❌ [Workflow] Failed to save user message to PostgreSQL: {e}")

        # # Add user message to state for processing
        # self.conversation_state["messages"].append(HumanMessage(content=message))

        # # Reset flags for this turn
        # self.conversation_state["next_agent"] = None
        # self.conversation_state["agent_task"] = None
        # self.conversation_state["agent_result"] = None
        # self.conversation_state["needs_clarification"] = False
        # self.conversation_state["error"] = None

        # # Stream through chatbot node directly
        # logger.debug("⚙️  [Workflow] Streaming through chatbot node...")

        # full_response = ""
        # async for chunk in self.chatbot_node.stream_process(self.conversation_state):
        #     if isinstance(chunk, dict) and "content" in chunk:
        #         # Stream content chunk
        #         content = chunk["content"]
        #         full_response += content
        #         yield {"type": "content", "chunk": content}
        #     elif isinstance(chunk, dict) and "state" in chunk:
        #         # Final state update
        #         final_state = chunk["state"]
        #         self.conversation_state.update(final_state)

        #         # Save AI response to PostgreSQL
        #         try:
        #             if full_response:
        #                 self.message_history.add_ai_message(full_response)
        #                 logger.debug(f"💾 [Workflow] AI message saved to PostgreSQL")
        #         except Exception as e:
        #             logger.error(f"❌ [Workflow] Failed to save AI message to PostgreSQL: {e}")

        #         # Yield metadata
        #         yield {
        #             "type": "metadata",
        #             "state": final_state,
        #             "needs_clarification": final_state.get("needs_clarification", False),
        #             "ready_for_crew": final_state.get("ready_for_crew", False),
        #             "platforms": final_state.get("platforms", []),
        #             "metrics": final_state.get("metrics", []),
        #             "date_range_start": final_state.get("date_range_start"),
        #             "date_range_end": final_state.get("date_range_end"),
        #         }

        # logger.info(f"✅ [Workflow] Streaming completed | Total messages: {len(self.conversation_state['messages'])}")


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

    # Initialize nodes (without conversation state for module-level graph)
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

    # Routing functions
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

    def route_from_agent(
        state: GraphState
    ) -> Literal["chatbot", "end"]:
        """Route from agent executor node based on state."""
        if state.get("agent_error"):
            return "chatbot"
        return "end"

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

    workflow.add_conditional_edges(
        "execute_agent",
        route_from_agent,
        {
            "chatbot": "chatbot",
            "end": END
        }
    )

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
    # During testing or when credentials are not available, graph will be built lazily
    import os
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        graph = None
    else:
        raise
