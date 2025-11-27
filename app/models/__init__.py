"""
Database models for SatoApp
"""

from .base import BaseModel
from .users import (
    Campaigner, Agency, Customer, CampaignerSession, InviteToken,
    UserRole, UserStatus, CustomerType, CustomerStatus, ClientType
)
from .agents import AgentConfig, RoutingRule
from .analytics import (
    DigitalAsset, Connection, KpiGoal, KpiValue, UserPropertySelection, KpiCatalog, KpiSettings,
    AssetType, AuthType, Audience, Metrics
)
from .customer_data import RTMTable, QuestionsTable
from .chat_feedback import ChatFeedback, FeedbackType
from .tasks import Task, TaskPriority, TaskStatus

__all__ = [
    # Base
    "BaseModel",

    # Users and related models
    "Campaigner", "Agency", "Customer", "CampaignerSession", "InviteToken",
    "UserRole", "UserStatus", "CustomerType", "CustomerStatus", "ClientType",

    # Agents
    "AgentConfig", "RoutingRule",

    # Analytics and assets
    "DigitalAsset", "Connection", "KpiGoal", "KpiValue", "UserPropertySelection", "KpiCatalog", "KpiSettings",
    "AssetType", "AuthType", "Audience", "Metrics",

    # Customer data tables
    "RTMTable", "QuestionsTable",

    # Chat feedback
    "ChatFeedback", "FeedbackType",

    # Tasks
    "Task", "TaskPriority", "TaskStatus"
]
