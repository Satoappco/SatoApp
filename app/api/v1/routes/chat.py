"""Chat/conversation endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List
from datetime import datetime
import uuid
import json
import asyncio
import logging

from app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationThread,
    ThreadListResponse
)
from app.api.dependencies import get_app_state, ApplicationState
from app.core.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    app_state: ApplicationState = Depends(get_app_state),
    current_user = Depends(get_current_user)
):
    """
    Send a message to the conversation agent.

    The agent will extract intent from your message and ask clarifying questions
    until it has all the information needed to run analytics.

    Requires authentication via JWT token.
    """
    try:
        # Generate thread ID if not provided
        thread_id = request.thread_id or str(uuid.uuid4())
        logger.info(f"💬 [Chat] Thread: {thread_id[:8]}... | Message: '{request.message[:50]}...'")

        # Get conversation workflow for this thread (with campaigner_id)
        logger.debug(f"📋 [Chat] Getting workflow for thread: {thread_id} | Request: {request}")
        workflow = app_state.get_conversation_workflow(current_user.id, thread_id)

        # Process message
        logger.debug(f"🔄 [Chat] Processing message through workflow...")
        result = workflow.process_message(request.message)
        logger.debug(f"✅ [Chat] Workflow processed. Result keys: {list(result.keys())}")

        # Extract response message
        messages = result.get("messages", [])
        assistant_message = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                assistant_message = last_message.content
                logger.debug(f"💭 [Chat] Assistant message: '{assistant_message[:100]}...'")

        # If clarification question exists, use that
        if result.get("clarification_question"):
            assistant_message = result["clarification_question"]
            logger.info(f"❓ [Chat] Clarification needed: '{assistant_message[:100]}...'")

        # Build intent dict
        intent = {
            "platforms": result.get("platforms", []),
            "metrics": result.get("metrics", []),
            "date_range_start": result.get("date_range_start"),
            "date_range_end": result.get("date_range_end"),
            "comparison_period": result.get("comparison_period", False),
            "specific_campaigns": result.get("specific_campaigns"),
        }

        needs_clarification = result.get("clarification_needed", False)
        ready_for_analysis = result.get("ready_for_crew", False)

        logger.info(
            f"📊 [Chat] State: clarification={needs_clarification}, "
            f"ready={ready_for_analysis}, "
            f"platforms={intent.get('platforms', [])}"
        )

        return ChatResponse(
            message=assistant_message or "I'm processing your request...",
            thread_id=thread_id,
            needs_clarification=needs_clarification,
            ready_for_analysis=ready_for_analysis,
            intent=intent if any(intent.values()) else None
        )

    except Exception as e:
        logger.error(f"❌ [Chat] Error processing chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    app_state: ApplicationState = Depends(get_app_state),
    current_user = Depends(get_current_user)
):
    """
    Stream chat response in real-time (SSE format).

    Returns Server-Sent Events with the response being generated.

    Requires authentication via JWT token.
    """

    async def generate():
        try:
            # Generate thread ID if not provided
            thread_id = request.thread_id or str(uuid.uuid4())
            logger.info(f"📡 [Stream] Thread: {thread_id[:8]}... | Message: '{request.message[:50]}...'")

            # Get conversation workflow for this thread (with campaigner_id)
            workflow = app_state.get_conversation_workflow(current_user.id, thread_id)

            # Process message
            logger.debug(f"🔄 [Stream] Processing message...")
            result = workflow.process_message(request.message)

            # Extract response message
            messages = result.get("messages", [])
            assistant_message = ""
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "content"):
                    assistant_message = last_message.content

            # If clarification question exists, use that
            if result.get("clarification_question"):
                assistant_message = result["clarification_question"]

            logger.info(f"📤 [Stream] Streaming {len(assistant_message.split())} words")

            # Stream the message word by word
            words = assistant_message.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.05)  # Simulate streaming

            # Send metadata at the end
            metadata = {
                "thread_id": thread_id,
                "needs_clarification": result.get("clarification_needed", False),
                "ready_for_analysis": result.get("ready_for_crew", False),
                "intent": {
                    "platforms": result.get("platforms", []),
                    "metrics": result.get("metrics", []),
                    "date_range_start": result.get("date_range_start"),
                    "date_range_end": result.get("date_range_end"),
                }
            }
            logger.info(f"✅ [Stream] Completed. Ready: {metadata['ready_for_analysis']}")
            yield f"data: {json.dumps({'metadata': metadata})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ [Stream] Error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    app_state: ApplicationState = Depends(get_app_state)
):
    """List all conversation threads."""
    threads = []
    all_workflows = app_state.get_all_threads()

    for thread_id, workflow in all_workflows.items():
        # Get state from workflow if available
        state = workflow.conversation_state if hasattr(workflow, 'conversation_state') else {}
        messages = state.get("messages", [])

        thread = ConversationThread(
            thread_id=thread_id,
            created_at=datetime.now(),  # Fixed deprecation
            last_message_at=datetime.now(),
            message_count=len(messages),
            intent_complete=state.get("is_complete", False),
            platforms=state.get("platforms", [])
        )
        threads.append(thread)

    return ThreadListResponse(
        threads=threads,
        total=len(threads)
    )


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    app_state: ApplicationState = Depends(get_app_state)
):
    """Delete/reset a conversation thread."""
    logger.info(f"🗑️  [Threads] Deleting thread: {thread_id[:8]}...")
    app_state.reset_thread(thread_id)
    return {"message": f"Thread {thread_id} deleted successfully"}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    app_state: ApplicationState = Depends(get_app_state)
):
    """Get conversation thread details."""
    workflows = app_state.get_all_threads()

    if thread_id not in workflows:
        raise HTTPException(status_code=404, detail="Thread not found")

    workflow = workflows[thread_id]
    state = workflow.conversation_state if hasattr(workflow, 'conversation_state') else {}

    return {
        "thread_id": thread_id,
        "state": {
            "platforms": state.get("platforms", []),
            "metrics": state.get("metrics", []),
            "date_range_start": state.get("date_range_start"),
            "date_range_end": state.get("date_range_end"),
            "is_complete": state.get("is_complete", False),
            "ready_for_crew": state.get("ready_for_crew", False),
            "crew_task": state.get("crew_task")
        },
        "messages": [
            {
                "role": msg.type if hasattr(msg, "type") else "unknown",
                "content": msg.content if hasattr(msg, "content") else str(msg)
            }
            for msg in state.get("messages", [])
        ]
    }
