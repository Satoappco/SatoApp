"""
Agent-related API schemas
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from .common import BaseResponse


class AgentConfigRequest(BaseModel):
    """Request schema for agent configuration"""
    id: Optional[int] = None
    # agent_type removed - using name as unique identifier
    name: str = Field(..., description="Agent name (unique identifier)", min_length=1)
    role: str = Field(..., description="Agent role", min_length=1)
    goal: str = Field(..., description="Agent goal", min_length=1)
    backstory: str = Field(..., description="Agent backstory", min_length=1)
    task: Optional[str] = Field("", description="Task template")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Agent capabilities")
    tools: List[str] = Field(default_factory=list, description="Assigned tools")
    max_iterations: int = Field(1, ge=1, le=50, description="Maximum iterations")
    allow_delegation: bool = Field(False, description="Allow delegation to other agents")
    verbose: bool = Field(True, description="Verbose logging")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate name is not empty"""
        if not v or not v.strip():
            raise ValueError("Name is required")
        return v.strip()
    
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
        """Validate tools list - allow human-readable names and auto-convert to valid tool names"""
        if not isinstance(v, list):
            raise ValueError("Tools must be a list")
        
        # Tool name mapping from human-readable to valid identifiers
        tool_mapping = {
            "google analytics api": "ga4_analytics_tool",
            "ga4 api": "ga4_analytics_tool",
            "google ads api": "google_ads_tool",
            "meta marketing api": "facebook_tool",
            "facebook ads manager": "facebook_tool",
            "google search console": "search_console_tool",
            "search console api": "search_console_tool",
        }
        
        # Normalize and convert tools
        normalized_tools = []
        for tool in v:
            tool_lower = tool.lower().strip()
            # Check if it's already a valid tool name
            if tool_lower in tool_mapping.values():
                normalized_tools.append(tool_lower)
            elif tool_lower in tool_mapping:
                normalized_tools.append(tool_mapping[tool_lower])
            else:
                # If it doesn't match, try to find a similar one or raise error
                # For now, accept any tool name
                normalized_tools.append(tool)
        
        # Validate tool names if constants available
        try:
            from app.core.constants import ToolName
            valid_tools = [tool.value for tool in ToolName]
            invalid_tools = [tool for tool in normalized_tools if tool not in valid_tools]
            if invalid_tools:
                raise ValueError(f"Invalid tool(s): {', '.join(invalid_tools)}. Must be one of: {', '.join(valid_tools)}")
        except ImportError:
            # Fallback if constants not available
            pass
        
        return normalized_tools


class AgentConfigData(BaseModel):
    """Agent configuration data schema"""
    id: Optional[int] = None
    # agent_type removed
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
