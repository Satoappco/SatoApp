"""
API routes for chat feedback (like/dislike) functionality.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.config.database import get_session
from app.config.logging import get_logger
from app.core.auth import get_current_user
from app.models.chat_feedback import ChatFeedback, FeedbackType
from app.models.chat_traces import ChatTrace, RecordType
from app.models.users import Campaigner
from app.services.clickup_service import ClickUpService

logger = get_logger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    thread_id: str
    message_id: int
    feedback_type: str  # "like" or "dislike"


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    success: bool
    message: str
    feedback_id: Optional[int] = None
    clickup_task_url: Optional[str] = None


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    session: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Submit like or dislike feedback for a chat message.

    For dislikes, this will create a ClickUp validation task.

    **Authentication Required**

    **Request Body:**
    - `thread_id`: Thread ID of the conversation
    - `message_id`: ID of the message being rated (from chat_traces table)
    - `feedback_type`: Either "like" or "dislike"

    **Returns:**
    - Success status and feedback ID
    - For dislikes: ClickUp task URL if notification was sent
    """
    try:
        # Validate feedback type
        if request.feedback_type not in [FeedbackType.LIKE, FeedbackType.DISLIKE]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback_type. Must be 'like' or 'dislike'"
            )

        # Verify the message exists
        message_stmt = select(ChatTrace).where(
            ChatTrace.id == request.message_id,
            ChatTrace.thread_id == request.thread_id,
            ChatTrace.record_type == RecordType.MESSAGE
        )
        message = session.exec(message_stmt).first()

        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"Message {request.message_id} not found in thread {request.thread_id}"
            )

        # Check for existing feedback from this user on this message
        existing_stmt = select(ChatFeedback).where(
            ChatFeedback.thread_id == request.thread_id,
            ChatFeedback.message_id == request.message_id,
            ChatFeedback.campaigner_id == current_user.id
        )
        existing_feedback = session.exec(existing_stmt).first()

        if existing_feedback:
            # Update existing feedback
            existing_feedback.feedback_type = request.feedback_type
            existing_feedback.updated_at = datetime.now(timezone.utc)
            feedback = existing_feedback
            logger.info(f"📝 Updated feedback {feedback.id} to {request.feedback_type}")
        else:
            # Create new feedback
            feedback = ChatFeedback(
                thread_id=request.thread_id,
                message_id=request.message_id,
                feedback_type=request.feedback_type,
                campaigner_id=current_user.id,
                customer_id=message.customer_id
            )
            session.add(feedback)
            logger.info(f"📝 Created new {request.feedback_type} feedback for message {request.message_id}")

        session.commit()
        session.refresh(feedback)

        # If dislike, create ClickUp notification
        clickup_task_url = None
        if request.feedback_type == FeedbackType.DISLIKE:
            try:
                clickup_result = await _create_clickup_notification(
                    session=session,
                    feedback=feedback,
                    message=message,
                    campaigner=current_user
                )

                if clickup_result.get("success"):
                    # Update feedback with ClickUp info
                    feedback.clickup_task_id = clickup_result.get("task_id")
                    feedback.clickup_task_url = clickup_result.get("task_url")
                    feedback.notification_sent = True
                    clickup_task_url = clickup_result.get("task_url")
                else:
                    feedback.notification_error = clickup_result.get("error")

                session.commit()

            except Exception as e:
                logger.error(f"❌ Failed to create ClickUp notification: {e}", exc_info=True)
                feedback.notification_error = str(e)
                session.commit()

        return FeedbackResponse(
            success=True,
            message=f"Feedback recorded successfully",
            feedback_id=feedback.id,
            clickup_task_url=clickup_task_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting feedback: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


async def _create_clickup_notification(
    session: Session,
    feedback: ChatFeedback,
    message: ChatTrace,
    campaigner: Campaigner
) -> dict:
    """Create ClickUp notification for dislike feedback."""
    try:
        # Get conversation record to find start time
        conv_stmt = select(ChatTrace).where(
            ChatTrace.thread_id == feedback.thread_id,
            ChatTrace.record_type == RecordType.CONVERSATION
        )
        conversation = session.exec(conv_stmt).first()

        if not conversation:
            logger.warning(f"⚠️  No conversation record found for thread {feedback.thread_id}")
            trace_start_time = message.created_at
        else:
            trace_start_time = conversation.created_at

        # Get customer name if available
        customer_name = None
        if message.customer_id:
            from app.models.users import Customer
            customer_stmt = select(Customer).where(Customer.id == message.customer_id)
            customer = session.exec(customer_stmt).first()
            if customer:
                customer_name = customer.full_name

        # Generate trace URL
        from app.config import get_settings
        settings = get_settings()
        frontend_url = settings.frontend_url or "http://localhost:3000"
        trace_url = f"{frontend_url}/traces/{feedback.thread_id}"

        # Create ClickUp task
        clickup_service = ClickUpService(session)
        result = clickup_service.create_validation_task(
            thread_id=feedback.thread_id,
            message_id=feedback.message_id,
            campaigner_name=campaigner.full_name,
            customer_name=customer_name,
            trace_url=trace_url,
            trace_start_time=trace_start_time,
            trace_end_time=message.created_at
        )

        return result

    except Exception as e:
        logger.error(f"❌ Exception in _create_clickup_notification: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.get("/feedback/{thread_id}")
async def get_thread_feedback(
    thread_id: str,
    session: Session = Depends(get_session),
    _: Campaigner = Depends(get_current_user)
):
    """
    Get all feedback for a conversation thread.

    **Authentication Required**

    **Path Parameters:**
    - `thread_id`: Thread ID of the conversation

    **Returns:**
    - List of feedback records for the thread
    """
    try:
        stmt = select(ChatFeedback).where(
            ChatFeedback.thread_id == thread_id
        ).order_by(ChatFeedback.created_at.desc())

        feedback_list = session.exec(stmt).all()

        return {
            "success": True,
            "thread_id": thread_id,
            "count": len(feedback_list),
            "feedback": [
                {
                    "id": f.id,
                    "message_id": f.message_id,
                    "feedback_type": f.feedback_type,
                    "campaigner_id": f.campaigner_id,
                    "created_at": f.created_at.isoformat(),
                    "clickup_task_url": f.clickup_task_url
                }
                for f in feedback_list
            ]
        }

    except Exception as e:
        logger.error(f"❌ Error fetching feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch feedback: {str(e)}")


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    session: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Delete a feedback record.

    **Authentication Required**

    Users can only delete their own feedback.

    **Path Parameters:**
    - `feedback_id`: ID of the feedback to delete

    **Returns:**
    - Success status
    """
    try:
        stmt = select(ChatFeedback).where(
            ChatFeedback.id == feedback_id,
            ChatFeedback.campaigner_id == current_user.id
        )
        feedback = session.exec(stmt).first()

        if not feedback:
            raise HTTPException(
                status_code=404,
                detail=f"Feedback {feedback_id} not found or you don't have permission to delete it"
            )

        session.delete(feedback)
        session.commit()

        logger.info(f"🗑️  Deleted feedback {feedback_id}")

        return {
            "success": True,
            "message": f"Feedback {feedback_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting feedback: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete feedback: {str(e)}")
