"""Chatbot routing workflow for campaign management.

This module implements a conversational interface where a chatbot interacts with users
to understand their intent and routes tasks to specialized agents.
"""

from .workflow import ConversationWorkflow, build_graph, get_graph
from .state import GraphState
from .nodes import ChatbotNode, AgentExecutorNode, ErrorHandlerNode
from .agents import AnalyticsCrewPlaceholder, CampaignPlanningCrewPlaceholder, get_agent
from .sql_agent import SQLBasicInfoAgent

__all__ = [
    "ChatbotWorkflow",
    "build_graph",
    "get_graph",
    "GraphState",
    "ConversationWorkflow",
    "AgentExecutorNode",
    "ErrorHandlerNode",
    "SQLBasicInfoAgent",
    "AnalyticsCrewPlaceholder",
    "CampaignPlanningCrewPlaceholder",
    "get_agent"
]
