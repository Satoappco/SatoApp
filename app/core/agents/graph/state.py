"""State management for the chatbot routing workflow."""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from langgraph.graph import MessagesState


class GraphState(MessagesState):
    """State for the chatbot routing graph.

    This state manages the conversation flow where a chatbot interacts with users
    and routes tasks to specialized agents based on intent.
    """

    # Routing information
    next_agent: Optional[Literal["basic_info_agent", "analytics_crew", "campaign_planning_crew"]]
    agent_task: Optional[Dict[str, Any]]
    agent_result: Optional[Dict[str, Any]]

    # Conversation control
    needs_clarification: bool
    conversation_complete: bool

    # Error handling
    error: Optional[str]

    # User context (for authorization and data filtering)
    campaigner_id: Optional[int] # ID of the authenticated campaigner
