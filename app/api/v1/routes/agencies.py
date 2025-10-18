"""
Agency API routes for fetching and managing agencies and customers
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.users import Agency, Customer, Campaigner, CustomerType, CustomerStatus, UserRole
from app.config.database import get_session

router = APIRouter(prefix="/agencies", tags=["agencies"])


class CreateAgencyRequest(BaseModel):
    """Request model for creating a new agency"""
    name: str
    type: CustomerType = CustomerType.BRAND
    status: CustomerStatus = CustomerStatus.TRIAL
    plan: str = "Basic"
    billing_currency: str = "ILS"
    vat_id: Optional[str] = None
    address: Optional[str] = None
    domains: List[str] = []
    tags: List[str] = []
    notes: Optional[str] = None


class UpdateAgencyRequest(BaseModel):
    """Request model for updating an agency"""
    name: Optional[str] = None
    type: Optional[CustomerType] = None
    status: Optional[CustomerStatus] = None
    plan: Optional[str] = None
    billing_currency: Optional[str] = None
    vat_id: Optional[str] = None
    address: Optional[str] = None
    domains: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/")
async def get_agencies(
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Get all agencies for the current authenticated campaigner with main agency identified
    """
    try:
        with get_session() as session:
            # Get current campaigner's primary agency and additional agencies
            campaigner = current_campaigner
            
            agencies = []
            main_agency_id = campaigner.agency_id
            
            # Get primary agency
            primary_agency = session.get(Agency, campaigner.agency_id)
            if primary_agency:
                agencies.append({
                    "id": primary_agency.id,
                    "name": primary_agency.name,
                    "email": primary_agency.email,
                    "phone": primary_agency.phone,
                    "status": primary_agency.status,
                    "is_main": True
                })
            
            # Note: Additional agencies removed - campaigners now belong to single agency
            
            return {
                "success": True,
                "agencies": agencies,
                "main_agency_id": main_agency_id,
                "total": len(agencies)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agencies: {str(e)}"
        )


@router.get("/{agency_id}/customers")
async def get_agency_customers(
    agency_id: int,
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Get all customers for a specific agency
    """
    try:
        with get_session() as session:
            # Verify agency exists
            agency = session.get(Agency, agency_id)
            if not agency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agency not found"
                )
            
            # Get customers for this agency
            statement = select(Customer).where(
                Customer.agency_id == agency_id
            )
            customers = session.exec(statement).all()
            
            return {
                "success": True,
                "customers": [
                    {
                        "id": c.id,
                        "full_name": c.full_name,
                        "agency_id": c.agency_id,
                        "status": c.status,
                        "login_email": c.login_email,
                        "phone": c.phone,
                        "address": c.address,
                        "opening_hours": c.opening_hours,
                        "website_url": c.website_url,
                        "facebook_page_url": c.facebook_page_url,
                        "instagram_page_url": c.instagram_page_url,
                        "is_active": c.is_active,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "updated_at": c.updated_at.isoformat() if c.updated_at else None
                    }
                    for c in customers
                ],
                "total": len(customers)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customers: {str(e)}"
        )


@router.get("/{agency_id}")
async def get_agency(
    agency_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a specific agency by ID
    """
    try:
        with get_session() as session:
            agency = session.get(Agency, agency_id)
            if not agency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agency not found"
                )
            
            return {
                "success": True,
                "agency": {
                    "id": agency.id,
                    "name": agency.name,
                    "email": agency.email,
                    "phone": agency.phone,
                    "status": agency.status,
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agency: {str(e)}"
        )


@router.post("/")
async def create_agency(
    request: CreateAgencyRequest,
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Create a new agency (Admin only)
    """
    # Check if user is admin
    # Check if user has permission (admin or owner)
    if current_campaigner.role not in [UserRole.ADMIN, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create agencies"
        )
    
    try:
        with get_session() as session:
            # Create new agency
            new_agency = Agency(
                name=request.name,
                type=request.type,
                status=request.status,
                plan=request.plan,
                billing_currency=request.billing_currency,
                vat_id=request.vat_id,
                address=request.address,
                domains=request.domains,
                tags=request.tags,
                notes=request.notes
            )
            
            session.add(new_agency)
            session.commit()
            session.refresh(new_agency)
            
            return {
                "success": True,
                "message": "Agency created successfully",
                "agency": {
                    "id": new_agency.id,
                    "name": new_agency.name,
                    "type": new_agency.type,
                    "status": new_agency.status,
                    "plan": new_agency.plan,
                    "billing_currency": new_agency.billing_currency
                }
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agency: {str(e)}"
        )


@router.put("/{agency_id}")
async def update_agency(
    agency_id: int,
    request: UpdateAgencyRequest,
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Update an agency (Admin only)
    """
    # Check if user is admin
    # Check if user has permission (admin or owner)
    if current_campaigner.role not in [UserRole.ADMIN, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update agencies"
        )
    
    try:
        with get_session() as session:
            # Get agency
            agency = session.get(Agency, agency_id)
            
            if not agency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agency not found"
                )
            
            # Update agency fields
            if request.name is not None:
                agency.name = request.name
            if request.type is not None:
                agency.type = request.type
            if request.status is not None:
                agency.status = request.status
            if request.plan is not None:
                agency.plan = request.plan
            if request.billing_currency is not None:
                agency.billing_currency = request.billing_currency
            if request.vat_id is not None:
                agency.vat_id = request.vat_id
            if request.address is not None:
                agency.address = request.address
            if request.domains is not None:
                agency.domains = request.domains
            if request.tags is not None:
                agency.tags = request.tags
            if request.notes is not None:
                agency.notes = request.notes
            
            session.add(agency)
            session.commit()
            session.refresh(agency)
            
            return {
                "success": True,
                "message": "Agency updated successfully",
                "agency": {
                    "id": agency.id,
                    "name": agency.name,
                    "email": agency.email,
                    "phone": agency.phone,
                    "status": agency.status
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agency: {str(e)}"
        )


@router.delete("/{agency_id}")
async def delete_agency(
    agency_id: int,
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Delete an agency (Admin only)
    """
    # Check if user is admin
    # Check if user has permission (admin or owner)
    if current_campaigner.role not in [UserRole.ADMIN, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete agencies"
        )
    
    try:
        with get_session() as session:
            # Get agency
            agency = session.get(Agency, agency_id)
            
            if not agency:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agency not found"
                )
            
            # Delete agency
            session.delete(agency)
            session.commit()
            
            return {
                "success": True,
                "message": "Agency deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agency: {str(e)}"
        )
