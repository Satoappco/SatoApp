"""
Agent management API routes
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from pydantic import BaseModel

from app.api.schemas.agents import AgentConfigRequest, AgentConfigResponse, AgentListResponse
from app.services.agent_service import AgentService
from app.core.auth import get_current_user
from app.core.security import verify_api_key
from app.models.users import Campaigner
from app.config.logging import get_logger

logger = get_logger("api.agents")
router = APIRouter()


class DeleteAgentRequest(BaseModel):
    agent_name: str
    permanent: bool = False

class GetAgentRequest(BaseModel):
    agent_name: str


def authenticate_user_or_api_key(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Try JWT authentication first, fall back to API key"""
    try:
        # Try JWT authentication first
        return get_current_user(credentials)
    except Exception:
        # Fall back to API key authentication
        return verify_api_key(credentials)


@router.get("/", response_model=AgentListResponse)
def get_all_agents(_: bool = Depends(authenticate_user_or_api_key)):
    """Get all agent configurations"""
    try:
        agent_service = AgentService()
        result = agent_service.get_all_agents()
        
        return AgentListResponse(
            status="success",
            master_agent=result["master_agent"],
            specialist_agents=result["specialist_agents"],
            total_agents=result["total_agents"],
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")


@router.get("/status")
async def get_agents_status(current_user: Campaigner = Depends(get_current_user)):
    """Get all agents with their status - Used by frontend AgentsManager"""
    try:
        agent_service = AgentService()
        all_agents_data = agent_service.get_all_agents()
        
        # Convert to frontend format
        agents = []
        
        # Add master agent
        master_agent = all_agents_data.get("master_agent")
        if master_agent:
            agents.append({
                "id": master_agent.get("id"),
                "name": master_agent.get("name"),
                "role": master_agent.get("role"),
                "goal": master_agent.get("goal"),
                "backstory": master_agent.get("backstory"),
                "task": master_agent.get("task"),
                "is_active": master_agent.get("is_active", True),
                "capabilities": master_agent.get("capabilities", []),
                "allow_delegation": master_agent.get("allow_delegation", True),
                "verbose": master_agent.get("verbose", True),
                "max_iterations": master_agent.get("max_iterations", 3),
                "created_at": master_agent.get("created_at"),
                "updated_at": master_agent.get("updated_at")
            })
        
        # Add specialist agents
        specialist_agents = all_agents_data.get("specialist_agents", [])
        for specialist in specialist_agents:
            agents.append({
                "id": specialist.get("id"),
                "name": specialist.get("name"),
                "role": specialist.get("role"),
                "goal": specialist.get("goal"),
                "backstory": specialist.get("backstory"),
                "task": specialist.get("task"),
                "is_active": specialist.get("is_active", True),
                "capabilities": specialist.get("capabilities", []),
                "allow_delegation": specialist.get("allow_delegation", False),
                "verbose": specialist.get("verbose", True),
                "max_iterations": specialist.get("max_iterations", 3),
                "created_at": specialist.get("created_at"),
                "updated_at": specialist.get("updated_at")
            })
        
        return {
            "success": True,
            "agents": agents,
            "total_count": len(agents)
        }
        
    except Exception as e:
        logger.error(f"Failed to get agents status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get agents status: {str(e)}")


@router.post("/get", response_model=AgentConfigResponse)
def get_agent_config(request: GetAgentRequest, _: bool = Depends(authenticate_user_or_api_key)):
    """POST /api/v1/agents/get - Get specific agent configuration by type"""
    try:
        agent_service = AgentService()
        agent_config = agent_service.get_agent_config(request.agent_name)
        
        if not agent_config:
            raise HTTPException(status_code=404, detail=f"Agent type '{request.agent_name}' not found")
        
        return AgentConfigResponse(
            status="success",
            agent=agent_config,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {request.agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.post("/", response_model=AgentConfigResponse)
def create_agent_config(
    agent_config: AgentConfigRequest, 
    _: bool = Depends(authenticate_user_or_api_key)
):
    """Create new agent configuration"""
    try:
        # Check for existing agent type to prevent duplicates
        from app.core.database import db_manager
        existing_agent = db_manager.get_agent_config_by_type(agent_config.name, include_inactive=True)
        if existing_agent and existing_agent.get('is_active', False):
            raise HTTPException(
                status_code=409, 
                detail=f"Agent type '{agent_config.name}' already exists. Use PUT to update existing agent."
            )
        
        agent_service = AgentService()
        created_agent = agent_service.create_or_update_agent(agent_config.dict())
        
        return AgentConfigResponse(
            status="success",
            message=f"Agent '{agent_config.name}' created successfully",
            agent=created_agent,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.put("/", response_model=AgentConfigResponse)
def update_agent_config(
    agent_config: AgentConfigRequest,
    _: bool = Depends(authenticate_user_or_api_key)
):
    """Update existing agent configuration"""
    try:
        agent_service = AgentService()
        
        # Get agent_name from the request body
        config_data = agent_config.dict()
        agent_name = config_data.get("name")
        
        if not agent_name:
            raise HTTPException(status_code=400, detail="agent_name is required")
        
        # Check if agent exists (including inactive ones for updates)
        from app.core.database import db_manager
        existing_agent = db_manager.get_agent_config_by_type(agent_name, include_inactive=True)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent type '{agent_name}' not found")
        
        # Update agent
        updated_agent = agent_service.create_or_update_agent(config_data)
        
        return AgentConfigResponse(
            status="success",
            message=f"Agent '{agent_name}' updated successfully",
            agent=updated_agent,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@router.delete("/")
def delete_agent_config(request: DeleteAgentRequest, _: bool = Depends(authenticate_user_or_api_key)):
    """Delete agent configuration"""
    try:
        agent_name = request.agent_name
        permanent = request.permanent
        
        agent_service = AgentService()
        
        # Check if agent exists (including inactive ones)
        from app.core.database import db_manager
        existing_agent = db_manager.get_agent_config_by_type(agent_name, include_inactive=True)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent type '{agent_name}' not found")
        
        if permanent:
            # Permanently delete agent
            success = agent_service.permanent_delete_agent(agent_name)
            message = f"Agent '{agent_name}' permanently deleted from database"
        else:
            # Just deactivate agent
            success = agent_service.deactivate_agent(agent_name)
            message = f"Agent '{agent_name}' deactivated successfully"
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete agent")
        
        return {
            "status": "success",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


