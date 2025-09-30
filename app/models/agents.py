"""
Agent configuration and execution models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from .base import BaseModel


class AgentConfig(BaseModel, table=True):
    """Agent configuration model for master and specialist agents"""
    __tablename__ = "agent_configs"
    
    agent_type: str = Field(max_length=50)  # master, google_analytics, facebook_ads, etc.
    name: str = Field(max_length=100)
    role: str = Field(description="Agent role description")
    goal: str = Field(description="Agent goal description")
    backstory: str = Field(description="Agent backstory description")
    task: Optional[str] = Field(default=None, description="Agent task description with placeholders")
    capabilities: Optional[str] = Field(default=None)  # JSON capabilities as string
    tools: Optional[str] = Field(default=None)  # JSON tools list as string
    prompt_template: Optional[str] = Field(default=None)
    output_schema: Optional[str] = Field(default=None)  # JSON schema as string
    max_iterations: int = Field(default=3)
    allow_delegation: bool = Field(default=False, description="Whether agent can delegate to other agents")
    verbose: bool = Field(default=True, description="Whether agent should log verbose output")
    is_active: bool = Field(default=True)
    created_by_user_id: Optional[int] = Field(default=None)


class RoutingRule(BaseModel, table=True):
    """Routing rules for master agent"""
    __tablename__ = "routing_rules"
    
    intent_pattern: str = Field(max_length=255)  # e.g., "organic_traffic"
    required_specialists: str = Field()  # JSON array of specialist types
    conditions: Optional[str] = Field(default=None)  # JSON additional conditions
    priority: int = Field(default=0)
    is_active: bool = Field(default=True)


class AnalysisExecution(BaseModel, table=True):
    """Analysis execution logs"""
    __tablename__ = "analysis_executions"
    
    user_id: Optional[int] = Field(default=None)
    session_id: Optional[str] = Field(default=None, max_length=255)
    master_agent_id: Optional[int] = Field(default=None)
    specialists_used: Optional[str] = Field(default=None)  # JSON array
    iterations: Optional[int] = Field(default=None)
    execution_time_ms: Optional[int] = Field(default=None)
    validation_results: Optional[str] = Field(default=None)  # JSON
    final_result: Optional[str] = Field(default=None)  # JSON


class CustomerLog(BaseModel, table=True):
    """Customer Log file Table - Comprehensive execution logging"""
    __tablename__ = "customer_logs"
    
    session_id: str = Field(max_length=255, index=True)
    date_time: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_intent: str = Field(description="User's intent category (e.g., 'Insight only/Campaigns Opt/Campaigns plan')")
    original_query: str = Field(description="User's original input query")
    crewai_input_prompt: str = Field(description="Prompt sent to CrewAI system")
    master_answer: str = Field(description="Final master answer generated")
    crewai_log: str = Field(description="Detailed CrewAI execution log")
    
    # Enhanced timing information
    total_execution_time_ms: int = Field(description="Total execution time in milliseconds")
    timing_breakdown: str = Field(description="JSON array of timing objects for each agent/tool")
    
    # Additional metadata
    user_id: Optional[int] = Field(default=None)
    analysis_id: Optional[str] = Field(default=None, max_length=255)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)
    agents_used: str = Field(description="JSON array of agents used in this execution")
    tools_used: str = Field(description="JSON array of tools used in this execution")


class ExecutionTiming(BaseModel, table=True):
    """Individual timing records for agents and tools"""
    __tablename__ = "execution_timings"
    
    session_id: str = Field(max_length=255, index=True)
    analysis_id: Optional[str] = Field(default=None, max_length=255, index=True)
    component_type: str = Field(description="'agent' or 'tool'")
    component_name: str = Field(description="Name of the agent or tool")
    start_time: datetime = Field(description="When the component started")
    end_time: Optional[datetime] = Field(default=None, description="When the component finished")
    duration_ms: Optional[int] = Field(default=None, description="Duration in milliseconds")
    status: str = Field(default="running", description="'running', 'completed', 'error'")
    input_data: Optional[str] = Field(default=None, description="Input data (truncated)")
    output_data: Optional[str] = Field(default=None, description="Output data (truncated)")
    error_message: Optional[str] = Field(default=None)
    parent_session_id: Optional[str] = Field(default=None, description="Parent session if this is a sub-execution")


class DetailedExecutionLog(BaseModel, table=True):
    """Detailed execution log entries - mirrors terminal output for comprehensive debugging"""
    __tablename__ = "detailed_execution_logs"
    
    session_id: str = Field(max_length=255, index=True)
    analysis_id: Optional[str] = Field(default=None, max_length=255, index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    sequence_number: int = Field(description="Order of this log entry in the session")
    
    # Log entry type and hierarchy
    log_type: str = Field(description="'crew_start', 'task_start', 'task_complete', 'agent_start', 'agent_complete', 'tool_execution', 'tool_error', 'delegation', 'final_answer', 'crew_complete', 'crew_error'")
    parent_log_id: Optional[int] = Field(default=None, description="Parent log entry for hierarchical structure")
    depth_level: int = Field(default=0, description="Nesting depth (0=crew, 1=task, 2=agent, 3=tool)")
    
    # Component identification
    crew_id: Optional[str] = Field(default=None, description="Crew identifier")
    task_id: Optional[str] = Field(default=None, description="Task identifier") 
    agent_name: Optional[str] = Field(default=None, description="Agent name/role")
    tool_name: Optional[str] = Field(default=None, description="Tool name")
    
    # Status and timing
    status: str = Field(description="'executing', 'completed', 'failed', 'thinking', 'delegating'")
    duration_ms: Optional[int] = Field(default=None, description="Duration if completed")
    
    # Content and data
    title: str = Field(description="Log entry title/header")
    content: Optional[str] = Field(default=None, description="Main log content")
    input_data: Optional[str] = Field(default=None, description="Tool input or task description")
    output_data: Optional[str] = Field(default=None, description="Tool output or agent response")
    error_details: Optional[str] = Field(default=None, description="Error information if failed")
    
    # Metadata
    log_metadata: Optional[str] = Field(default=None, description="JSON metadata (tool args, agent config, etc.)")
    
    # Display formatting
    icon: Optional[str] = Field(default=None, description="Display icon (🚀, 📋, 🧠, 🔧, ❌, ✅)")
    color: Optional[str] = Field(default=None, description="Display color for UI")
    is_collapsible: bool = Field(default=False, description="Whether this log entry can be collapsed in UI")


