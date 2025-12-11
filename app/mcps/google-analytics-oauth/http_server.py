#!/usr/bin/env python3
"""
HTTP/SSE Server for Google Analytics MCP

Provides HTTP endpoints and Server-Sent Events for MCP protocol
instead of stdio subprocess communication.

This server wraps the existing ga4_oauth_server.py MCP tools with
an HTTP API for improved performance and session management.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

# Import the MCP tools from ga4_oauth_server
from ga4_oauth_server import (
    get_account_summaries,
    get_property_details,
    run_report,
    _create_oauth_credentials,
)


# Session models
class GA4Session:
    """Manages credentials and state for a GA4 MCP session."""

    def __init__(
        self,
        session_id: str,
        refresh_token: str,
        property_id: str,
        client_id: str,
        client_secret: str,
    ):
        self.session_id = session_id
        self.refresh_token = refresh_token
        self.property_id = property_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.created_at = datetime.now(timezone.utc)
        self.last_accessed = self.created_at
        self.credentials = None

    def update_access_time(self):
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        age = datetime.now(timezone.utc) - self.last_accessed
        return age > timedelta(minutes=timeout_minutes)

    def setup_environment(self):
        """Set environment variables for this session."""
        os.environ["GOOGLE_ANALYTICS_REFRESH_TOKEN"] = self.refresh_token
        os.environ["GOOGLE_ANALYTICS_PROPERTY_ID"] = self.property_id
        os.environ["GOOGLE_ANALYTICS_CLIENT_ID"] = self.client_id
        os.environ["GOOGLE_ANALYTICS_CLIENT_SECRET"] = self.client_secret

    def cleanup_environment(self):
        """Remove environment variables for this session."""
        for key in [
            "GOOGLE_ANALYTICS_REFRESH_TOKEN",
            "GOOGLE_ANALYTICS_PROPERTY_ID",
            "GOOGLE_ANALYTICS_CLIENT_ID",
            "GOOGLE_ANALYTICS_CLIENT_SECRET",
        ]:
            os.environ.pop(key, None)


# Request/Response models
class InitializeRequest(BaseModel):
    """Request to initialize a new MCP session."""

    refresh_token: str
    property_id: str
    client_id: str
    client_secret: str


class InitializeResponse(BaseModel):
    """Response after initializing session."""

    session_id: str
    status: str
    message: str


class ToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """Response from tool call."""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


# Global session store
sessions: Dict[str, GA4Session] = {}
session_lock = asyncio.Lock()


# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    # Startup: start cleanup task
    cleanup_task = asyncio.create_task(cleanup_expired_sessions())

    yield

    # Shutdown: cancel cleanup task and clear sessions
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    async with session_lock:
        for session in sessions.values():
            session.cleanup_environment()
        sessions.clear()


# Create FastAPI app
app = FastAPI(
    title="Google Analytics MCP HTTP Server",
    description="HTTP/SSE interface for Google Analytics MCP",
    version="1.0.0",
    lifespan=lifespan,
)


# Session cleanup task
async def cleanup_expired_sessions():
    """Periodically clean up expired sessions."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute

            async with session_lock:
                expired_ids = [
                    sid for sid, session in sessions.items() if session.is_expired()
                ]

                for sid in expired_ids:
                    session = sessions.pop(sid, None)
                    if session:
                        session.cleanup_environment()
                        print(f"Cleaned up expired session: {sid}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in cleanup task: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "google-analytics-mcp-http",
        "active_sessions": len(sessions),
    }


# Initialize session
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_session(request: InitializeRequest):
    """Initialize a new MCP session with credentials."""
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())

        # Create session
        session = GA4Session(
            session_id=session_id,
            refresh_token=request.refresh_token,
            property_id=request.property_id,
            client_id=request.client_id,
            client_secret=request.client_secret,
        )

        # Test credentials by setting up environment and creating credentials
        session.setup_environment()
        try:
            credentials = _create_oauth_credentials()
            session.credentials = credentials
        except Exception as e:
            session.cleanup_environment()
            raise HTTPException(
                status_code=401,
                detail=f"Failed to validate credentials: {str(e)}",
            )
        finally:
            # Clean up environment variables after validation
            # They will be set again when tools are called
            session.cleanup_environment()

        # Store session
        async with session_lock:
            sessions[session_id] = session

        return InitializeResponse(
            session_id=session_id,
            status="success",
            message="Session initialized successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize session: {str(e)}"
        )


# Get session info
@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get information about a session."""
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "property_id": session.property_id,
        "created_at": session.created_at.isoformat(),
        "last_accessed": session.last_accessed.isoformat(),
        "is_expired": session.is_expired(),
    }


# Delete session
@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and cleanup resources."""
    async with session_lock:
        session = sessions.pop(session_id, None)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.cleanup_environment()

    return {"status": "success", "message": "Session deleted"}


# SSE endpoint for MCP protocol
@app.get("/sse/{session_id}")
async def sse_endpoint(session_id: str, request: Request):
    """Server-Sent Events endpoint for MCP protocol communication."""
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield f"data: {{'type': 'connected', 'session_id': '{session_id}'}}\n\n"

            # Keep connection alive with periodic heartbeats
            while True:
                if await request.is_disconnected():
                    break

                # Send heartbeat every 15 seconds
                yield f"data: {{'type': 'heartbeat', 'timestamp': '{datetime.now(timezone.utc).isoformat()}'}}\n\n"
                await asyncio.sleep(15)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield f"data: {{'type': 'error', 'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Tool call endpoint
@app.post("/tool/{session_id}/{tool_name}", response_model=ToolCallResponse)
async def call_tool(session_id: str, tool_name: str, request: ToolCallRequest):
    """Call an MCP tool with the given arguments."""
    # Get session
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update access time
    session.update_access_time()

    # Setup environment for this request
    # CRITICAL: Set environment variables before calling tools
    session.setup_environment()

    try:
        # Route to appropriate tool
        # Note: Tools will read from environment variables set above
        if tool_name == "get_account_summaries":
            result = await get_account_summaries()
        elif tool_name == "get_property_details":
            result = await get_property_details(**request.arguments)
        elif tool_name == "run_report":
            result = await run_report(**request.arguments)
        else:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        return ToolCallResponse(success=True, result=result)

    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        return ToolCallResponse(success=False, error=error_detail)

    finally:
        # Cleanup environment variables to prevent leakage between sessions
        session.cleanup_environment()


# List available tools
@app.get("/tools/{session_id}")
async def list_tools(session_id: str):
    """List available MCP tools."""
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.update_access_time()

    return {
        "tools": [
            {
                "name": "get_account_summaries",
                "description": "Retrieves information about the user's Google Analytics accounts and properties.",
            },
            {
                "name": "get_property_details",
                "description": "Returns details about a property.",
                "parameters": {"property_id": "int | str (optional)"},
            },
            {
                "name": "run_report",
                "description": "Run a Google Analytics 4 report.",
                "parameters": {
                    "property_id": "int | str (optional)",
                    "dimensions": "List[str] (optional)",
                    "metrics": "List[str] (optional)",
                    "date_range_start": "str (default: '30daysAgo')",
                    "date_range_end": "str (default: 'today')",
                    "limit": "int (default: 10)",
                },
            },
        ]
    }


def main():
    """Start the HTTP server."""
    port = int(os.getenv("MCP_HTTP_PORT", "8001"))
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")

    print(f"Starting Google Analytics MCP HTTP server on {host}:{port}")
    print(f"Session timeout: 30 minutes")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
