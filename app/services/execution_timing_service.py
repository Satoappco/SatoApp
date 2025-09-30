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
        """Get structured timing breakdown for a session"""
        try:
            with get_session() as session:
                timings = session.query(ExecutionTiming).filter(
                    ExecutionTiming.session_id == session_id
                ).order_by(ExecutionTiming.start_time).all()
                
                breakdown = {
                    'total_components': len(timings),
                    'total_duration_ms': sum(t.duration_ms or 0 for t in timings),
                    'agents': [],
                    'tools': [],
                    'api_calls': [],
                    'timeline': []
                }
                
                for timing in timings:
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
                
                return breakdown
                
        except Exception as e:
            logger.error(f"Failed to get timing breakdown: {str(e)}")
            return {'error': str(e)}
    
    def log_detailed_step(self, session_id: str, component_type: str, component_name: str, 
                         step_data: Dict[str, Any], analysis_id: str = None):
        """Log a detailed execution step"""
        try:
            timing_record = ExecutionTiming(
                session_id=session_id,
                analysis_id=analysis_id,
                component_type=component_type,
                component_name=component_name,
                start_time=datetime.fromisoformat(step_data['timestamp'].replace('Z', '+00:00')),
                end_time=datetime.fromisoformat(step_data['timestamp'].replace('Z', '+00:00')),
                duration_ms=0,  # Step-level timing
                status="completed",
                input_data=json.dumps(step_data.get('data', {})),
                output_data=json.dumps(step_data),
                parent_session_id=session_id
            )
            
            with get_session() as session:
                session.add(timing_record)
                session.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to log detailed step: {str(e)}")

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
