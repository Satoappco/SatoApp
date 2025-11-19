"""Service for managing customer-campaigner assignments"""

from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.models.users import (
    Customer,
    Campaigner,
    CustomerCampaignerAssignment,
    AssignmentRole
)


class CustomerAssignmentService:
    """Service for managing customer-campaigner assignments"""

    @staticmethod
    def get_customer_campaigners(
        session: Session,
        customer_id: int,
        active_only: bool = True
    ) -> List[Campaigner]:
        """Get all campaigners assigned to a customer"""
        query = (
            select(Campaigner)
            .join(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
        )

        if active_only:
            query = query.where(CustomerCampaignerAssignment.is_active == True)

        return session.exec(query).all()

    @staticmethod
    def get_customer_assignments(
        session: Session,
        customer_id: int,
        active_only: bool = True
    ) -> List[CustomerCampaignerAssignment]:
        """Get all assignments for a customer"""
        query = select(CustomerCampaignerAssignment).where(
            CustomerCampaignerAssignment.customer_id == customer_id
        )

        if active_only:
            query = query.where(CustomerCampaignerAssignment.is_active == True)

        return session.exec(query).all()

    @staticmethod
    def get_primary_campaigner(
        session: Session,
        customer_id: int
    ) -> Optional[Campaigner]:
        """Get primary campaigner for a customer"""
        assignment = session.exec(
            select(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
            .where(CustomerCampaignerAssignment.is_primary == True)
            .where(CustomerCampaignerAssignment.is_active == True)
        ).first()

        if assignment:
            return session.get(Campaigner, assignment.campaigner_id)
        return None

    @staticmethod
    def assign_campaigner(
        session: Session,
        customer_id: int,
        campaigner_id: int,
        is_primary: bool = False,
        role: AssignmentRole = AssignmentRole.ASSIGNED,
        assigned_by_id: Optional[int] = None
    ) -> CustomerCampaignerAssignment:
        """Assign a campaigner to a customer"""
        # Check if already assigned
        existing = session.exec(
            select(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
            .where(CustomerCampaignerAssignment.campaigner_id == campaigner_id)
            .where(CustomerCampaignerAssignment.is_active == True)
        ).first()

        if existing:
            raise ValueError("Campaigner already assigned to this customer")

        # If setting as primary, unset other primary assignments
        if is_primary:
            CustomerAssignmentService._unset_primary_assignments(session, customer_id)

        # Create assignment
        assignment = CustomerCampaignerAssignment(
            customer_id=customer_id,
            campaigner_id=campaigner_id,
            is_primary=is_primary,
            role=role if not is_primary else AssignmentRole.PRIMARY,
            assigned_by_campaigner_id=assigned_by_id
        )

        session.add(assignment)

        # Update denormalized field if primary
        if is_primary:
            customer = session.get(Customer, customer_id)
            if customer:
                customer.primary_campaigner_id = campaigner_id

        session.commit()
        session.refresh(assignment)

        return assignment

    @staticmethod
    def unassign_campaigner(
        session: Session,
        customer_id: int,
        campaigner_id: int,
        unassigned_by_id: Optional[int] = None
    ) -> bool:
        """Remove a campaigner assignment from a customer"""
        assignment = session.exec(
            select(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
            .where(CustomerCampaignerAssignment.campaigner_id == campaigner_id)
            .where(CustomerCampaignerAssignment.is_active == True)
        ).first()

        if not assignment:
            return False

        # Deactivate assignment
        assignment.is_active = False
        assignment.unassigned_at = datetime.utcnow()
        assignment.unassigned_by_campaigner_id = unassigned_by_id

        # If was primary, clear denormalized field
        if assignment.is_primary:
            customer = session.get(Customer, customer_id)
            if customer:
                customer.primary_campaigner_id = None

        session.commit()
        return True

    @staticmethod
    def set_primary_campaigner(
        session: Session,
        customer_id: int,
        campaigner_id: int
    ) -> CustomerCampaignerAssignment:
        """Set a campaigner as primary for a customer"""
        # Verify assignment exists
        assignment = session.exec(
            select(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
            .where(CustomerCampaignerAssignment.campaigner_id == campaigner_id)
            .where(CustomerCampaignerAssignment.is_active == True)
        ).first()

        if not assignment:
            raise ValueError("Campaigner is not assigned to this customer")

        # Unset other primary assignments
        CustomerAssignmentService._unset_primary_assignments(session, customer_id)

        # Set as primary
        assignment.is_primary = True
        assignment.role = AssignmentRole.PRIMARY

        # Update denormalized field
        customer = session.get(Customer, customer_id)
        if customer:
            customer.primary_campaigner_id = campaigner_id

        session.commit()
        session.refresh(assignment)

        return assignment

    @staticmethod
    def get_campaigner_customers(
        session: Session,
        campaigner_id: int,
        active_only: bool = True
    ) -> List[Customer]:
        """Get all customers assigned to a campaigner"""
        query = (
            select(Customer)
            .join(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.campaigner_id == campaigner_id)
        )

        if active_only:
            query = query.where(CustomerCampaignerAssignment.is_active == True)

        return session.exec(query).all()

    @staticmethod
    def _unset_primary_assignments(session: Session, customer_id: int) -> None:
        """Internal method to unset all primary assignments for a customer"""
        primary_assignments = session.exec(
            select(CustomerCampaignerAssignment)
            .where(CustomerCampaignerAssignment.customer_id == customer_id)
            .where(CustomerCampaignerAssignment.is_primary == True)
            .where(CustomerCampaignerAssignment.is_active == True)
        ).all()

        for assignment in primary_assignments:
            assignment.is_primary = False
            if assignment.role == AssignmentRole.PRIMARY:
                assignment.role = AssignmentRole.ASSIGNED
