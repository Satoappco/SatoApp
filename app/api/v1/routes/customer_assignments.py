"""API endpoints for managing customer-campaigner assignments"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlmodel import Session
from typing import List
from pydantic import BaseModel

from app.config.database import get_session
from app.models.users import (
    Customer,
    Campaigner,
    CustomerCampaignerAssignment,
    AssignmentRole
)
from app.services.customer_assignment_service import CustomerAssignmentService
from app.core.api_auth import verify_api_token

router = APIRouter()


# Request/Response Models
class CampaignerAssignmentCreate(BaseModel):
    """Request model for creating a campaigner assignment"""
    campaigner_id: int
    is_primary: bool = False
    role: AssignmentRole = AssignmentRole.ASSIGNED


class CampaignerAssignmentResponse(BaseModel):
    """Response model for campaigner assignment"""
    id: int
    customer_id: int
    campaigner_id: int
    role: AssignmentRole
    is_primary: bool
    is_active: bool
    assigned_at: str

    class Config:
        from_attributes = True


class CampaignerWithAssignment(BaseModel):
    """Response model for campaigner with assignment details"""
    id: int
    email: str
    full_name: str
    avatar_url: str | None
    assignment_id: int
    role: AssignmentRole
    is_primary: bool
    assigned_at: str


# Endpoints
@router.get("/{customer_id}/campaigners", response_model=List[CampaignerWithAssignment])
async def get_customer_campaigners(
    customer_id: int = Path(..., description="Customer ID"),
    active_only: bool = Query(True, description="Only return active assignments"),
    session: Session = Depends(get_session),
    _: dict = Depends(verify_api_token)
):
    """Get all campaigners assigned to a customer"""
    # Verify customer exists
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get assignments
    assignments = CustomerAssignmentService.get_customer_assignments(
        session, customer_id, active_only
    )

    # Build response with campaigner details
    result = []
    for assignment in assignments:
        campaigner = session.get(Campaigner, assignment.campaigner_id)
        if campaigner:
            result.append(CampaignerWithAssignment(
                id=campaigner.id,
                email=campaigner.email,
                full_name=campaigner.full_name,
                avatar_url=campaigner.avatar_url,
                assignment_id=assignment.id,
                role=assignment.role,
                is_primary=assignment.is_primary,
                assigned_at=assignment.assigned_at.isoformat()
            ))

    return result


@router.post("/{customer_id}/campaigners", response_model=CampaignerAssignmentResponse)
async def assign_campaigner_to_customer(
    customer_id: int = Path(..., description="Customer ID"),
    assignment: CampaignerAssignmentCreate = ...,
    session: Session = Depends(get_session),
    token_info: dict = Depends(verify_api_token)
):
    """Assign a campaigner to a customer"""
    # Verify customer exists
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify campaigner exists
    campaigner = session.get(Campaigner, assignment.campaigner_id)
    if not campaigner:
        raise HTTPException(status_code=404, detail="Campaigner not found")

    # Create assignment
    try:
        new_assignment = CustomerAssignmentService.assign_campaigner(
            session=session,
            customer_id=customer_id,
            campaigner_id=assignment.campaigner_id,
            is_primary=assignment.is_primary,
            role=assignment.role,
            assigned_by_id=None  # TODO: Get from token_info when auth is implemented
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CampaignerAssignmentResponse(
        id=new_assignment.id,
        customer_id=new_assignment.customer_id,
        campaigner_id=new_assignment.campaigner_id,
        role=new_assignment.role,
        is_primary=new_assignment.is_primary,
        is_active=new_assignment.is_active,
        assigned_at=new_assignment.assigned_at.isoformat()
    )


@router.delete("/{customer_id}/campaigners/{campaigner_id}")
async def unassign_campaigner_from_customer(
    customer_id: int = Path(..., description="Customer ID"),
    campaigner_id: int = Path(..., description="Campaigner ID"),
    session: Session = Depends(get_session),
    token_info: dict = Depends(verify_api_token)
):
    """Remove a campaigner assignment from a customer"""
    # Verify customer exists
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Unassign
    success = CustomerAssignmentService.unassign_campaigner(
        session=session,
        customer_id=customer_id,
        campaigner_id=campaigner_id,
        unassigned_by_id=None  # TODO: Get from token_info when auth is implemented
    )

    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return {"success": True, "message": "Campaigner unassigned successfully"}


@router.put("/{customer_id}/campaigners/{campaigner_id}/primary")
async def set_primary_campaigner(
    customer_id: int = Path(..., description="Customer ID"),
    campaigner_id: int = Path(..., description="Campaigner ID"),
    session: Session = Depends(get_session),
    _: dict = Depends(verify_api_token)
):
    """Set a campaigner as the primary campaigner for a customer"""
    # Verify customer exists
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Set as primary
    try:
        assignment = CustomerAssignmentService.set_primary_campaigner(
            session=session,
            customer_id=customer_id,
            campaigner_id=campaigner_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CampaignerAssignmentResponse(
        id=assignment.id,
        customer_id=assignment.customer_id,
        campaigner_id=assignment.campaigner_id,
        role=assignment.role,
        is_primary=assignment.is_primary,
        is_active=assignment.is_active,
        assigned_at=assignment.assigned_at.isoformat()
    )


@router.get("/campaigners/{campaigner_id}/customers", response_model=List[dict])
async def get_campaigner_customers(
    campaigner_id: int = Path(..., description="Campaigner ID"),
    active_only: bool = Query(True, description="Only return active assignments"),
    session: Session = Depends(get_session),
    _: dict = Depends(verify_api_token)
):
    """Get all customers assigned to a campaigner"""
    # Verify campaigner exists
    campaigner = session.get(Campaigner, campaigner_id)
    if not campaigner:
        raise HTTPException(status_code=404, detail="Campaigner not found")

    # Get customers
    customers = CustomerAssignmentService.get_campaigner_customers(
        session, campaigner_id, active_only
    )

    return [
        {
            "id": customer.id,
            "full_name": customer.full_name,
            "status": customer.status,
            "agency_id": customer.agency_id,
            "is_active": customer.is_active
        }
        for customer in customers
    ]
