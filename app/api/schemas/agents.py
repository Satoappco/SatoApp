"""
Agent-related API schemas
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from .common import BaseResponse


class AgentConfigRequest(BaseModel):
    """Request schema for agent configuration"""
    id: Optional[int] = None
    agent_type: str = Field(..., description="Agent type from constants", min_length=1)
    name: str = Field(..., description="Agent name", min_length=1)
    role: str = Field(..., description="Agent role", min_length=1)
    goal: str = Field(..., description="Agent goal", min_length=1)
    backstory: str = Field(..., description="Agent backstory", min_length=1)
    task: Optional[str] = Field("", description="Task template")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Agent capabilities")
    tools: List[str] = Field(default_factory=list, description="Assigned tools")
    max_iterations: int = Field(1, ge=1, le=50, description="Maximum iterations")
    allow_delegation: bool = Field(False, description="Allow delegation to other agents")
    verbose: bool = Field(True, description="Verbose logging")
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        """Validate agent type against constants"""
        try:
            from app.core.constants import AgentType
            valid_types = [agent.value for agent in AgentType]
            if v not in valid_types:
                raise ValueError(f"Invalid agent type: {v}. Must be one of: {', '.join(valid_types)}")
            return v
        except ImportError:
            # Fallback if constants not available
            return v
    
    @validator('capabilities')
    def validate_capabilities(cls, v):
        """Validate capabilities structure"""
        if not isinstance(v, dict):
            raise ValueError("Capabilities must be a dictionary")
        
        # Validate data sources if present
        if 'data_sources' in v:
            if not isinstance(v['data_sources'], list):
                raise ValueError("data_sources must be a list")
            
            try:
                from app.core.constants import VALID_DATA_SOURCES
                for source in v['data_sources']:
                    if source not in VALID_DATA_SOURCES:
                        raise ValueError(f"Invalid data source: {source}. Must be one of: {', '.join(VALID_DATA_SOURCES)}")
            except ImportError:
                # Fallback if constants not available
                pass
        
        return v
    
    @validator('tools')
    def validate_tools(cls, v):
        """Validate tools list"""
        if not isinstance(v, list):
            raise ValueError("Tools must be a list")
        
        # Validate tool names if constants available
        try:
            from app.core.constants import ToolName
            valid_tools = [tool.value for tool in ToolName]
            for tool in v:
                if tool not in valid_tools:
                    raise ValueError(f"Invalid tool: {tool}. Must be one of: {', '.join(valid_tools)}")
        except ImportError:
            # Fallback if constants not available
            pass
        
        return v


class AgentConfigData(BaseModel):
    """Agent configuration data schema"""
    id: Optional[int] = None
    agent_type: str
    name: str
    role: str
    goal: str
    backstory: str
    task: Optional[str] = ""
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    tools: List[str] = Field(default_factory=list)
    max_iterations: int = Field(1, ge=1, le=50)
    allow_delegation: bool = False
    verbose: bool = True
    is_active: bool = True
    created_at: str
    updated_at: str


class AgentConfigResponse(BaseResponse):
    """Response schema for single agent configuration"""
    agent: Optional[AgentConfigData] = None


class AgentListResponse(BaseResponse):
    """Response schema for agent list"""
    master_agent: Optional[AgentConfigData] = None
    specialist_agents: List[AgentConfigData] = []
    total_agents: int = 0
