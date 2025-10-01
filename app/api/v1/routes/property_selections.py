"""
API endpoints for managing user property selections
Handles saving and retrieving selected Google Analytics properties, Facebook pages, and Google Ads accounts
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.models.users import User
from app.services.property_selection_service import PropertySelectionService

router = APIRouter(prefix="/property-selections", tags=["property-selections"])


class SavePropertySelectionRequest(BaseModel):
    """Request model for saving property selection"""
    subclient_id: int
    service: str  # "google_analytics", "facebook", "google_ads"
    property_id: str
    property_name: str


class PropertySelectionResponse(BaseModel):
    """Response model for property selection operations"""
    success: bool
    message: str
    selection_id: int = None
    property_id: str = None
    property_name: str = None


class GetPropertySelectionsResponse(BaseModel):
    """Response model for getting property selections"""
    success: bool
    selections: Dict[str, Dict[str, Any]]


@router.post("/save", response_model=PropertySelectionResponse)
async def save_property_selection(
    request: SavePropertySelectionRequest,
    current_user: User = Depends(get_current_user)
):
    """Save or update a user's property selection for a specific service"""
    
    try:
        service = PropertySelectionService()
        
        result = await service.save_property_selection(
            user_id=current_user.id,
            subclient_id=request.subclient_id,
            service=request.service,
            property_id=request.property_id,
            property_name=request.property_name
        )
        
        return PropertySelectionResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save property selection: {str(e)}"
        )


@router.get("/{subclient_id}", response_model=GetPropertySelectionsResponse)
async def get_property_selections(
    subclient_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get all property selections for a user and subclient"""
    
    try:
        service = PropertySelectionService()
        
        result = await service.get_property_selections(
            user_id=current_user.id,
            subclient_id=subclient_id
        )
        
        return GetPropertySelectionsResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get property selections: {str(e)}"
        )


@router.delete("/{subclient_id}/{service}")
async def clear_property_selection(
    subclient_id: int,
    service: str,
    current_user: User = Depends(get_current_user)
):
    """Clear a specific property selection"""
    
    try:
        service = PropertySelectionService()
        
        result = await service.clear_property_selection(
            user_id=current_user.id,
            subclient_id=subclient_id,
            service=service
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear property selection: {str(e)}"
        )
