"""
Customer Data Management API routes
Handles RTM Table and Questions Table operations
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, and_
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.users import Campaigner, Customer
from app.models.customer_data import RTMTable, QuestionsTable, RTMTableResponse, QuestionsTableResponse, RTMTableUpdate, QuestionsTableUpdate
from app.models.analytics import KpiSettings


def create_composite_id(agency_id: int, campaigner_id: int, customer_id: int) -> str:
    """Create composite ID from individual components"""
    return f"{agency_id}_{campaigner_id}_{customer_id}"
from app.config.database import get_session
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/customer-data", tags=["customer-data"])


# ===== Pydantic Schemas =====

class RTMTableResponse(BaseModel):
    """Response schema for RTM Table"""
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


class RTMTableUpdate(BaseModel):
    """Schema for updating RTM Table"""
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


class QuestionsTableResponse(BaseModel):
    """Response schema for Questions Table"""
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


class QuestionsTableUpdate(BaseModel):
    """Schema for updating Questions Table"""
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


# ===== Helper Functions =====

def create_composite_id(agency_id: int, campaigner_id: int, customer_id: int) -> str:
    """Create composite ID for customer data tables"""
    return f"{agency_id}_{campaigner_id}_{customer_id}"


# ===== RTM Table Endpoints =====

@router.get("/rtm-table/{composite_id}")
async def get_rtm_table_by_composite_id(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get RTM table by composite_id (for frontend compatibility)"""
    try:
        with get_session() as session:
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="RTM table not found for this composite_id"
                )
            
            return {
                "success": True,
                "data": RTMTableResponse.model_validate(rtm_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get RTM table for composite_id {composite_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get RTM table: {str(e)}"
        )


@router.put("/rtm-table/{composite_id}")
async def update_rtm_table_by_composite_id(
    composite_id: str,
    request: RTMTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update RTM table by composite_id (for frontend compatibility)"""
    try:
        with get_session() as session:
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="RTM table not found for this composite_id"
                )
            
            # Update only provided fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(rtm_entry, field, value)
            
            session.add(rtm_entry)
            session.commit()
            session.refresh(rtm_entry)
            
            return {
                "success": True,
                "message": "RTM table updated successfully",
                "data": RTMTableResponse.model_validate(rtm_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RTM table for composite_id {composite_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update RTM table: {str(e)}"
        )


@router.get("/rtm/{customer_id}")
async def get_rtm_table(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get RTM table for a specific customer"""
    try:
        with get_session() as session:
            composite_id = create_composite_id(current_user.agency_id, current_user.id, customer_id)
            
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="RTM table not found for this customer"
                )
            
            return {
                "success": True,
                "data": RTMTableResponse.model_validate(rtm_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get RTM table for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get RTM table: {str(e)}"
        )


@router.put("/rtm/{customer_id}")
async def update_rtm_table(
    customer_id: int,
    request: RTMTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update RTM table for a specific customer"""
    try:
        with get_session() as session:
            composite_id = create_composite_id(current_user.agency_id, current_user.id, customer_id)
            
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if not rtm_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="RTM table not found for this customer"
                )
            
            # Update only provided fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(rtm_entry, field, value)
            
            session.add(rtm_entry)
            session.commit()
            session.refresh(rtm_entry)
            
            return {
                "success": True,
                "message": "RTM table updated successfully",
                "data": RTMTableResponse.model_validate(rtm_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RTM table for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update RTM table: {str(e)}"
        )


# ===== Questions Table Endpoints =====

@router.get("/questions-table/{composite_id}")
async def get_questions_table_by_composite_id(
    composite_id: str,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get Questions table by composite_id (for frontend compatibility)"""
    try:
        # Extract customer_id from composite_id (format: agency_id_campaigner_id_customer_id)
        logger.info(f"🔍 Extracting customer_id from composite_id: {composite_id}")
        try:
            # Simple extraction without import to avoid issues
            parts = composite_id.split("_")
            if len(parts) != 3:
                raise ValueError(f"Invalid composite_id format: {composite_id}")
            customer_id = int(parts[2])
            logger.info(f"✅ Extracted customer_id: {customer_id}")
        except Exception as extract_error:
            logger.error(f"❌ Failed to extract customer_id from {composite_id}: {extract_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid composite_id format: {composite_id}"
            )
        
        with get_session() as session:
            # First, verify the customer belongs to the user's agency
            from app.models.users import Customer
            logger.info(f"🔍 Looking for customer with ID: {customer_id}")
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                logger.error(f"❌ Customer not found with ID: {customer_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            logger.info(f"✅ Found customer: {customer.full_name} (agency_id: {customer.agency_id})")
            logger.info(f"🔍 Current user agency_id: {current_user.agency_id}")
            
            if customer.agency_id != current_user.agency_id:
                logger.error(f"❌ Agency mismatch: customer agency {customer.agency_id} != user agency {current_user.agency_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer's data"
                )
            
            # Get questions table by composite_id pattern matching
            # Look for any Questions data where the composite_id ends with the customer_id
            logger.info(f"🔍 Looking for QuestionsTable with customer_id: {customer_id}")
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id.like(f"%_{customer_id}"))
            ).first()
            
            if not questions_entry:
                logger.error(f"❌ QuestionsTable not found for customer_id: {customer_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Questions table not found for this customer"
                )
            
            logger.info(f"✅ Found QuestionsTable: {questions_entry.id}")
            
            try:
                response_data = QuestionsTableResponse.model_validate(questions_entry)
                logger.info(f"✅ Successfully created response data")
                return {
                    "success": True,
                    "data": response_data
                }
            except Exception as response_error:
                logger.error(f"❌ Failed to create response from QuestionsTable: {response_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to format response data: {str(response_error)}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Questions table for composite_id {composite_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Questions table: {str(e)}"
        )


@router.put("/questions-table/{composite_id}")
async def update_questions_table_by_composite_id(
    composite_id: str,
    request: QuestionsTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update Questions table by composite_id (for frontend compatibility)"""
    try:
        # Extract customer_id from composite_id
        logger.info(f"🔍 PUT: Extracting customer_id from composite_id: {composite_id}")
        try:
            # Simple extraction without import to avoid issues
            parts = composite_id.split("_")
            if len(parts) != 3:
                raise ValueError(f"Invalid composite_id format: {composite_id}")
            customer_id = int(parts[2])
            logger.info(f"✅ PUT: Extracted customer_id: {customer_id}")
        except Exception as extract_error:
            logger.error(f"❌ PUT: Failed to extract customer_id from {composite_id}: {extract_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid composite_id format: {composite_id}"
            )
        
        with get_session() as session:
            # First, verify the customer belongs to the user's agency
            from app.models.users import Customer
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer's data"
                )
            
            # Get questions table by composite_id pattern matching
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id.like(f"%_{customer_id}"))
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Questions table not found for this customer"
                )
            
            # Update only provided fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(questions_entry, field, value)
            
            session.add(questions_entry)
            session.commit()
            session.refresh(questions_entry)
            
            return {
                "success": True,
                "message": "Questions table updated successfully",
                "data": QuestionsTableResponse.model_validate(questions_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update Questions table for composite_id {composite_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update Questions table: {str(e)}"
        )


@router.get("/questions/{customer_id}")
async def get_questions_table(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get Questions table for a specific customer"""
    try:
        with get_session() as session:
            composite_id = create_composite_id(current_user.agency_id, current_user.id, customer_id)
            
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Questions table not found for this customer"
                )
            
            return {
                "success": True,
                "data": QuestionsTableResponse.model_validate(questions_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Questions table for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Questions table: {str(e)}"
        )


@router.put("/questions/{customer_id}")
async def update_questions_table(
    customer_id: int,
    request: QuestionsTableUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update Questions table for a specific customer"""
    try:
        with get_session() as session:
            composite_id = create_composite_id(current_user.agency_id, current_user.id, customer_id)
            
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if not questions_entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Questions table not found for this customer"
                )
            
            # Update only provided fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(questions_entry, field, value)
            
            session.add(questions_entry)
            session.commit()
            session.refresh(questions_entry)
            
            return {
                "success": True,
                "message": "Questions table updated successfully",
                "data": QuestionsTableResponse.model_validate(questions_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update Questions table for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update Questions table: {str(e)}"
        )


# ===== Customer Information Endpoint =====

@router.get("/customer/{customer_id}")
async def get_customer_info(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """Get comprehensive customer information including RTM and Questions data"""
    try:
        with get_session() as session:
            # Get customer
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # Verify customer is in the same agency
            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )
            
            # Get RTM data - use pattern matching to find ANY record for this customer in this agency
            # Format: agency_id_*_customer_id (any campaigner)
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.composite_id.like(f"{customer.agency_id}_%_{customer_id}"))
            ).first()

            # Get Questions data - use pattern matching to find ANY record for this customer in this agency
            # Format: agency_id_*_customer_id (any campaigner)
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id.like(f"{customer.agency_id}_%_{customer_id}"))
            ).first()
            
            # Create empty RTM data if none exists
            if rtm_entry:
                rtm_data = RTMTableResponse.model_validate(rtm_entry)
            else:
                rtm_data = RTMTableResponse(
                    id=0,
                    composite_id=f"{customer.agency_id}_{current_user.id}_{customer_id}",
                    link_1=None,
                    link_2=None,
                    link_3=None,
                    link_4=None,
                    link_5=None,
                    link_6=None,
                    link_7=None,
                    link_8=None,
                    link_9=None,
                    link_10=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            
            # Create empty Questions data if none exists
            if questions_entry:
                questions_data = QuestionsTableResponse.model_validate(questions_entry)
            else:
                questions_data = QuestionsTableResponse(
                    id=0,
                    composite_id=f"{customer.agency_id}_{current_user.id}_{customer_id}",
                    q1=None,
                    q2=None,
                    q3=None,
                    q4=None,
                    q5=None,
                    q6=None,
                    q7=None,
                    q8=None,
                    q9=None,
                    q10=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )

            # Get assigned campaigners for this customer
            from app.services.customer_assignment_service import CustomerAssignmentService
            from app.models.users import Campaigner as CampaignerModel
            assignments = CustomerAssignmentService.get_customer_assignments(
                session, customer.id, active_only=True
            )
            assigned_campaigners = []
            for assignment in assignments:
                campaigner = session.get(CampaignerModel, assignment.campaigner_id)
                if campaigner:
                    assigned_campaigners.append({
                        "id": campaigner.id,
                        "full_name": campaigner.full_name,
                        "email": campaigner.email,
                        "avatar_url": campaigner.avatar_url,
                        "is_primary": assignment.is_primary
                    })

            return {
                "success": True,
                "data": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "contact_email": customer.contact_email,
                    "phone": customer.phone,
                    "address": customer.address,
                    "country": customer.country,
                    "currency": customer.currency,
                    "opening_hours": customer.opening_hours,
                    "narrative_report": customer.narrative_report,
                    "website_url": customer.website_url,
                    "facebook_page_url": customer.facebook_page_url,
                    "instagram_page_url": customer.instagram_page_url,
                    "llm_engine_preference": customer.llm_engine_preference,
                    "enable_meta": customer.enable_meta,
                    "enable_google": customer.enable_google,
                    "status": customer.status,
                    "is_active": customer.is_active,
                    "agency_id": customer.agency_id,
                    "assigned_campaigners": assigned_campaigners,
                    "primary_campaigner_id": customer.primary_campaigner_id,
                    "created_at": customer.created_at.isoformat(),
                    "updated_at": customer.updated_at.isoformat(),
                    "rtm_data": rtm_data,
                    "questions_data": questions_data,
                    "has_rtm_data": rtm_entry is not None,
                    "has_questions_data": questions_entry is not None
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer info for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer info: {str(e)}"
        )


@router.put("/customer/{customer_id}")
async def update_customer_info(
    customer_id: int,
    request: dict,
    current_user: Campaigner = Depends(get_current_user)
):
    """Update customer information"""
    try:
        with get_session() as session:
            # Get customer
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # Verify customer is in the same agency
            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )

            # Store old currency before update to detect changes
            old_currency = customer.currency

            # Update customer fields (removed assigned_campaigner_id - use customer_assignments endpoint)
            update_fields = [
                'full_name', 'contact_email', 'phone', 'address', 'opening_hours',
                'narrative_report', 'website_url', 'facebook_page_url',
                'instagram_page_url', 'llm_engine_preference', 'enable_meta', 'enable_google',
                'status', 'is_active', 'country', 'currency'
            ]
            
            for field in update_fields:
                if field in request:
                    setattr(customer, field, request[field])
            
            session.add(customer)
            
            # Update KPI settings currency units if currency changed
            if 'currency' in request and old_currency != customer.currency and customer.currency:
                from app.core.constants import CURRENCIES
                
                # Get new currency symbol
                currency_info = CURRENCIES.get(customer.currency)
                if currency_info:
                    new_currency_symbol = currency_info.symbol
                    
                    # Currency unit detection - standard symbols and Hebrew
                    currency_units = ['₪', '$', '€', '£', '¥', 'ש"ח']
                    
                    # Find all KPI settings for this customer with currency units
                    pattern = f"{customer.agency_id}_%_{customer_id}"
                    kpi_settings = session.exec(
                        select(KpiSettings).where(
                            KpiSettings.composite_id.like(pattern)
                        )
                    ).all()
                    
                    updated_count = 0
                    for kpi_setting in kpi_settings:
                        # Check if unit is a currency symbol
                        if kpi_setting.unit in currency_units:
                            kpi_setting.unit = new_currency_symbol
                            session.add(kpi_setting)
                            updated_count += 1
                    
                    if updated_count > 0:
                        logger.info(f"Updated {updated_count} KPI settings with new currency symbol {new_currency_symbol} for customer {customer_id}")
            
            session.commit()
            session.refresh(customer)

            # Get assigned campaigners for response
            from app.services.customer_assignment_service import CustomerAssignmentService
            from app.models.users import Campaigner as CampaignerModel
            assignments = CustomerAssignmentService.get_customer_assignments(
                session, customer.id, active_only=True
            )
            assigned_campaigners = []
            for assignment in assignments:
                campaigner = session.get(CampaignerModel, assignment.campaigner_id)
                if campaigner:
                    assigned_campaigners.append({
                        "id": campaigner.id,
                        "full_name": campaigner.full_name,
                        "email": campaigner.email,
                        "avatar_url": campaigner.avatar_url,
                        "is_primary": assignment.is_primary
                    })

            return {
                "success": True,
                "message": "Customer information updated successfully",
                "data": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "contact_email": customer.contact_email,
                    "phone": customer.phone,
                    "address": customer.address,
                    "country": customer.country,
                    "currency": customer.currency,
                    "opening_hours": customer.opening_hours,
                    "narrative_report": customer.narrative_report,
                    "website_url": customer.website_url,
                    "facebook_page_url": customer.facebook_page_url,
                    "instagram_page_url": customer.instagram_page_url,
                    "llm_engine_preference": customer.llm_engine_preference,
                    "enable_meta": customer.enable_meta,
                    "enable_google": customer.enable_google,
                    "status": customer.status,
                    "is_active": customer.is_active,
                    "agency_id": customer.agency_id,
                    "assigned_campaigners": assigned_campaigners,
                    "primary_campaigner_id": customer.primary_campaigner_id,
                    "created_at": customer.created_at.isoformat(),
                    "updated_at": customer.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update customer info for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer info: {str(e)}"
        )


# ===== RTM Table Create/Update Endpoints =====

@router.post("/rtm-table")
async def create_rtm_table(
    request: dict,
    current_user: Campaigner = Depends(get_current_user)
):
    """Create new RTM table entry"""
    try:
        # Validate request data
        if not request.get('customer_id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="customer_id is required"
            )
        
        customer_id = request.get('customer_id')
        
        with get_session() as session:
            # Get customer to verify access
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )
            
            # Create composite_id
            composite_id = create_composite_id(customer.agency_id, current_user.id, customer_id)
            
            # Check if record already exists
            existing = session.exec(
                select(RTMTable).where(RTMTable.composite_id == composite_id)
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="RTM table already exists for this customer"
                )
            
            # Create new RTM record
            rtm_entry = RTMTable(
                composite_id=composite_id,
                link_1=request.get('link_1'),
                link_2=request.get('link_2'),
                link_3=request.get('link_3'),
                link_4=request.get('link_4'),
                link_5=request.get('link_5'),
                link_6=request.get('link_6'),
                link_7=request.get('link_7'),
                link_8=request.get('link_8'),
                link_9=request.get('link_9'),
                link_10=request.get('link_10')
            )
            
            session.add(rtm_entry)
            session.commit()
            session.refresh(rtm_entry)
            
            return {
                "success": True,
                "message": "RTM table created successfully",
                "data": RTMTableResponse.model_validate(rtm_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create RTM table: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create RTM table: {str(e)}"
        )


@router.post("/questions-table")
async def create_questions_table(
    request: dict,
    current_user: Campaigner = Depends(get_current_user)
):
    """Create new Questions table entry"""
    try:
        # Validate request data
        if not request.get('customer_id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="customer_id is required"
            )
        
        customer_id = request.get('customer_id')
        
        with get_session() as session:
            # Get customer to verify access
            customer = session.exec(
                select(Customer).where(Customer.id == customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )
            
            # Create composite_id
            composite_id = create_composite_id(customer.agency_id, current_user.id, customer_id)
            
            # Check if record already exists
            existing = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Questions table already exists for this customer"
                )
            
            # Create new Questions record
            questions_entry = QuestionsTable(
                composite_id=composite_id,
                q1=request.get('q1'),
                q2=request.get('q2'),
                q3=request.get('q3'),
                q4=request.get('q4'),
                q5=request.get('q5'),
                q6=request.get('q6'),
                q7=request.get('q7'),
                q8=request.get('q8'),
                q9=request.get('q9'),
                q10=request.get('q10')
            )
            
            session.add(questions_entry)
            session.commit()
            session.refresh(questions_entry)
            
            return {
                "success": True,
                "message": "Questions table created successfully",
                "data": QuestionsTableResponse.model_validate(questions_entry)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Questions table: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Questions table: {str(e)}"
        )