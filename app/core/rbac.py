"""
Role-Based Access Control (RBAC) framework
Provides centralized authorization helpers and decorators
"""

from enum import IntEnum
from typing import Optional, List, Callable
from fastapi import HTTPException, status, Depends
from sqlmodel import select
from app.models.users import Campaigner, UserRole, CustomerCampaignerAssignment
from app.config.database import get_session


class RoleLevel(IntEnum):
    """Role hierarchy levels for comparison"""

    VIEWER = 0
    CAMPAIGNER = 1
    ADMIN = 2
    OWNER = 3


# Role to level mapping
ROLE_HIERARCHY = {
    UserRole.VIEWER: RoleLevel.VIEWER,
    UserRole.CAMPAIGNER: RoleLevel.CAMPAIGNER,
    UserRole.ADMIN: RoleLevel.ADMIN,
    UserRole.OWNER: RoleLevel.OWNER,
}


def get_role_level(role: UserRole) -> RoleLevel:
    """Get numeric level for a role"""
    return ROLE_HIERARCHY.get(role, RoleLevel.VIEWER)


def user_is_at_least(user: Campaigner, required_role: UserRole) -> bool:
    """
    Check if user has at least the required role level.

    Examples:
        user_is_at_least(admin_user, UserRole.CAMPAIGNER) -> True
        user_is_at_least(admin_user, UserRole.ADMIN) -> True
        user_is_at_least(campaigner_user, UserRole.ADMIN) -> False
        user_is_at_least(owner_user, UserRole.ADMIN) -> True

    Args:
        user: The user to check
        required_role: Minimum required role

    Returns:
        True if user's role level >= required role level
    """
    user_level = get_role_level(user.role)
    required_level = get_role_level(required_role)
    return user_level >= required_level


def require_role(
    required_role: UserRole, error_message: Optional[str] = None
) -> Callable:
    """
    Dependency that requires user to have at least the specified role.

    Usage:
        @router.post("/workers")
        async def create_worker(
            current_user: Campaigner = Depends(require_role(UserRole.ADMIN))
        ):
            # Only ADMIN and OWNER can access this
            pass

    Args:
        required_role: Minimum required role
        error_message: Custom error message

    Returns:
        Dependency function that validates role
    """
    from app.core.auth import get_current_user

    def role_checker(
        current_user: Campaigner = Depends(get_current_user),
    ) -> Campaigner:
        if not user_is_at_least(current_user, required_role):
            message = (
                error_message
                or f"This operation requires at least {required_role.value} role"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
        return current_user

    return role_checker


def user_can_access_agency(user: Campaigner, agency_id: int) -> bool:
    """
    Check if user can access resources for specified agency.

    Args:
        user: The user to check
        agency_id: Agency ID to check access for

    Returns:
        True if user can access the agency
    """
    # OWNERs can access all agencies
    if user.role == UserRole.OWNER:
        return True

    # Others can only access their own agency
    return user.agency_id == agency_id


def user_can_access_customer(
    user: Campaigner, customer_id: int, require_assignment: bool = True
) -> bool:
    """
    Check if user can access a specific customer.

    Args:
        user: The user to check
        customer_id: Customer ID to check access for
        require_assignment: If True, CAMPAIGNER must be assigned to customer

    Returns:
        True if user can access the customer
    """
    from app.models.users import Customer

    with get_session() as session:
        customer = session.get(Customer, customer_id)
        if not customer:
            return False

        # OWNERs can access all customers
        if user.role == UserRole.OWNER:
            return True

        # Check same agency
        if customer.agency_id != user.agency_id:
            return False

        # ADMINs can access all customers in their agency
        if user.role == UserRole.ADMIN:
            return True

        # CAMPAIGNERs and VIEWERs must be assigned (if required)
        if require_assignment:
            assignment = session.exec(
                select(CustomerCampaignerAssignment).where(
                    CustomerCampaignerAssignment.customer_id == customer_id,
                    CustomerCampaignerAssignment.campaigner_id == user.id,
                    CustomerCampaignerAssignment.is_active == True,
                )
            ).first()
            return assignment is not None

        return True


def require_customer_access(customer_id_param: str = "customer_id"):
    """
    Dependency that requires user to have access to specified customer.

    Usage:
        @router.get("/customers/{customer_id}")
        async def get_customer(
            customer_id: int,
            current_user: Campaigner = Depends(require_customer_access())
        ):
            # current_user is guaranteed to have access to customer_id
            pass

    Args:
        customer_id_param: Name of the path parameter containing customer_id

    Returns:
        Dependency function that validates customer access
    """
    from app.core.auth import get_current_user
    from fastapi import Path

    def access_checker(
        customer_id: int = Path(..., alias=customer_id_param),
        current_user: Campaigner = Depends(get_current_user),
    ) -> Campaigner:
        if not user_can_access_customer(current_user, customer_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this customer",
            )
        return current_user

    return access_checker


def get_accessible_customers(user: Campaigner) -> List[int]:
    """
    Get list of customer IDs that user can access.

    Args:
        user: The user to check

    Returns:
        List of customer IDs user can access
    """
    from app.models.users import Customer

    with get_session() as session:
        # OWNERs can access all customers
        if user.role == UserRole.OWNER:
            customers = session.exec(select(Customer.id)).all()
            return [id for id in customers if id is not None]

        # ADMINs can access all customers in their agency
        if user.role == UserRole.ADMIN:
            customers = session.exec(
                select(Customer.id).where(Customer.agency_id == user.agency_id)
            ).all()
            return [id for id in customers if id is not None]

        # CAMPAIGNERs and VIEWERs can only access assigned customers
        assignments = session.exec(
            select(CustomerCampaignerAssignment.customer_id).where(
                CustomerCampaignerAssignment.campaigner_id == user.id,
                CustomerCampaignerAssignment.is_active == True,
            )
        ).all()
        return [id for id in assignments if id is not None]


# Convenience dependencies for common role requirements
def require_owner():
    return require_role(UserRole.OWNER)


def require_admin():
    return require_role(UserRole.ADMIN)


def require_campaigner():
    return require_role(UserRole.CAMPAIGNER)
