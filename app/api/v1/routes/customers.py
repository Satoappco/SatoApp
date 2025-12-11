"""
Customer Management API routes
Handles CRUD operations for customers with full initialization
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_
from pydantic import BaseModel, Field, EmailStr

from app.core.auth import get_current_user
from app.models.users import Agency, Campaigner, Customer, CustomerStatus, UserRole, CustomerCampaignerAssignment
from app.models.customer_data import RTMTable, QuestionsTable
from app.models.analytics import KpiGoal, DigitalAsset, Connection, UserPropertySelection, KpiValue
from app.config.database import get_session
from app.config.logging import get_logger
from app.services.customer_assignment_service import CustomerAssignmentService
from app.utils.priority_utils import CustomerPriorityData, compute_priority_scores

logger = get_logger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


# ===== Pydantic Schemas =====

class CustomerCreate(BaseModel):
    """Schema for creating a new customer"""
    full_name: str = Field(max_length=255, description="Full name or business name")
    contact_email: Optional[EmailStr] = Field(None, description="Primary business contact email address")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    address: Optional[str] = Field(None, max_length=500, description="Physical address")
    opening_hours: Optional[str] = Field(None, description="Business opening hours")
    narrative_report: Optional[str] = Field(None, description="Narrative report text")
    website_url: Optional[str] = Field(None, max_length=500, description="Website URL")
    facebook_page_url: Optional[str] = Field(None, max_length=500, description="Facebook page URL")
    instagram_page_url: Optional[str] = Field(None, max_length=500, description="Instagram page URL")
    llm_engine_preference: Optional[str] = Field(None, max_length=50, description="Preferred LLM engine")
    enable_meta: Optional[bool] = Field(None, description="Enable Meta/Facebook marketing features")
    enable_google: Optional[bool] = Field(None, description="Enable Google marketing features")
    importance: Optional[int] = Field(3, ge=1, le=5, description="Client importance level (1-5)")
    budget: Optional[float] = Field(0.0, ge=0, description="Monthly budget")
    campaign_health: Optional[int] = Field(3, ge=1, le=5, description="Campaign health score (1=bad, 5=excellent)")


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    full_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    opening_hours: Optional[str] = Field(None)
    narrative_report: Optional[str] = None
    website_url: Optional[str] = Field(None, max_length=500)
    facebook_page_url: Optional[str] = Field(None, max_length=500)
    instagram_page_url: Optional[str] = Field(None, max_length=500)
    llm_engine_preference: Optional[str] = Field(None, max_length=50)
    enable_meta: Optional[bool] = Field(None, description="Enable Meta/Facebook marketing features")
    enable_google: Optional[bool] = Field(None, description="Enable Google marketing features")
    status: Optional[CustomerStatus] = None
    is_active: Optional[bool] = None
    importance: Optional[int] = Field(None, ge=1, le=5, description="Client importance level (1-5)")
    budget: Optional[float] = Field(None, ge=0, description="Monthly budget")
    campaign_health: Optional[int] = Field(None, ge=1, le=5, description="Campaign health score (1=bad, 5=excellent)")
    last_work_date: Optional[datetime] = Field(None, description="Date of last work on this customer")


# ===== API Endpoints =====

@router.get("")
async def get_customers(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get all customers assigned to the current campaigner.
    Campaigners can only see customers they have created/are assigned to.
    """
    try:
        with get_session() as session:
            # Get only customers assigned to the current campaigner via junction table
            customer_ids = session.exec(
                select(CustomerCampaignerAssignment.customer_id).where(
                    and_(
                        CustomerCampaignerAssignment.campaigner_id == current_user.id,
                        CustomerCampaignerAssignment.is_active == True
                    )
                )
            ).all()

            if not customer_ids:
                return {
                    "success": True,
                    "customers": [],
                    "total": 0
                }

            # Get customers in current user's agency with the assigned IDs
            statement = select(Customer).where(
                and_(
                    Customer.agency_id == current_user.agency_id,
                    Customer.id.in_(customer_ids)
                )
            ).order_by(Customer.created_at.desc())

            customers = session.exec(statement).all()

            # Get all campaigner assignments for each customer
            customer_campaigners = {}
            for customer in customers:
                assignments = CustomerAssignmentService.get_customer_assignments(
                    session, customer.id, active_only=True
                )
                campaigners = []
                for assignment in assignments:
                    campaigner = session.get(Campaigner, assignment.campaigner_id)
                    if campaigner:
                        campaigners.append({
                            "id": campaigner.id,
                            "full_name": campaigner.full_name,
                            "email": campaigner.email,
                            "avatar_url": campaigner.avatar_url,
                            "is_primary": assignment.is_primary
                        })
                customer_campaigners[customer.id] = campaigners

            # Compute priority scores for all customers
            priority_data = []
            for customer in customers:
                priority_data.append(CustomerPriorityData(
                    customer_id=customer.id,
                    name=customer.full_name,
                    importance=customer.importance,
                    budget=customer.budget,
                    campaign_health=customer.campaign_health,
                    last_work_date=customer.last_work_date
                ))

            # Calculate priority scores
            priority_scores = {}
            if priority_data:
                try:
                    scores = compute_priority_scores(priority_data)
                    priority_scores = {s["customer_id"]: s for s in scores}
                except ValueError as e:
                    logger.warning(f"Priority calculation skipped: {str(e)}")

            return {
                "success": True,
                "customers": [
                    {
                        "id": customer.id,
                        "full_name": customer.full_name,
                        "contact_email": customer.contact_email,
                        "phone": customer.phone,
                        "address": customer.address,
                        "opening_hours": customer.opening_hours,
                        "narrative_report": customer.narrative_report,
                        "website_url": customer.website_url,
                        "facebook_page_url": customer.facebook_page_url,
                        "instagram_page_url": customer.instagram_page_url,
                        "llm_engine_preference": customer.llm_engine_preference,
                        "country": customer.country,
                        "currency": customer.currency,
                        "enable_meta": customer.enable_meta,
                        "enable_google": customer.enable_google,
                        "status": customer.status,
                        "is_active": customer.is_active,
                        "agency_id": customer.agency_id,
                        "agency_name": customer.agency_name,
                        "assigned_campaigners": customer_campaigners.get(customer.id, []),
                        "primary_campaigner_id": customer.primary_campaigner_id,
                        "importance": customer.importance,
                        "budget": customer.budget,
                        "campaign_health": customer.campaign_health,
                        "last_work_date": customer.last_work_date.isoformat() if customer.last_work_date else None,
                        "priority": priority_scores.get(customer.id, {}).get("score", 0),
                        "priority_details": priority_scores.get(customer.id, {}),
                        "created_at": customer.created_at.isoformat() if customer.created_at else None,
                        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None
                    }
                    for customer in customers
                ],
                "total": len(customers)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customers: {str(e)}"
        )


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a specific customer by ID.
    """
    try:
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # OWNER can only access customers in their own agency, ADMIN can access any
            if current_user.role != UserRole.ADMIN and customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )

            # Verify customer is assigned to current campaigner via junction table
            is_assigned = session.exec(
                select(CustomerCampaignerAssignment).where(
                    and_(
                        CustomerCampaignerAssignment.customer_id == customer_id,
                        CustomerCampaignerAssignment.campaigner_id == current_user.id,
                        CustomerCampaignerAssignment.is_active == True
                    )
                )
            ).first()

            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied - customer not assigned to you"
                )

            # Get related RTM and Questions data
            rtm_entry = session.exec(
                select(RTMTable).where(RTMTable.customer_id == customer_id)
            ).first()
            
            questions_entry = session.exec(
                select(QuestionsTable).where(QuestionsTable.customer_id == customer_id)
            ).first()

            # Get all assigned campaigners for this customer
            assignments = CustomerAssignmentService.get_customer_assignments(
                session, customer.id, active_only=True
            )
            assigned_campaigners = []
            for assignment in assignments:
                campaigner = session.get(Campaigner, assignment.campaigner_id)
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
                "customer": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "contact_email": customer.contact_email,
                    "phone": customer.phone,
                    "address": customer.address,
                    "opening_hours": customer.opening_hours,
                    "narrative_report": customer.narrative_report,
                    "website_url": customer.website_url,
                    "facebook_page_url": customer.facebook_page_url,
                    "instagram_page_url": customer.instagram_page_url,
                    "llm_engine_preference": customer.llm_engine_preference,
                    "country": customer.country,
                    "currency": customer.currency,
                    "enable_meta": customer.enable_meta,
                    "enable_google": customer.enable_google,
                    "status": customer.status,
                    "is_active": customer.is_active,
                    "agency_id": customer.agency_id,
                    "agency_name": customer.agency_name,
                    "assigned_campaigners": assigned_campaigners,
                    "primary_campaigner_id": customer.primary_campaigner_id,
                    "has_rtm_data": rtm_entry is not None,
                    "has_questions_data": questions_entry is not None,
                    "created_at": customer.created_at.isoformat() if customer.created_at else None,
                    "updated_at": customer.updated_at.isoformat() if customer.updated_at else None
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer: {str(e)}"
        )


@router.post("")
async def create_customer(
    request: CustomerCreate,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Create a new customer with initialization of related tables.
    Creates Customer, RTMTable, and QuestionsTable entries.
    """
    try:
        with get_session() as session:
            # Fetch agency name for denormalization
            agency = session.get(Agency, current_user.agency_id)
            agency_name = agency.name if agency else None

            # Create customer (without assigned_campaigner_id - use junction table instead)
            new_customer = Customer(
                agency_id=current_user.agency_id,
                full_name=request.full_name,
                contact_email=request.contact_email,
                phone=request.phone,
                address=request.address,
                opening_hours=request.opening_hours,
                narrative_report=request.narrative_report,
                website_url=request.website_url,
                facebook_page_url=request.facebook_page_url,
                instagram_page_url=request.instagram_page_url,
                llm_engine_preference=request.llm_engine_preference,
                enable_meta=request.enable_meta,
                enable_google=request.enable_google,
                agency_name=agency_name,  # Denormalized agency name
                status=CustomerStatus.ACTIVE,
                is_active=True,
                importance=request.importance if request.importance is not None else 3,
                budget=request.budget if request.budget is not None else 0.0,
                campaign_health=request.campaign_health if request.campaign_health is not None else 3
            )

            session.add(new_customer)
            session.commit()
            session.refresh(new_customer)

            # Create primary campaigner assignment via junction table
            from app.models.users import AssignmentRole
            CustomerAssignmentService.assign_campaigner(
                session=session,
                customer_id=new_customer.id,
                campaigner_id=current_user.id,
                is_primary=True,
                role=AssignmentRole.PRIMARY,
                assigned_by_id=current_user.id
            )
            
            # Initialize RTM Table entry with composite_id
            composite_id = f"{current_user.agency_id}_{current_user.id}_{new_customer.id}"
            rtm_entry = RTMTable(composite_id=composite_id)
            session.add(rtm_entry)
            
            # Initialize Questions Table entry with composite_id
            questions_entry = QuestionsTable(composite_id=composite_id)
            session.add(questions_entry)
            
            session.commit()
            
            # Create default data for the new customer
            try:
                from app.services.default_data_service import default_data_service
                default_data_service.create_default_data_for_customer(
                    new_customer.id,
                    current_user.agency_id,
                    current_user.id
                )
                logger.info(f"✅ Created default data for new customer {new_customer.id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to create default data for customer {new_customer.id}: {str(e)}")
                # Don't fail customer creation if default data fails

            # Get assigned campaigners for response
            assignments = CustomerAssignmentService.get_customer_assignments(
                session, new_customer.id, active_only=True
            )
            assigned_campaigners = []
            for assignment in assignments:
                campaigner = session.get(Campaigner, assignment.campaigner_id)
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
                "message": "Customer created successfully",
                "customer": {
                    "id": new_customer.id,
                    "full_name": new_customer.full_name,
                    "contact_email": new_customer.contact_email,
                    "phone": new_customer.phone,
                    "assigned_campaigners": assigned_campaigners,
                    "primary_campaigner_id": new_customer.primary_campaigner_id,
                    "status": new_customer.status,
                    "is_active": new_customer.is_active,
                    "created_at": new_customer.created_at.isoformat() if new_customer.created_at else None
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: int,
    request: CustomerUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update a customer's information.
    Only the assigned campaigner can update their customers.
    """
    try:
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # OWNER can only update customers in their own agency, ADMIN can update from any agency
            if current_user.role != UserRole.ADMIN and customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )

            # Verify customer is assigned to current campaigner via junction table
            is_assigned = session.exec(
                select(CustomerCampaignerAssignment).where(
                    and_(
                        CustomerCampaignerAssignment.customer_id == customer_id,
                        CustomerCampaignerAssignment.campaigner_id == current_user.id,
                        CustomerCampaignerAssignment.is_active == True
                    )
                )
            ).first()

            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied - customer not assigned to you"
                )

            # Update fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(customer, field, value)

            # Refresh denormalized agency name
            agency = session.get(Agency, customer.agency_id)
            customer.agency_name = agency.name if agency else None
            
            session.add(customer)
            session.commit()
            session.refresh(customer)

            # Get assigned campaigners for response
            assignments = CustomerAssignmentService.get_customer_assignments(
                session, customer.id, active_only=True
            )
            assigned_campaigners = []
            for assignment in assignments:
                campaigner = session.get(Campaigner, assignment.campaigner_id)
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
                "message": "Customer updated successfully",
                "customer": {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "contact_email": customer.contact_email,
                    "phone": customer.phone,
                    "address": customer.address,
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
                    "agency_name": customer.agency_name,
                    "assigned_campaigners": assigned_campaigners,
                    "primary_campaigner_id": customer.primary_campaigner_id,
                    "updated_at": customer.updated_at.isoformat() if customer.updated_at else None
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Delete a customer.
    Cascades to related tables (RTM, Questions, KPI Goals, etc.).
    Only OWNER and ADMIN can delete customers.
    """
    from app.models.users import UserRole
    
    # Check permissions
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can delete customers"
        )
    
    try:
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
            
            # OWNER can only delete customers in their own agency, ADMIN can delete from any agency
            if current_user.role != UserRole.ADMIN and customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this customer"
                )
            
            # Delete related entries (cascade should handle this, but being explicit)
            # Connections (must be deleted first as they reference digital_assets)
            connections = session.exec(
                select(Connection).where(Connection.customer_id == customer_id)
            ).all()
            # Track digital asset IDs to check for orphans after deletion
            digital_asset_ids = set()
            for connection in connections:
                digital_asset_ids.add(connection.digital_asset_id)
                session.delete(connection)
            session.commit()

            # Check for and delete orphaned digital assets
            from app.services.digital_asset_service import delete_orphaned_digital_asset
            for asset_id in digital_asset_ids:
                delete_orphaned_digital_asset(session, asset_id)
            
            # Digital Assets
            digital_assets = session.exec(
                select(DigitalAsset).where(DigitalAsset.customer_id == customer_id)
            ).all()
            for asset in digital_assets:
                session.delete(asset)
            
            # User Property Selections
            user_property_selections = session.exec(
                select(UserPropertySelection).where(UserPropertySelection.customer_id == customer_id)
            ).all()
            for selection in user_property_selections:
                session.delete(selection)
            
            # KPI Values (actual measured values)
            kpi_values = session.exec(
                select(KpiValue).where(KpiValue.customer_id == customer_id)
            ).all()
            for value in kpi_values:
                session.delete(value)
            
            # KPI Goals (target values)
            kpi_goals = session.exec(
                select(KpiGoal).where(KpiGoal.customer_id == customer_id)
            ).all()
            for goal in kpi_goals:
                session.delete(goal)
            
            # RTM Table (uses composite_id format: agency_id_campaigner_id_customer_id)
            rtm_entries = session.exec(
                select(RTMTable).where(RTMTable.composite_id.like(f"{customer.agency_id}_%_{customer_id}"))
            ).all()
            for entry in rtm_entries:
                session.delete(entry)
            
            # Questions Table (uses composite_id format: agency_id_campaigner_id_customer_id)
            questions_entries = session.exec(
                select(QuestionsTable).where(QuestionsTable.composite_id.like(f"{customer.agency_id}_%_{customer_id}"))
            ).all()
            for entry in questions_entries:
                session.delete(entry)
            
            # Delete customer
            session.delete(customer)
            session.commit()
            
            return {
                "success": True,
                "message": "Customer deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete customer: {str(e)}"
        )

