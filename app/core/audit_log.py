"""
Audit logging for authorization decisions
Tracks who accessed what and when
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from app.models.users import Campaigner, UserRole

logger = logging.getLogger(__name__)


def log_authorization_check(
    user: Campaigner,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    allowed: bool = True,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None,
):
    """
    Log an authorization decision to both application logger and database.

    Args:
        user: User who attempted the action
        action: Action attempted (e.g., "read", "update", "delete")
        resource_type: Type of resource (e.g., "customer", "agency")
        resource_id: ID of specific resource
        allowed: Whether access was granted
        reason: Reason for denial (if applicable)
        ip_address: Client IP address (optional)
        user_agent: Client user agent (optional)
        request_path: API endpoint path (optional)
        request_method: HTTP method (optional)
    """
    # Log to application logger
    if allowed:
        logger.info(
            f"✅ [AUTHZ] {user.email} ({user.role.value}) {action} {resource_type}:{resource_id}"
        )
    else:
        logger.warning(
            f"🚫 [AUTHZ] {user.email} ({user.role.value}) DENIED {action} {resource_type}:{resource_id} - {reason}"
        )

    # Persist to database
    try:
        from app.models.audit import AuditLog
        from app.config.database import get_session

        with get_session() as session:
            audit_entry = AuditLog(
                user_id=user.id if user.id is not None else 0,
                user_email=user.email,
                user_role=user.role.value,
                agency_id=user.agency_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                allowed=allowed,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                request_method=request_method,
            )
            session.add(audit_entry)
            session.commit()
    except Exception as e:
        # Don't fail the request if audit logging fails
        logger.error(f"❌ [AUTHZ] Failed to persist audit log to database: {str(e)}")
