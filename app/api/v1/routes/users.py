"""
Users API routes for managing workers and team members
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import select, and_

from app.core.auth import get_current_user
from app.models.users import User, UserRole, UserStatus
from app.config.database import get_session

router = APIRouter(prefix="/users", tags=["users"])


class CreateWorkerRequest(BaseModel):
    """Request model for creating a new worker"""
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.ANALYST


class UpdateWorkerRequest(BaseModel):
    """Request model for updating a worker"""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


@router.get("/workers")
async def get_workers(
    current_user: User = Depends(get_current_user)
):
    """
    Get all workers (team members) for the current user's agency/customer.
    Returns all users that belong to the same primary_customer_id.
    """
    try:
        with get_session() as session:
            # Get all users in the same agency/customer
            statement = select(User).where(
                User.primary_customer_id == current_user.primary_customer_id
            )
            
            workers = session.exec(statement).all()
            
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
                        "created_at": worker.created_at.isoformat() if worker.created_at else None
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
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific worker by ID.
    Only returns workers in the same agency/customer.
    """
    try:
        with get_session() as session:
            # Get worker
            worker = session.get(User, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # Verify worker is in the same agency
            if worker.primary_customer_id != current_user.primary_customer_id:
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
    current_user: User = Depends(get_current_user)
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
                select(User).where(User.email == request.email)
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email already exists"
                )
            
            # Create new worker
            new_worker = User(
                email=request.email,
                full_name=request.full_name,
                role=request.role,
                status=UserStatus.PENDING,  # New workers start as pending
                primary_customer_id=current_user.primary_customer_id,
                email_verified=False
            )
            
            session.add(new_worker)
            session.commit()
            session.refresh(new_worker)
            
            return {
                "success": True,
                "message": "Worker created successfully",
                "worker": {
                    "id": new_worker.id,
                    "email": new_worker.email,
                    "full_name": new_worker.full_name,
                    "role": new_worker.role,
                    "status": new_worker.status
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
    current_user: User = Depends(get_current_user)
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
            worker = session.get(User, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # Verify worker is in the same agency
            if worker.primary_customer_id != current_user.primary_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this worker"
                )
            
            # Update worker fields
            if request.full_name is not None:
                worker.full_name = request.full_name
            if request.role is not None:
                worker.role = request.role
            if request.status is not None:
                worker.status = request.status
            
            session.add(worker)
            session.commit()
            session.refresh(worker)
            
            return {
                "success": True,
                "message": "Worker updated successfully",
                "worker": {
                    "id": worker.id,
                    "email": worker.email,
                    "full_name": worker.full_name,
                    "role": worker.role,
                    "status": worker.status
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
    current_user: User = Depends(get_current_user)
):
    """
    Delete a worker.
    Only owners can delete workers.
    """
    # Check permissions
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can delete workers"
        )
    
    try:
        with get_session() as session:
            # Get worker
            worker = session.get(User, worker_id)
            
            if not worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker not found"
                )
            
            # Verify worker is in the same agency
            if worker.primary_customer_id != current_user.primary_customer_id:
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

