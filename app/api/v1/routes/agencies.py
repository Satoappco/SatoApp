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
    email: Optional[str] = None
    phone: Optional[str] = None
    status: CustomerStatus = CustomerStatus.ACTIVE


class UpdateAgencyRequest(BaseModel):
    """Request model for updating an agency"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[CustomerStatus] = None


@router.get("/")
async def get_agencies(
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Get agencies for the current user
    - Regular users (OWNER, CAMPAIGNER, VIEWER): only their own agency
    - Admin users: all agencies
    """
    try:
        with get_session() as session:
            agencies = []
            main_agency_id = current_campaigner.agency_id
            
            # Check if user is admin - only ADMIN can see all agencies
            if current_campaigner.role == UserRole.ADMIN:
                # Get all agencies for admin
                statement = select(Agency).order_by(Agency.name)
                all_agencies = session.exec(statement).all()
                
                for agency in all_agencies:
                    agencies.append({
                        "id": agency.id,
                        "name": agency.name,
                        "email": agency.email,
                        "phone": agency.phone,
                        "status": agency.status,
                        "created_at": agency.created_at.isoformat() if agency.created_at else None,
                        "updated_at": agency.updated_at.isoformat() if agency.updated_at else None
                    })
            else:
                # Regular users (including OWNER) only see their own agency
                primary_agency = session.get(Agency, current_campaigner.agency_id)
                if primary_agency:
                    agencies.append({
                        "id": primary_agency.id,
                        "name": primary_agency.name,
                        "email": primary_agency.email,
                        "phone": primary_agency.phone,
                        "status": primary_agency.status,
                        "created_at": primary_agency.created_at.isoformat() if primary_agency.created_at else None,
                        "updated_at": primary_agency.updated_at.isoformat() if primary_agency.updated_at else None
                    })
            
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


@router.get("/list")
async def get_agencies_list(
    current_campaigner: Campaigner = Depends(get_current_user)
):
    """
    Get lightweight list of agencies for dropdown population.
    Returns only id and name for efficient dropdown loading.
    """
    try:
        with get_session() as session:
            statement = select(Agency).order_by(Agency.name)
            agencies = session.exec(statement).all()
            
            return {
                "success": True,
                "agencies": [
                    {
                        "id": agency.id,
                        "name": agency.name
                    }
                    for agency in agencies
                ]
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agencies list: {str(e)}"
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
                        "contact_email": c.contact_email,
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
                    "created_at": agency.created_at.isoformat() if agency.created_at else None,
                    "updated_at": agency.updated_at.isoformat() if agency.updated_at else None
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
    # Check if user is admin - only ADMIN can create agencies
    if current_campaigner.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create agencies"
        )
    
    try:
        with get_session() as session:
            # Create new agency
            new_agency = Agency(
                name=request.name,
                email=request.email,
                phone=request.phone,
                status=request.status
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
                    "email": new_agency.email,
                    "phone": new_agency.phone,
                    "status": new_agency.status,
                    "created_at": new_agency.created_at.isoformat() if new_agency.created_at else None,
                    "updated_at": new_agency.updated_at.isoformat() if new_agency.updated_at else None
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
    # Check if user is admin - only ADMIN can update agencies
    if current_campaigner.role != UserRole.ADMIN:
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
            if request.email is not None:
                agency.email = request.email
            if request.phone is not None:
                agency.phone = request.phone
            if request.status is not None:
                agency.status = request.status
            
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
                    "status": agency.status,
                    "created_at": agency.created_at.isoformat() if agency.created_at else None,
                    "updated_at": agency.updated_at.isoformat() if agency.updated_at else None
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
    # Check if user is admin - only ADMIN can delete agencies
    if current_campaigner.role != UserRole.ADMIN:
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
