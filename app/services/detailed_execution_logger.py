"""
Detailed Execution Logger - Captures comprehensive CrewAI execution logs
Mirrors terminal output for complete debugging visibility
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from threading import Lock
import uuid

from app.config.database import get_session
try:
    from app.models.agents import DetailedExecutionLog
except ImportError:
    # If the model doesn't exist yet (migration not run), create a dummy class
    class DetailedExecutionLog:
        pass
from app.config.logging import get_logger

logger = get_logger("services.detailed_logger")


class DetailedExecutionLogger:
    """
    Comprehensive execution logger that captures all CrewAI execution details
    similar to what's shown in terminal output
    """
    
    def __init__(self, session_id: str, analysis_id: Optional[str] = None):
        self.session_id = session_id
        self.analysis_id = analysis_id
        self.sequence_counter = 0
        self.lock = Lock()
        self.log_stack = []  # Stack to track hierarchy
        
    def _get_next_sequence(self) -> int:
        """Get next sequence number for this session"""
        with self.lock:
            self.sequence_counter += 1
            return self.sequence_counter
    
    def _save_log_entry(self, log_data: Dict[str, Any]) -> int:
        """Save log entry to database"""
        try:
            # Check if DetailedExecutionLog is a real model (table exists)
            if not hasattr(DetailedExecutionLog, '__tablename__'):
                logger.debug("DetailedExecutionLog table not available - skipping database save")
                return None
                
            with get_session() as session:
                log_entry = DetailedExecutionLog(**log_data)
                session.add(log_entry)
                session.commit()
                session.refresh(log_entry)
                return log_entry.id
        except Exception as e:
            logger.error(f"Failed to save detailed log entry: {str(e)}")
            return None
    
    def log_crew_start(self, crew_name: str = "crew", agents: List[str] = None, 
                      tasks: List[str] = None, process: str = "sequential") -> int:
        """Log crew execution start - 🚀 Crew: crew"""
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "crew_start",
            "depth_level": 0,
            "crew_id": crew_name,
            "status": "executing",
            "title": f"🚀 Crew: {crew_name}",
            "content": f"Starting crew execution with {len(agents or [])} agents and {len(tasks or [])} tasks",
            "log_metadata": json.dumps({
                "agents": agents or [],
                "tasks": tasks or [],
                "process": process,
                "start_time": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "🚀",
            "color": "blue",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        self.log_stack.append({"type": "crew", "id": log_id, "name": crew_name})
        return log_id
    
    def log_task_start(self, task_id: str, task_description: str, 
                      assigned_agent: str = None) -> int:
        """Log task start - └── 📋 Task: task_id"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "task_start",
            "parent_log_id": parent_log_id,
            "depth_level": 1,
            "task_id": task_id,
            "agent_name": assigned_agent,
            "status": "executing",
            "title": f"└── 📋 Task: {task_id}",
            "content": f"Status: Executing Task...",
            "input_data": task_description,
            "log_metadata": json.dumps({
                "assigned_agent": assigned_agent,
                "task_description": task_description[:200] + "..." if len(task_description) > 200 else task_description,
                "start_time": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "📋",
            "color": "yellow",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        self.log_stack.append({"type": "task", "id": log_id, "name": task_id})
        return log_id
    
    def log_agent_start(self, agent_name: str, task_description: str = None) -> int:
        """Log agent start - 🤖 Agent Started"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "agent_start",
            "parent_log_id": parent_log_id,
            "depth_level": 2,
            "agent_name": agent_name,
            "status": "executing",
            "title": f"🤖 Agent Started",
            "content": f"Agent: {agent_name}",
            "input_data": task_description,
            "log_metadata": json.dumps({
                "agent_name": agent_name,
                "task_description": task_description[:200] + "..." if task_description and len(task_description) > 200 else task_description,
                "start_time": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "🤖",
            "color": "green",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        self.log_stack.append({"type": "agent", "id": log_id, "name": agent_name})
        return log_id
    
    def log_agent_thinking(self, agent_name: str, thought: str = None) -> int:
        """Log agent thinking - └── 🧠 Thinking..."""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "agent_thinking",
            "parent_log_id": parent_log_id,
            "depth_level": 3,
            "agent_name": agent_name,
            "status": "thinking",
            "title": f"└── 🧠 Thinking...",
            "content": thought,
            "log_metadata": json.dumps({
                "agent_name": agent_name,
                "thought": thought[:200] + "..." if thought and len(thought) > 200 else thought,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "🧠",
            "color": "purple",
            "is_collapsible": False
        }
        
        return self._save_log_entry(log_data)
    
    def log_tool_execution_start(self, agent_name: str, tool_name: str, 
                               tool_input: str = None, attempt_number: int = 1) -> int:
        """Log tool execution start - └── 🔧 Used Tool_Name (1)"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "tool_execution",
            "parent_log_id": parent_log_id,
            "depth_level": 3,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "status": "executing",
            "title": f"└── 🔧 Used {tool_name} ({attempt_number})",
            "content": "🔧 Agent Tool Execution",
            "input_data": tool_input,
            "log_metadata": json.dumps({
                "agent_name": agent_name,
                "tool_name": tool_name,
                "attempt_number": attempt_number,
                "tool_input": tool_input[:200] + "..." if tool_input and len(tool_input) > 200 else tool_input,
                "start_time": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "🔧",
            "color": "blue",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        self.log_stack.append({"type": "tool", "id": log_id, "name": tool_name})
        return log_id
    
    def log_tool_input(self, tool_name: str, tool_input: str) -> int:
        """Log tool input details - Tool Input section"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "tool_input",
            "parent_log_id": parent_log_id,
            "depth_level": 4,
            "tool_name": tool_name,
            "status": "input",
            "title": "Tool Input",
            "content": tool_input,
            "input_data": tool_input,
            "log_metadata": json.dumps({
                "tool_name": tool_name,
                "input_size": len(tool_input) if tool_input else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "📥",
            "color": "gray",
            "is_collapsible": False
        }
        
        return self._save_log_entry(log_data)
    
    def log_tool_output(self, tool_name: str, tool_output: str, 
                       duration_ms: int = None) -> int:
        """Log tool output details - Tool Output section"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "tool_output",
            "parent_log_id": parent_log_id,
            "depth_level": 4,
            "tool_name": tool_name,
            "status": "completed",
            "duration_ms": duration_ms,
            "title": "Tool Output",
            "content": tool_output,
            "output_data": tool_output,
            "log_metadata": json.dumps({
                "tool_name": tool_name,
                "output_size": len(tool_output) if tool_output else 0,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "📤",
            "color": "gray",
            "is_collapsible": False
        }
        
        return self._save_log_entry(log_data)
    
    def log_tool_error(self, agent_name: str, tool_name: str, error_message: str, 
                      tool_input: str = None, attempt_number: int = 1) -> int:
        """Log tool error - └── 🔧 Failed Tool_Name (1)"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "tool_error",
            "parent_log_id": parent_log_id,
            "depth_level": 3,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "status": "failed",
            "title": f"└── 🔧 Failed {tool_name} ({attempt_number})",
            "content": "Tool Usage Failed",
            "input_data": tool_input,
            "error_details": error_message,
            "log_metadata": json.dumps({
                "agent_name": agent_name,
                "tool_name": tool_name,
                "attempt_number": attempt_number,
                "error_message": error_message,
                "tool_input": tool_input[:200] + "..." if tool_input and len(tool_input) > 200 else tool_input,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "❌",
            "color": "red",
            "is_collapsible": True
        }
        
        return self._save_log_entry(log_data)
    
    def log_delegation(self, agent_name: str, delegated_to: str, task: str, 
                      context: str = None) -> int:
        """Log delegation attempt"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "delegation",
            "parent_log_id": parent_log_id,
            "depth_level": 3,
            "agent_name": agent_name,
            "status": "delegating",
            "title": f"└── 🔄 Delegating to {delegated_to}",
            "content": task,
            "input_data": context,
            "log_metadata": json.dumps({
                "delegating_agent": agent_name,
                "delegated_to": delegated_to,
                "task": task[:200] + "..." if task and len(task) > 200 else task,
                "context": context[:200] + "..." if context and len(context) > 200 else context,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "🔄",
            "color": "orange",
            "is_collapsible": True
        }
        
        return self._save_log_entry(log_data)
    
    def log_agent_final_answer(self, agent_name: str, final_answer: str) -> int:
        """Log agent final answer - ✅ Agent Final Answer"""
        parent_log_id = self.log_stack[-1]["id"] if self.log_stack else None
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "final_answer",
            "parent_log_id": parent_log_id,
            "depth_level": 2,
            "agent_name": agent_name,
            "status": "completed",
            "title": f"✅ Agent Final Answer",
            "content": f"Agent: {agent_name}",
            "output_data": final_answer,
            "log_metadata": json.dumps({
                "agent_name": agent_name,
                "answer_length": len(final_answer) if final_answer else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "✅",
            "color": "green",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        
        # Pop agent from stack
        if self.log_stack and self.log_stack[-1]["type"] == "agent":
            self.log_stack.pop()
        
        return log_id
    
    def log_task_complete(self, task_id: str, assigned_agent: str, 
                         duration_ms: int = None, tools_used: List[str] = None) -> int:
        """Log task completion - Task Completion"""
        parent_log_id = self.log_stack[0]["id"] if self.log_stack else None  # Crew level
        
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "task_complete",
            "parent_log_id": parent_log_id,
            "depth_level": 1,
            "task_id": task_id,
            "agent_name": assigned_agent,
            "status": "completed",
            "duration_ms": duration_ms,
            "title": f"Task Completed",
            "content": f"Name: {task_id}\nAgent: {assigned_agent}",
            "log_metadata": json.dumps({
                "task_id": task_id,
                "assigned_agent": assigned_agent,
                "duration_ms": duration_ms,
                "tools_used": tools_used or [],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "✅",
            "color": "green",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        
        # Pop task from stack
        if self.log_stack and self.log_stack[-1]["type"] == "task":
            self.log_stack.pop()
        
        return log_id
    
    def log_crew_complete(self, crew_name: str, final_output: str, 
                         duration_seconds: float = None) -> int:
        """Log crew completion - Crew Completion"""
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "crew_complete",
            "depth_level": 0,
            "crew_id": crew_name,
            "status": "completed",
            "duration_ms": int(duration_seconds * 1000) if duration_seconds else None,
            "title": f"Crew Execution Completed",
            "content": f"Name: {crew_name}",
            "output_data": final_output,
            "log_metadata": json.dumps({
                "crew_name": crew_name,
                "duration_seconds": duration_seconds,
                "output_length": len(final_output) if final_output else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "✅",
            "color": "green",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        
        # Clear stack
        self.log_stack.clear()
        
        return log_id
    
    def log_crew_error(self, crew_name: str, error_message: str, 
                      duration_seconds: float = None) -> int:
        """Log crew error - Crew Error"""
        log_data = {
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "timestamp": datetime.now(timezone.utc),
            "sequence_number": self._get_next_sequence(),
            "log_type": "crew_error",
            "depth_level": 0,
            "crew_id": crew_name,
            "status": "failed",
            "duration_ms": int(duration_seconds * 1000) if duration_seconds else None,
            "title": f"❌ Crew Execution Failed",
            "content": f"Name: {crew_name}",
            "error_details": error_message,
            "log_metadata": json.dumps({
                "crew_name": crew_name,
                "duration_seconds": duration_seconds,
                "error_message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }),
            "icon": "❌",
            "color": "red",
            "is_collapsible": True
        }
        
        log_id = self._save_log_entry(log_data)
        
        # Clear stack
        self.log_stack.clear()
        
        return log_id
    
    def get_execution_logs(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all execution logs for this session"""
        try:
            # Check if DetailedExecutionLog is a real model (table exists)
            if not hasattr(DetailedExecutionLog, '__tablename__'):
                logger.warning("DetailedExecutionLog table not available - returning empty logs")
                return []
                
            with get_session() as session:
                logs = session.query(DetailedExecutionLog).filter(
                    DetailedExecutionLog.session_id == self.session_id
                ).order_by(DetailedExecutionLog.sequence_number).limit(limit).all()
                
                return [{
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "sequence_number": log.sequence_number,
                    "log_type": log.log_type,
                    "parent_log_id": log.parent_log_id,
                    "depth_level": log.depth_level,
                    "crew_id": log.crew_id,
                    "task_id": log.task_id,
                    "agent_name": log.agent_name,
                    "tool_name": log.tool_name,
                    "status": log.status,
                    "duration_ms": log.duration_ms,
                    "title": log.title,
                    "content": log.content,
                    "input_data": log.input_data,
                    "output_data": log.output_data,
                    "error_details": log.error_details,
                    "metadata": json.loads(log.log_metadata) if log.log_metadata else {},
                    "icon": log.icon,
                    "color": log.color,
                    "is_collapsible": log.is_collapsible
                } for log in logs]
                
        except Exception as e:
            logger.error(f"Failed to get execution logs: {str(e)}")
            return []


# Global detailed logger instances
_detailed_loggers: Dict[str, DetailedExecutionLogger] = {}
_logger_lock = Lock()


def get_detailed_logger(session_id: str, analysis_id: str = None) -> DetailedExecutionLogger:
    """Get or create detailed logger for session"""
    with _logger_lock:
        if session_id not in _detailed_loggers:
            _detailed_loggers[session_id] = DetailedExecutionLogger(session_id, analysis_id)
        return _detailed_loggers[session_id]


def cleanup_detailed_logger(session_id: str):
    """Cleanup detailed logger for session"""
    with _logger_lock:
        if session_id in _detailed_loggers:
            del _detailed_loggers[session_id]
