"""
Execution Timing Service - DEPRECATED
This service is deprecated as the ExecutionTiming table has been removed.
Timing data is now stored in customer_logs.timing_breakdown.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from threading import Lock
import uuid

from app.config.database import get_session
from app.models.agents import CustomerLog
from app.config.logging import get_logger

logger = get_logger("services.timing")


class ExecutionTimingService:
    """DEPRECATED: Service for tracking detailed execution timing of CrewAI components"""
    
    def __init__(self):
        self.active_timings: Dict[str, Dict[str, Any]] = {}
        self.session_timings: Dict[str, List[str]] = {}
        self.lock = Lock()
        logger.warning("ExecutionTimingService is DEPRECATED - ExecutionTiming table removed")
    
    def start_timing(self, session_id: str, component_type: str, component_name: str, 
                    input_data: str = None, analysis_id: str = None) -> str:
        """Start timing a component - DEPRECATED"""
        logger.debug(f"Timing start requested for {component_type}: {component_name} (deprecated)")
        return str(uuid.uuid4())
    
    def end_timing(self, timing_id: str, status: str = "completed", error_message: str = None):
        """End timing a component - DEPRECATED"""
        logger.debug(f"Timing end requested for {timing_id} (deprecated)")
    
    def get_session_timings(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all timing records for a session - DEPRECATED"""
        logger.debug(f"Session timings requested for {session_id} (deprecated)")
        return []
    
    def get_timing_breakdown(self, session_id: str) -> Dict[str, Any]:
        """Get structured timing breakdown for a session - DEPRECATED"""
        logger.debug(f"Timing breakdown for session {session_id} would be retrieved from customer_logs")
        return {
            'total_components': 0,
            'total_duration_ms': 0,
            'agents': [],
            'tools': [],
            'api_calls': [],
            'timeline': []
        }
    
    def log_detailed_step(self, session_id: str, component_type: str, component_name: str, 
                         step_data: Dict[str, Any], analysis_id: str = None):
        """
        DEPRECATED: This method was creating redundant ExecutionTiming records with 0ms duration.
        Detailed logging should go to DetailedExecutionLog table, not ExecutionTiming table.
        
        ExecutionTiming table is for performance metrics (agents, tools, crew) with actual durations.
        DetailedExecutionLog table is for step-by-step debugging (_agent_start, _agent_complete, etc).
        
        This method is now a no-op to prevent polluting the ExecutionTiming table.
        """
        # NO-OP: Don't create ExecutionTiming records for detailed steps
        # The detailed_execution_logger handles this separately
        logger.debug(f"Skipping detailed step logging for {component_type}: {component_name} (deprecated method)")

    def create_customer_log(self, session_id: str, user_intent: str, original_query: str, 
                           crewai_input_prompt: str, master_answer: str, crewai_log: str,
                           user_id: int = None, analysis_id: str = None, success: bool = True,
                           error_message: str = None) -> str:
        """Create comprehensive customer log entry"""
        try:
            # Get timing breakdown (now returns empty structure)
            timing_breakdown = self.get_timing_breakdown(session_id)
            total_time_ms = timing_breakdown.get('total_duration_ms', 0)
            
            # Extract agents and tools used
            agents_used = [t['name'] for t in timing_breakdown.get('agents', [])]
            tools_used = [t['name'] for t in timing_breakdown.get('tools', [])]
            
            with get_session() as session:
                customer_log = CustomerLog(
                    session_id=session_id,
                    user_intent=user_intent,
                    original_query=original_query,
                    crewai_input_prompt=crewai_input_prompt,
                    master_answer=master_answer,
                    crewai_log=crewai_log,
                    total_execution_time_ms=total_time_ms,
                    timing_breakdown=json.dumps(timing_breakdown),
                    campaigner_id=user_id,
                    analysis_id=analysis_id,
                    success=success,
                    error_message=error_message,
                    agents_used=json.dumps(agents_used),
                    tools_used=json.dumps(tools_used)
                )
                session.add(customer_log)
                session.commit()
                
                logger.info(f"📊 Customer log created for session {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"Failed to create customer log: {str(e)}")
            return None


# Global timing service instance
timing_service = ExecutionTimingService()