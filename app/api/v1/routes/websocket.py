"""
WebSocket API routes for real-time communication

Provides WebSocket endpoint for bidirectional communication between
frontend and backend for real-time CrewAI results and progress updates.
"""

import asyncio
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.exceptions import WebSocketException
from typing import Optional
from datetime import datetime, timezone

from app.core.websocket_manager import connection_manager
from app.config.logging import get_logger
from app.config.settings import get_settings

logger = get_logger("api.websocket")
router = APIRouter()


async def verify_websocket_token(token: str) -> dict:
    """
    Verify JWT token for WebSocket authentication.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        dict: Decoded token payload with user information
        
    Raises:
        WebSocketException: If token is invalid or expired
    """
    try:
        # Decode and verify JWT token
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=["HS256"]
        )
        
        # Extract user information
        user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")
        
        if not user_id:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid token: missing user ID"
            )
        
        logger.info(f"✅ WebSocket token verified: user_id={user_id}, email={email}")
        
        return {
            "user_id": int(user_id),
            "email": email,
            "customer_id": payload.get("customer_id")
        }
        
    except jwt.ExpiredSignatureError:
        logger.error("❌ WebSocket authentication failed: token expired")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Token expired"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ WebSocket authentication failed: {str(e)}")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token"
        )
    except Exception as e:
        logger.error(f"❌ WebSocket authentication error: {str(e)}")
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Authentication error"
        )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time communication.
    
    Accepts WebSocket connections for a specific session and enables
    real-time bidirectional communication between frontend and backend.
    
    Args:
        websocket: The WebSocket connection
        session_id: The session ID for this conversation
        token: JWT token for authentication
        
    Connection lifecycle:
        1. Verify JWT token
        2. Accept WebSocket connection
        3. Register with ConnectionManager
        4. Keep connection alive with heartbeat
        5. Handle incoming messages (optional)
        6. Clean up on disconnect
    """
    user_info = None
    
    try:
        # Step 1: Authenticate user
        logger.info(f"🔐 WebSocket connection attempt: session={session_id}")
        user_info = await verify_websocket_token(token)
        
        # Step 2: Connect and register with manager
        await connection_manager.connect(
            websocket=websocket,
            session_id=session_id,
            user_id=user_info["user_id"],
            customer_id=user_info.get("customer_id")
        )
        
        logger.info(
            f"✅ WebSocket connected successfully: session={session_id}, "
            f"user={user_info['user_id']}, email={user_info.get('email')}"
        )
        
        # Step 3: Keep connection alive and handle messages
        heartbeat_interval = 30  # seconds
        last_heartbeat = datetime.now(timezone.utc)
        
        while True:
            try:
                # Wait for messages with timeout for heartbeat
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=heartbeat_interval
                )
                
                # Handle incoming messages from client
                await handle_client_message(websocket, session_id, message, user_info)
                
            except asyncio.TimeoutError:
                # Timeout reached - send heartbeat/ping
                current_time = datetime.now(timezone.utc)
                elapsed = (current_time - last_heartbeat).total_seconds()
                
                if elapsed >= heartbeat_interval:
                    try:
                        # Send ping to keep connection alive
                        await websocket.send_json({
                            "type": "ping",
                            "timestamp": current_time.isoformat()
                        })
                        
                        # Update heartbeat timestamp
                        await connection_manager.heartbeat(websocket, session_id)
                        last_heartbeat = current_time
                        
                    except Exception as e:
                        logger.error(f"❌ Heartbeat failed: {str(e)}")
                        break
                
            except WebSocketDisconnect:
                logger.info(f"🔌 Client disconnected: session={session_id}")
                break
                
            except Exception as e:
                logger.error(f"❌ Error receiving message: {str(e)}")
                # Send error to client
                try:
                    await websocket.send_json({
                        "type": "error",
                        "data": {
                            "error": "Message processing error",
                            "details": str(e)
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    # If we can't send error, connection is broken
                    break
    
    except WebSocketException as e:
        logger.error(f"❌ WebSocket exception: {e.reason}")
        # WebSocket exceptions are handled by FastAPI
        raise
        
    except Exception as e:
        logger.error(f"❌ WebSocket error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Try to send error message before closing
        try:
            await websocket.send_json({
                "type": "error",
                "data": {
                    "error": "Connection error",
                    "details": str(e)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception:
            pass
    
    finally:
        # Step 4: Cleanup on disconnect
        if user_info:
            logger.info(
                f"🧹 Cleaning up WebSocket: session={session_id}, "
                f"user={user_info['user_id']}"
            )
            await connection_manager.disconnect(websocket, session_id)
        else:
            logger.warning(f"🧹 Cleaning up unauthenticated WebSocket: session={session_id}")


async def handle_client_message(
    websocket: WebSocket,
    session_id: str,
    message: dict,
    user_info: dict
) -> None:
    """
    Handle incoming messages from WebSocket clients.
    
    Args:
        websocket: The WebSocket connection
        session_id: The session ID
        message: The received message
        user_info: Authenticated user information
    """
    try:
        message_type = message.get("type", "unknown")
        
        logger.info(
            f"📨 Received WebSocket message: session={session_id}, "
            f"type={message_type}, user={user_info['user_id']}"
        )
        
        # Handle different message types
        if message_type == "pong":
            # Client responded to ping - update heartbeat
            await connection_manager.heartbeat(websocket, session_id)
            
        elif message_type == "status_request":
            # Client requesting status update
            await websocket.send_json({
                "type": "status",
                "data": {
                    "session_id": session_id,
                    "connected": True,
                    "connection_count": connection_manager.get_session_connection_count(session_id)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        elif message_type == "ack":
            # Client acknowledging receipt of a message
            logger.debug(f"Client acknowledged message: {message.get('message_id')}")
            
        else:
            logger.warning(f"⚠️ Unknown message type: {message_type}")
            await websocket.send_json({
                "type": "error",
                "data": {
                    "error": f"Unknown message type: {message_type}",
                    "received_message": message
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        logger.error(f"❌ Error handling client message: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "data": {
                "error": "Message handling error",
                "details": str(e)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


@router.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket connection status and statistics.
    
    Returns:
        dict: Connection statistics
    """
    try:
        return {
            "status": "operational",
            "total_connections": connection_manager.get_total_connections(),
            "active_sessions": len(connection_manager.get_active_sessions()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error getting WebSocket status: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
