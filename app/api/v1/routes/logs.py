"""
API routes for viewing and managing application logs.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, Literal, AsyncGenerator
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio
import os
import json

from app.core.file_logger import file_logger
from app.core.rbac import require_owner
from app.models.users import Campaigner

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
    lines: int = Query(
        default=100, ge=1, le=10000, description="Number of recent lines to retrieve"
    ),
    current_user=Depends(require_owner()),
):
    """
    Get the most recent log entries.

    **Authentication Required**: Owner token

    **Query Parameters:**
    - `lines` (int): Number of recent lines to retrieve (default: 100, max: 10000)

    **Returns:**
    - Log entries in reverse chronological order (newest first)
    """
    try:
        logs = file_logger.get_recent_logs(lines=lines)
        lines_returned = len(logs.split("\n"))

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} recent log lines",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve logs: {str(e)}"
        )


@router.get("/search", response_model=LogResponse)
async def search_logs(
    query: str = Query(..., min_length=1, description="Search term"),
    max_results: int = Query(
        default=100, ge=1, le=10000, description="Maximum number of results"
    ),
    case_sensitive: bool = Query(default=False, description="Case-sensitive search"),
    current_user=Depends(require_owner()),
):
    """
    Search for a term in log files.

    **Authentication Required**: Owner token

    **Query Parameters:**
    - `query` (str): Search term (required)
    - `max_results` (int): Maximum number of matching lines (default: 100, max: 10000)
    - `case_sensitive` (bool): Whether search should be case-sensitive (default: false)

    **Returns:**
    - Matching log entries
    """
    try:
        logs = file_logger.search_logs(
            search_term=query, max_results=max_results, case_sensitive=case_sensitive
        )
        lines_returned = len(logs.split("\n")) if logs else 0

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Found {lines_returned} matching log lines for '{query}'",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")


@router.get("/level/{level}", response_model=LogResponse)
async def get_logs_by_level(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    max_results: int = Query(
        default=100, ge=1, le=10000, description="Maximum number of results"
    ),
    current_user=Depends(require_owner()),
):
    """
    Get log entries of a specific level.

    **Authentication Required**: Owner token

    **Path Parameters:**
    - `level` (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    **Query Parameters:**
    - `max_results` (int): Maximum number of entries (default: 100, max: 10000)

    **Returns:**
    - Filtered log entries
    """
    try:
        logs = file_logger.get_logs_by_level(level=level, max_results=max_results)
        lines_returned = len(logs.split("\n")) if logs else 0

        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} {level} log lines",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve logs: {str(e)}"
        )


@router.get("/timerange", response_model=LogResponse)
async def get_logs_by_timerange(
    start_time: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End time (ISO format)"),
    hours_ago: Optional[int] = Query(
        None, ge=1, le=168, description="Hours ago from now (alternative to start_time)"
    ),
    max_results: int = Query(
        default=1000, ge=1, le=10000, description="Maximum number of results"
    ),
    current_user=Depends(require_owner()),
):
    """
    Get log entries within a time range.

    **Authentication Required**: Owner token

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
            start_time=start_time, end_time=end_time, max_results=max_results
        )
        lines_returned = len(logs.split("\n")) if logs else 0

        time_range = f"{start_time or 'start'} to {end_time or 'now'}"
        return LogResponse(
            success=True,
            logs=logs,
            lines_returned=lines_returned,
            message=f"Retrieved {lines_returned} log lines from {time_range}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve logs: {str(e)}"
        )


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(current_user: Campaigner = Depends(require_owner())):
    """
    Get statistics about log files.

    **Authentication Required**: Owner token

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
            message=f"Retrieved stats for {stats['total_files']} log file(s)",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve log stats: {str(e)}"
        )


@router.delete("/old")
async def clear_old_logs(
    days: int = Query(
        default=7, ge=1, le=365, description="Delete logs older than N days"
    ),
    current_user=Depends(require_owner()),
):
    """
    Clear log files older than specified days.

    **Authentication Required**: Owner token

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
            "message": f"Deleted {deleted_count} log file(s) older than {days} days",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear old logs: {str(e)}"
        )


@router.get("/tail")
async def tail_logs(
    lines: int = Query(
        default=50, ge=1, le=1000, description="Number of lines to tail"
    ),
    follow: bool = Query(
        default=False, description="Keep connection open for live updates"
    ),
    current_user=Depends(require_owner()),
):
    """
    Tail the log file (like 'tail -f').

    **Authentication Required**: Owner token

    **Query Parameters:**
    - `lines` (int): Number of lines to show (default: 50, max: 1000)
    - `follow` (bool): Keep connection open for live updates (default: false)

    **Note:** Live follow mode not yet implemented. Returns most recent lines only.

    **Returns:**
    - Most recent log lines
    """
    try:
        logs = file_logger.get_recent_logs(lines=lines)
        lines_returned = len(logs.split("\n"))

        return {
            "success": True,
            "logs": logs,
            "lines_returned": lines_returned,
            "follow_mode": follow,
            "message": f"Tailed {lines_returned} log lines"
            + (" (follow mode not yet implemented)" if follow else ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tail logs: {str(e)}")




@router.get("/stream")
async def stream_logs(
    lines: int = Query(
        default=50, ge=1, le=1000, description="Number of initial lines to send"
    ),
    current_user: Campaigner = Depends(require_owner()),
):
    """
    Stream log updates in real-time using Server-Sent Events (SSE).

    **Authentication Required**: Owner authentication (via standard auth headers)

    **Query Parameters:**
    - `lines` (int): Number of initial lines to send (default: 50, max: 1000)

    **Returns:**
    - Server-Sent Events stream with log updates

    **Note**: Frontend must use fetch() with streaming instead of EventSource
    because EventSource doesn't support custom authorization headers.
    """

    async def generate_log_stream() -> AsyncGenerator[str, None]:
        """Generate log updates for SSE streaming."""
        # Get initial log lines
        initial_logs = file_logger.get_recent_logs(lines=lines)

        # Send initial logs as the first event
        initial_data = {
            "type": "initial",
            "logs": initial_logs,
            "lines_count": len(initial_logs.split("\n")) if initial_logs else 0,
            "timestamp": datetime.now().isoformat(),
        }
        yield f"data: {json.dumps(initial_data)}\n\n"

        # Track the last position in the log file
        log_file_path = file_logger.log_file
        last_size = 0

        # Get initial file size
        if os.path.exists(log_file_path):
            last_size = os.path.getsize(log_file_path)

        try:
            while True:
                # Check if file exists and has grown
                if os.path.exists(log_file_path):
                    current_size = os.path.getsize(log_file_path)

                    if current_size > last_size:
                        # Read new content
                        with open(log_file_path, 'r', encoding='utf-8') as f:
                            f.seek(last_size)
                            new_content = f.read()

                        if new_content.strip():
                            # Send new log lines
                            update_data = {
                                "type": "update",
                                "logs": new_content,
                                "lines_count": len(new_content.split("\n")),
                                "timestamp": datetime.now().isoformat(),
                            }
                            yield f"data: {json.dumps(update_data)}\n\n"

                        last_size = current_size

                # Check for log rotation (file size reset)
                elif last_size > 0:
                    # File was rotated, send everything from the new file
                    initial_logs = file_logger.get_recent_logs(lines=lines)
                    rotation_data = {
                        "type": "rotation",
                        "logs": initial_logs,
                        "lines_count": len(initial_logs.split("\n")) if initial_logs else 0,
                        "timestamp": datetime.now().isoformat(),
                    }
                    yield f"data: {json.dumps(rotation_data)}\n\n"
                    last_size = os.path.getsize(log_file_path) if os.path.exists(log_file_path) else 0

                # Wait before checking again
                await asyncio.sleep(0.5)  # Check every 500ms for new logs

        except asyncio.CancelledError:
            # Client disconnected
            yield f"data: {json.dumps({'type': 'disconnect', 'message': 'Stream disconnected'})}\n\n"
        except Exception as e:
            # Send error to client
            error_data = {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
