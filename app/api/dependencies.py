"""FastAPI dependencies."""

from functools import lru_cache
from typing import Dict
import os
import logging

from app.core.agents.graph.workflow import ConversationWorkflow
from app.core.agents.crew.crew import AnalyticsCrew
from app.core.auth import get_current_user
from app.models.users import Campaigner
from fastapi import Depends

logger = logging.getLogger(__name__)


def get_current_campaigner(current_user: Campaigner = Depends(get_current_user)) -> Campaigner:
    """Get current authenticated campaigner (alias for get_current_user)"""
    return current_user


class ApplicationState:
    """Singleton application state."""

    _instance = None
    _conversation_workflows: Dict[str, ConversationWorkflow] = {}
    _analytics_crew: AnalyticsCrew = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.info("🏗️  [AppState] Created new ApplicationState singleton")
        return cls._instance

    def get_conversation_workflow(self, current_user: Campaigner, thread_id: str = "default", customer_id: int = None, trace=None) -> ConversationWorkflow:
        """Get or create conversation workflow for thread."""
        if thread_id not in self._conversation_workflows:
            logger.info(f"🆕 [AppState] Creating new workflow for thread: {thread_id[:8]}... | Campaigner: {current_user.id} | Customer: {customer_id}")
            self._conversation_workflows[thread_id] = ConversationWorkflow(
                campaigner=current_user,
                thread_id=thread_id,
                customer_id=customer_id,
                trace=trace
            )
        else:
            logger.debug(f"♻️  [AppState] Reusing existing workflow for thread: {thread_id[:8]}...")
            # Update trace for existing workflow
            if trace:
                self._conversation_workflows[thread_id].trace = trace
        return self._conversation_workflows[thread_id]

    def get_analytics_crew(self) -> AnalyticsCrew:
        """Get or create analytics crew."""
        if self._analytics_crew is None:
            logger.info("🆕 [AppState] Creating new AnalyticsCrew instance")
            self._analytics_crew = AnalyticsCrew()
        else:
            logger.debug("♻️  [AppState] Reusing existing AnalyticsCrew instance")
        return self._analytics_crew

    def reset_thread(self, thread_id: str):
        """Reset a conversation thread."""
        if thread_id in self._conversation_workflows:
            logger.info(f"🔄 [AppState] Resetting thread: {thread_id[:8]}...")
            del self._conversation_workflows[thread_id]
        else:
            logger.debug(f"⚠️  [AppState] Thread {thread_id[:8]}... not found, nothing to reset")

    def get_all_threads(self) -> Dict[str, ConversationWorkflow]:
        """Get all conversation threads."""
        logger.debug(f"📋 [AppState] Returning {len(self._conversation_workflows)} threads")
        return self._conversation_workflows


@lru_cache()
def get_app_state() -> ApplicationState:
    """Get application state singleton."""
    return ApplicationState()

