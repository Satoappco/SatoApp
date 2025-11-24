"""Chat/conversation endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from typing import List
from datetime import datetime
import uuid
import json
import logging

from app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationThread,
    ThreadListResponse
)
from app.api.dependencies import get_app_state, ApplicationState
from app.core.auth import get_current_user
from app.services.chat_trace_service import ChatTraceService

try:
    from langfuse import propagate_attributes
except ImportError:
    propagate_attributes = None

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# @router.api_route("", methods=["POST"])
# async def debug_request(request: Request):
#     data = {
#         "method": request.method,
#         "url": str(request.url),
#         "query_params": dict(request.query_params),  # URL parameters (?a=1&b=2)
#         "headers": dict(request.headers),
#         "cookies": request.cookies,
#         "client": request.client.host,
#     }

#     # Body can be JSON, form, or raw data
#     body = await request.body()  # Raw bytes
#     try:
#         data["json"] = await request.json()  # Parsed JSON (if valid)
#     except:
#         data["json"] = None

#     data["body_raw"] = body.decode("utf-8", errors="ignore")
#     logger.debug(f"🔍 [Debug Request] Data: {data}")
#     return JSONResponse(data)

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
    # Initialize ChatTraceService
    trace_service = ChatTraceService()

    # Generate thread ID if not provided
    thread_id = request.thread_id or str(uuid.uuid4())
    logger.info(f"💬 [Chat] Thread: {thread_id[:8]}... | Message: '{request.message[:50]}...'")

    # Parse customer_id if provided
    customer_id = None
    if request.customer_id:
        try:
            customer_id = int(request.customer_id)
        except (ValueError, TypeError):
            logger.warning(f"⚠️  Invalid customer_id format: {request.customer_id}")

    # Create conversation with ChatTraceService (includes Langfuse trace)
    conversation, trace = trace_service.create_conversation(
        thread_id=thread_id,
        campaigner_id=current_user.id,
        customer_id=customer_id,
        metadata={
            "campaigner_name": current_user.full_name,
            "timestamp": datetime.now().isoformat()
        }
    )

    try:
        # Add user message to trace
        user_message_record = trace_service.add_message(
            thread_id=thread_id,
            role="user",
            content=request.message
        )
        user_message_id = user_message_record.id if user_message_record else None

        # Get conversation workflow for this thread (with campaigner_id)
        logger.debug(f"📋 [Chat] Getting workflow for thread: {thread_id} | Campaigner: {current_user.full_name} (ID: {current_user.id}) | Customer: {request.customer_id}")

        workflow = app_state.get_conversation_workflow(current_user, thread_id, customer_id)

        # Most likely never come here because of get_current_user requires msg len >= 1
        if not request.message.strip():
            # Return chat intialization response without processing
            logger.info(f"ℹ️  [Chat] Empty message received, returning initialization response.")
            return ChatResponse(
                message="",
                thread_id=thread_id,
                needs_clarification=False,
                ready_for_analysis=False,
                intent=None
            )

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

        # Add assistant message to trace
        assistant_message_record = trace_service.add_message(
            thread_id=thread_id,
            role="assistant",
            content=assistant_message or "I'm processing your request..."
        )
        assistant_message_id = assistant_message_record.id if assistant_message_record else None

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

        # Update conversation intent in trace
        trace_service.update_intent(
            thread_id=thread_id,
            intent=intent,
            needs_clarification=needs_clarification,
            ready_for_analysis=ready_for_analysis
        )

        # Complete conversation if ready for analysis
        if ready_for_analysis:
            trace_service.complete_conversation(
                thread_id=thread_id,
                status="completed",
                final_intent=intent
            )

        # Flush Langfuse traces
        trace_service.flush_langfuse()

        response = ChatResponse(
            message=assistant_message or "I'm processing your request...",
            thread_id=thread_id,
            needs_clarification=needs_clarification,
            ready_for_analysis=ready_for_analysis,
            intent=intent if any(intent.values()) else None,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id
        )

        return response

    except Exception as e:
        logger.error(f"❌ [Chat] Error processing chat: {str(e)}", exc_info=True)

        # Complete conversation with error status
        try:
            trace_service.complete_conversation(
                thread_id=thread_id,
                status="error"
            )
            trace_service.flush_langfuse()
        except Exception as trace_error:
            logger.warning(f"⚠️  [Chat] Failed to update trace with error: {trace_error}")

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
        trace_service = None
        thread_id = None
        try:
            # Initialize ChatTraceService
            trace_service = ChatTraceService()

            # Generate thread ID if not provided
            thread_id = request.thread_id or str(uuid.uuid4())
            logger.info(f"📡 [Stream] Thread: {thread_id[:8]}... | Message: '{request.message[:50]}...'")

            # # Parse customer_id if provided
            # customer_id = None
            # if request.customer_id:
            #     try:
            #         customer_id = int(request.customer_id)
            #     except (ValueError, TypeError):
            #         logger.warning(f"⚠️  Invalid customer_id format: {request.customer_id}")

            # Create conversation with ChatTraceService
            conversation, trace = trace_service.create_conversation(
                thread_id=thread_id,
                campaigner_id=current_user.id,
                customer_id=customer_id,
                metadata={
                    "campaigner_name": current_user.full_name,
                    "timestamp": datetime.now().isoformat(),
                    "streaming": True
                }
            )

            # Add user message to trace
            user_message_record = trace_service.add_message(
                thread_id=thread_id,
                role="user",
                content=request.message
            )
            user_message_id = user_message_record.id if user_message_record else None

            # Get conversation workflow for this thread (with campaigner_id and customer_id)
            workflow = app_state.get_conversation_workflow(current_user, thread_id) #, customer_id)
            customer_id = workflow.customer_id

            # Stream message through workflow
            logger.debug(f"📡 [Stream] Starting real-time streaming...")

            full_response = ""
            final_metadata = None

            async for chunk in workflow.stream_message(request.message):
                if chunk.get("type") == "content":
                    # Stream content chunk (character)
                    char = chunk.get("chunk", "")
                    full_response += char
                    yield f"data: {json.dumps({'chunk': char})}\n\n"

                #TODO: Why is that?
                elif chunk.get("type") == "metadata":
                    # Final metadata with state
                    final_metadata = {
                        "thread_id": thread_id,
                        "user_message_id" : user_message_id,
                        "needs_clarification": chunk.get("needs_clarification", False),
                        "ready_for_analysis": chunk.get("ready_for_crew", False),
                        "intent": {
                            "platforms": chunk.get("platforms", []),
                            "metrics": chunk.get("metrics", []),
                            "date_range_start": chunk.get("date_range_start"),
                            "date_range_end": chunk.get("date_range_end"),
                        }
                    }
                    logger.info(f"✅ [Stream] Completed. Ready: {final_metadata['ready_for_analysis']}")
                    yield f"data: {json.dumps({'metadata': final_metadata})}\n\n"

            # Add assistant message to trace after streaming completes
            assistant_message_record = trace_service.add_message(
                thread_id=thread_id,
                role="assistant",
                content=full_response or "I'm processing your request..."
            )
            assistant_message_id = assistant_message_record.id if assistant_message_record else None

            # Update conversation intent if we have final metadata
            if final_metadata:
                # Add message IDs to final metadata
                final_metadata["assistant_message_id"] = assistant_message_id

                trace_service.update_intent(
                    thread_id=thread_id,
                    intent=final_metadata["intent"],
                    needs_clarification=final_metadata["needs_clarification"],
                    ready_for_analysis=final_metadata["ready_for_analysis"]
                )

                # Complete conversation if ready for analysis
                if final_metadata["ready_for_analysis"]:
                    trace_service.complete_conversation(
                        thread_id=thread_id,
                        status="completed",
                        final_intent=final_metadata["intent"]
                    )

                # Send final metadata with message IDs
                yield f"data: {json.dumps({'message_ids': {'user_message_id': user_message_id, 'assistant_message_id': assistant_message_id}})}\n\n"

            # Flush Langfuse traces
            trace_service.flush_langfuse()

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ [Stream] Error: {str(e)}", exc_info=True)

            # Complete conversation with error status
            if trace_service and thread_id:
                try:
                    trace_service.complete_conversation(
                        thread_id=thread_id,
                        status="error"
                    )
                    trace_service.flush_langfuse()
                except Exception as trace_error:
                    logger.warning(f"⚠️  [Stream] Failed to update trace with error: {trace_error}")

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
