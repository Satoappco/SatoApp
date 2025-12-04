"""
Campaigners API routes for managing agency workers and team members
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import select, and_

from app.core.auth import get_current_user
from app.models.users import Campaigner, UserRole, UserStatus, InviteToken
from app.config.database import get_session
from app.config.settings import get_settings
from app.services.invite_service import InviteService
import os

router = APIRouter(prefix="/campaigners", tags=["campaigners"])


class CreateWorkerRequest(BaseModel):
    """Request model for creating a new worker"""
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    agency_id: int
    role: UserRole = UserRole.CAMPAIGNER


class UpdateWorkerRequest(BaseModel):
    """Request model for updating a worker"""
    # Note: email is managed by Google OAuth and should not be updated via API
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    agency_id: Optional[int] = None


@router.get("/workers")
async def get_workers(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get all workers (team members) for the current user's agency/customer.
    Returns all users that belong to the same agency_id.
    """
    try:
        with get_session() as session:
            # Get all users in the same agency/customer
            statement = select(Campaigner).where(
                Campaigner.agency_id == current_user.agency_id
            )
            
            workers = session.exec(statement).all()
            
            # Get customer counts for each worker from customer_campaigner_assignments
            from app.models.users import Customer, CustomerCampaignerAssignment
            customer_counts = {}
            for worker in workers:
                count = session.exec(
                    select(CustomerCampaignerAssignment).where(
                        and_(
                            CustomerCampaignerAssignment.campaigner_id == worker.id,
                            CustomerCampaignerAssignment.is_active == True
                        )
                    )
                ).all()
                customer_counts[worker.id] = len(count)
            
            return {
                "success": True,
                "workers": [
                    {
                        "id": worker.id,
                        "email": worker.email,
                        "full_name": worker.full_name,
                        "role": worker.role,
                        "status": worker.status,
                        "avatar_url": worker.avatar_url,
                        "email_verified": worker.email_verified,
                        "last_login_at": worker.last_login_at.isoformat() if worker.last_login_at else None,
                        "created_at": worker.created_at.isoformat() if worker.created_at else None,
                        "phone": worker.phone,
                        "locale": worker.locale,
                        "timezone": worker.timezone,
                        "google_id": worker.google_id,
                        "customer_count": customer_counts.get(worker.id, 0)
                    }
                    for worker in workers
                ],
                "total": len(workers)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workers: {str(e)}"
        )


@router.get("/workers/{worker_id}")
async def get_worker(
    worker_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a specific worker by ID.
    Only returns workers in the same agency/customer.
    """
    try:
        with get_session() as session:
            # Get worker
            worker = session.get(Campaigner, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # Verify worker is in the same agency
            if worker.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this worker"
                )
            
            return {
                "success": True,
                "worker": {
                    "id": worker.id,
                    "email": worker.email,
                    "full_name": worker.full_name,
                    "role": worker.role,
                    "status": worker.status,
                    "avatar_url": worker.avatar_url,
                    "email_verified": worker.email_verified,
                    "last_login_at": worker.last_login_at.isoformat() if worker.last_login_at else None,
                    "created_at": worker.created_at.isoformat() if worker.created_at else None,
                    "locale": worker.locale,
                    "timezone": worker.timezone
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get worker: {str(e)}"
        )


@router.post("/workers")
async def create_worker(
    request: CreateWorkerRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Create a new worker in the current user's agency/customer.
    Only owners and admins can create workers.
    """
    # Check permissions
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create workers"
        )
    
    try:
        with get_session() as session:
            # Check if user with this email already exists
            existing_user = session.exec(
                select(Campaigner).where(Campaigner.email == request.email)
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Campaigner with this email already exists"
                )
            
            # OWNER can only create workers in their own agency, ADMIN can create in any agency
            if current_user.role != UserRole.ADMIN and request.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only create workers in your own agency"
                )
            
            # Create new worker
            new_worker = Campaigner(
                email=request.email,
                full_name=request.full_name,
                phone=request.phone,
                role=request.role,
                status=UserStatus.INVITED,  # New workers start as invited
                agency_id=request.agency_id,
                email_verified=False
            )
            
            session.add(new_worker)
            session.commit()
            session.refresh(new_worker)
            
            return {
                "success": True,
                "message": "Worker created successfully",
                "data": {
                    "id": new_worker.id,
                    "email": new_worker.email,
                    "full_name": new_worker.full_name,
                    "phone": new_worker.phone,
                    "role": new_worker.role,
                    "status": new_worker.status,
                    "agency_id": new_worker.agency_id,
                    "created_at": new_worker.created_at.isoformat(),
                    "updated_at": new_worker.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create worker: {str(e)}"
        )


@router.patch("/workers/{worker_id}")
async def update_worker(
    worker_id: int,
    request: UpdateWorkerRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update a worker's information.
    Only owners and admins can update workers.
    """
    # Check permissions
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update workers"
        )
    
    try:
        with get_session() as session:
            # Get worker
            worker = session.get(Campaigner, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # OWNER can only update workers in their own agency, ADMIN can update any
            if current_user.role != UserRole.ADMIN and worker.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this worker"
                )
            
            # Update worker fields
            # Note: email is managed by Google OAuth and should not be updated via API
            if request.full_name is not None:
                worker.full_name = request.full_name
            if request.phone is not None:
                worker.phone = request.phone
            if request.role is not None:
                worker.role = request.role
            if request.status is not None:
                worker.status = request.status
            if request.agency_id is not None:
                worker.agency_id = request.agency_id
            
            session.add(worker)
            session.commit()
            session.refresh(worker)
            
            return {
                "success": True,
                "message": "Worker updated successfully",
                "data": {
                    "id": worker.id,
                    "email": worker.email,
                    "full_name": worker.full_name,
                    "phone": worker.phone,
                    "role": worker.role,
                    "status": worker.status,
                    "agency_id": worker.agency_id,
                    "created_at": worker.created_at.isoformat(),
                    "updated_at": worker.updated_at.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update worker: {str(e)}"
        )


@router.delete("/workers/{worker_id}")
async def delete_worker(
    worker_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Delete a worker.
    Only owners and admins can delete workers.
    """
    # Check permissions
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can delete workers"
        )
    
    try:
        with get_session() as session:
            # Get worker
            worker = session.get(Campaigner, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # OWNER can only delete workers in their own agency, ADMIN can delete any
            if current_user.role != UserRole.ADMIN and worker.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this worker"
                )
            
            # Prevent deleting yourself
            if worker.id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete yourself"
                )
            
            # Deactivate customer assignments for this worker
            from app.models.users import Customer, CampaignerSession, InviteToken, CustomerCampaignerAssignment
            from app.models.analytics import Connection, UserPropertySelection

            # Deactivate assignments (don't delete - keeps history)
            assignments_to_deactivate = session.exec(
                select(CustomerCampaignerAssignment).where(
                    and_(
                        CustomerCampaignerAssignment.campaigner_id == worker_id,
                        CustomerCampaignerAssignment.is_active == True
                    )
                )
            ).all()

            for assignment in assignments_to_deactivate:
                assignment.is_active = False
                assignment.unassigned_at = datetime.now(timezone.utc)

            # Also update old deprecated field for backward compatibility
            customers_to_update = session.exec(
                select(Customer).where(Customer.assigned_campaigner_id == worker_id)
            ).all()

            for customer in customers_to_update:
                customer.assigned_campaigner_id = None
                customer.primary_campaigner_id = None
            
            # Delete all sessions for this worker
            sessions_to_delete = session.exec(
                select(CampaignerSession).where(CampaignerSession.campaigner_id == worker_id)
            ).all()
            
            for session_obj in sessions_to_delete:
                session.delete(session_obj)
            
            # Delete all connections created by this worker
            connections_to_delete = session.exec(
                select(Connection).where(Connection.campaigner_id == worker_id)
            ).all()

            # Track digital asset IDs to check for orphans after deletion
            digital_asset_ids = set()
            for connection in connections_to_delete:
                digital_asset_ids.add(connection.digital_asset_id)
                session.delete(connection)
            session.commit()

            # Check for and delete orphaned digital assets
            from app.services.digital_asset_service import delete_orphaned_digital_asset
            for asset_id in digital_asset_ids:
                delete_orphaned_digital_asset(session, asset_id)
            
            # Delete all user property selections for this worker
            property_selections_to_delete = session.exec(
                select(UserPropertySelection).where(UserPropertySelection.campaigner_id == worker_id)
            ).all()
            
            for selection in property_selections_to_delete:
                session.delete(selection)
            
            # Delete all invite tokens created by this worker
            invites_created_by_worker = session.exec(
                select(InviteToken).where(InviteToken.invited_by_campaigner_id == worker_id)
            ).all()
            
            for invite in invites_created_by_worker:
                session.delete(invite)
            
            # Update invite tokens used by this worker to remove the reference
            invites_used_by_worker = session.exec(
                select(InviteToken).where(InviteToken.used_by_campaigner_id == worker_id)
            ).all()
            
            for invite in invites_used_by_worker:
                invite.used_by_campaigner_id = None
                invite.used_at = None
                invite.is_used = False
                invite.use_count = 0
            
            # Delete worker
            session.delete(worker)
            session.commit()
            
            return {
                "success": True,
                "message": "Worker deleted successfully"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete worker: {str(e)}"
        )


# Invite Management Endpoints

class GenerateInviteRequest(BaseModel):
    """Request model for generating invite link"""
    role: UserRole = UserRole.CAMPAIGNER
    email: Optional[str] = None


class AcceptInviteRequest(BaseModel):
    """Request model for accepting invite"""
    token: str
    google_token: Optional[str] = None
    user_info: dict


@router.post("/invite/generate")
async def generate_invite_link(
    request: GenerateInviteRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """Generate secure invite link for team member"""
    print(f"🔵 Invite Generation Request - User ID: {current_user.id}, Role: {current_user.role}")
    
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        print(f"❌ Permission denied - User role: {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can generate invites"
        )
    
    try:
        with get_session() as session:
            # Debug logging for invite generation
            print(f"🔍 Generate Invite Debug:")
            print(f"  - Current User ID: {current_user.id}")
            print(f"  - Current User Agency ID: {current_user.agency_id}")
            print(f"  - Request Role: {request.role}")
            print(f"  - Request Email: {request.email}")
            
            invite = InviteService.generate_invite_token(
                agency_id=current_user.agency_id,
                invited_by_id=current_user.id,
                role=request.role,
                email=request.email
            )
            
            session.add(invite)
            session.commit()
            session.refresh(invite)
            
            # Debug logging after invite creation
            print(f"🔍 Created Invite Debug:")
            print(f"  - Invite ID: {invite.id}")
            print(f"  - Agency ID: {invite.agency_id}")
            print(f"  - Role: {invite.role}")
            print(f"  - Token: {invite.token}")
            
            # Generate invite URL using settings
            settings = get_settings()
            frontend_url = os.getenv("FRONTEND_URL") or settings.frontend_url
            # Ensure we don't use localhost in production - fail if not configured
            if "localhost" in frontend_url.lower() and os.getenv("ENVIRONMENT", "").lower() in ["production", "prod"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="FRONTEND_URL must be configured for production environment"
                )
            invite_url = f"{frontend_url}/join?token={invite.token}"
            
            print(f"✅ Invite URL generated: {invite_url}")
            
            response_data = {
                "success": True,
                "invite_token": invite.token,
                "invite_url": invite_url,
                "expires_at": invite.expires_at.isoformat()
            }
            
            print(f"📤 Returning response: {response_data}")
            return response_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating invite: {str(e)}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invite: {str(e)}"
        )


@router.post("/invite/accept")
async def accept_invite(request: AcceptInviteRequest):
    """Accept invitation and create campaigner account"""
    try:
        with get_session() as session:
            # Validate token
            is_valid, error_msg, invite = InviteService.validate_token(
                request.token, session
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
            
            # Debug logging
            print(f"🔍 Invite Debug:")
            print(f"  - Token: {request.token}")
            print(f"  - Invite ID: {invite.id}")
            print(f"  - Agency ID: {invite.agency_id}")
            print(f"  - Role: {invite.role}")
            print(f"  - Is Used: {invite.is_used}")
            
            # Extract user info
            email = request.user_info.get('email')
            full_name = request.user_info.get('name') or 'Unknown User'  # Fallback for null name
            google_id = request.user_info.get('sub')
            avatar_url = request.user_info.get('picture')
            
            # Validate required fields
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is required"
                )
            
            # Check if user already exists
            existing = session.exec(
                select(Campaigner).where(Campaigner.email == email)
            ).first()
            
            if existing:
                # Update existing user to join the agency from the invite
                existing.agency_id = invite.agency_id
                existing.role = invite.role
                existing.status = UserStatus.ACTIVE
                existing.last_login_at = datetime.now(timezone.utc)
                
                # Update Google info if provided
                if google_id:
                    existing.google_id = google_id
                if avatar_url:
                    existing.avatar_url = avatar_url
                if full_name != 'Unknown User':
                    existing.full_name = full_name
                
                session.add(existing)
                session.commit()
                session.refresh(existing)
                
                # Mark invite as used
                invite.is_used = True
                invite.use_count += 1
                invite.used_at = datetime.now(timezone.utc)
                invite.used_by_campaigner_id = existing.id
                session.add(invite)
                session.commit()
                
                # Debug logging for existing user update
                print(f"🔍 Updated Existing User Debug:")
                print(f"  - Campaigner ID: {existing.id}")
                print(f"  - Email: {existing.email}")
                print(f"  - Agency ID: {existing.agency_id}")
                print(f"  - Role: {existing.role}")
                
                # Generate JWT tokens
                from app.core.auth import create_access_token
                access_token = create_access_token({"sub": str(existing.id)})
                
                return {
                    "success": True,
                    "message": "Successfully joined the team",
                    "campaigner": {
                        "id": existing.id,
                        "email": existing.email,
                        "full_name": existing.full_name,
                        "role": existing.role
                    },
                    "access_token": access_token
                }
            
            # Create new campaigner
            new_campaigner = Campaigner(
                email=email,
                full_name=full_name,
                google_id=google_id,
                avatar_url=avatar_url,
                email_verified=True,
                role=invite.role,
                status=UserStatus.ACTIVE,
                agency_id=invite.agency_id,
                last_login_at=datetime.now(timezone.utc)
            )
            
            session.add(new_campaigner)
            
            # Mark invite as used
            invite.is_used = True
            invite.use_count += 1
            invite.used_at = datetime.now(timezone.utc)
            invite.used_by_campaigner_id = new_campaigner.id
            
            session.commit()
            session.refresh(new_campaigner)
            
            # Debug logging after creation
            print(f"🔍 Created Campaigner Debug:")
            print(f"  - Campaigner ID: {new_campaigner.id}")
            print(f"  - Email: {new_campaigner.email}")
            print(f"  - Agency ID: {new_campaigner.agency_id}")
            print(f"  - Role: {new_campaigner.role}")
            
            # Generate JWT tokens (reuse existing auth logic)
            from app.core.auth import create_access_token
            access_token = create_access_token({"sub": str(new_campaigner.id)})
            
            return {
                "success": True,
                "message": "Successfully joined the team",
                "campaigner": {
                    "id": new_campaigner.id,
                    "email": new_campaigner.email,
                    "full_name": new_campaigner.full_name,
                    "role": new_campaigner.role
                },
                "access_token": access_token
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to accept invite: {str(e)}"
        )


@router.get("/invite/info/{token}")
async def get_invite_info(token: str):
    """Get invite information including agency name (public endpoint)"""
    try:
        with get_session() as session:
            # Get invite token with agency info
            from app.models.users import Agency
            invite = session.exec(
                select(InviteToken, Agency)
                .join(Agency, InviteToken.agency_id == Agency.id)
                .where(InviteToken.token == token)
            ).first()
            
            if not invite:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invalid invitation token"
                )
            
            invite_token, agency = invite
            
            # Check if token is expired
            if invite_token.expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This invitation has expired"
                )
            
            # Note: We don't check if token is already used here
            # This endpoint is for display purposes only
            # The actual acceptance will handle the "already used" case
            
            return {
                "success": True,
                "agency_name": agency.name,
                "role": invite_token.role,
                "expires_at": invite_token.expires_at.isoformat(),
                "is_used": invite_token.is_used
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get invite info: {str(e)}"
        )


@router.get("/invite/list")
async def list_invites(
    current_user: Campaigner = Depends(get_current_user)
):
    """List active invites for current agency"""
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can view invites"
        )
    
    try:
        with get_session() as session:
            invites = InviteService.get_active_invites_for_agency(
                current_user.agency_id, session
            )
            
            return {
                "success": True,
                "invites": [
                    {
                        "token": inv.token,
                        "role": inv.role,
                        "invited_email": inv.invited_email,
                        "expires_at": inv.expires_at.isoformat(),
                        "created_at": inv.created_at.isoformat()
                    }
                    for inv in invites
                ]
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list invites: {str(e)}"
        )




COUNTRIES = [
    {"code": "IL", "name_en": "Israel", "name_he": "ישראל"},
    {"code": "US", "name_en": "United States", "name_he": "ארצות הברית"},
    {"code": "GB", "name_en": "United Kingdom", "name_he": "בריטניה"},
    {"code": "DE", "name_en": "Germany", "name_he": "גרמניה"},
    {"code": "FR", "name_en": "France", "name_he": "צרפת"},
    {"code": "IT", "name_en": "Italy", "name_he": "איטליה"},
    {"code": "ES", "name_en": "Spain", "name_he": "ספרד"},
    {"code": "NL", "name_en": "Netherlands", "name_he": "הולנד"},
    {"code": "SE", "name_en": "Sweden", "name_he": "שוודיה"},
    {"code": "CH", "name_en": "Switzerland", "name_he": "שווייץ"},
    {"code": "AT", "name_en": "Austria", "name_he": "אוסטריה"},
    {"code": "BE", "name_en": "Belgium", "name_he": "בלגיה"},
    {"code": "CA", "name_en": "Canada", "name_he": "קנדה"},
    {"code": "AU", "name_en": "Australia", "name_he": "אוסטרליה"},
    {"code": "JP", "name_en": "Japan", "name_he": "יפן"},
    {"code": "CN", "name_en": "China", "name_he": "סין"},
    {"code": "IN", "name_en": "India", "name_he": "הודו"},
    {"code": "BR", "name_en": "Brazil", "name_he": "ברזיל"},
    {"code": "MX", "name_en": "Mexico", "name_he": "מקסיקו"},
    {"code": "AR", "name_en": "Argentina", "name_he": "ארגנטינה"},
    {"code": "ZA", "name_en": "South Africa", "name_he": "דרום אפריקה"},
    {"code": "AE", "name_en": "United Arab Emirates", "name_he": "איחוד האמירויות"},
    {"code": "SA", "name_en": "Saudi Arabia", "name_he": "ערב הסעודית"},
    {"code": "TR", "name_en": "Turkey", "name_he": "טורקיה"},
    {"code": "RU", "name_en": "Russia", "name_he": "רוסיה"},
    {"code": "PL", "name_en": "Poland", "name_he": "פולין"},
    {"code": "GR", "name_en": "Greece", "name_he": "יוון"},
    {"code": "PT", "name_en": "Portugal", "name_he": "פורטוגל"},
    {"code": "IE", "name_en": "Ireland", "name_he": "אירלנד"},
    {"code": "DK", "name_en": "Denmark", "name_he": "דנמרק"},
    {"code": "NO", "name_en": "Norway", "name_he": "נורווגיה"},
    {"code": "FI", "name_en": "Finland", "name_he": "פינלנד"},
    {"code": "CZ", "name_en": "Czech Republic", "name_he": "צ׳כיה"},
    {"code": "HU", "name_en": "Hungary", "name_he": "הונגריה"},
    {"code": "RO", "name_en": "Romania", "name_he": "רומניה"},
    {"code": "NZ", "name_en": "New Zealand", "name_he": "ניו זילנד"},
    {"code": "SG", "name_en": "Singapore", "name_he": "סינגפור"},
    {"code": "KR", "name_en": "South Korea", "name_he": "דרום קוריאה"},
    {"code": "TH", "name_en": "Thailand", "name_he": "תאילנד"},
    {"code": "MY", "name_en": "Malaysia", "name_he": "מלזיה"},
    {"code": "ID", "name_en": "Indonesia", "name_he": "אינדונזיה"},
    {"code": "PH", "name_en": "Philippines", "name_he": "פיליפינים"},
    {"code": "VN", "name_en": "Vietnam", "name_he": "וייטנאם"},
    {"code": "EG", "name_en": "Egypt", "name_he": "מצרים"},
    {"code": "JO", "name_en": "Jordan", "name_he": "ירדן"},
]
CURRENCIES = [
    {"code": "ILS", "symbol": "₪", "name_en": "Israeli Shekel", "name_he": "שקל חדש"},
    {"code": "USD", "symbol": "$", "name_en": "US Dollar", "name_he": "דולר אמריקאי"},
    {"code": "EUR", "symbol": "€", "name_en": "Euro", "name_he": "אירו"},
    {"code": "GBP", "symbol": "£", "name_en": "British Pound", "name_he": "לירה שטרלינג"},
    {"code": "JPY", "symbol": "¥", "name_en": "Japanese Yen", "name_he": "ין יפני"},
    {"code": "CHF", "symbol": "CHF", "name_en": "Swiss Franc", "name_he": "פרנק שוויצרי"},
    {"code": "CAD", "symbol": "C$", "name_en": "Canadian Dollar", "name_he": "דולר קנדי"},
    {"code": "AUD", "symbol": "A$", "name_en": "Australian Dollar", "name_he": "דולר אוסטרלי"},
    {"code": "CNY", "symbol": "¥", "name_en": "Chinese Yuan", "name_he": "יואן סיני"},
    {"code": "INR", "symbol": "₹", "name_en": "Indian Rupee", "name_he": "רופי הודי"},
    {"code": "BRL", "symbol": "R$", "name_en": "Brazilian Real", "name_he": "ריאל ברזילאי"},
    {"code": "MXN", "symbol": "MX$", "name_en": "Mexican Peso", "name_he": "פזו מקסיקני"},
    {"code": "AED", "symbol": "د.إ", "name_en": "UAE Dirham", "name_he": "דירהם איחוד האמירויות"},
    {"code": "SAR", "symbol": "﷼", "name_en": "Saudi Riyal", "name_he": "ריאל סעודי"},
    {"code": "TRY", "symbol": "₺", "name_en": "Turkish Lira", "name_he": "לירה טורקית"},
    {"code": "RUB", "symbol": "₽", "name_en": "Russian Ruble", "name_he": "רובל רוסי"},
    {"code": "KRW", "symbol": "₩", "name_en": "South Korean Won", "name_he": "וון דרום קוריאני"},
    {"code": "SGD", "symbol": "S$", "name_en": "Singapore Dollar", "name_he": "דולר סינגפורי"},
    {"code": "THB", "symbol": "฿", "name_en": "Thai Baht", "name_he": "בהט תאילנדי"},
    {"code": "ZAR", "symbol": "R", "name_en": "South African Rand", "name_he": "ראנד דרום אפריקאי"},
]
ADVERTISING_CHANNELS = [
    "Google AdSense",
    "Google Search Ads", 
    "Google Gmail",
    "Facebook",
    "Instagram(IG)"
]