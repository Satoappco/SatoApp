#!/usr/bin/env python3
"""
HTTP/SSE Server for Google Ads MCP

Provides HTTP endpoints and Server-Sent Events for MCP protocol
instead of stdio subprocess communication.

This server wraps the Google Ads MCP tools with an HTTP API for improved performance and session management.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

# Add the Google Ads MCP to Python path
import pathlib
# In Docker, http_server.py is at /app, and google_ads_mcp is at /app/google_ads_mcp
ads_mcp_path = pathlib.Path(__file__).parent / "google_ads_mcp"
if str(ads_mcp_path) not in sys.path:
    sys.path.insert(0, str(ads_mcp_path))

# Import the MCP tools from Google Ads MCP
from ads_mcp.tools.api import list_accessible_accounts, execute_gaql


# Session models
class GoogleAdsSession:
    """Manages credentials and state for a Google Ads MCP session."""

    def __init__(
        self,
        session_id: str,
        refresh_token: str,
        customer_id: str,
        client_id: str,
        client_secret: str,
        developer_token: str,
        login_customer_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.refresh_token = refresh_token
        self.customer_id = customer_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.developer_token = developer_token
        self.login_customer_id = login_customer_id
        self.created_at = datetime.now(timezone.utc)
        self.last_accessed = self.created_at

    def update_access_time(self):
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        age = datetime.now(timezone.utc) - self.last_accessed
        return age > timedelta(minutes=timeout_minutes)

    def setup_environment(self):
        """Set environment variables for this session."""
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = self.refresh_token
        os.environ["GOOGLE_ADS_CUSTOMER_ID"] = self.customer_id
        os.environ["GOOGLE_ADS_CLIENT_ID"] = self.client_id
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = self.client_secret
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = self.developer_token
        if self.login_customer_id:
            os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = self.login_customer_id

    def cleanup_environment(self):
        """Remove environment variables for this session."""
        for key in [
            "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
        ]:
            os.environ.pop(key, None)


# Request/Response models
class InitializeRequest(BaseModel):
    """Request to initialize a new MCP session."""

    refresh_token: str
    customer_id: str
    client_id: str
    client_secret: str
    developer_token: str
    login_customer_id: Optional[str] = None


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
sessions: Dict[str, GoogleAdsSession] = {}
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
    title="Google Ads MCP HTTP Server",
    description="HTTP/SSE interface for Google Ads MCP",
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
        "service": "google-ads-mcp-http",
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
        session = GoogleAdsSession(
            session_id=session_id,
            refresh_token=request.refresh_token,
            customer_id=request.customer_id,
            client_id=request.client_id,
            client_secret=request.client_secret,
            developer_token=request.developer_token,
            login_customer_id=request.login_customer_id,
        )

        # Test credentials by setting up environment
        session.setup_environment()
        try:
            # Try to list accessible accounts to validate credentials
            from ads_mcp.tools.api import get_ads_client
            client = get_ads_client()
        except Exception as e:
            session.cleanup_environment()
            raise HTTPException(
                status_code=401,
                detail=f"Failed to validate credentials: {str(e)}",
            )
        finally:
            # Clean up environment variables after validation
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
        "customer_id": session.customer_id,
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
    session.setup_environment()

    try:
        # Route to appropriate tool
        # These tools are FunctionTool objects from fastmcp, not regular functions
        # We need to call .fn to get the underlying function
        if tool_name == "list_accessible_accounts":
            # Call the underlying function
            if hasattr(list_accessible_accounts, 'fn'):
                result = list_accessible_accounts.fn()
            else:
                result = list_accessible_accounts()
        elif tool_name == "execute_gaql":
            # Call the underlying function with arguments
            if hasattr(execute_gaql, 'fn'):
                result = execute_gaql.fn(**request.arguments)
            else:
                result = execute_gaql(**request.arguments)
        else:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        return ToolCallResponse(success=True, result=result)

    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        return ToolCallResponse(success=False, error=error_detail)

    finally:
        # Cleanup environment variables to prevent leakage
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
                "name": "list_accessible_accounts",
                "description": "Lists Google Ads customers id directly accessible by the user.",
            },
            {
                "name": "execute_gaql",
                "description": "Executes a GAQL query against the Google Ads API.",
                "parameters": {
                    "query": "str",
                    "customer_id": "str",
                    "login_customer_id": "str | None (optional)",
                },
            },
        ]
    }


def main():
    """Start the HTTP server."""
    port = int(os.getenv("MCP_HTTP_PORT", "8002"))
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")

    print(f"Starting Google Ads MCP HTTP server on {host}:{port}")
    print(f"Session timeout: 30 minutes")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
