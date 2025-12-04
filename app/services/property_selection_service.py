"""
Service for managing user property selections
Handles saving and retrieving selected Google Analytics properties, Facebook pages, and Google Ads accounts
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlmodel import select, and_
from app.config.database import get_session
from app.models.analytics import UserPropertySelection
from app.models.users import Campaigner


class PropertySelectionService:
    """Service for managing user property selections"""
    
    def __init__(self):
        pass
    
    async def save_property_selection(
        self,
        campaigner_id: int,
        customer_id: int,
        service: str,
        property_id: str,
        property_name: str
    ) -> Dict[str, Any]:
        """Save or update a campaigner's property selection for a specific service"""
        
        with get_session() as session:
            # Check if selection already exists
            statement = select(UserPropertySelection).where(
                and_(
                    UserPropertySelection.campaigner_id == campaigner_id,
                    UserPropertySelection.customer_id == customer_id,
                    UserPropertySelection.service == service
                )
            )
            existing_selection = session.exec(statement).first()
            
            if existing_selection:
                # Update existing selection
                existing_selection.selected_property_id = property_id
                existing_selection.property_name = property_name
                existing_selection.updated_at = datetime.now(timezone.utc)
                existing_selection.is_active = True
                session.add(existing_selection)
                session.commit()
                session.refresh(existing_selection)
                
                return {
                    "success": True,
                    "message": f"Updated {service} property selection",
                    "selection_id": existing_selection.id,
                    "property_id": property_id,
                    "property_name": property_name
                }
            else:
                # Create new selection
                new_selection = UserPropertySelection(
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    service=service,
                    selected_property_id=property_id,
                    property_name=property_name,
                    is_active=True
                )
                session.add(new_selection)
                session.commit()
                session.refresh(new_selection)
                
                return {
                    "success": True,
                    "message": f"Saved {service} property selection",
                    "selection_id": new_selection.id,
                    "property_id": property_id,
                    "property_name": property_name
                }
    
    async def get_property_selections(
        self,
        campaigner_id: int,
        customer_id: int
    ) -> Dict[str, Any]:
        """Get all property selections for a campaigner and customer"""
        
        with get_session() as session:
            statement = select(UserPropertySelection).where(
                and_(
                    UserPropertySelection.campaigner_id == campaigner_id,
                    UserPropertySelection.customer_id == customer_id,
                    UserPropertySelection.is_active == True
                )
            )
            selections = session.exec(statement).all()
            
            # Convert to dictionary format
            selections_dict = {}
            for selection in selections:
                selections_dict[selection.service] = {
                    "property_id": selection.selected_property_id,
                    "property_name": selection.property_name,
                    "updated_at": selection.updated_at.isoformat()
                }
            
            return {
                "success": True,
                "selections": selections_dict
            }
    
    async def clear_property_selection(
        self,
        campaigner_id: int,
        customer_id: int,
        service: str
    ) -> Dict[str, Any]:
        """Clear a specific property selection"""
        
        with get_session() as session:
            statement = select(UserPropertySelection).where(
                and_(
                    UserPropertySelection.campaigner_id == campaigner_id,
                    UserPropertySelection.customer_id == customer_id,
                    UserPropertySelection.service == service
                )
            )
            selection = session.exec(statement).first()
            
            if selection:
                selection.is_active = False
                selection.updated_at = datetime.now(timezone.utc)
                session.add(selection)
                session.commit()
                
                return {
                    "success": True,
                    "message": f"Cleared {service} property selection"
                }
            else:
                return {
                    "success": False,
                    "message": f"No {service} property selection found"
                }
