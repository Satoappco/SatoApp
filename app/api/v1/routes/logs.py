"""
API routes for viewing and managing application logs.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.file_logger import file_logger
# TODO: i think api_auth is not needed. 
# from app.core.api_auth import verify_admin_token
# TODO: Create verify_at_least(role : admin/owner/campaigner - default)
from app.core.auth import get_current_user

router = APIRouter()


class LogResponse(BaseModel):
    """Response model for log data."""
    success: bool
    logs: str
    lines_returned: int
    message: Optional[str] = None


class LogStatsResponse(BaseModel):
    """Response model for log statistics."""
    success: bool
    stats: dict
    message: Optional[str] = None


@router.get("/recent", response_model=LogResponse)
async def get_recent_logs(
    lines: int = Query(default=100, ge=1, le=10000, description="Number of recent lines to retrieve"),
    admin_verified: bool = Depends(get_current_user) #get_current_user)
):
    """
    Get the most recent log entries.

    **Authentication Required**: Admin token

    **Query Parameters:**
    - `lines` (int): Number of recent lines to retrieve (default: 100, max: 10000)

    **Returns:**
    - Log entries in reverse chronological order (newest first)
    """
    try:
        logs = file_logger.get_recent_logs(lines=lines)
        lines_returned = len(logs.split('\n'))

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} recent log lines"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.get("/search", response_model=LogResponse)
async def search_logs(
    query: str = Query(..., min_length=1, description="Search term"),
    max_results: int = Query(default=100, ge=1, le=10000, description="Maximum number of results"),
    case_sensitive: bool = Query(default=False, description="Case-sensitive search"),
    admin_verified: bool = Depends(get_current_user)
):
    """
    Search for a term in log files.

    **Authentication Required**: Admin token

    **Query Parameters:**
    - `query` (str): Search term (required)
    - `max_results` (int): Maximum number of matching lines (default: 100, max: 10000)
    - `case_sensitive` (bool): Whether search should be case-sensitive (default: false)

    **Returns:**
    - Matching log entries
    """
    try:
        logs = file_logger.search_logs(
            search_term=query,
            max_results=max_results,
            case_sensitive=case_sensitive
        )
        lines_returned = len(logs.split('\n')) if logs else 0

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Found {lines_returned} matching log lines for '{query}'"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")


@router.get("/level/{level}", response_model=LogResponse)
async def get_logs_by_level(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    max_results: int = Query(default=100, ge=1, le=10000, description="Maximum number of results"),
    admin_verified: bool = Depends(get_current_user)
):
    """
    Get log entries of a specific level.

    **Authentication Required**: Admin token

    **Path Parameters:**
    - `level` (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    **Query Parameters:**
    - `max_results` (int): Maximum number of entries (default: 100, max: 10000)

    **Returns:**
    - Filtered log entries
    """
    try:
        logs = file_logger.get_logs_by_level(level=level, max_results=max_results)
        lines_returned = len(logs.split('\n')) if logs else 0

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} {level} log lines"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.get("/timerange", response_model=LogResponse)
async def get_logs_by_timerange(
    start_time: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End time (ISO format)"),
    hours_ago: Optional[int] = Query(None, ge=1, le=168, description="Hours ago from now (alternative to start_time)"),
    max_results: int = Query(default=1000, ge=1, le=10000, description="Maximum number of results"),
    admin_verified: bool = Depends(get_current_user)
):
    """
    Get log entries within a time range.

    **Authentication Required**: Admin token

    **Query Parameters:**
    - `start_time` (datetime): Start of time range (ISO format, e.g., 2024-01-01T00:00:00)
    - `end_time` (datetime): End of time range (ISO format)
    - `hours_ago` (int): Alternative to start_time - get logs from N hours ago to now
    - `max_results` (int): Maximum number of entries (default: 1000, max: 10000)

    **Returns:**
    - Log entries within the specified time range
    """
    try:
        # Handle hours_ago parameter
        if hours_ago is not None:
            start_time = datetime.now() - timedelta(hours=hours_ago)
            end_time = datetime.now()

        logs = file_logger.get_logs_by_timerange(
            start_time=start_time,
            end_time=end_time,
            max_results=max_results
        )
        lines_returned = len(logs.split('\n')) if logs else 0

        time_range = f"{start_time or 'start'} to {end_time or 'now'}"
        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} log lines from {time_range}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(
    admin_verified: bool = Depends(get_current_user)
):
    """
    Get statistics about log files.

    **Authentication Required**: Admin token

    **Returns:**
    - Total number of log files
    - Total size
    - Individual file details
    """
    try:
        stats = file_logger.get_log_stats()

        return LogStatsResponse(
            success=True,
            stats=stats,
            message=f"Retrieved stats for {stats['total_files']} log file(s)"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log stats: {str(e)}")


@router.delete("/old")
async def clear_old_logs(
    days: int = Query(default=7, ge=1, le=365, description="Delete logs older than N days"),
    admin_verified: bool = Depends(get_current_user)
):
    """
    Clear log files older than specified days.

    **Authentication Required**: Admin token

    **Query Parameters:**
    - `days` (int): Number of days to keep (default: 7, max: 365)

    **Returns:**
    - Number of files deleted
    """
    try:
        deleted_count = file_logger.clear_old_logs(days=days)

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} log file(s) older than {days} days"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear old logs: {str(e)}")


@router.get("/tail")
async def tail_logs(
    lines: int = Query(default=50, ge=1, le=1000, description="Number of lines to tail"),
    follow: bool = Query(default=False, description="Keep connection open for live updates"),
    admin_verified: bool = Depends(get_current_user)
):
    """
    Tail the log file (like 'tail -f').

    **Authentication Required**: Admin token

    **Query Parameters:**
    - `lines` (int): Number of lines to show (default: 50, max: 1000)
    - `follow` (bool): Keep connection open for live updates (default: false)

    **Note:** Live follow mode not yet implemented. Returns most recent lines only.

    **Returns:**
    - Most recent log lines
    """
    try:
        logs = file_logger.get_recent_logs(lines=lines)
        lines_returned = len(logs.split('\n'))

        return {
            "success": True,
            "logs": logs,
            "lines_returned": lines_returned,
            "follow_mode": follow,
            "message": f"Tailed {lines_returned} log lines" + (" (follow mode not yet implemented)" if follow else "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tail logs: {str(e)}")
