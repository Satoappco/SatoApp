"""
Delegate to Coworker Tool

This tool allows agents to delegate tasks to other specialized agents
when they don't have the necessary expertise or tools to handle a request.
"""
import json
import logging
from typing import Optional, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field as PydanticField
from app.services.chat_trace_service import ChatTraceService

logger = logging.getLogger(__name__)


class DelegateToCoworkerInput(BaseModel):
    """Input schema for DelegateToCoworkerTool"""
    message: str = PydanticField(
        ...,
        description="The task or question to delegate to the coworker agent. Be specific and include all necessary context."
    )
    agent_name: str = PydanticField(
        ...,
        description="The name of the coworker agent to delegate to. Available agents: 'single_analytics_agent' (for Google Analytics, Google Ads, Facebook Ads queries)"
    )


class DelegateToCoworkerTool(BaseTool):
    """
    Tool for delegating tasks to other specialized agents.

    This tool allows an agent to request help from another agent when it encounters
    a task that requires specialized knowledge or tools that it doesn't have access to.

    Example use cases:
    - SQL agent encountering an analytics platform query (delegate to analytics agent)
    - General agent needing database queries (delegate to SQL agent)
    """

    name: str = "delegate_to_coworker"
    description: str = (
        "Delegate a task to another specialized agent when you don't have the necessary "
        "expertise or tools to handle it yourself. Use this when the user's question requires "
        "specialized knowledge or access to tools you don't have. "
        "Available coworkers: 'single_analytics_agent' for Google Analytics, Google Ads, and Facebook Ads queries."
    )
    args_schema: Type[BaseModel] = DelegateToCoworkerInput

    # Context fields passed from the calling agent
    llm: Optional[object] = PydanticField(default=None, exclude=True)
    customer_id: Optional[int] = PydanticField(default=None)
    campaigner_id: Optional[int] = PydanticField(default=None)
    context: Optional[dict] = PydanticField(default=None)
    thread_id: Optional[str] = PydanticField(default=None)
    level: int = PydanticField(default=1)
    allowed_agents: Optional[List[str]] = PydanticField(default=None)

    def _run(self, message: str, agent_name: str) -> str:
        """
        Delegate a task to another agent.

        Args:
            message: The task or question to delegate
            agent_name: The name of the agent to delegate to

        Returns:
            The response from the delegated agent
        """
        try:
            # Validate agent name is in allowed list
            if self.allowed_agents and agent_name not in self.allowed_agents:
                error_msg = (
                    f"Cannot delegate to '{agent_name}'. "
                    f"Allowed agents: {', '.join(self.allowed_agents)}"
                )
                logger.warning(error_msg)
                return json.dumps({
                    "error": error_msg,
                    "status": "error"
                })

            # Log delegation attempt
            logger.info(
                f"Delegating task to {agent_name} "
                f"(thread_id={self.thread_id}, level={self.level})"
            )

            # Trace the delegation
            if self.thread_id:
                trace_service = ChatTraceService()
                trace_service.add_tool_usage(
                    thread_id=self.thread_id,
                    tool_name=self.name,
                    tool_input={
                        "message": message,
                        "agent_name": agent_name
                    },
                    tool_output={"status": "delegating"},
                    success=True,
                    level=self.level
                )

            # Get the target agent instance
            if not self.llm:
                raise ValueError("LLM instance not provided to DelegateToCoworkerTool")

            # Lazy import to avoid circular dependency
            from app.core.agents.graph.agents import get_agent

            target_agent = get_agent(agent_name, self.llm)

            # Prepare task for the target agent
            delegated_task = {
                "query": message,
                "customer_id": self.customer_id,
                "campaigner_id": self.campaigner_id,
                "context": self.context or {},
                "thread_id": self.thread_id,
                "level": self.level + 1  # Increment level to show delegation hierarchy
            }

            # Execute the delegated task
            result = target_agent.execute(delegated_task)

            # Extract response
            if result.get("status") == "error":
                error_msg = result.get("result", "Unknown error occurred")
                logger.error(f"Delegation to {agent_name} failed: {error_msg}")
                return json.dumps({
                    "error": f"The {agent_name} encountered an error: {error_msg}",
                    "status": "error"
                })

            response = result.get("result", "No response from agent")

            # Log successful delegation
            logger.info(f"Successfully received response from {agent_name}")

            # Trace the successful delegation result
            if self.thread_id:
                trace_service = ChatTraceService()
                trace_service.add_tool_usage(
                    thread_id=self.thread_id,
                    tool_name=self.name,
                    tool_input={
                        "message": message,
                        "agent_name": agent_name
                    },
                    tool_output={
                        "status": "completed",
                        "response_length": len(str(response))
                    },
                    success=True,
                    level=self.level
                )

            return response

        except Exception as e:
            error_msg = f"Error delegating to {agent_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Trace the error
            if self.thread_id:
                trace_service = ChatTraceService()
                trace_service.add_tool_usage(
                    thread_id=self.thread_id,
                    tool_name=self.name,
                    tool_input={
                        "message": message,
                        "agent_name": agent_name
                    },
                    tool_output={"error": str(e)},
                    success=False,
                    level=self.level
                )

            return json.dumps({
                "error": error_msg,
                "status": "error"
            })

    async def _arun(self, message: str, agent_name: str) -> str:
        """Async version - calls synchronous implementation"""
        return self._run(message, agent_name)
