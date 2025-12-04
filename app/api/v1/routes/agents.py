"""
Agent management API routes
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlmodel import select

from app.api.schemas.agents import AgentConfigRequest, AgentConfigResponse, AgentListResponse
from app.services.agent_service import AgentService
from app.core.auth import get_current_user
from app.core.security import verify_api_key
from app.models.users import Campaigner
from app.config.logging import get_logger

logger = get_logger("api.agents")
router = APIRouter()


class DeleteAgentRequest(BaseModel):
    name: str  # Changed from agent_type
    permanent: bool = False

class GetAgentRequest(BaseModel):
    name: str  # Changed from agent_type


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
            timestamp=datetime.now(timezone.utc).isoformat()
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
        
        # Convert to frontend format - only use specialist_agents (master_agent is also in that list)
        agents = []
        
        # Get all agents from specialist_agents list (includes the "master" agent)
        specialist_agents = all_agents_data.get("specialist_agents", [])
        seen_ids = set()  # Track to avoid duplicates
        
        for agent in specialist_agents:
            agent_id = agent.get("id")
            if agent_id and agent_id not in seen_ids:
                seen_ids.add(agent_id)
                agents.append({
                    "id": agent_id,
                    "name": agent.get("name"),
                    "role": agent.get("role"),
                    "goal": agent.get("goal"),
                    "backstory": agent.get("backstory"),
                    "task": agent.get("task"),
                    "is_active": agent.get("is_active", True),
                    "capabilities": agent.get("capabilities", []),
                    "allow_delegation": agent.get("allow_delegation", False),
                    "verbose": agent.get("verbose", True),
                    "max_iterations": agent.get("max_iterations", 3),
                    "created_at": agent.get("created_at"),
                    "updated_at": agent.get("updated_at")
                })
        
        # Sort agents: master agent (name contains "master") first, then alphabetically by name
        def sort_key(agent):
            name_lower = agent.get("name", "").lower()
            return (0 if 'master' in name_lower else 1, name_lower)
        
        agents.sort(key=sort_key)
        
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
    """POST /api/v1/agents/get - Get specific agent configuration by name"""
    try:
        agent_service = AgentService()
        agent_config = agent_service.get_agent_config(request.name)
        
        if not agent_config:
            raise HTTPException(status_code=404, detail=f"Agent name '{request.name}' not found")
        
        return AgentConfigResponse(
            status="success",
            agent=agent_config,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {request.name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.post("/", response_model=AgentConfigResponse)
def create_agent_config(
    agent_config: AgentConfigRequest, 
    _: bool = Depends(authenticate_user_or_api_key)
):
    """Create new agent configuration"""
    try:
        # Check for existing agent by name to prevent duplicates
        from app.core.database import db_manager
        existing_agent = db_manager.get_agent_config_by_name(agent_config.name, include_inactive=True)
        if existing_agent and existing_agent.get('is_active', False):
            raise HTTPException(
                status_code=409, 
                detail=f"Agent with name '{agent_config.name}' already exists. Use PUT to update existing agent."
            )
        
        agent_service = AgentService()
        created_agent = agent_service.create_or_update_agent(agent_config.dict())
        
        return AgentConfigResponse(
            status="success",
            message=f"Agent '{agent_config.name}' created successfully",
            agent=created_agent,
            timestamp=datetime.now(timezone.utc).isoformat()
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
        if not agent_config.id:
            raise HTTPException(status_code=400, detail="Agent ID is required for update")
        
        agent_service = AgentService()
        
        # Check for duplicate name (excluding current agent)
        from app.core.database import db_manager
        from app.models.agents import AgentConfig
        from app.config.database import get_session

        existing_agent = db_manager.get_agent_config_by_id(agent_config.id, include_inactive=True)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent with ID {agent_config.id} not found")

        with db_manager.get_session() as session:
            existing = session.exec(
                select(AgentConfig).where(
                    AgentConfig.name == agent_config.name,
                    AgentConfig.id != agent_config.id
                )
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=[{
                        "type": "value_error",
                        "loc": ["body", "name"],
                        "msg": f"Agent with name '{agent_config.name}' already exists",
                        "input": agent_config.name
                    }]
                )
        
        # Update agent
        updated_agent = agent_service.create_or_update_agent(agent_config.dict())
        
        return AgentConfigResponse(
            status="success",
            message=f"Agent '{agent_config.name}' updated successfully",
            agent=updated_agent,
            timestamp=datetime.now(timezone.utc).isoformat()
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
        name = request.name
        permanent = request.permanent
        
        agent_service = AgentService()
        
        # Check if agent exists (including inactive ones)
        from app.core.database import db_manager
        existing_agent = db_manager.get_agent_config_by_name(name, include_inactive=True)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent with name '{name}' not found")
        
        if permanent:
            # Permanently delete agent
            success = agent_service.permanent_delete_agent(name)
            message = f"Agent '{name}' permanently deleted from database"
        else:
            # Just deactivate agent
            success = agent_service.deactivate_agent(name)
            message = f"Agent '{name}' deactivated successfully"
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete agent")
        
        return {
            "status": "success",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


