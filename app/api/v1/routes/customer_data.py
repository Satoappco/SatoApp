"""
Customer Data API routes
Handles CRUD operations for customer-specific data tables:
- Customer (merged table with client info)
- RTMTable (real-time monitoring links)
- QuestionsTable (pre-defined questions)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.users import Campaigner, Agency, Customer
from app.models.customer_data import RTMTable, QuestionsTable
from app.utils.composite_id import compose_id, decompose_id, extract_customer_id
from app.config.database import get_session

router = APIRouter(prefix="/customer-data", tags=["customer-data"])

# ===== Customer (Client Info) Schemas =====

class CustomerUpdate(BaseModel):
    """Schema for updating customer/client info"""
    full_name: Optional[str] = Field(None, max_length=255)
    login_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    opening_hours: Optional[str] = Field(None, max_length=255)
    narrative_report: Optional[str] = Field(None)
    website_url: Optional[str] = Field(None, max_length=500)
    facebook_page_url: Optional[str] = Field(None, max_length=500)
    instagram_page_url: Optional[str] = Field(None, max_length=500)
    llm_engine_preference: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

# ===== RTM Table Schemas =====

class RTMTableCreate(BaseModel):
    """Schema for creating RTM table entry"""
    agency_id: int
    campaigner_id: int
    customer_id: int
    link_1: Optional[str] = Field(None, max_length=500)
    link_2: Optional[str] = Field(None, max_length=500)
    link_3: Optional[str] = Field(None, max_length=500)
    link_4: Optional[str] = Field(None, max_length=500)
    link_5: Optional[str] = Field(None, max_length=500)
    link_6: Optional[str] = Field(None, max_length=500)
    link_7: Optional[str] = Field(None, max_length=500)
    link_8: Optional[str] = Field(None, max_length=500)
    link_9: Optional[str] = Field(None, max_length=500)
    link_10: Optional[str] = Field(None, max_length=500)

class RTMTableUpdate(BaseModel):
    """Schema for updating RTM table entry"""
    link_1: Optional[str] = Field(None, max_length=500)
    link_2: Optional[str] = Field(None, max_length=500)
    link_3: Optional[str] = Field(None, max_length=500)
    link_4: Optional[str] = Field(None, max_length=500)
    link_5: Optional[str] = Field(None, max_length=500)
    link_6: Optional[str] = Field(None, max_length=500)
    link_7: Optional[str] = Field(None, max_length=500)
    link_8: Optional[str] = Field(None, max_length=500)
    link_9: Optional[str] = Field(None, max_length=500)
    link_10: Optional[str] = Field(None, max_length=500)

# ===== Questions Table Schemas =====

class QuestionsTableCreate(BaseModel):
    """Schema for creating questions table entry"""
    agency_id: int
    campaigner_id: int
    customer_id: int
    q1: Optional[str] = Field(None, max_length=500)
    q2: Optional[str] = Field(None, max_length=500)
    q3: Optional[str] = Field(None, max_length=500)
    q4: Optional[str] = Field(None, max_length=500)
    q5: Optional[str] = Field(None, max_length=500)
    q6: Optional[str] = Field(None, max_length=500)
    q7: Optional[str] = Field(None, max_length=500)
    q8: Optional[str] = Field(None, max_length=500)
    q9: Optional[str] = Field(None, max_length=500)
    q10: Optional[str] = Field(None, max_length=500)

class QuestionsTableUpdate(BaseModel):
    """Schema for updating questions table entry"""
    q1: Optional[str] = Field(None, max_length=500)
    q2: Optional[str] = Field(None, max_length=500)
    q3: Optional[str] = Field(None, max_length=500)
    q4: Optional[str] = Field(None, max_length=500)
    q5: Optional[str] = Field(None, max_length=500)
    q6: Optional[str] = Field(None, max_length=500)
    q7: Optional[str] = Field(None, max_length=500)
    q8: Optional[str] = Field(None, max_length=500)
    q9: Optional[str] = Field(None, max_length=500)
    q10: Optional[str] = Field(None, max_length=500)

# ===== Customer (Client Info) Routes =====

@router.get("/customer/{customer_id}")
async def get_customer_info(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get customer/client info by customer ID"""
    try:
        with get_session() as session:
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer not found with ID: {customer_id}"
                )
            
            return {
                "success": True,
                "data": {
                    "id": customer.id,
                    "agency_id": customer.agency_id,
                    "full_name": customer.full_name,
                    "login_email": customer.login_email,
                    "phone": customer.phone,
                    "address": customer.address,
                    "opening_hours": customer.opening_hours,
                    "narrative_report": customer.narrative_report,
                    "website_url": customer.website_url,
                    "facebook_page_url": customer.facebook_page_url,
                    "instagram_page_url": customer.instagram_page_url,
                    "llm_engine_preference": customer.llm_engine_preference,
                    "status": customer.status,
                    "is_active": customer.is_active,
                    "created_at": customer.created_at.isoformat(),
                    "updated_at": customer.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customer info: {str(e)}"
        )

@router.put("/customer/{customer_id}")
async def update_customer_info(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update customer/client info by customer ID"""
    try:
        with get_session() as session:
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer not found with ID: {customer_id}"
                )
            
            # Update fields
            update_data = customer_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(customer, field, value)
            
            session.add(customer)
            session.commit()
            session.refresh(customer)
            
            return {
                "success": True,
                "message": "Customer info updated successfully",
                "data": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "login_email": customer.login_email,
                    "llm_engine_preference": customer.llm_engine_preference,
                    "is_active": customer.is_active,
                    "updated_at": customer.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer info: {str(e)}"
        )

# ===== RTM Table Routes =====

@router.post("/rtm-table")
async def create_rtm_table(
    rtm_data: RTMTableCreate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Create RTM table entry"""
    try:
        # Create composite_id
        composite_id = compose_id(
            rtm_data.agency_id,
            rtm_data.campaigner_id,
            rtm_data.customer_id
        )
        
        with get_session() as session:
            # Check if entry already exists
            existing = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"RTM table entry already exists for composite_id: {composite_id}"
                )
            
            # Create new entry
            rtm_entry = RTMTable(
                composite_id=composite_id,
                link_1=rtm_data.link_1,
                link_2=rtm_data.link_2,
                link_3=rtm_data.link_3,
                link_4=rtm_data.link_4,
                link_5=rtm_data.link_5,
                link_6=rtm_data.link_6,
                link_7=rtm_data.link_7,
                link_8=rtm_data.link_8,
                link_9=rtm_data.link_9,
                link_10=rtm_data.link_10
            )
            
            session.add(rtm_entry)
            session.commit()
            session.refresh(rtm_entry)
            
            return {
                "success": True,
                "message": "RTM table entry created successfully",
                "data": {
                    "id": rtm_entry.id,
                    "composite_id": rtm_entry.composite_id,
                    "created_at": rtm_entry.created_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create RTM table entry: {str(e)}"
        )

@router.get("/rtm-table/{composite_id}")
async def get_rtm_table_by_composite_id(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get RTM table entry by composite_id"""
    try:
        with get_session() as session:
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"RTM table entry not found for composite_id: {composite_id}"
                )
            
            return {
                "success": True,
                "data": {
                    "id": rtm_entry.id,
                    "composite_id": rtm_entry.composite_id,
                    "link_1": rtm_entry.link_1,
                    "link_2": rtm_entry.link_2,
                    "link_3": rtm_entry.link_3,
                    "link_4": rtm_entry.link_4,
                    "link_5": rtm_entry.link_5,
                    "link_6": rtm_entry.link_6,
                    "link_7": rtm_entry.link_7,
                    "link_8": rtm_entry.link_8,
                    "link_9": rtm_entry.link_9,
                    "link_10": rtm_entry.link_10,
                    "created_at": rtm_entry.created_at.isoformat(),
                    "updated_at": rtm_entry.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch RTM table entry: {str(e)}"
        )

@router.put("/rtm-table/{composite_id}")
async def update_rtm_table(
    composite_id: str,
    rtm_data: RTMTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update RTM table entry by composite_id"""
    try:
        with get_session() as session:
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"RTM table entry not found for composite_id: {composite_id}"
                )
            
            # Update fields
            update_data = rtm_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(rtm_entry, field, value)
            
            session.add(rtm_entry)
            session.commit()
            session.refresh(rtm_entry)
            
            return {
                "success": True,
                "message": "RTM table entry updated successfully",
                "data": {
                    "id": rtm_entry.id,
                    "composite_id": rtm_entry.composite_id,
                    "updated_at": rtm_entry.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update RTM table entry: {str(e)}"
        )

@router.delete("/rtm-table/{composite_id}")
async def delete_rtm_table(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Delete RTM table entry by composite_id"""
    try:
        with get_session() as session:
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"RTM table entry not found for composite_id: {composite_id}"
                )
            
            session.delete(rtm_entry)
            session.commit()
            
            return {
                "success": True,
                "message": "RTM table entry deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete RTM table entry: {str(e)}"
        )

# ===== Questions Table Routes =====

@router.post("/questions-table")
async def create_questions_table(
    questions_data: QuestionsTableCreate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Create questions table entry"""
    try:
        # Create composite_id
        composite_id = compose_id(
            questions_data.agency_id,
            questions_data.campaigner_id,
            questions_data.customer_id
        )
        
        with get_session() as session:
            # Check if entry already exists
            existing = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Questions table entry already exists for composite_id: {composite_id}"
                )
            
            # Create new entry
            questions_entry = QuestionsTable(
                composite_id=composite_id,
                q1=questions_data.q1,
                q2=questions_data.q2,
                q3=questions_data.q3,
                q4=questions_data.q4,
                q5=questions_data.q5,
                q6=questions_data.q6,
                q7=questions_data.q7,
                q8=questions_data.q8,
                q9=questions_data.q9,
                q10=questions_data.q10
            )
            
            session.add(questions_entry)
            session.commit()
            session.refresh(questions_entry)
            
            return {
                "success": True,
                "message": "Questions table entry created successfully",
                "data": {
                    "id": questions_entry.id,
                    "composite_id": questions_entry.composite_id,
                    "created_at": questions_entry.created_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create questions table entry: {str(e)}"
        )

@router.get("/questions-table/{composite_id}")
async def get_questions_table_by_composite_id(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get questions table entry by composite_id"""
    try:
        with get_session() as session:
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Questions table entry not found for composite_id: {composite_id}"
                )
            
            return {
                "success": True,
                "data": {
                    "id": questions_entry.id,
                    "composite_id": questions_entry.composite_id,
                    "q1": questions_entry.q1,
                    "q2": questions_entry.q2,
                    "q3": questions_entry.q3,
                    "q4": questions_entry.q4,
                    "q5": questions_entry.q5,
                    "q6": questions_entry.q6,
                    "q7": questions_entry.q7,
                    "q8": questions_entry.q8,
                    "q9": questions_entry.q9,
                    "q10": questions_entry.q10,
                    "created_at": questions_entry.created_at.isoformat(),
                    "updated_at": questions_entry.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch questions table entry: {str(e)}"
        )

@router.put("/questions-table/{composite_id}")
async def update_questions_table(
    composite_id: str,
    questions_data: QuestionsTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update questions table entry by composite_id"""
    try:
        with get_session() as session:
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Questions table entry not found for composite_id: {composite_id}"
                )
            
            # Update fields
            update_data = questions_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(questions_entry, field, value)
            
            session.add(questions_entry)
            session.commit()
            session.refresh(questions_entry)
            
            return {
                "success": True,
                "message": "Questions table entry updated successfully",
                "data": {
                    "id": questions_entry.id,
                    "composite_id": questions_entry.composite_id,
                    "updated_at": questions_entry.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update questions table entry: {str(e)}"
        )

@router.delete("/questions-table/{composite_id}")
async def delete_questions_table(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Delete questions table entry by composite_id"""
    try:
        with get_session() as session:
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Questions table entry not found for composite_id: {composite_id}"
                )
            
            session.delete(questions_entry)
            session.commit()
            
            return {
                "success": True,
                "message": "Questions table entry deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete questions table entry: {str(e)}"
        )