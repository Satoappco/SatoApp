"""
Customer-specific data models (Info, RTM, Questions)

These models use composite_id instead of separate foreign keys.
The composite_id format is: <agency_id>_<campaigner_id>_<customer_id>
"""

from sqlmodel import Field, Column, String
from typing import Optional
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

