"""
WebSocket Connection Manager for real-time communication

Manages WebSocket connections per session, handles message broadcasting,
connection lifecycle, and cleanup.
"""

import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from app.config.logging import get_logger

logger = get_logger("websocket.manager")


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.
    
    Supports:
    - Multiple connections per session (multiple browser tabs)
    - Session-based message broadcasting
    - Connection metadata tracking
    - Automatic cleanup on disconnect
    - Heartbeat/ping mechanism
    """
    
    def __init__(self):
        """Initialize the connection manager"""
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_metadata: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        logger.info("🔌 ConnectionManager initialized")
    
    async def connect(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        user_id: int,
        customer_id: Optional[int] = None
    ) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            session_id: The session ID for this connection
            user_id: The authenticated user ID
            customer_id: Optional customer ID
        """
        try:
            await websocket.accept()
            
            async with self._lock:
                # Initialize session list if not exists
                if session_id not in self.active_connections:
                    self.active_connections[session_id] = []
                
                # Add connection to session
                self.active_connections[session_id].append(websocket)
                
                # Store metadata
                connection_key = f"{session_id}_{id(websocket)}"
                self.connection_metadata[connection_key] = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "customer_id": customer_id,
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                    "websocket_id": id(websocket)
                }
            
            logger.info(
                f"✅ WebSocket connected: session={session_id}, user={user_id}, "
                f"total_connections={len(self.active_connections[session_id])}"
            )
            
            # Send connection acknowledgment
            await self._send_to_websocket(websocket, {
                "type": "connected",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "WebSocket connection established"
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to connect WebSocket: {str(e)}")
            raise
    
    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """
        Remove and cleanup a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to remove
            session_id: The session ID for this connection
        """
        try:
            async with self._lock:
                # Remove from active connections
                if session_id in self.active_connections:
                    if websocket in self.active_connections[session_id]:
                        self.active_connections[session_id].remove(websocket)
                    
                    # Clean up empty session lists
                    if not self.active_connections[session_id]:
                        del self.active_connections[session_id]
                
                # Remove metadata
                connection_key = f"{session_id}_{id(websocket)}"
                if connection_key in self.connection_metadata:
                    metadata = self.connection_metadata[connection_key]
                    del self.connection_metadata[connection_key]
                    
                    logger.info(
                        f"🔌 WebSocket disconnected: session={session_id}, "
                        f"user={metadata.get('user_id')}, "
                        f"remaining_connections={len(self.active_connections.get(session_id, []))}"
                    )
        
        except Exception as e:
            logger.error(f"❌ Error during disconnect cleanup: {str(e)}")
    
    async def send_to_session(
        self, 
        session_id: str, 
        message: dict,
        message_type: Optional[str] = None
    ) -> bool:
        """
        Send a message to all connections for a specific session.
        
        Args:
            session_id: The session ID to send to
            message: The message dictionary to send
            message_type: Optional message type override
            
        Returns:
            bool: True if message was sent to at least one connection
        """
        try:
            # Ensure message has required fields
            if "type" not in message and message_type:
                message["type"] = message_type
            
            if "timestamp" not in message:
                message["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Get connections for this session
            connections = self.active_connections.get(session_id, [])
            
            if not connections:
                logger.warning(f"⚠️ No active connections for session: {session_id}")
                return False
            
            # Send to all connections for this session
            disconnected = []
            success_count = 0
            
            for websocket in connections:
                try:
                    await self._send_to_websocket(websocket, message)
                    success_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to send to WebSocket: {str(e)}")
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            if disconnected:
                async with self._lock:
                    for ws in disconnected:
                        if ws in self.active_connections.get(session_id, []):
                            self.active_connections[session_id].remove(ws)
            
            logger.info(
                f"📤 Message sent: session={session_id}, type={message.get('type')}, "
                f"success={success_count}/{len(connections)}"
            )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Error sending message to session {session_id}: {str(e)}")
            return False
    
    async def send_typing_indicator(
        self, 
        session_id: str, 
        is_typing: bool,
        agent_name: Optional[str] = None
    ) -> bool:
        """
        Send typing indicator to frontend.
        
        Args:
            session_id: The session ID
            is_typing: Whether typing is active
            agent_name: Optional name of the typing agent
            
        Returns:
            bool: True if sent successfully
        """
        message = {
            "type": "typing",
            "data": {
                "is_typing": is_typing,
                "agent_name": agent_name
            }
        }
        return await self.send_to_session(session_id, message)
    
    async def send_progress_update(
        self,
        session_id: str,
        stage: str,
        percentage: int,
        agent: Optional[str] = None,
        task: Optional[str] = None,
        message: Optional[str] = None
    ) -> bool:
        """
        Send progress update during CrewAI execution.
        
        Args:
            session_id: The session ID
            stage: Current stage (e.g., 'initializing', 'analyzing', 'completing')
            percentage: Progress percentage (0-100)
            agent: Current agent working
            task: Current task being executed
            message: Optional progress message
            
        Returns:
            bool: True if sent successfully
        """
        progress_message = {
            "type": "progress",
            "data": {
                "stage": stage,
                "percentage": min(100, max(0, percentage)),  # Clamp between 0-100
                "agent": agent,
                "task": task,
                "message": message
            }
        }
        return await self.send_to_session(session_id, progress_message)
    
    async def send_crew_result(
        self,
        session_id: str,
        result: str,
        analysis_id: str,
        execution_time: Optional[float] = None,
        agents_used: Optional[List[str]] = None
    ) -> bool:
        """
        Send CrewAI analysis result to frontend.
        
        Args:
            session_id: The session ID
            result: The analysis result text
            analysis_id: Unique analysis identifier
            execution_time: Optional execution time in seconds
            agents_used: Optional list of agents that participated
            
        Returns:
            bool: True if sent successfully
        """
        result_message = {
            "type": "crew_result",
            "data": {
                "result": result,
                "analysis_id": analysis_id,
                "execution_time": execution_time,
                "agents_used": agents_used or []
            }
        }
        return await self.send_to_session(session_id, result_message)
    
    async def send_error(
        self,
        session_id: str,
        error: str,
        details: Optional[str] = None,
        retry_possible: bool = False
    ) -> bool:
        """
        Send error message to frontend.
        
        Args:
            session_id: The session ID
            error: Error message
            details: Optional error details
            retry_possible: Whether the operation can be retried
            
        Returns:
            bool: True if sent successfully
        """
        error_message = {
            "type": "error",
            "data": {
                "error": error,
                "details": details,
                "retry_possible": retry_possible
            }
        }
        return await self.send_to_session(session_id, error_message)
    
    async def _send_to_websocket(self, websocket: WebSocket, message: dict) -> None:
        """
        Send a message to a specific WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            message: The message dictionary to send
        """
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected during send")
            raise
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {str(e)}")
            raise
    
    async def heartbeat(self, websocket: WebSocket, session_id: str) -> None:
        """
        Update last heartbeat timestamp for a connection.
        
        Args:
            websocket: The WebSocket connection
            session_id: The session ID
        """
        connection_key = f"{session_id}_{id(websocket)}"
        if connection_key in self.connection_metadata:
            self.connection_metadata[connection_key]["last_heartbeat"] = \
                datetime.now(timezone.utc).isoformat()
    
    def get_session_connection_count(self, session_id: str) -> int:
        """
        Get the number of active connections for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            int: Number of active connections
        """
        return len(self.active_connections.get(session_id, []))
    
    def get_total_connections(self) -> int:
        """
        Get the total number of active connections across all sessions.
        
        Returns:
            int: Total number of connections
        """
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_active_sessions(self) -> List[str]:
        """
        Get list of all active session IDs.
        
        Returns:
            List[str]: List of session IDs with active connections
        """
        return list(self.active_connections.keys())


# Global connection manager instance
connection_manager = ConnectionManager()
