"""Deep Research Agent for conducting comprehensive multi-step research."""

from typing import Dict, Any, Optional
import logging
from langchain_core.language_models import BaseChatModel

from app.services.deep_research_service import DeepResearchService

logger = logging.getLogger(__name__)


class DeepResearchAgent:
    """
    Specialized agent for conducting deep research using open_deep_research.

    This agent provides comprehensive, academic-level research on any topic through
    multi-step process including planning, iterative searching, compression, and
    report generation.
    """

    def __init__(self, llm: BaseChatModel):
        """
        Initialize DeepResearchAgent.

        Args:
            llm: Language model instance (for compatibility with agent registry)
        """
        self.llm = llm
        self.research_service = DeepResearchService()

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a deep research task.

        Args:
            task: Dictionary containing the research request with keys:
                - query: Research question (required)
                - campaigner_id: ID of campaigner initiating research (required)
                - customer_id: Customer context (optional)
                - thread_id: Chat thread ID for conversation linking (optional)
                - config: Research configuration (optional):
                    - llm_config: Model selections for different phases
                    - search_provider: tavily, anthropic, or mcp
                    - research_depth: shallow, medium, or deep
                    - max_iterations: Number of search iterations

        Returns:
            Dictionary containing:
                - status: "completed" or "error"
                - report: Final research report (markdown)
                - sources: List of discovered sources
                - session_id: Research session ID
                - execution_time_ms: Total execution time
                - tokens_used: Total tokens consumed
                - agent: "deep_research_agent"
                - error: Error message (if status is "error")
        """
        # Extract task details
        query = task.get("query")
        campaigner_id = task.get("campaigner_id")
        customer_id = task.get("customer_id")
        thread_id = task.get("thread_id")
        config = task.get("config", {})

        # Validate required fields
        if not query:
            logger.error("[DeepResearchAgent] No query provided")
            return {
                "status": "error",
                "error": "Research query is required",
                "agent": "deep_research_agent"
            }

        if not campaigner_id:
            logger.error("[DeepResearchAgent] No campaigner_id provided")
            return {
                "status": "error",
                "error": "Campaigner ID is required",
                "agent": "deep_research_agent"
            }

        logger.info(f"[DeepResearchAgent] Executing research: {query[:100]}...")
        logger.info(f"[DeepResearchAgent] Config: {config}")

        try:
            # Execute research via service
            result = self.research_service.conduct_research(
                query=query,
                campaigner_id=campaigner_id,
                customer_id=customer_id,
                thread_id=thread_id,
                config=config,
                streaming=False  # Synchronous execution
            )

            # Record to chat trace if thread_id provided
            if thread_id and result.get("success"):
                self.research_service.record_research_to_chat_trace(
                    thread_id=thread_id,
                    session_id=result.get("session_id"),
                    query=query,
                    report=result.get("report"),
                    sources=result.get("sources", []),
                    execution_time_ms=result.get("execution_time_ms", 0),
                    tokens_used=result.get("tokens_used", 0),
                    config=config,
                    success=result.get("success", False),
                    error_message=result.get("error")
                )

            # Format response
            if result.get("success"):
                return {
                    "status": "completed",
                    "report": result.get("report"),
                    "sources": result.get("sources", []),
                    "session_id": result.get("session_id"),
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "tokens_used": result.get("tokens_used", 0),
                    "agent": "deep_research_agent"
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Research failed"),
                    "session_id": result.get("session_id"),
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "agent": "deep_research_agent"
                }

        except Exception as e:
            logger.error(f"[DeepResearchAgent] Execution failed: {e}")
            return {
                "status": "error",
                "error": f"Research execution failed: {str(e)}",
                "agent": "deep_research_agent"
            }
