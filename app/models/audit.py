"""
Audit log models for tracking authorization decisions and user actions
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, Column, String
from .base import BaseModel


class AuditLog(BaseModel, table=True):
    """
    Audit log for authorization decisions and security events.

    Tracks who accessed what, when, and whether access was granted or denied.
    Essential for compliance, security auditing, and detecting unauthorized access attempts.
    """
    __tablename__ = "audit_logs"

    # Who
    user_id: int = Field(foreign_key="campaigners.id", index=True)
    user_email: str = Field(max_length=255, index=True)
    user_role: str = Field(max_length=50)
    agency_id: int = Field(foreign_key="agencies.id", index=True)

    # What
    action: str = Field(max_length=100, index=True, description="Action attempted (e.g., 'read', 'create', 'update', 'delete')")
    resource_type: str = Field(max_length=100, index=True, description="Type of resource (e.g., 'customer', 'agency', 'campaigner')")
    resource_id: Optional[int] = Field(default=None, index=True, description="ID of specific resource accessed")

    # Result
    allowed: bool = Field(index=True, description="Whether access was granted")
    reason: Optional[str] = Field(default=None, sa_column=Column(String), description="Reason for denial (if applicable)")

    # Request metadata
    ip_address: Optional[str] = Field(default=None, max_length=45, description="IPv4/IPv6 address")
    user_agent: Optional[str] = Field(default=None, max_length=500, description="Browser/client user agent")
    request_path: Optional[str] = Field(default=None, max_length=500, description="API endpoint path")
    request_method: Optional[str] = Field(default=None, max_length=10, description="HTTP method (GET, POST, etc.)")
