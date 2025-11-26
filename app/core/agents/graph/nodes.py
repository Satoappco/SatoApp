"""Node implementations for the chatbot routing workflow."""
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessage
import json
import logging

from .state import GraphState
from .agents import get_agent
from ..database.tools import DatabaseTool
from app.models.users import Campaigner
from app.services.agent_service import AgentService
from app.services.chat_trace_service import ChatTraceService
import os
import time

logger = logging.getLogger(__name__)


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
        thread_id = state.get("thread_id")  # Get thread_id for tracing

        logger.info(f"⚙️  [AgentExecutor] Executing agent: {agent_name}")

        if not agent_name:
            logger.error("❌ [AgentExecutor] No agent specified")
            return {
                "error": "No agent specified for execution",
                "conversation_complete": True
            }

        # Initialize trace service for logging agent steps
        trace_service = ChatTraceService() if thread_id else None
        start_time = time.time()

        # Get current level from conversation and increment for this agent execution
        current_level = 0
        if trace_service and thread_id:
            conversation = trace_service.get_conversation(thread_id)
            if conversation:
                current_level = conversation.data.get("current_level", 0) + 1

        try:
            # Get and execute the agent
            # Note: agent_start will be logged by the agent itself with its system prompt
            logger.debug(f"🔍 [AgentExecutor] Getting agent instance: {agent_name}")
            agent = get_agent(agent_name, self.llm)

            # Add thread_id and level to task for tracing inside the agent
            task_with_trace = {**task, "thread_id": thread_id, "level": current_level} if thread_id else task

            # Trace: Starting agent execution
            if trace_service and thread_id:
                try:
                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="progress",
                        content=f"Executing {agent_name} agent to process your request...",
                        agent_name=agent_name,
                        metadata={
                            "progress_stage": "agent_execution_start",
                            "task_type": task.get("type", "unknown")
                        },
                        level=current_level
                    )
                except Exception as e:
                    logger.warning(f"⚠️  [AgentExecutor] Failed to trace agent execution start: {e}")

            logger.info(f"🚀 [AgentExecutor] Executing {agent_name} with task...")
            logger.debug(f"📋 [AgentExecutor] Task details: {task}")
            result = agent.execute(task_with_trace)
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [AgentExecutor] Agent {agent_name} completed. Status: {result.get('status')}")

            # Check if agent returned error status
            if result.get("status") == "error":
                logger.warning(f"⚠️  [AgentExecutor] Agent {agent_name} returned error status")

                # Get user-friendly error message from result
                error_message = result.get("result", result.get("message", "An error occurred"))

                # Log agent error step
                if trace_service and thread_id:
                    error_metadata = {
                        "error_message": str(error_message),
                        "error_type": result.get("error_type", "unknown"),
                        "execution_time_ms": execution_time_ms,
                        "end_time": time.time()
                    }

                    # Include traceback if available in result
                    if "traceback" in result:
                        error_metadata["traceback"] = result["traceback"]

                    trace_service.add_agent_step(
                        thread_id=thread_id,
                        step_type="agent_error",
                        content=f"Agent {agent_name} encountered an error: {error_message}",
                        agent_name=agent_name,
                        metadata=error_metadata
                    )

                # Return state that will route back to chatbot with error context
                return {
                    "agent_result": result,
                    "agent_error": error_message,  # Special flag for routing
                    "messages": state["messages"],  # Don't add message yet - let chatbot handle it
                    "conversation_complete": False,  # Keep conversation active
                    "error": None  # Don't set error - we want chatbot to handle it gracefully
                }

            # Format response message for successful completion
            response_message = self._format_agent_response(result)

            # Log the raw result for debugging
            logger.info(f"📋 [AgentExecutor] Raw result status: {result.get('status')}")
            logger.info(f"📋 [AgentExecutor] Raw result keys: {list(result.keys())}")
            logger.debug(f"📋 [AgentExecutor] Raw result.result type: {type(result.get('result'))}")

            # Safe preview of response (handle both string and CrewOutput)
            try:
                preview = str(response_message)[:100] if response_message else "No response"
                logger.info(f"💬 [AgentExecutor] Formatted response: '{preview}...'")
                logger.info(f"💬 [AgentExecutor] Response length: {len(str(response_message)) if response_message else 0} characters")
            except Exception as e:
                logger.error(f"💬 [AgentExecutor] Response formatting error: {e}")
                logger.debug(f"💬 [AgentExecutor] Response: (non-string type: {type(response_message)})")

            # Log agent completion step
            if trace_service and thread_id:
                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="agent_complete",
                    content=f"Agent {agent_name} completed successfully",
                    agent_name=agent_name,
                    metadata={
                        "result_preview": str(response_message)[:500],
                        "execution_time_ms": execution_time_ms,
                        "status": str(result.get("status")),
                        "end_time": time.time()
                    }
                )

            # Ensure we have a valid response message
            final_message = str(response_message) if response_message else "Task completed."
            if not final_message or final_message.strip() == "":
                logger.error(f"❌ [AgentExecutor] Empty response message! Using fallback.")
                final_message = "I've processed your request, but encountered an issue generating the response. Please check the traces for details."

            logger.info(f"✅ [AgentExecutor] Adding AI message with {len(final_message)} characters")

            return {
                "agent_result": result,
                "messages": state["messages"] + [AIMessage(content=final_message)],
                "conversation_complete": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ [AgentExecutor] Agent execution failed: {str(e)}", exc_info=True)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Get full traceback
            import traceback
            traceback_str = traceback.format_exc()

            # Log agent exception step
            if trace_service and thread_id:
                trace_service.add_agent_step(
                    thread_id=thread_id,
                    step_type="agent_exception",
                    content=f"Agent {agent_name} raised exception: {str(e)}",
                    agent_name=agent_name,
                    metadata={
                        "exception": str(e),
                        "exception_type": type(e).__name__,
                        "traceback": traceback_str,
                        "execution_time_ms": execution_time_ms,
                        "end_time": time.time()
                    }
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

        logger.debug(f"🔍 [_format_agent_response] Formatting result with status: {status}, agent: {agent}")

        if status == "completed":
            crew_result = result.get("result", "Task completed successfully.")

            logger.debug(f"🔍 [_format_agent_response] crew_result type: {type(crew_result)}")

            # Handle CrewOutput object from CrewAI
            # CrewOutput has multiple attributes: raw, pydantic, json_dict, tasks_output, token_usage
            if hasattr(crew_result, "raw"):
                # Use the raw string output from CrewAI
                formatted = str(crew_result.raw)
                logger.debug(f"🔍 [_format_agent_response] Using .raw attribute: {len(formatted)} chars")
                return formatted
            elif hasattr(crew_result, "__str__"):
                # Fallback to string representation
                formatted = str(crew_result)
                logger.debug(f"🔍 [_format_agent_response] Using __str__: {len(formatted)} chars")
                return formatted
            else:
                # Already a string
                logger.debug(f"🔍 [_format_agent_response] Using as-is: {len(str(crew_result))} chars")
                return crew_result if isinstance(crew_result, str) else str(crew_result)

        elif status == "placeholder":
            message = result.get("message", "")
            return f"{message}\n\nThis feature is coming soon!"
        else:
            logger.warning(f"⚠️  [_format_agent_response] Unknown status: {status}, using fallback")
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
