"""
ClickUp integration service for creating validation tasks when users dislike chat responses.
"""

import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.config.logging import get_logger
from sqlmodel import Session, select
from app.models.settings import AppSettings
from app.config.settings import get_settings as get_app_settings
logger = get_logger(__name__)


class ClickUpService:
    """Service for creating ClickUp tasks for chat feedback validation."""

    def __init__(self, session: Session):
        """Initialize the ClickUp service with database session."""
        self.session = session
        self._load_settings()

    def _load_settings(self):
        """Load ClickUp settings from database."""
        def get_setting(key: str, default: Any = None) -> Any:
            stmt = select(AppSettings).where(AppSettings.key == key)
            setting = self.session.exec(stmt).first()
            if setting:
                # Convert value based on type
                if setting.value_type == "bool":
                    return setting.value.lower() in ("true", "1", "yes")
                elif setting.value_type == "int":
                    return int(setting.value)
                return setting.value
            return default

        app_settings = get_app_settings()
        self.auth_token = app_settings.clickup_auth_token or get_setting("clickup_auth_token", "")
        self.dev_list_id = get_setting("clickup_dev_list_id", "901413553845")
        self.workspace_id = get_setting("clickup_workspace_id", "9014865885")
        self.assignee_id = get_setting("clickup_assignee_id", 9014865885)
        self.attach_logs = get_setting("clickup_attach_logs", False)

        logger.debug(f"ClickUp settings loaded: list_id={self.dev_list_id}, attach_logs={self.attach_logs}")

    def create_validation_task(
        self,
        thread_id: str,
        message_id: int,
        campaigner_name: str,
        customer_name: Optional[str],
        trace_url: str,
        trace_start_time: datetime,
        trace_end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a ClickUp task for validating a disliked chat response.

        Args:
            thread_id: Thread ID of the conversation
            message_id: Message ID that was disliked
            campaigner_name: Name of the campaigner who gave feedback
            customer_name: Name of the customer (if applicable)
            trace_url: URL to the trace viewer
            trace_start_time: Start time of the conversation
            trace_end_time: End time of the conversation (defaults to now)

        Returns:
            Dictionary with task details:
            {
                "success": bool,
                "task_id": str,
                "task_url": str,
                "error": str (if failed)
            }
        """
        if not self.auth_token:
            error_msg = "ClickUp auth token not configured"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

        try:
            # Generate log URL for the timeframe
            if not trace_end_time:
                trace_end_time = datetime.now()

            log_url = self._generate_log_url(trace_start_time, trace_end_time)

            # Create task name
            customer_part = f"_{customer_name}" if customer_name else ""
            task_name = f"dislike_validation_{campaigner_name}{customer_part}"

            # Create description
            description = self._create_task_description(
                campaigner_name=campaigner_name,
                customer_name=customer_name,
                thread_id=thread_id,
                message_id=message_id,
                trace_url=trace_url,
                log_url=log_url
            )

            # Create the task
            task_response = self.create_task(task_name, description)

            if not task_response or not task_response.get("id"):
                error_msg = f"Failed to create ClickUp task: {task_response}"
                logger.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}

            task_id = task_response["id"]
            task_url = task_response.get("url", "")

            logger.info(f"✅ Created ClickUp task {task_id} for dislike validation: {task_url}")

            # Optionally attach logs
            if self.attach_logs:
                try:
                    self._attach_logs(task_id, trace_start_time, trace_end_time)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to attach logs to task {task_id}: {e}")

            return {
                "success": True,
                "task_id": task_id,
                "task_url": task_url
            }

        except Exception as e:
            error_msg = f"Exception creating ClickUp task: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {"success": False, "error": error_msg}

    def _generate_log_url(self, start_time: datetime, end_time: datetime) -> str:
        """Generate URL for fetching logs in the trace timeframe."""
        # Add 5 minute buffer before and after
        buffered_start = start_time - timedelta(minutes=5)
        buffered_end = end_time + timedelta(minutes=5)

        # Format as ISO strings
        start_str = buffered_start.isoformat()
        end_str = buffered_end.isoformat()

        # Construct log API URL
        # This assumes the frontend URL is set in settings
        from app.config import get_settings
        settings = get_settings()
        base_url = settings.frontend_url or "http://localhost:3000"

        # Generate API URL for logs
        log_url = f"{base_url}/api/v1/logs/timerange?start_time={start_str}&end_time={end_str}&max_results=5000"

        return log_url

    def _create_task_description(
        self,
        campaigner_name: str,
        customer_name: Optional[str],
        thread_id: str,
        message_id: int,
        trace_url: str,
        log_url: str
    ) -> str:
        """Create formatted task description."""
        customer_info = f"\n**Customer:** {customer_name}" if customer_name else ""

        description = f"""# Dislike Validation Required

User pressed DISLIKE button on a chat response that needs review.

**Campaigner:** {campaigner_name}{customer_info}
**Thread ID:** `{thread_id}`
**Message ID:** `{message_id}`

## Links
- **Trace:** {trace_url}
- **Logs:** {"See attachment" if self.attach_logs else log_url}

## Action Required
1. Review the trace to understand what happened
2. Check if the response was genuinely problematic
3. Document the issue and recommended fix
4. Update training data if needed
"""
        return description

    def create_task(self, task_name: str, description: str, tags : List[str] = ["validation_needed"]) -> Dict[str, Any]:
        """Create a ClickUp task."""
        url = f"https://api.clickup.com/api/v2/list/{self.dev_list_id}/task"

        payload = {
            # "assignees": [self.assignee_id],
            "tags": tags,
            "name": task_name,
            "description": description
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": self.auth_token
        }

        logger.debug(f"📤 Creating ClickUp task: {task_name}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code not in (200, 201):
            logger.error(f"❌ ClickUp API error: [{headers}] {response.status_code} - {response.text}")
            return {}

        return response.json()

    def send_message(self, message: str, channel_id: str = "6-901413553845-8") -> bool:
        """Send a message to a ClickUp channel."""
        url = f"https://api.clickup.com/api/v3/workspaces/{self.workspace_id}/chat/channels/{channel_id}/messages"

        payload = {
            "type": "message",
            "content_format": "text/md",
            "content": message
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": self.auth_token
        }

        logger.debug(f"📤 Sending message to ClickUp channel {channel_id}: {message}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code not in (200, 201):
            logger.error(f"❌ ClickUp API error sending message: [{headers}] {response.status_code} - {response.text}")
            return False

        return True

    def _attach_logs(self, task_id: str, start_time: datetime, end_time: datetime):
        """
        Attach log files to a ClickUp task.

        Note: This is a placeholder implementation. Full implementation would:
        1. Fetch logs from the file logger for the time range
        2. Create a temporary file
        3. Upload as multipart/form-data to ClickUp
        """
        logger.info(f"📎 Log attachment requested for task {task_id}, but not yet fully implemented")

        # TODO: Implement log attachment
        # This would require:
        # 1. Using file_logger.get_logs_by_timerange() to get logs
        # 2. Creating a temporary file
        # 3. Using requests with files parameter:
        #    url = f"https://api.clickup.com/api/v2/task/{task_id}/attachment"
        #    headers = {"Authorization": self.auth_token}
        #    files = {"attachment": ("logs.txt", log_content, "text/plain")}
        #    requests.post(url, headers=headers, files=files)

        pass
