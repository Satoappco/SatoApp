"""
Traces API endpoints for viewing chat history and debugging.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlmodel import Session, select, func, and_, or_
from sqlalchemy import desc, outerjoin

from app.models.chat_traces import ChatTrace, RecordType
from app.config.database import get_session
from app.core.auth import get_current_user
from app.models.users import Campaigner
from app.models.users import Customer

router = APIRouter(prefix="/traces", tags=["traces"])


# Response Schemas
class TraceListItem(BaseModel):
    """Summary of a trace/conversation for list view."""
    thread_id: str
    campaigner_id: int
    campaigner_name: Optional[str]
    customer_id: Optional[int]
    customer_email: Optional[str]
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    message_count: int
    agent_step_count: int
    tool_usage_count: int
    total_tokens: int
    duration_seconds: Optional[float]
    langfuse_trace_url: Optional[str]
    created_at: str
    updated_at: str


class TraceListResponse(BaseModel):
    """Response for trace list endpoint."""
    traces: List[TraceListItem]
    total: int
    page: int
    page_size: int


class TraceDetailResponse(BaseModel):
    """Full trace details including all events."""
    conversation: dict
    messages: List[dict]
    agent_steps: List[dict]
    tool_usages: List[dict]
    crewai_executions: List[dict]


@router.get("", response_model=TraceListResponse)
async def list_traces(
    campaigner_id: Optional[int] = Query(None, description="Filter by campaigner ID"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    status: Optional[str] = Query(None, description="Filter by status (active, completed, error)"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    page: int = Query(1, description="Page number", ge=1),
    page_size: int = Query(20, description="Items per page", ge=1, le=100),
    current_user: Campaigner = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    List all conversation traces with filtering and pagination.

    Returns summary information for each conversation.
    """
    # Build query for conversation records only
    query = select(ChatTrace).where(
        and_(
            ChatTrace.record_type == RecordType.CONVERSATION,
            ChatTrace.created_at >= datetime.utcnow() - timedelta(days=days)
        )
    )

    # Apply filters
    if campaigner_id:
        query = query.where(ChatTrace.campaigner_id == campaigner_id)
    else:
        # Default: show only current user's traces
        query = query.where(ChatTrace.campaigner_id == current_user.id)

    if customer_id:
        query = query.where(ChatTrace.customer_id == customer_id)

    if status:
        # Query JSONB data field
        query = query.where(ChatTrace.data["status"].astext == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # Apply pagination and ordering
    query = query.order_by(desc(ChatTrace.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    conversations = session.exec(query).all()

    # Build response with campaigner and customer names
    traces = []
    for conv in conversations:
        data = conv.data

        # Get campaigner name
        campaigner = session.get(Campaigner, conv.campaigner_id)
        campaigner_name = campaigner.full_name if campaigner else None

        # Get customer email
        customer_email = None
        if conv.customer_id:
            customer = session.get(Customer, conv.customer_id)
            customer_email = customer.email if customer else None

        traces.append(TraceListItem(
            thread_id=conv.thread_id,
            campaigner_id=conv.campaigner_id,
            campaigner_name=campaigner_name,
            customer_id=conv.customer_id,
            customer_email=customer_email,
            status=data.get("status", "unknown"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            message_count=data.get("message_count", 0),
            agent_step_count=data.get("agent_step_count", 0),
            tool_usage_count=data.get("tool_usage_count", 0),
            total_tokens=data.get("total_tokens", 0),
            duration_seconds=data.get("duration_seconds"),
            langfuse_trace_url=conv.langfuse_trace_url,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
            updated_at=conv.updated_at.isoformat() if conv.updated_at else None
        ))

    return TraceListResponse(
        traces=traces,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{thread_id}", response_model=TraceDetailResponse)
async def get_trace_detail(
    thread_id: str,
    current_user: Campaigner = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get full trace details for a specific thread_id.

    Includes all messages, agent steps, tool usages, and CrewAI executions.
    """
    # Get conversation record
    conversation = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.thread_id == thread_id,
                ChatTrace.record_type == RecordType.CONVERSATION
            )
        )
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail=f"Trace not found: {thread_id}")

    # Check access (user can only see their own traces)
    if conversation.campaigner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get messages
    messages = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.thread_id == thread_id,
                ChatTrace.record_type == RecordType.MESSAGE
            )
        ).order_by(ChatTrace.sequence_number)
    ).all()

    # Get agent steps
    agent_steps = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.thread_id == thread_id,
                ChatTrace.record_type == RecordType.AGENT_STEP
            )
        ).order_by(ChatTrace.sequence_number)
    ).all()

    # Get tool usages
    tool_usages = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.thread_id == thread_id,
                ChatTrace.record_type == RecordType.TOOL_USAGE
            )
        ).order_by(ChatTrace.sequence_number)
    ).all()

    # Get CrewAI executions
    crewai_executions = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.thread_id == thread_id,
                ChatTrace.record_type == RecordType.CREWAI_EXECUTION
            )
        ).order_by(ChatTrace.created_at)
    ).all()

    # Get campaigner and customer info
    campaigner = session.get(Campaigner, conversation.campaigner_id)
    campaigner_name = campaigner.full_name if campaigner else None

    customer_email = None
    if conversation.customer_id:
        customer = session.get(Customer, conversation.customer_id)
        customer_email = customer.email if customer else None

    # Build response
    return TraceDetailResponse(
        conversation={
            "id": conversation.id,
            "thread_id": conversation.thread_id,
            "campaigner_id": conversation.campaigner_id,
            "campaigner_name": campaigner_name,
            "customer_id": conversation.customer_id,
            "customer_email": customer_email,
            "langfuse_trace_url": conversation.langfuse_trace_url,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            **conversation.data
        },
        messages=[
            {
                "id": msg.id,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "sequence_number": msg.sequence_number,
                **msg.data
            }
            for msg in messages
        ],
        agent_steps=[
            {
                "id": step.id,
                "created_at": step.created_at.isoformat() if step.created_at else None,
                "sequence_number": step.sequence_number,
                "langfuse_span_id": step.langfuse_span_id,
                **step.data
            }
            for step in agent_steps
        ],
        tool_usages=[
            {
                "id": tool.id,
                "created_at": tool.created_at.isoformat() if tool.created_at else None,
                "sequence_number": tool.sequence_number,
                "langfuse_span_id": tool.langfuse_span_id,
                **tool.data
            }
            for tool in tool_usages
        ],
        crewai_executions=[
            {
                "id": exec.id,
                "session_id": exec.session_id,
                "created_at": exec.created_at.isoformat() if exec.created_at else None,
                **exec.data
            }
            for exec in crewai_executions
        ]
    )


@router.get("/stats/summary")
async def get_trace_stats(
    days: int = Query(7, description="Number of days to analyze", ge=1, le=90),
    current_user: Campaigner = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get summary statistics for traces.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Total conversations
    total_conversations = session.exec(
        select(func.count(ChatTrace.id)).where(
            and_(
                ChatTrace.record_type == RecordType.CONVERSATION,
                ChatTrace.campaigner_id == current_user.id,
                ChatTrace.created_at >= since
            )
        )
    ).one()

    # Conversations by status
    conversations = session.exec(
        select(ChatTrace).where(
            and_(
                ChatTrace.record_type == RecordType.CONVERSATION,
                ChatTrace.campaigner_id == current_user.id,
                ChatTrace.created_at >= since
            )
        )
    ).all()

    status_counts = {}
    total_messages = 0
    total_tokens = 0

    for conv in conversations:
        status = conv.data.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_messages += conv.data.get("message_count", 0)
        total_tokens += conv.data.get("total_tokens", 0)

    return {
        "total_conversations": total_conversations,
        "status_breakdown": status_counts,
        "total_messages": total_messages,
        "total_tokens": total_tokens,
        "period_days": days
    }
