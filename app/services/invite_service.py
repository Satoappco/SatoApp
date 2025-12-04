"""
Invite Service for managing team member invitations
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlmodel import select
from app.models.users import InviteToken, Campaigner, UserRole


class InviteService:
    """Service for managing invitation tokens"""
    
    @staticmethod
    def generate_invite_token(
        agency_id: int,
        invited_by_id: int,
        role: UserRole = UserRole.CAMPAIGNER,
        email: Optional[str] = None,
        expiry_days: int = 7
    ) -> InviteToken:
        """Generate secure invite token"""
        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        
        invite = InviteToken(
            token=token,
            agency_id=agency_id,
            invited_by_campaigner_id=invited_by_id,
            invited_email=email,
            role=role,
            expires_at=expires_at
        )
        return invite
    
    @staticmethod
    def validate_token(token: str, session) -> Tuple[bool, str, Optional[InviteToken]]:
        """Validate invite token and return (is_valid, error_msg, token_obj)"""
        invite = session.exec(
            select(InviteToken).where(InviteToken.token == token)
        ).first()
        
        if not invite:
            return False, "Invalid invitation token", None
        
        if invite.is_used and invite.use_count >= invite.max_uses:
            return False, "This invitation has already been used", None
        
        if invite.expires_at < datetime.now(timezone.utc):
            return False, "This invitation has expired", None
        
        return True, "", invite
    
    @staticmethod
    def mark_token_as_used(token: str, used_by_campaigner_id: int, session) -> bool:
        """Mark an invite token as used"""
        invite = session.exec(
            select(InviteToken).where(InviteToken.token == token)
        ).first()
        
        if not invite:
            return False
        
        invite.is_used = True
        invite.use_count += 1
        invite.used_at = datetime.now(timezone.utc)
        invite.used_by_campaigner_id = used_by_campaigner_id
        
        session.add(invite)
        session.commit()
        return True
    
    @staticmethod
    def get_active_invites_for_agency(agency_id: int, session) -> list[InviteToken]:
        """Get all active (unused, not expired) invites for an agency"""
        invites = session.exec(
            select(InviteToken)
            .where(InviteToken.agency_id == agency_id)
            .where(InviteToken.is_used == False)
            .where(InviteToken.expires_at > datetime.now(timezone.utc))
        ).all()
        
        return list(invites)
