"""
Crew-related API schemas
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class CrewRequest(BaseModel):
    """Crew execution request schema"""
    topic: str
    current_year: str = str(datetime.now().year)


class CrewResponse(BaseModel):
    """Crew execution response schema"""
    result: str
    topic: str
    execution_time: float
    timestamp: str
    agent_type: Optional[str] = None
    thinking_steps: Optional[list] = None


class MasterAgentRequest(BaseModel):
    """Master agent request schema"""
    user_text: str
    user_parameters: Optional[Dict[str, Any]] = {}
    session_id: Optional[str] = None
    source: Optional[str] = "api_call"


class MasterAgentResponse(BaseModel):
    """Master agent response schema"""
    fulfillment_response: Dict[str, Any]
    analysis_complete: Optional[bool] = True
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
