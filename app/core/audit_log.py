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
):
    """
    Log an authorization decision.

    Args:
        user: User who attempted the action
        action: Action attempted (e.g., "read", "update", "delete")
        resource_type: Type of resource (e.g., "customer", "agency")
        resource_id: ID of specific resource
        allowed: Whether access was granted
        reason: Reason for denial (if applicable)
    """
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "user_email": user.email,
        "user_role": user.role.value,
        "agency_id": user.agency_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "allowed": allowed,
        "reason": reason,
    }

    if allowed:
        logger.info(
            f"✅ [AUTHZ] {user.email} ({user.role.value}) {action} {resource_type}:{resource_id}"
        )
    else:
        logger.warning(
            f"🚫 [AUTHZ] {user.email} ({user.role.value}) DENIED {action} {resource_type}:{resource_id} - {reason}"
        )
