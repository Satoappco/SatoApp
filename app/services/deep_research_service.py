"""
Deep Research Service for managing research sessions and MCP integration.

This service provides:
- Research session creation and management
- MCP client integration for deep research server
- Database persistence for sessions, steps, and sources
- Langfuse tracing integration
- Streaming and synchronous research execution
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, AsyncGenerator
from sqlmodel import Session, select
import uuid
import logging
import time

from app.models.deep_research import ResearchSession, ResearchStep, ResearchSource
from app.config.database import get_engine
from app.services.chat_trace_service import ChatTraceService
from app.models.chat_traces import RecordType

logger = logging.getLogger(__name__)


class DeepResearchService:
    """Service for managing deep research sessions and MCP integration."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize DeepResearchService.

        Args:
            session: Optional SQLModel session. If not provided, creates new session for each operation.
        """
        self.session = session
        self._should_close_session = session is None
        self.trace_service = ChatTraceService(session)
        self.mcp_client = None  # Lazy initialization

    def _get_session(self) -> Session:
        """Get or create a database session."""
        if self.session:
            return self.session
        return Session(get_engine())

    def _close_session(self, session: Session):
        """Close session if it was created internally."""
        if self._should_close_session and session:
            session.close()

    def _get_mcp_client(self):
        """
        Get or create HTTP client for deep-research MCP server.
        """
        if not self.mcp_client:
            import httpx
            from app.config.settings import get_settings
            settings = get_settings()

            # Create HTTP client for MCP server
            self.mcp_client = httpx.Client(
                base_url=settings.deep_research_mcp_url,
                timeout=600.0  # 10 minute timeout for long research sessions
            )
            logger.info(f"[DeepResearch] Initialized MCP client for {settings.deep_research_mcp_url}")
        return self.mcp_client

    def create_research_session(
        self,
        query: str,
        campaigner_id: int,
        customer_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> ResearchSession:
        """
        Create a new research session in database.

        Args:
            query: Research question
            campaigner_id: ID of the campaigner initiating research
            customer_id: Optional customer context
            thread_id: Optional link to chat thread
            config: Research configuration (models, search provider, depth, etc.)

        Returns:
            Created ResearchSession instance
        """
        session = self._get_session()
        try:
            session_id = f"res_{uuid.uuid4().hex[:12]}"

            research_session = ResearchSession(
                session_id=session_id,
                thread_id=thread_id,
                campaigner_id=campaigner_id,
                customer_id=customer_id,
                query=query,
                status="pending",
                config=config or {},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            session.add(research_session)
            session.commit()
            session.refresh(research_session)

            logger.info(f"[DeepResearch] Created session {session_id} for campaigner {campaigner_id}")

            return research_session

        except Exception as e:
            session.rollback()
            logger.error(f"[DeepResearch] Failed to create session: {e}")
            raise
        finally:
            self._close_session(session)

    def update_research_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        final_report: Optional[str] = None,
        intermediate_artifacts: Optional[Dict] = None,
        total_execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        api_calls_made: Optional[int] = None,
        langfuse_trace_id: Optional[str] = None,
        langfuse_trace_url: Optional[str] = None
    ) -> Optional[ResearchSession]:
        """
        Update research session with results.

        Args:
            session_id: Research session ID
            status: New status (pending, running, completed, error, cancelled)
            final_report: Final research report markdown
            intermediate_artifacts: Intermediate data (sources, summaries, etc.)
            total_execution_time_ms: Total execution time
            tokens_used: Total tokens consumed
            api_calls_made: Total API calls made
            langfuse_trace_id: Langfuse trace ID
            langfuse_trace_url: Langfuse trace URL

        Returns:
            Updated ResearchSession or None if not found
        """
        session = self._get_session()
        try:
            statement = select(ResearchSession).where(ResearchSession.session_id == session_id)
            research_session = session.exec(statement).first()

            if not research_session:
                logger.warning(f"[DeepResearch] Session {session_id} not found for update")
                return None

            # Update fields
            if status is not None:
                research_session.status = status
            if final_report is not None:
                research_session.final_report = final_report
            if intermediate_artifacts is not None:
                research_session.intermediate_artifacts = intermediate_artifacts
            if total_execution_time_ms is not None:
                research_session.total_execution_time_ms = total_execution_time_ms
            if tokens_used is not None:
                research_session.tokens_used = tokens_used
            if api_calls_made is not None:
                research_session.api_calls_made = api_calls_made
            if langfuse_trace_id is not None:
                research_session.langfuse_trace_id = langfuse_trace_id
            if langfuse_trace_url is not None:
                research_session.langfuse_trace_url = langfuse_trace_url

            research_session.updated_at = datetime.now(timezone.utc)

            session.add(research_session)
            session.commit()
            session.refresh(research_session)

            logger.info(f"[DeepResearch] Updated session {session_id} with status {status}")

            return research_session

        except Exception as e:
            session.rollback()
            logger.error(f"[DeepResearch] Failed to update session {session_id}: {e}")
            raise
        finally:
            self._close_session(session)

    def create_research_step(
        self,
        research_session_id: int,
        step_type: str,
        step_index: int,
        input_data: Dict,
        output_data: Optional[Dict] = None,
        status: str = "pending",
        execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> ResearchStep:
        """
        Create a research step record.

        Args:
            research_session_id: ID of parent research session
            step_type: Type of step (planning, search, compression, synthesis, report)
            step_index: Order within session
            input_data: Input data for this step
            output_data: Output data from this step
            status: Step status
            execution_time_ms: Execution time
            tokens_used: Tokens used
            error_message: Error message if failed

        Returns:
            Created ResearchStep instance
        """
        session = self._get_session()
        try:
            research_step = ResearchStep(
                research_session_id=research_session_id,
                step_type=step_type,
                step_index=step_index,
                status=status,
                input_data=input_data,
                output_data=output_data or {},
                error_message=error_message,
                execution_time_ms=execution_time_ms,
                tokens_used=tokens_used,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            session.add(research_step)
            session.commit()
            session.refresh(research_step)

            logger.debug(f"[DeepResearch] Created step {step_type}[{step_index}] for session {research_session_id}")

            return research_step

        except Exception as e:
            session.rollback()
            logger.error(f"[DeepResearch] Failed to create step: {e}")
            raise
        finally:
            self._close_session(session)

    def create_research_source(
        self,
        research_session_id: int,
        url: str,
        title: Optional[str] = None,
        content_summary: Optional[str] = None,
        relevance_score: Optional[float] = None,
        search_query: Optional[str] = None,
        metadata: Optional[Dict] = None,
        research_step_id: Optional[int] = None
    ) -> ResearchSource:
        """
        Create a research source record.

        Args:
            research_session_id: ID of parent research session
            url: Source URL
            title: Source title
            content_summary: Summary of source content
            relevance_score: Relevance score (0-1)
            search_query: Query that found this source
            metadata: Additional metadata
            research_step_id: Optional ID of step that discovered this source

        Returns:
            Created ResearchSource instance
        """
        session = self._get_session()
        try:
            research_source = ResearchSource(
                research_session_id=research_session_id,
                research_step_id=research_step_id,
                url=url,
                title=title,
                content_summary=content_summary,
                relevance_score=relevance_score,
                search_query=search_query,
                metadata=metadata or {},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            session.add(research_source)
            session.commit()
            session.refresh(research_source)

            logger.debug(f"[DeepResearch] Created source {url} for session {research_session_id}")

            return research_source

        except Exception as e:
            session.rollback()
            logger.error(f"[DeepResearch] Failed to create source: {e}")
            raise
        finally:
            self._close_session(session)

    def get_research_session(self, session_id: str) -> Optional[ResearchSession]:
        """
        Get research session by ID.

        Args:
            session_id: Research session ID

        Returns:
            ResearchSession or None if not found
        """
        session = self._get_session()
        try:
            statement = select(ResearchSession).where(ResearchSession.session_id == session_id)
            return session.exec(statement).first()
        finally:
            self._close_session(session)

    def conduct_research(
        self,
        query: str,
        campaigner_id: int,
        customer_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        config: Optional[Dict] = None,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Conduct deep research via MCP server.

        Args:
            query: Research question
            campaigner_id: ID of campaigner
            customer_id: Optional customer ID
            thread_id: Optional chat thread ID
            config: Research configuration
            streaming: Whether to stream results

        Returns:
            Research result dictionary with success, report, sources, etc.
        """
        start_time = time.time()

        # Create research session in database
        research_session = self.create_research_session(
            query=query,
            campaigner_id=campaigner_id,
            customer_id=customer_id,
            thread_id=thread_id,
            config=config or {}
        )

        logger.info(f"[DeepResearch] Starting research for session {research_session.session_id}")

        try:
            # Get MCP client
            mcp_client = self._get_mcp_client()

            # Initialize MCP session
            logger.info(f"[DeepResearch] Initializing MCP session for {research_session.session_id}")
            init_response = mcp_client.post(
                "/initialize",
                json={
                    "campaigner_id": campaigner_id,
                    "customer_id": customer_id,
                    "llm_config": config.get("llm_config", {}),
                    "search_provider": config.get("search_provider", "tavily"),
                    "research_depth": config.get("research_depth", "medium"),
                    "max_iterations": config.get("max_iterations", 5)
                }
            )
            init_response.raise_for_status()
            mcp_session_id = init_response.json()["session_id"]

            # Update database session status
            self.update_research_session(
                session_id=research_session.session_id,
                status="running"
            )

            # Execute research via MCP server
            logger.info(f"[DeepResearch] Executing research via MCP session {mcp_session_id}")
            research_response = mcp_client.post(
                f"/research/{mcp_session_id}",
                json={
                    "query": query,
                    "streaming": False
                }
            )
            research_response.raise_for_status()
            result = research_response.json()

            # Cleanup MCP session
            try:
                mcp_client.delete(f"/session/{mcp_session_id}")
            except Exception as cleanup_error:
                logger.warning(f"[DeepResearch] Failed to cleanup MCP session {mcp_session_id}: {cleanup_error}")

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update database session with results
            status = "completed" if result.get("success") else "error"
            self.update_research_session(
                session_id=research_session.session_id,
                status=status,
                final_report=result.get("report"),
                total_execution_time_ms=execution_time_ms,
                tokens_used=result.get("tokens_used", 0)
            )

            # Store sources in database
            if result.get("success") and result.get("sources"):
                session_obj = self.get_research_session(research_session.session_id)
                if session_obj:
                    for source in result.get("sources", []):
                        self.create_research_source(
                            research_session_id=session_obj.id,
                            url=source.get("url"),
                            title=source.get("title"),
                            relevance_score=source.get("relevance_score")
                        )

            return {
                "success": result.get("success", False),
                "session_id": research_session.session_id,
                "report": result.get("report"),
                "sources": result.get("sources", []),
                "execution_time_ms": execution_time_ms,
                "tokens_used": result.get("tokens_used", 0),
                "error": result.get("error")
            }

        except Exception as e:
            logger.error(f"[DeepResearch] Research failed for session {research_session.session_id}: {e}")

            # Update session as error
            self.update_research_session(
                session_id=research_session.session_id,
                status="error"
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return {
                "success": False,
                "session_id": research_session.session_id,
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }

    def record_research_to_chat_trace(
        self,
        thread_id: str,
        session_id: str,
        query: str,
        report: Optional[str],
        sources: List[Dict],
        execution_time_ms: int,
        tokens_used: int,
        config: Dict,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Record deep research execution to chat traces.

        Args:
            thread_id: Chat thread ID
            session_id: Research session ID
            query: Research query
            report: Final report
            sources: List of sources
            execution_time_ms: Execution time
            tokens_used: Tokens used
            config: Research configuration
            success: Whether research succeeded
            error_message: Optional error message
        """
        if not thread_id:
            logger.debug("[DeepResearch] No thread_id, skipping chat trace recording")
            return

        try:
            # Get research session for step count
            research_session = self.get_research_session(session_id)
            steps_count = 0
            if research_session:
                session = self._get_session()
                try:
                    statement = select(ResearchStep).where(
                        ResearchStep.research_session_id == research_session.id
                    )
                    steps_count = len(list(session.exec(statement)))
                finally:
                    self._close_session(session)

            # Record to chat traces using ChatTraceService
            self.trace_service.record_deep_research(
                thread_id=thread_id,
                query=query,
                report=report,
                sources=sources,
                session_id=session_id,
                execution_time_ms=execution_time_ms,
                tokens_used=tokens_used,
                config=config,
                success=success,
                error_message=error_message,
                research_steps_count=steps_count
            )

            logger.info(f"[DeepResearch] Recorded research to chat trace for thread {thread_id}")

        except Exception as e:
            logger.error(f"[DeepResearch] Failed to record to chat trace: {e}")
