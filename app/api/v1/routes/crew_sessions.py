"""API endpoints for CrewAI session recordings."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pathlib import Path
import json
from datetime import datetime

from app.core.auth import get_current_user
from app.models.users import Campaigner

router = APIRouter(prefix="/crew-sessions", tags=["crew-sessions"])


@router.get("/{session_id}")
async def get_session_recording(
    session_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get session recording by ID.

    Args:
        session_id: Session UUID
        current_user: Authenticated user

    Returns:
        Complete session recording with all tasks, steps, and tool usage
    """
    sessions_dir = Path("crew_sessions")

    # Find session file
    session_files = list(sessions_dir.glob(f"session_{session_id}_*.json"))

    if not session_files:
        raise HTTPException(status_code=404, detail="Session not found")

    # Read the most recent file if multiple exist
    session_file = max(session_files, key=lambda p: p.stat().st_mtime)

    try:
        with open(session_file, 'r') as f:
            session_data = json.load(f)

        # TODO: Add permission check - verify user has access to this customer's sessions
        # customer_id = session_data.get("summary", {}).get("customer_id")
        # if not has_access(current_user, customer_id):
        #     raise HTTPException(status_code=403, detail="Access denied")

        return session_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading session: {str(e)}")


@router.get("/customer/{customer_id}")
async def list_customer_sessions(
    customer_id: int,
    limit: int = 50,
    current_user: Campaigner = Depends(get_current_user)
):
    """List all session recordings for a customer.

    Args:
        customer_id: Customer ID
        limit: Maximum number of sessions to return
        current_user: Authenticated user

    Returns:
        List of session summaries
    """
    sessions_dir = Path("crew_sessions")

    if not sessions_dir.exists():
        return []

    # TODO: Add permission check
    # if not has_access(current_user, customer_id):
    #     raise HTTPException(status_code=403, detail="Access denied")

    sessions = []

    try:
        for session_file in sorted(sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(sessions) >= limit:
                break

            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)

                summary = session_data.get("summary", {})

                # Filter by customer_id
                if summary.get("customer_id") == customer_id:
                    sessions.append({
                        "session_id": summary.get("session_id"),
                        "started_at": summary.get("started_at"),
                        "duration_seconds": summary.get("duration_seconds"),
                        "total_tasks": summary.get("total_tasks"),
                        "completed_tasks": summary.get("completed_tasks"),
                        "total_steps": summary.get("total_steps"),
                        "tools_used_count": summary.get("tools_used_count"),
                        "errors_count": summary.get("errors_count"),
                        "query": summary.get("metadata", {}).get("query"),
                        "platforms": summary.get("metadata", {}).get("platforms")
                    })

            except Exception as e:
                # Skip files that can't be read
                continue

        return sessions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")


@router.get("/")
async def list_all_sessions(
    limit: int = 100,
    current_user: Campaigner = Depends(get_current_user)
):
    """List all session recordings (admin only).

    Args:
        limit: Maximum number of sessions to return
        current_user: Authenticated user

    Returns:
        List of session summaries
    """
    # TODO: Add admin check
    # if current_user.role != "ADMIN":
    #     raise HTTPException(status_code=403, detail="Admin access required")

    sessions_dir = Path("crew_sessions")

    if not sessions_dir.exists():
        return []

    sessions = []

    try:
        for session_file in sorted(sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(sessions) >= limit:
                break

            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)

                summary = session_data.get("summary", {})
                sessions.append({
                    "session_id": summary.get("session_id"),
                    "customer_id": summary.get("customer_id"),
                    "started_at": summary.get("started_at"),
                    "duration_seconds": summary.get("duration_seconds"),
                    "total_tasks": summary.get("total_tasks"),
                    "completed_tasks": summary.get("completed_tasks"),
                    "total_steps": summary.get("total_steps"),
                    "tools_used_count": summary.get("tools_used_count"),
                    "errors_count": summary.get("errors_count"),
                    "query": summary.get("metadata", {}).get("query"),
                    "platforms": summary.get("metadata", {}).get("platforms")
                })

            except Exception as e:
                # Skip files that can't be read
                continue

        return sessions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")
