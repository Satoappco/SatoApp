"""
Composite ID utility functions for customer data tables.

The composite_id format is: <agency_id>_<campaigner_id>_<customer_id>
This creates a unique identifier that represents the relationship between
agency, campaigner, and customer for client-specific data.
"""

from typing import Tuple, Optional


def compose_id(agency_id: int, campaigner_id: int, customer_id: int) -> str:
    """
    Compose a composite ID from individual IDs.
    
    Args:
        agency_id: The agency ID
        campaigner_id: The campaigner ID  
        customer_id: The customer ID
        
    Returns:
        Composite ID string in format: "agency_id_campaigner_id_customer_id"
        
    Example:
        compose_id(123, 456, 789) -> "123_456_789"
    """
    return f"{agency_id}_{campaigner_id}_{customer_id}"


def decompose_id(composite_id: str) -> Tuple[int, int, int]:
    """
    Decompose a composite ID into individual IDs.
    
    Args:
        composite_id: The composite ID string
        
    Returns:
        Tuple of (agency_id, campaigner_id, customer_id)
        
    Raises:
        ValueError: If the composite_id format is invalid
        
    Example:
        decompose_id("123_456_789") -> (123, 456, 789)
    """
    try:
        parts = composite_id.split("_")
        if len(parts) != 3:
            raise ValueError(f"Invalid composite_id format: {composite_id}")
        
        agency_id = int(parts[0])
        campaigner_id = int(parts[1])
        customer_id = int(parts[2])
        
        return agency_id, campaigner_id, customer_id
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid composite_id format: {composite_id}") from e


def extract_customer_id(composite_id: str) -> int:
    """
    Extract just the customer_id from a composite_id.
    
    Args:
        composite_id: The composite ID string
        
    Returns:
        The customer_id
        
    Example:
        extract_customer_id("123_456_789") -> 789
    """
    _, _, customer_id = decompose_id(composite_id)
    return customer_id


def extract_agency_id(composite_id: str) -> int:
    """
    Extract just the agency_id from a composite_id.
    
    Args:
        composite_id: The composite ID string
        
    Returns:
        The agency_id
        
    Example:
        extract_agency_id("123_456_789") -> 123
    """
    agency_id, _, _ = decompose_id(composite_id)
    return agency_id


def extract_campaigner_id(composite_id: str) -> int:
    """
    Extract just the campaigner_id from a composite_id.
    
    Args:
        composite_id: The composite ID string
        
    Returns:
        The campaigner_id
        
    Example:
        extract_campaigner_id("123_456_789") -> 456
    """
    _, campaigner_id, _ = decompose_id(composite_id)
    return campaigner_id


def validate_composite_id(composite_id: str) -> bool:
    """
    Validate that a composite_id has the correct format.
    
    Args:
        composite_id: The composite ID string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        decompose_id(composite_id)
        return True
    except ValueError:
        return False


def create_composite_id_from_context(agency_id: int, campaigner_id: int, customer_id: int) -> str:
    """
    Create a composite_id from the current context (agency, campaigner, customer).
    This is a convenience function that ensures the correct order.
    
    Args:
        agency_id: The agency ID
        campaigner_id: The campaigner ID
        customer_id: The customer ID
        
    Returns:
        Composite ID string
        
    Example:
        create_composite_id_from_context(123, 456, 789) -> "123_456_789"
    """
    return compose_id(agency_id, campaigner_id, customer_id)
