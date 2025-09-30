"""
Customer API routes for fetching customers and subcustomers
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.core.auth import get_current_user
from app.models.users import Customer, SubCustomer, User
from app.config.database import get_session

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/")
async def get_customers(
    current_user: User = Depends(get_current_user)
):
    """
    Get all customers for the current authenticated user with main customer identified
    """
    try:
        with get_session() as session:
            # Get current user's primary customer and additional customers
            user = current_user
            
            customers = []
            main_customer_id = user.primary_customer_id
            
            # Get primary customer
            primary_customer = session.get(Customer, user.primary_customer_id)
            if primary_customer:
                customers.append({
                    "id": primary_customer.id,
                    "name": primary_customer.name,
                    "type": primary_customer.type,
                    "status": primary_customer.status,
                    "plan": primary_customer.plan,
                    "billing_currency": primary_customer.billing_currency,
                    "domains": primary_customer.domains,
                    "tags": primary_customer.tags,
                    "notes": primary_customer.notes,
                    "is_main": True
                })
            
            # Get additional customers
            if user.additional_customer_ids:
                for customer_id in user.additional_customer_ids:
                    customer = session.get(Customer, customer_id)
                    if customer:
                        customers.append({
                            "id": customer.id,
                            "name": customer.name,
                            "type": customer.type,
                            "status": customer.status,
                            "plan": customer.plan,
                            "billing_currency": customer.billing_currency,
                            "domains": customer.domains,
                            "tags": customer.tags,
                            "notes": customer.notes,
                            "is_main": False
                        })
            
            return {
                "success": True,
                "customers": customers,
                "main_customer_id": main_customer_id,
                "total": len(customers)
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customers: {str(e)}"
        )


@router.get("/{customer_id}/subcustomers")
async def get_customer_subcustomers(
    customer_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get all subcustomers for a specific customer
    """
    try:
        with get_session() as session:
            # Verify customer exists
            customer = session.get(Customer, customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # Get subcustomers for this customer
            statement = select(SubCustomer).where(
                SubCustomer.customer_id == customer_id
            )
            subcustomers = session.exec(statement).all()
            
            return {
                "success": True,
                "subcustomers": [
                    {
                        "id": sc.id,
                        "name": sc.name,
                        "customer_id": sc.customer_id,
                        "subtype": sc.subtype,
                        "status": sc.status,
                        "timezone": sc.timezone,
                        "markets": sc.markets,
                        "budget_monthly": sc.budget_monthly,
                        "tags": sc.tags,
                        "notes": sc.notes,
                        "external_ids": sc.external_ids
                    }
                    for sc in subcustomers
                ],
                "total": len(subcustomers)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subcustomers: {str(e)}"
        )


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific customer by ID
    """
    try:
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            return {
                "success": True,
                "customer": {
                    "id": customer.id,
                    "name": customer.name,
                    "type": customer.type,
                    "status": customer.status,
                    "plan": customer.plan,
                    "billing_currency": customer.billing_currency,
                    "vat_id": customer.vat_id,
                    "address": customer.address,
                    "domains": customer.domains,
                    "tags": customer.tags,
                    "notes": customer.notes,
                    "primary_contact_user_id": customer.primary_contact_user_id
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer: {str(e)}"
        )
