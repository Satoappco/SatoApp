"""
Admin routes for debugging and managing CrewAI agents
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from app.core.security import verify_api_key
from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from app.models.users import Campaigner
from app.services.agent_service import AgentService

router = APIRouter(prefix="/admin", tags=["Admin"])


class AgentTestRequest(BaseModel):
    """Request model for testing agents"""
    campaigner_id: int
    customer_id: int
    user_question: str
    data_sources: List[str] = []
    intent_name: str = "admin.test"


class AgentTestResponse(BaseModel):
    """Response model for agent testing"""
    success: bool
    message: str
    agents_used: List[str]
    processing_time: float
    response: str
    debug_info: Dict[str, Any]


@router.get("/agents", response_model=List[Dict[str, Any]])
async def get_all_agents(
    _: bool = Depends(verify_api_key)
):
    """Get all available agents from database"""
    try:
        agent_service = AgentService()
        agents_data = agent_service.get_all_agents()
        
        # Format for admin display
        formatted_agents = []
        
        # Add master agent if exists
        if agents_data.get("master_agent"):
            master = agents_data["master_agent"]
            formatted_agents.append({
                "id": master.get("id"),
                "agent_type": master.get("agent_type"),
                "name": master.get("name"),
                "role": master.get("role"),
                "goal": master.get("goal"),
                "backstory": master.get("backstory"),
                "task": master.get("task"),
                "allow_delegation": master.get("allow_delegation"),
                "verbose": master.get("verbose"),
                "is_active": master.get("is_active"),
                "created_at": master.get("created_at"),
                "updated_at": master.get("updated_at"),
                "type": "master"
            })
        
        # Add specialist agents
        for agent in agents_data.get("specialist_agents", []):
            formatted_agents.append({
                "id": agent.get("id"),
                "agent_type": agent.get("agent_type"),
                "name": agent.get("name"),
                "role": agent.get("role"),
                "goal": agent.get("goal"),
                "backstory": agent.get("backstory"),
                "task": agent.get("task"),
                "allow_delegation": agent.get("allow_delegation"),
                "verbose": agent.get("verbose"),
                "is_active": agent.get("is_active"),
                "created_at": agent.get("created_at"),
                "updated_at": agent.get("updated_at"),
                "type": "specialist"
            })
        
        return formatted_agents
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agents: {str(e)}"
        )


@router.get("/connections", response_model=List[Dict[str, Any]])
async def get_all_connections(
    _: bool = Depends(verify_api_key)
):
    """Get all user connections"""
    try:
        with get_session() as session:
            from sqlmodel import select
            
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(Connection.revoked == False)
            
            results = session.exec(statement).all()
            
            connections = []
            for connection, asset in results:
                connections.append({
                    "connection_id": connection.id,
                    "customer_id": connection.customer_id,
                    "campaigner_id": connection.campaigner_id,
                    "asset_name": asset.name,
                    "asset_type": asset.asset_type,
                    "provider": asset.provider,
                    "status": "Active" if not connection.revoked else "Revoked",
                    "expires_at": connection.expires_at,
                    "created_at": connection.created_at
                })
            
            return connections
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connections: {str(e)}"
        )


@router.post("/test-agent", response_model=AgentTestResponse)
async def test_agent(
    request: AgentTestRequest,
    _: bool = Depends(verify_api_key)
):
    """Test a specific agent with custom parameters"""
    try:
        import time
        start_time = time.time()
        
        # Create a simple test by calling the webhook endpoint directly
        import httpx
        
        test_payload = {
            "sessionInfo": {
                "session": f"admin-test-session-{int(time.time())}",
                "parameters": {
                    "campaigner_id": str(request.campaigner_id),
                    "customer_id": str(request.customer_id),
                    "user_question": request.user_question
                }
            },
            "intentInfo": {
                "displayName": request.intent_name,
                "confidence": 0.95
            },
            "messages": {
                "text": request.user_question
            },
            "data_sources": request.data_sources
        }
        
        # Call the webhook endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://localhost:8000/api/v1/webhooks/dialogcx",
                json=test_payload,
                headers={"Authorization": "Bearer SatoLogos"}
            )
            
            result = response.json()
        
        processing_time = time.time() - start_time
        
        # Extract debug info
        debug_info = {
            "request_data": test_payload,
            "data_sources": request.data_sources,
            "intent_name": request.intent_name,
            "processing_time_seconds": processing_time,
            "status_code": response.status_code
        }
        
        # Parse the response correctly
        if response.status_code == 200:
            # Extract the actual response from the webhook
            fulfillment_response = result.get("fulfillment_response", {})
            messages = fulfillment_response.get("messages", [])
            
            # Get the text response
            response_text = ""
            if messages and len(messages) > 0:
                first_message = messages[0]
                if isinstance(first_message, dict):
                    text_obj = first_message.get("text", {})
                    if isinstance(text_obj, dict):
                        text_list = text_obj.get("text", [])
                        if text_list and len(text_list) > 0:
                            response_text = text_list[0]
                    elif isinstance(text_obj, str):
                        response_text = text_obj
                elif isinstance(first_message, str):
                    response_text = first_message
            
            # If no text found, use the raw result
            if not response_text:
                response_text = str(result)
            
            return AgentTestResponse(
                success=True,
                message="Agent test completed successfully",
                agents_used=result.get("session_info", {}).get("parameters", {}).get("agents_used", []),
                processing_time=processing_time,
                response=response_text,
                debug_info=debug_info
            )
        else:
            return AgentTestResponse(
                success=False,
                message=f"Agent test failed with status {response.status_code}",
                agents_used=[],
                processing_time=processing_time,
                response=str(result),
                debug_info=debug_info
            )
        
    except Exception as e:
        return AgentTestResponse(
            success=False,
            message=f"Agent test failed: {str(e)}",
            agents_used=[],
            processing_time=0.0,
            response="",
            debug_info={"error": str(e)}
        )


@router.get("/agent/{agent_type}", response_model=Dict[str, Any])
async def get_agent_details(
    agent_type: str,
    _: bool = Depends(verify_api_key)
):
    """Get detailed information about a specific agent"""
    try:
        agent_service = AgentService()
        agent = agent_service.get_agent_by_type(agent_type)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent type '{agent_type}' not found"
            )
        
        return agent
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent details: {str(e)}"
        )


@router.put("/agent/{agent_type}/task", response_model=Dict[str, str])
async def update_agent_task(
    agent_type: str,
    task: str,
    _: bool = Depends(verify_api_key)
):
    """Update an agent's task template"""
    try:
        agent_service = AgentService()
        success = agent_service.update_agent_task(agent_type, task)
        
        if success:
            return {"message": f"Successfully updated task for agent '{agent_type}'"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent type '{agent_type}' not found"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent task: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, Any])
async def admin_health_check(
    _: bool = Depends(verify_api_key)
):
    """Admin health check with detailed system status"""
    try:
        # Check database connection
        with get_session() as session:
            from sqlmodel import text
            result = session.exec(text("SELECT 1")).first()
            db_status = "Connected" if result else "Disconnected"
        
        # Check agent service
        agent_service = AgentService()
        agents_count = len(agent_service.get_all_agents())
        
        # Check connections
        with get_session() as session:
            from sqlmodel import select
            connections_count = len(session.exec(select(Connection)).all())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "agents_count": agents_count,
            "connections_count": connections_count,
            "services": {
                "agent_service": "active",
                "database": "active"
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
