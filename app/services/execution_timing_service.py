"""
Execution Timing Service for CrewAI Components
Tracks detailed timing for agents, tools, and API calls
"""

import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from threading import Lock
import uuid

from app.config.database import get_session
from app.models.agents import ExecutionTiming, CustomerLog
from app.config.logging import get_logger

logger = get_logger("services.timing")


def safe_json_serialize(obj):
    """Safely serialize objects to JSON, converting non-serializable objects to strings"""
    try:
        return json.dumps(obj)
    except TypeError:
        # If direct serialization fails, convert all non-serializable objects to strings
        def convert_to_serializable(item):
            if isinstance(item, dict):
                return {k: convert_to_serializable(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [convert_to_serializable(i) for i in item]
            elif isinstance(item, (str, int, float, bool, type(None))):
                return item
            else:
                return str(item)
        
        serializable_obj = convert_to_serializable(obj)
        return json.dumps(serializable_obj)


class ExecutionTimingService:
    """Service for tracking detailed execution timing of CrewAI components"""
    
    def __init__(self):
        self.active_timings = {}
        self.session_timings = {}
        self.lock = Lock()
    
    def start_timing(self, session_id: str, component_type: str, component_name: str, 
                    input_data: str = None, analysis_id: str = None) -> str:
        """Start timing a component (agent or tool)"""
        timing_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        with self.lock:
            self.active_timings[timing_id] = {
                'session_id': session_id,
                'analysis_id': analysis_id,
                'component_type': component_type,
                'component_name': component_name,
                'start_time': start_time,
                'input_data': input_data[:500] + "..." if input_data and len(input_data) > 500 else input_data,
                'status': 'running'
            }
            
            # Track in session
            if session_id not in self.session_timings:
                self.session_timings[session_id] = []
            self.session_timings[session_id].append(timing_id)
        
        logger.info(f"⏱️ Started timing {component_type}: {component_name} (ID: {timing_id})")
        return timing_id
    
    def end_timing(self, timing_id: str, output_data: str = None, error_message: str = None):
        """End timing a component"""
        end_time = datetime.utcnow()
        
        with self.lock:
            if timing_id not in self.active_timings:
                logger.warning(f"Timing ID {timing_id} not found in active timings")
                return
            
            timing_data = self.active_timings[timing_id]
            start_time = timing_data['start_time']
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update timing data
            timing_data.update({
                'end_time': end_time,
                'duration_ms': duration_ms,
                'output_data': output_data[:500] + "..." if output_data and len(output_data) > 500 else output_data,
                'error_message': error_message,
                'status': 'error' if error_message else 'completed'
            })
            
            # Store in database
            self._store_timing_record(timing_data)
            
            # Remove from active
            del self.active_timings[timing_id]
        
        status_emoji = "❌" if error_message else "✅"
        logger.info(f"{status_emoji} Ended timing {timing_data['component_type']}: {timing_data['component_name']} ({duration_ms}ms)")
    
    def _store_timing_record(self, timing_data: Dict[str, Any]):
        """Store timing record in database"""
        try:
            with get_session() as session:
                timing_record = ExecutionTiming(
                    session_id=timing_data['session_id'],
                    analysis_id=timing_data.get('analysis_id'),
                    component_type=timing_data['component_type'],
                    component_name=timing_data['component_name'],
                    start_time=timing_data['start_time'],
                    end_time=timing_data.get('end_time'),
                    duration_ms=timing_data.get('duration_ms'),
                    status=timing_data['status'],
                    input_data=timing_data.get('input_data'),
                    output_data=timing_data.get('output_data'),
                    error_message=timing_data.get('error_message')
                )
                session.add(timing_record)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to store timing record: {str(e)}")
    
    @contextmanager
    def time_component(self, session_id: str, component_type: str, component_name: str, 
                      input_data: str = None, analysis_id: str = None):
        """Context manager for timing a component"""
        timing_id = self.start_timing(session_id, component_type, component_name, input_data, analysis_id)
        try:
            yield timing_id
        except Exception as e:
            self.end_timing(timing_id, error_message=str(e))
            raise
        else:
            self.end_timing(timing_id)
    
    def get_session_timings(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all timing records for a session"""
        with self.lock:
            timing_ids = self.session_timings.get(session_id, [])
            return [self.active_timings.get(tid, {}) for tid in timing_ids if tid in self.active_timings]
    
    def get_timing_breakdown(self, session_id: str) -> Dict[str, Any]:
        """Get structured timing breakdown for a session with deduplication"""
        try:
            with get_session() as session:
                timings = session.query(ExecutionTiming).filter(
                    ExecutionTiming.session_id == session_id
                ).order_by(ExecutionTiming.start_time).all()
                
                breakdown = {
                    'total_components': 0,  # Will be updated after deduplication
                    'total_duration_ms': 0,  # Will be updated after deduplication
                    'agents': [],
                    'tools': [],
                    'api_calls': [],
                    'timeline': []
                }
                
                # Filter and deduplicate timing records
                # 1. EXCLUDE agent_step, crew_step, crew types (crew is wrapper, agents/tools are actual work)
                # 2. Deduplicate remaining records by component_name + component_type
                # 3. For agents, only keep the first occurrence to avoid massive duplication
                seen_components = {}
                deduplicated_timings = []
                excluded_types = ['agent_step', 'crew_step', 'crew']  # Exclude wrapper timings
                
                for timing in timings:
                    # Skip excluded types (debugging steps with 0ms duration)
                    if timing.component_type in excluded_types:
                        continue
                    
                    component_key = f"{timing.component_name}_{timing.component_type}"
                    
                    # For agents, only keep the first occurrence to prevent massive duplication
                    if timing.component_type == 'agent':
                        if component_key not in seen_components:
                            seen_components[component_key] = timing
                            deduplicated_timings.append(timing)
                        # Skip all subsequent agent executions with the same name
                        continue
                    
                    # For other components, keep the first occurrence (earliest start_time)
                    if component_key not in seen_components:
                        seen_components[component_key] = timing
                        deduplicated_timings.append(timing)
                    else:
                        # If we find a duplicate, keep the one with longer duration (more complete data)
                        existing = seen_components[component_key]
                        if timing.duration_ms and (not existing.duration_ms or timing.duration_ms > existing.duration_ms):
                            # Replace with the more complete timing
                            deduplicated_timings.remove(existing)
                            deduplicated_timings.append(timing)
                            seen_components[component_key] = timing
                
                # Update totals after deduplication
                breakdown['total_components'] = len(deduplicated_timings)
                breakdown['total_duration_ms'] = sum(t.duration_ms or 0 for t in deduplicated_timings)
                
                # Build breakdown from deduplicated timings
                for timing in deduplicated_timings:
                    component_data = {
                        'name': timing.component_name,
                        'type': timing.component_type,
                        'duration_ms': timing.duration_ms,
                        'start_time': timing.start_time.isoformat(),
                        'end_time': timing.end_time.isoformat() if timing.end_time else None,
                        'status': timing.status,
                        'error': timing.error_message
                    }
                    
                    if timing.component_type == 'agent':
                        breakdown['agents'].append(component_data)
                    elif timing.component_type == 'tool':
                        breakdown['tools'].append(component_data)
                    elif 'api' in timing.component_name.lower():
                        breakdown['api_calls'].append(component_data)
                    
                    breakdown['timeline'].append(component_data)
                
                excluded_count = len(timings) - len([t for t in timings if t.component_type not in excluded_types])
                logger.info(f"📊 Timing breakdown for session {session_id}: {len(timings)} raw → {excluded_count} excluded (agent_step/crew_step) → {len(deduplicated_timings)} final")
                return breakdown
                
        except Exception as e:
            logger.error(f"Failed to get timing breakdown: {str(e)}")
            return {'error': str(e)}
    
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
            # Get timing breakdown
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
                    user_id=user_id,
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
