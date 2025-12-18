#!/usr/bin/env python3
"""
HTTP/SSE Server for Deep Research MCP

Provides HTTP endpoints and Server-Sent Events for deep research protocol.
This server wraps the open_deep_research LangGraph workflow with an HTTP API
for improved performance and session management.
"""

import asyncio
import os
import sys
import uuid
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

# Import research engine
from research_engine import ResearchEngine


# Session models
class DeepResearchSession:
    """Manages configuration and state for a deep research session."""

    def __init__(
        self,
        session_id: str,
        campaigner_id: int,
        customer_id: Optional[int] = None,
        llm_config: Optional[Dict[str, str]] = None,
        search_provider: str = "tavily",
        research_depth: str = "medium",
        max_iterations: int = 5,
    ):
        self.session_id = session_id
        self.campaigner_id = campaigner_id
        self.customer_id = customer_id
        self.llm_config = llm_config or {}
        self.search_provider = search_provider
        self.research_depth = research_depth
        self.max_iterations = max_iterations
        self.created_at = datetime.now(timezone.utc)
        self.last_accessed = self.created_at
        self.current_state: Optional[Dict] = None
        self.status = "initialized"  # initialized, running, completed, error, cancelled

    def update_access_time(self):
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        age = datetime.now(timezone.utc) - self.last_accessed
        return age > timedelta(minutes=timeout_minutes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "campaigner_id": self.campaigner_id,
            "customer_id": self.customer_id,
            "llm_config": self.llm_config,
            "search_provider": self.search_provider,
            "research_depth": self.research_depth,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "status": self.status,
        }


# Request/Response models
class InitializeRequest(BaseModel):
    """Request to initialize a new research session."""

    campaigner_id: int
    customer_id: Optional[int] = None
    llm_config: Optional[Dict[str, str]] = None
    search_provider: str = "tavily"
    research_depth: str = "medium"
    max_iterations: int = 5


class InitializeResponse(BaseModel):
    """Response after initializing session."""

    session_id: str
    status: str
    message: str


class ResearchRequest(BaseModel):
    """Request to conduct research."""

    query: str
    streaming: bool = False


class ResearchResponse(BaseModel):
    """Response from research execution."""

    success: bool
    session_id: str
    report: Optional[str] = None
    sources: list = []
    execution_time_ms: int = 0
    tokens_used: int = 0
    error: Optional[str] = None
    steps_completed: int = 0


# Global session store
sessions: Dict[str, DeepResearchSession] = {}
session_lock = asyncio.Lock()

# Global research engine
research_engine: Optional[ResearchEngine] = None


# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    global research_engine

    # Startup: initialize research engine and cleanup task
    print("[DeepResearch] Initializing research engine...")
    research_engine = ResearchEngine()

    cleanup_task = asyncio.create_task(cleanup_expired_sessions())

    yield

    # Shutdown: cancel cleanup task and clear sessions
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    async with session_lock:
        sessions.clear()


# Create FastAPI app
app = FastAPI(
    title="Deep Research MCP HTTP Server",
    description="HTTP/SSE interface for open_deep_research",
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
                        print(f"[DeepResearch] Cleaned up expired session: {sid}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[DeepResearch] Error in cleanup task: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "deep-research-mcp-http",
        "active_sessions": len(sessions),
    }


# Initialize session
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_session(request: InitializeRequest):
    """Initialize a new research session with configuration."""
    try:
        # Generate session ID
        session_id = f"res_{uuid.uuid4().hex[:12]}"

        # Create session
        session = DeepResearchSession(
            session_id=session_id,
            campaigner_id=request.campaigner_id,
            customer_id=request.customer_id,
            llm_config=request.llm_config,
            search_provider=request.search_provider,
            research_depth=request.research_depth,
            max_iterations=request.max_iterations,
        )

        # Store session
        async with session_lock:
            sessions[session_id] = session

        print(f"[DeepResearch] Initialized session {session_id} for campaigner {request.campaigner_id}")

        return InitializeResponse(
            session_id=session_id,
            status="success",
            message="Session initialized successfully",
        )

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

    return session.to_dict()


# Delete session
@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and cleanup resources."""
    async with session_lock:
        session = sessions.pop(session_id, None)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    print(f"[DeepResearch] Deleted session {session_id}")

    return {"status": "success", "message": "Session deleted"}


# Execute research (synchronous)
@app.post("/research/{session_id}", response_model=ResearchResponse)
async def execute_research(session_id: str, request: ResearchRequest):
    """Execute research synchronously."""
    # Get session
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update access time and status
    session.update_access_time()
    session.status = "running"

    start_time = time.time()

    try:
        print(f"[DeepResearch] Starting research for session {session_id}: {request.query[:100]}...")

        # Execute research via engine
        result = await research_engine.execute_research(
            query=request.query,
            llm_config=session.llm_config,
            search_provider=session.search_provider,
            max_iterations=session.max_iterations,
            streaming=False
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Update session status
        session.status = "completed" if result["success"] else "error"
        session.current_state = result

        print(f"[DeepResearch] Completed research for session {session_id} in {execution_time_ms}ms")

        return ResearchResponse(
            success=result["success"],
            session_id=session_id,
            report=result.get("report"),
            sources=result.get("sources", []),
            execution_time_ms=execution_time_ms,
            tokens_used=result.get("tokens_used", 0),
            error=result.get("error"),
            steps_completed=result.get("steps_completed", 0)
        )

    except Exception as e:
        session.status = "error"
        execution_time_ms = int((time.time() - start_time) * 1000)

        print(f"[DeepResearch] Research failed for session {session_id}: {e}")

        return ResearchResponse(
            success=False,
            session_id=session_id,
            error=str(e),
            execution_time_ms=execution_time_ms
        )


# Stream research progress (SSE)
@app.post("/research/{session_id}/stream")
async def stream_research(session_id: str, request: ResearchRequest, http_request: Request):
    """Stream research progress via Server-Sent Events."""
    # Get session
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update access time and status
    session.update_access_time()
    session.status = "running"

    async def event_generator():
        """Generate SSE events for research progress."""
        start_time = time.time()

        try:
            print(f"[DeepResearch] Starting streaming research for session {session_id}: {request.query[:100]}...")

            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'query': request.query})}\n\n"

            # Execute research with streaming
            async for event in research_engine.execute_research_stream(
                query=request.query,
                llm_config=session.llm_config,
                search_provider=session.search_provider,
                max_iterations=session.max_iterations
            ):
                # Check if client disconnected
                if await http_request.is_disconnected():
                    print(f"[DeepResearch] Client disconnected for session {session_id}")
                    session.status = "cancelled"
                    break

                # Send progress event
                yield f"data: {json.dumps(event)}\n\n"

                # Update session status based on event type
                if event.get("type") == "complete":
                    session.status = "completed"
                    session.current_state = event
                elif event.get("type") == "error":
                    session.status = "error"

            execution_time_ms = int((time.time() - start_time) * 1000)
            print(f"[DeepResearch] Completed streaming research for session {session_id} in {execution_time_ms}ms")

        except asyncio.CancelledError:
            session.status = "cancelled"
            yield f"data: {json.dumps({'type': 'cancelled', 'session_id': session_id})}\n\n"
        except Exception as e:
            session.status = "error"
            execution_time_ms = int((time.time() - start_time) * 1000)
            print(f"[DeepResearch] Streaming research failed for session {session_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'execution_time_ms': execution_time_ms})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Get research status
@app.get("/research/{session_id}/status")
async def get_research_status(session_id: str):
    """Get current research status."""
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.update_access_time()

    return {
        "session_id": session_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "last_accessed": session.last_accessed.isoformat(),
        "current_state": session.current_state,
    }


# Cancel research
@app.post("/research/{session_id}/cancel")
async def cancel_research(session_id: str):
    """Cancel running research session."""
    async with session_lock:
        session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel session in {session.status} status"
        )

    session.status = "cancelled"
    session.update_access_time()

    print(f"[DeepResearch] Cancelled session {session_id}")

    return {"status": "success", "message": "Research cancelled"}


def main():
    """Start the HTTP server."""
    port = int(os.getenv("MCP_HTTP_PORT", "8004"))
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")

    print(f"[DeepResearch] Starting Deep Research MCP HTTP server on {host}:{port}")
    print(f"[DeepResearch] Session timeout: 30 minutes")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
