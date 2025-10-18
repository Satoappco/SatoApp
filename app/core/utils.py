"""
Common utilities for SatoApp
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional


def generate_session_id() -> str:
    """Generate a unique session ID"""
    return str(uuid.uuid4())




def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.utcnow().isoformat()


def extract_dialogcx_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and structure DialogCX data with support for both old and new field names"""
    session_info = raw_data.get('sessionInfo', {})
    parameters = session_info.get('parameters', {})
    
    # Support both old and new field names
    campaigner_id = parameters.get('campaigner_id') or parameters.get('user_id')
    agency_id = parameters.get('agency_id') or parameters.get('customer_id')
    customer_id = parameters.get('customer_id')
    
    return {
        'sessionInfo': session_info,
        'campaigner_id': campaigner_id,
        'agency_id': agency_id,
        'customer_id': customer_id,
        'session_id': session_info.get('session', '').split('/')[-1],
        'intent_type': raw_data.get('intentInfo', {}).get('displayName', ''),
        'confidence': raw_data.get('intentInfo', {}).get('confidence', 0.0),
        'parameters': parameters
    }


def should_trigger_crew_analysis(message: str) -> bool:
    """Determine if a message should trigger CrewAI analysis"""
    research_keywords = [
        'research', 'analyze', 'study', 'investigate', 'find', 'search',
        'trends', 'data', 'report', 'analysis', 'insights', 'information',
        'help me with', 'can you', 'what is', 'how to', 'explain',
        'traffic', 'seo', 'conversion', 'performance', 'marketing'
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in research_keywords)


def format_execution_time(start_time: datetime, end_time: Optional[datetime] = None) -> float:
    """Format execution time in seconds"""
    if end_time is None:
        end_time = datetime.utcnow()
    
    return (end_time - start_time).total_seconds()


def sanitize_agent_response(response: str) -> str:
    """Sanitize agent response for safe display"""
    # Remove any potential harmful content
    # For now, just return as-is, but this could be expanded
    return response.strip()


def get_default_customer_for_agency(agency_id: int) -> int:
    """Get the default customer ID for an agency (the first active customer)"""
    from app.config.database import get_session
    from app.models.users import Customer
    from sqlmodel import select
    
    with get_session() as session:
        # Get the first active customer for this agency
        statement = select(Customer).where(
            Customer.agency_id == agency_id
        ).order_by(Customer.id.asc())  # Get the first one (usually ID 1)
        
        customer = session.exec(statement).first()
        if customer:
            return customer.id
        return agency_id  # Fallback to agency_id if no customer found
