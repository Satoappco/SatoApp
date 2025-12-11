"""
Connection Failure Tracking Utilities

Provides centralized functions for logging connection failures and successes to the database.
This helps track connection health and provides visibility into why connections fail.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from app.config.database import get_session
from app.models.analytics import Connection
from sqlmodel import select

logger = logging.getLogger(__name__)


def record_connection_failure(
    connection_id: int,
    failure_reason: str,
    also_set_needs_reauth: bool = False
) -> bool:
    """
    Record a connection failure in the database.

    Args:
        connection_id: ID of the connection that failed
        failure_reason: Reason for failure (e.g., 'token_refresh_failed', 'mcp_validation_failed', 'invalid_credentials')
        also_set_needs_reauth: Whether to also set the needs_reauth flag to True

    Returns:
        True if the failure was recorded successfully, False otherwise
    """
    try:
        with get_session() as session:
            connection = session.get(Connection, connection_id)
            if not connection:
                logger.warning(f"⚠️  Connection {connection_id} not found, cannot record failure")
                return False

            # Update failure tracking fields
            connection.last_failure_at = datetime.now(timezone.utc)
            connection.failure_count = (connection.failure_count or 0) + 1
            connection.failure_reason = failure_reason

            # Optionally set needs_reauth flag
            if also_set_needs_reauth:
                connection.needs_reauth = True

            session.add(connection)
            session.commit()

            logger.info(
                f"✅ Recorded failure for connection {connection_id}: {failure_reason} "
                f"(failure count: {connection.failure_count})"
            )
            return True

    except Exception as e:
        logger.error(f"❌ Failed to record connection failure: {e}")
        return False


def record_connection_success(
    connection_id: int,
    reset_failure_count: bool = True
) -> bool:
    """
    Record a successful connection validation.

    Args:
        connection_id: ID of the connection that succeeded
        reset_failure_count: Whether to reset the failure count to 0

    Returns:
        True if the success was recorded successfully, False otherwise
    """
    try:
        with get_session() as session:
            connection = session.get(Connection, connection_id)
            if not connection:
                logger.warning(f"⚠️  Connection {connection_id} not found, cannot record success")
                return False

            # Update validation timestamp
            connection.last_validated_at = datetime.now(timezone.utc)
            connection.last_used_at = datetime.now(timezone.utc)

            # Reset failure tracking
            if reset_failure_count:
                connection.failure_count = 0
                connection.failure_reason = None
                connection.last_failure_at = None

            # Clear needs_reauth flag if set
            connection.needs_reauth = False

            session.add(connection)
            session.commit()

            logger.info(f"✅ Recorded success for connection {connection_id}")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to record connection success: {e}")
        return False


def get_connection_by_digital_asset_id(
    digital_asset_id: int,
    campaigner_id: Optional[int] = None
) -> Optional[Connection]:
    """
    Get an active connection for a digital asset.

    Args:
        digital_asset_id: ID of the digital asset
        campaigner_id: Optional campaigner ID to filter by

    Returns:
        Connection object if found, None otherwise
    """
    try:
        with get_session() as session:
            query = select(Connection).where(
                Connection.digital_asset_id == digital_asset_id,
                Connection.revoked == False
            )

            if campaigner_id:
                query = query.where(Connection.campaigner_id == campaigner_id)

            connection = session.exec(query).first()
            return connection

    except Exception as e:
        logger.error(f"❌ Failed to get connection by digital asset ID: {e}")
        return None


def get_failing_connections(
    customer_id: Optional[int] = None,
    min_failure_count: int = 1
) -> list[Connection]:
    """
    Get connections that have failures.

    Args:
        customer_id: Optional customer ID to filter by
        min_failure_count: Minimum failure count to consider (default: 1)

    Returns:
        List of Connection objects with failures
    """
    try:
        with get_session() as session:
            query = select(Connection).where(
                Connection.failure_count >= min_failure_count,
                Connection.revoked == False
            )

            if customer_id:
                query = query.where(Connection.customer_id == customer_id)

            connections = session.exec(query).all()
            return list(connections)

    except Exception as e:
        logger.error(f"❌ Failed to get failing connections: {e}")
        return []


def should_retry_connection(connection: Connection, max_failures: int = 3) -> bool:
    """
    Determine if a connection should be retried based on failure count.

    Args:
        connection: Connection object to check
        max_failures: Maximum number of failures before giving up (default: 3)

    Returns:
        True if the connection should be retried, False if too many failures
    """
    failure_count = connection.failure_count or 0
    return failure_count < max_failures
