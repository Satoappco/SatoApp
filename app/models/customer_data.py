"""
Customer-specific data models (Info, RTM, Questions)

These models use composite_id instead of separate foreign keys.
The composite_id format is: <agency_id>_<campaigner_id>_<customer_id>
Data is stored with the campaigner who created it, but retrieved by any campaigner in the same agency.
"""

from sqlmodel import Field, Column, String
from typing import Optional
from datetime import datetime
from pydantic import BaseModel as PydanticBaseModel
from .base import BaseModel


class RTMTable(BaseModel, table=True):
    """
    Stores up to 10 RTM (Real-Time Monitoring) links per customer.
    Uses composite_id instead of separate foreign keys.
    Format: <agency_id>_<campaigner_id>_<customer_id>
    """
    __tablename__ = "rtm_table"
    
    # Composite identifier
    composite_id: str = Field(
        max_length=100,
        index=True,
        description="Concatenation: <Agency ID>_<Campaigner ID>_<Customer ID>"
    )
    
    # Up to 10 links
    link_1: Optional[str] = Field(default=None, max_length=500, description="RTM Link 1")
    link_2: Optional[str] = Field(default=None, max_length=500, description="RTM Link 2")
    link_3: Optional[str] = Field(default=None, max_length=500, description="RTM Link 3")
    link_4: Optional[str] = Field(default=None, max_length=500, description="RTM Link 4")
    link_5: Optional[str] = Field(default=None, max_length=500, description="RTM Link 5")
    link_6: Optional[str] = Field(default=None, max_length=500, description="RTM Link 6")
    link_7: Optional[str] = Field(default=None, max_length=500, description="RTM Link 7")
    link_8: Optional[str] = Field(default=None, max_length=500, description="RTM Link 8")
    link_9: Optional[str] = Field(default=None, max_length=500, description="RTM Link 9")
    link_10: Optional[str] = Field(default=None, max_length=500, description="RTM Link 10")


class QuestionsTable(BaseModel, table=True):
    """
    Stores up to 10 pre-defined questions per customer for quick chat access.
    Uses composite_id instead of separate foreign keys.
    Format: <agency_id>_<campaigner_id>_<customer_id>
    """
    __tablename__ = "questions_table"
    
    # Composite identifier
    composite_id: str = Field(
        max_length=100,
        index=True,
        description="Concatenation: <Agency ID>_<Campaigner ID>_<Customer ID>"
    )
    
    # Up to 10 questions
    q1: Optional[str] = Field(default=None, max_length=500, description="Question 1")
    q2: Optional[str] = Field(default=None, max_length=500, description="Question 2")
    q3: Optional[str] = Field(default=None, max_length=500, description="Question 3")
    q4: Optional[str] = Field(default=None, max_length=500, description="Question 4")
    q5: Optional[str] = Field(default=None, max_length=500, description="Question 5")
    q6: Optional[str] = Field(default=None, max_length=500, description="Question 6")
    q7: Optional[str] = Field(default=None, max_length=500, description="Question 7")
    q8: Optional[str] = Field(default=None, max_length=500, description="Question 8")
    q9: Optional[str] = Field(default=None, max_length=500, description="Question 9")
    q10: Optional[str] = Field(default=None, max_length=500, description="Question 10")


# ===== Pydantic Models for API Responses =====

class RTMTableResponse(PydanticBaseModel):
    """Response model for RTM table data"""
    model_config = {"from_attributes": True}
    
    id: int
    composite_id: str
    link_1: Optional[str] = None
    link_2: Optional[str] = None
    link_3: Optional[str] = None
    link_4: Optional[str] = None
    link_5: Optional[str] = None
    link_6: Optional[str] = None
    link_7: Optional[str] = None
    link_8: Optional[str] = None
    link_9: Optional[str] = None
    link_10: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QuestionsTableResponse(PydanticBaseModel):
    """Response model for Questions table data"""
    model_config = {"from_attributes": True}
    
    id: int
    composite_id: str
    q1: Optional[str] = None
    q2: Optional[str] = None
    q3: Optional[str] = None
    q4: Optional[str] = None
    q5: Optional[str] = None
    q6: Optional[str] = None
    q7: Optional[str] = None
    q8: Optional[str] = None
    q9: Optional[str] = None
    q10: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RTMTableUpdate(PydanticBaseModel):
    """Update model for RTM table data"""
    customer_id: int
    link_1: Optional[str] = None
    link_2: Optional[str] = None
    link_3: Optional[str] = None
    link_4: Optional[str] = None
    link_5: Optional[str] = None
    link_6: Optional[str] = None
    link_7: Optional[str] = None
    link_8: Optional[str] = None
    link_9: Optional[str] = None
    link_10: Optional[str] = None


class QuestionsTableUpdate(PydanticBaseModel):
    """Update model for Questions table data"""
    customer_id: int
    q1: Optional[str] = None
    q2: Optional[str] = None
    q3: Optional[str] = None
    q4: Optional[str] = None
    q5: Optional[str] = None
    q6: Optional[str] = None
    q7: Optional[str] = None
    q8: Optional[str] = None
    q9: Optional[str] = None
    q10: Optional[str] = None

