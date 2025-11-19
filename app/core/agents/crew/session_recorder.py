"""Session Recording for CrewAI Execution.

This module captures the complete thinking process of all agents during crew execution,
including task execution, agent reasoning steps, tool usage, and final outputs.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionRecorder:
    """Records detailed execution trace of CrewAI sessions."""

    def __init__(self, session_id: str, customer_id: Optional[int] = None):
        """Initialize session recorder.

        Args:
            session_id: Unique session identifier
            customer_id: Customer ID (optional)
        """
        self.session_id = session_id
        self.customer_id = customer_id
        self.started_at = datetime.utcnow()
        self.tasks: List[Dict[str, Any]] = []
        self.steps: List[Dict[str, Any]] = []
        self.tools_used: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def record_task_start(self, task_description: str, agent_role: str, task_index: int):
        """Record task start.

        Args:
            task_description: Description of the task
            agent_role: Role of the agent executing the task
            task_index: Index of the task in the crew
        """
        task_record = {
            "task_index": task_index,
            "agent_role": agent_role,
            "description": task_description,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "status": "running",
            "output": None,
            "steps": []
        }
        self.tasks.append(task_record)
        logger.info(f"📝 [SessionRecorder] Task {task_index} started by {agent_role}")

    def record_task_complete(self, task_index: int, output: str, status: str = "completed"):
        """Record task completion.

        Args:
            task_index: Index of the task
            output: Task output
            status: Task status (completed, failed, etc.)
        """
        if task_index < len(self.tasks):
            self.tasks[task_index].update({
                "completed_at": datetime.utcnow().isoformat(),
                "status": status,
                "output": output
            })
            logger.info(f"✅ [SessionRecorder] Task {task_index} {status}")

    def record_step(
        self,
        task_index: int,
        step_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record an agent reasoning step.

        Args:
            task_index: Index of the task this step belongs to
            step_type: Type of step (thought, action, observation, etc.)
            content: Content of the step
            metadata: Additional metadata
        """
        step_record = {
            "task_index": task_index,
            "timestamp": datetime.utcnow().isoformat(),
            "type": step_type,
            "content": content,
            "metadata": metadata or {}
        }
        self.steps.append(step_record)

        # Also add to task's steps list
        if task_index < len(self.tasks):
            self.tasks[task_index]["steps"].append(step_record)

        logger.debug(f"🧠 [SessionRecorder] Step recorded: {step_type}")

    def record_tool_usage(
        self,
        task_index: int,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        success: bool = True
    ):
        """Record tool usage.

        Args:
            task_index: Index of the task
            tool_name: Name of the tool used
            tool_input: Input to the tool
            tool_output: Output from the tool
            success: Whether tool execution was successful
        """
        tool_record = {
            "task_index": task_index,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "input": str(tool_input)[:500],  # Limit size
            "output": str(tool_output)[:500] if success else None,
            "error": str(tool_output)[:500] if not success else None,
            "success": success
        }
        self.tools_used.append(tool_record)
        logger.info(f"🔧 [SessionRecorder] Tool used: {tool_name} (success={success})")

    def record_error(self, error: str, context: Optional[Dict[str, Any]] = None):
        """Record an error.

        Args:
            error: Error message
            context: Additional context
        """
        error_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "context": context or {}
        }
        self.errors.append(error_record)
        logger.error(f"❌ [SessionRecorder] Error: {error}")

    def set_metadata(self, key: str, value: Any):
        """Set session metadata.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary.

        Returns:
            Dictionary containing session summary
        """
        completed_at = datetime.utcnow()
        duration = (completed_at - self.started_at).total_seconds()

        return {
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration,
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks if t["status"] == "completed"),
            "total_steps": len(self.steps),
            "tools_used_count": len(self.tools_used),
            "errors_count": len(self.errors),
            "metadata": self.metadata
        }

    def get_full_trace(self) -> Dict[str, Any]:
        """Get complete execution trace.

        Returns:
            Dictionary containing full execution trace
        """
        return {
            "summary": self.get_summary(),
            "tasks": self.tasks,
            "steps": self.steps,
            "tools": self.tools_used,
            "errors": self.errors,
            "metadata": self.metadata
        }

    def save_to_file(self, output_dir: str = "crew_sessions"):
        """Save session to JSON file.

        Args:
            output_dir: Directory to save session files
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            filename = f"session_{self.session_id}_{self.started_at.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = output_path / filename

            with open(filepath, 'w') as f:
                json.dump(self.get_full_trace(), f, indent=2, default=str)

            logger.info(f"💾 [SessionRecorder] Session saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"❌ [SessionRecorder] Failed to save session: {e}")
            return None


class CrewCallbacks:
    """Callback handlers for CrewAI execution."""

    def __init__(self, recorder: SessionRecorder):
        """Initialize callbacks.

        Args:
            recorder: SessionRecorder instance
        """
        self.recorder = recorder
        self.current_task_index = -1

    def task_callback(self, task_output):
        """Called when a task completes.

        Args:
            task_output: TaskOutput from CrewAI
        """
        try:
            # Extract task information
            description = getattr(task_output.description, 'description', str(task_output.description))
            agent_role = getattr(task_output.agent, 'role', 'Unknown')
            output = str(task_output.raw) if hasattr(task_output, 'raw') else str(task_output)

            # Record task completion
            if self.current_task_index >= 0:
                self.recorder.record_task_complete(
                    self.current_task_index,
                    output,
                    "completed"
                )

            logger.info(f"✅ [CrewCallbacks] Task completed: {description[:50]}...")

        except Exception as e:
            logger.error(f"❌ [CrewCallbacks] Error in task_callback: {e}")
            self.recorder.record_error(f"Task callback error: {e}")

    def step_callback(self, step_output):
        """Called after each agent step.

        Args:
            step_output: Step output from CrewAI
        """
        try:
            # Extract step information
            step_type = "action" if hasattr(step_output, 'action') else "thought"
            content = str(step_output)

            # Record step
            self.recorder.record_step(
                self.current_task_index,
                step_type,
                content[:1000]  # Limit content size
            )

            logger.debug(f"🧠 [CrewCallbacks] Step: {step_type}")

        except Exception as e:
            logger.error(f"❌ [CrewCallbacks] Error in step_callback: {e}")

    def start_task(self, task, agent, task_index: int):
        """Manually called before task starts.

        Args:
            task: Task object
            agent: Agent object
            task_index: Task index
        """
        self.current_task_index = task_index
        description = task.description if hasattr(task, 'description') else str(task)
        agent_role = agent.role if hasattr(agent, 'role') else 'Unknown'

        self.recorder.record_task_start(description, agent_role, task_index)
