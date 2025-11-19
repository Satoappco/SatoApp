"""
Centralized service for recording chat traces using single-table design.

This service provides a unified interface for:
- Creating and managing conversations
- Recording messages, agent steps, and tool usages
- Recording CrewAI execution results
- Dual recording to both PostgreSQL and Langfuse
- Retrieving conversation history

All records stored in single `chat_traces` table with type-specific JSON data.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlmodel import Session, select, func
from sqlalchemy import and_, or_

from app.models.chat_traces import ChatTrace, RecordType
from app.config.langfuse_config import LangfuseConfig
from app.config.database import engine

try:
    from langfuse import Langfuse
    from langfuse.client import StatefulTraceClient as LangfuseTrace
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    LangfuseTrace = None


class ChatTraceService:
    """Centralized service for recording chat traces using single-table design."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize ChatTraceService.

        Args:
            session: Optional SQLModel session. If not provided, will create a new session for each operation.
        """
        self.session = session
        self._should_close_session = session is None

    def _get_session(self) -> Session:
        """Get or create a database session."""
        if self.session:
            return self.session
        return Session(engine)

    def _close_session(self, session: Session):
        """Close session if it was created internally."""
        if self._should_close_session and session:
            session.close()

    # ===== Conversation Management =====

    def create_conversation(
        self,
        thread_id: str,
        campaigner_id: int,
        customer_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[ChatTrace, Optional[LangfuseTrace]]:
        """
        Create a new conversation record with optional Langfuse trace.

        Args:
            thread_id: Unique thread identifier
            campaigner_id: ID of the campaigner (user)
            customer_id: Optional ID of the customer
            metadata: Optional metadata dictionary

        Returns:
            Tuple of (ChatTrace conversation record, Optional[LangfuseTrace])
        """
        session = self._get_session()
        try:
            # Check if conversation already exists
            existing = session.exec(
                select(ChatTrace).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.CONVERSATION
                    )
                )
            ).first()

            if existing:
                langfuse_trace = self._get_langfuse_trace(existing.langfuse_trace_id) if existing.langfuse_trace_id else None
                return existing, langfuse_trace

            # Create Langfuse trace
            langfuse_trace = None
            langfuse_trace_id = None
            langfuse_trace_url = None

            if LANGFUSE_AVAILABLE:
                try:
                    langfuse = LangfuseConfig.get_client()
                    if langfuse:
                        langfuse_trace = langfuse.trace(
                            name="chat_conversation",
                            session_id=thread_id,
                            user_id=str(campaigner_id),
                            metadata={
                                "thread_id": thread_id,
                                "campaigner_id": campaigner_id,
                                "customer_id": customer_id,
                                **(metadata or {})
                            }
                        )
                        langfuse_trace_id = langfuse_trace.id if hasattr(langfuse_trace, 'id') else None
                        langfuse_trace_url = langfuse_trace.get_trace_url() if hasattr(langfuse_trace, 'get_trace_url') else None
                except Exception as e:
                    print(f"⚠️ Failed to create Langfuse trace: {e}")

            # Create conversation record
            conversation_data = {
                "status": "active",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "intent": None,
                "needs_clarification": True,
                "ready_for_analysis": False,
                "message_count": 0,
                "agent_step_count": 0,
                "tool_usage_count": 0,
                "total_tokens": 0,
                "duration_seconds": None,
                "extra_metadata": metadata or {}
            }

            conversation = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.CONVERSATION,
                campaigner_id=campaigner_id,
                customer_id=customer_id,
                data=conversation_data,
                langfuse_trace_id=langfuse_trace_id,
                langfuse_trace_url=langfuse_trace_url
            )

            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            print(f"✅ Created conversation: thread_id={thread_id}, id={conversation.id}")

            return conversation, langfuse_trace

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to create conversation: {e}")
            raise
        finally:
            self._close_session(session)

    def get_conversation(self, thread_id: str, session: Optional[Session] = None) -> Optional[ChatTrace]:
        """
        Get conversation record by thread_id.

        Args:
            thread_id: Thread identifier
            session: Optional session to use (if not provided, creates new one)

        Returns:
            ChatTrace conversation record or None if not found
        """
        _session = session or self._get_session()
        should_close = session is None and self._should_close_session

        try:
            conversation = _session.exec(
                select(ChatTrace).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.CONVERSATION
                    )
                )
            ).first()
            return conversation
        finally:
            if should_close:
                _session.close()

    def update_conversation_data(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> Optional[ChatTrace]:
        """
        Update conversation data fields.

        Args:
            thread_id: Thread identifier
            updates: Dictionary of fields to update in data JSON

        Returns:
            Updated ChatTrace or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(ChatTrace).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.CONVERSATION
                    )
                )
            ).first()

            if not conversation:
                return None

            # Update data fields
            conversation.data.update(updates)
            # Mark as updated
            conversation.updated_at = datetime.utcnow()

            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            return conversation

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to update conversation: {e}")
            raise
        finally:
            self._close_session(session)

    def complete_conversation(
        self,
        thread_id: str,
        status: str = "completed",
        final_intent: Optional[Dict] = None
    ) -> Optional[ChatTrace]:
        """
        Mark a conversation as completed.

        Args:
            thread_id: Thread identifier
            status: Final status (completed, abandoned, error)
            final_intent: Optional final intent dictionary

        Returns:
            Updated ChatTrace or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(ChatTrace).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.CONVERSATION
                    )
                )
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Calculate duration
            started_at_str = conversation.data.get("started_at")
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str)
                duration = (datetime.utcnow() - started_at).total_seconds()
                conversation.data["duration_seconds"] = duration

            # Update status
            conversation.data["status"] = status
            conversation.data["completed_at"] = datetime.utcnow().isoformat()

            if final_intent:
                conversation.data["intent"] = final_intent

            conversation.updated_at = datetime.utcnow()

            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            # Update Langfuse trace
            if LANGFUSE_AVAILABLE and conversation.langfuse_trace_id:
                try:
                    langfuse = LangfuseConfig.get_client()
                    if langfuse:
                        trace = self._get_langfuse_trace(conversation.langfuse_trace_id)
                        if trace:
                            trace.update(
                                output={"status": status, "final_intent": final_intent},
                                metadata={"completed_at": datetime.utcnow().isoformat()}
                            )
                except Exception as e:
                    print(f"⚠️ Failed to update Langfuse trace: {e}")

            print(f"✅ Completed conversation: thread_id={thread_id}, status={status}")

            return conversation

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to complete conversation: {e}")
            raise
        finally:
            self._close_session(session)

    # ===== Message Recording =====

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[ChatTrace]:
        """
        Add a message to a conversation.

        Args:
            thread_id: Thread identifier
            role: Message role (user, assistant, system, tool)
            content: Message content
            model: Optional model name
            tokens_used: Optional token count
            latency_ms: Optional latency in milliseconds
            metadata: Optional metadata dictionary

        Returns:
            Created ChatTrace message record or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = self.get_conversation(thread_id, session=session)
            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Get sequence number (count of messages so far)
            message_count = session.exec(
                select(func.count(ChatTrace.id)).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.MESSAGE
                    )
                )
            ).one()

            # Create Langfuse generation if this is an assistant message
            langfuse_generation_id = None
            if LANGFUSE_AVAILABLE and role == "assistant" and conversation.langfuse_trace_id:
                try:
                    langfuse = LangfuseConfig.get_client()
                    if langfuse:
                        trace = self._get_langfuse_trace(conversation.langfuse_trace_id)
                        if trace:
                            generation = trace.generation(
                                name="assistant_message",
                                input=content,
                                model=model,
                                usage={"total": tokens_used} if tokens_used else None,
                                metadata=metadata or {}
                            )
                            langfuse_generation_id = generation.id if hasattr(generation, 'id') else None
                except Exception as e:
                    print(f"⚠️ Failed to create Langfuse generation: {e}")

            # Create message record
            message_data = {
                "role": role,
                "content": content,
                "model": model,
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
                "langfuse_generation_id": langfuse_generation_id,
                "extra_metadata": metadata or {}
            }

            message = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.MESSAGE,
                campaigner_id=conversation.campaigner_id,
                customer_id=conversation.customer_id,
                data=message_data,
                sequence_number=message_count
            )

            session.add(message)

            # Update conversation metrics
            conversation.data["message_count"] += 1
            if tokens_used:
                conversation.data["total_tokens"] += tokens_used
            conversation.updated_at = datetime.utcnow()

            session.add(conversation)
            session.commit()
            session.refresh(message)

            print(f"✅ Added message: thread_id={thread_id}, role={role}, id={message.id}")

            return message

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to add message: {e}")
            raise
        finally:
            self._close_session(session)

    # ===== Agent Step Recording =====

    def add_agent_step(
        self,
        thread_id: str,
        step_type: str,
        content: str,
        agent_name: Optional[str] = None,
        agent_role: Optional[str] = None,
        task_index: Optional[int] = None,
        task_description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[ChatTrace]:
        """
        Add an agent step to a conversation.

        Args:
            thread_id: Thread identifier
            step_type: Step type (thought, action, observation, task_start, task_complete)
            content: Step content
            agent_name: Optional agent name
            agent_role: Optional agent role
            task_index: Optional task index (for CrewAI)
            task_description: Optional task description
            metadata: Optional metadata dictionary

        Returns:
            Created ChatTrace agent_step record or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = self.get_conversation(thread_id, session=session)
            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Get sequence number
            step_count = session.exec(
                select(func.count(ChatTrace.id)).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.AGENT_STEP
                    )
                )
            ).one()

            # Create Langfuse span
            langfuse_span_id = None
            if LANGFUSE_AVAILABLE and conversation.langfuse_trace_id:
                try:
                    langfuse = LangfuseConfig.get_client()
                    if langfuse:
                        trace = self._get_langfuse_trace(conversation.langfuse_trace_id)
                        if trace:
                            span = trace.span(
                                name=f"{step_type}_{agent_name or 'agent'}",
                                input={"step_type": step_type, "content": content},
                                metadata={
                                    "agent_name": agent_name,
                                    "agent_role": agent_role,
                                    "task_index": task_index,
                                    **(metadata or {})
                                }
                            )
                            langfuse_span_id = span.id if hasattr(span, 'id') else None
                except Exception as e:
                    print(f"⚠️ Failed to create Langfuse span: {e}")

            # Create agent step record
            step_data = {
                "step_type": step_type,
                "content": content,
                "agent_name": agent_name,
                "agent_role": agent_role,
                "task_index": task_index,
                "task_description": task_description,
                "extra_metadata": metadata or {}
            }

            step = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.AGENT_STEP,
                campaigner_id=conversation.campaigner_id,
                customer_id=conversation.customer_id,
                data=step_data,
                langfuse_span_id=langfuse_span_id,
                sequence_number=step_count
            )

            session.add(step)

            # Update conversation metrics
            conversation.data["agent_step_count"] += 1
            conversation.updated_at = datetime.utcnow()

            session.add(conversation)
            session.commit()
            session.refresh(step)

            print(f"✅ Added agent step: thread_id={thread_id}, type={step_type}, id={step.id}")

            return step

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to add agent step: {e}")
            raise
        finally:
            self._close_session(session)

    # ===== Tool Usage Recording =====

    def add_tool_usage(
        self,
        thread_id: str,
        tool_name: str,
        tool_input: Optional[Any] = None,
        tool_output: Optional[Any] = None,
        success: bool = True,
        error: Optional[str] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[ChatTrace]:
        """
        Add a tool usage to a conversation.

        Args:
            thread_id: Thread identifier
            tool_name: Name of the tool
            tool_input: Optional tool input
            tool_output: Optional tool output
            success: Whether the tool call succeeded
            error: Optional error message
            latency_ms: Optional latency in milliseconds
            metadata: Optional metadata dictionary

        Returns:
            Created ChatTrace tool_usage record or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = self.get_conversation(thread_id, session=session)
            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Get sequence number
            tool_count = session.exec(
                select(func.count(ChatTrace.id)).where(
                    and_(
                        ChatTrace.thread_id == thread_id,
                        ChatTrace.record_type == RecordType.TOOL_USAGE
                    )
                )
            ).one()

            # Convert input/output to strings if needed
            tool_input_str = str(tool_input) if tool_input is not None else None
            tool_output_str = str(tool_output) if tool_output is not None else None

            # Create Langfuse span
            langfuse_span_id = None
            if LANGFUSE_AVAILABLE and conversation.langfuse_trace_id:
                try:
                    langfuse = LangfuseConfig.get_client()
                    if langfuse:
                        trace = self._get_langfuse_trace(conversation.langfuse_trace_id)
                        if trace:
                            span = trace.span(
                                name=f"tool_{tool_name}",
                                input={"tool_input": tool_input_str},
                                output={"tool_output": tool_output_str, "success": success},
                                metadata={
                                    "tool_name": tool_name,
                                    "error": error,
                                    "latency_ms": latency_ms,
                                    **(metadata or {})
                                }
                            )
                            langfuse_span_id = span.id if hasattr(span, 'id') else None
                except Exception as e:
                    print(f"⚠️ Failed to create Langfuse span: {e}")

            # Create tool usage record
            tool_data = {
                "tool_name": tool_name,
                "tool_input": tool_input_str,
                "tool_output": tool_output_str,
                "success": success,
                "error": error,
                "latency_ms": latency_ms,
                "extra_metadata": metadata or {}
            }

            tool_usage = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.TOOL_USAGE,
                campaigner_id=conversation.campaigner_id,
                customer_id=conversation.customer_id,
                data=tool_data,
                langfuse_span_id=langfuse_span_id,
                sequence_number=tool_count
            )

            session.add(tool_usage)

            # Update conversation metrics
            conversation.data["tool_usage_count"] += 1
            conversation.updated_at = datetime.utcnow()

            session.add(conversation)
            session.commit()
            session.refresh(tool_usage)

            print(f"✅ Added tool usage: thread_id={thread_id}, tool={tool_name}, id={tool_usage.id}")

            return tool_usage

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to add tool usage: {e}")
            raise
        finally:
            self._close_session(session)

    # ===== CrewAI Execution Recording =====

    def record_crewai_execution(
        self,
        thread_id: str,
        user_intent: str,
        original_query: str,
        crewai_input_prompt: str,
        master_answer: str,
        crewai_log: str,
        total_execution_time_ms: int,
        timing_breakdown: Dict,
        agents_used: List[str],
        tools_used: List[str],
        success: bool = True,
        error_message: Optional[str] = None,
        analysis_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[ChatTrace]:
        """
        Record a CrewAI execution result.

        This replaces the customer_logs table functionality.

        Args:
            thread_id: Thread identifier
            user_intent: User's intent category
            original_query: User's original query
            crewai_input_prompt: Prompt sent to CrewAI
            master_answer: Final answer from CrewAI
            crewai_log: Execution log
            total_execution_time_ms: Total execution time
            timing_breakdown: Detailed timing data
            agents_used: List of agents used
            tools_used: List of tools used
            success: Whether execution succeeded
            error_message: Optional error message
            analysis_id: Optional analysis ID
            session_id: Optional session ID

        Returns:
            Created ChatTrace crewai_execution record
        """
        session = self._get_session()
        try:
            conversation = self.get_conversation(thread_id, session=session)
            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Create CrewAI execution record
            crewai_data = {
                "user_intent": user_intent,
                "original_query": original_query,
                "crewai_input_prompt": crewai_input_prompt,
                "master_answer": master_answer,
                "crewai_log": crewai_log,
                "total_execution_time_ms": total_execution_time_ms,
                "timing_breakdown": timing_breakdown,
                "agents_used": agents_used,
                "tools_used": tools_used,
                "success": success,
                "error_message": error_message,
                "analysis_id": analysis_id
            }

            crewai_record = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.CREWAI_EXECUTION,
                campaigner_id=conversation.campaigner_id,
                customer_id=conversation.customer_id,
                data=crewai_data,
                session_id=session_id or thread_id
            )

            session.add(crewai_record)
            session.commit()
            session.refresh(crewai_record)

            print(f"✅ Recorded CrewAI execution: thread_id={thread_id}, id={crewai_record.id}")

            return crewai_record

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to record CrewAI execution: {e}")
            raise
        finally:
            self._close_session(session)

    # ===== Update Methods =====

    def update_intent(
        self,
        thread_id: str,
        intent: Dict,
        needs_clarification: bool = False,
        ready_for_analysis: bool = False
    ) -> Optional[ChatTrace]:
        """
        Update conversation intent and readiness flags.

        Args:
            thread_id: Thread identifier
            intent: Intent dictionary
            needs_clarification: Whether clarification is needed
            ready_for_analysis: Whether ready for analysis

        Returns:
            Updated ChatTrace or None if not found
        """
        return self.update_conversation_data(
            thread_id,
            {
                "intent": intent,
                "needs_clarification": needs_clarification,
                "ready_for_analysis": ready_for_analysis
            }
        )

    # ===== Query Methods =====

    def get_conversation_history(
        self,
        thread_id: str,
        include_messages: bool = True,
        include_steps: bool = False,
        include_tools: bool = False,
        include_crewai: bool = False
    ) -> Optional[Dict]:
        """
        Get full conversation history with related data.

        Args:
            thread_id: Thread identifier
            include_messages: Include messages in response
            include_steps: Include agent steps in response
            include_tools: Include tool usages in response
            include_crewai: Include CrewAI executions in response

        Returns:
            Dictionary with conversation and related data, or None if not found
        """
        session = self._get_session()
        try:
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
                return None

            result = {
                "conversation": {
                    "id": conversation.id,
                    "thread_id": conversation.thread_id,
                    "campaigner_id": conversation.campaigner_id,
                    "customer_id": conversation.customer_id,
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                    "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                    "langfuse_trace_url": conversation.langfuse_trace_url,
                    **conversation.data  # Include all data fields
                }
            }

            if include_messages:
                messages = session.exec(
                    select(ChatTrace).where(
                        and_(
                            ChatTrace.thread_id == thread_id,
                            ChatTrace.record_type == RecordType.MESSAGE
                        )
                    ).order_by(ChatTrace.sequence_number)
                ).all()
                result["messages"] = [
                    {
                        "id": msg.id,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        **msg.data  # Include all data fields
                    }
                    for msg in messages
                ]

            if include_steps:
                steps = session.exec(
                    select(ChatTrace).where(
                        and_(
                            ChatTrace.thread_id == thread_id,
                            ChatTrace.record_type == RecordType.AGENT_STEP
                        )
                    ).order_by(ChatTrace.sequence_number)
                ).all()
                result["agent_steps"] = [
                    {
                        "id": step.id,
                        "created_at": step.created_at.isoformat() if step.created_at else None,
                        "langfuse_span_id": step.langfuse_span_id,
                        **step.data
                    }
                    for step in steps
                ]

            if include_tools:
                tools = session.exec(
                    select(ChatTrace).where(
                        and_(
                            ChatTrace.thread_id == thread_id,
                            ChatTrace.record_type == RecordType.TOOL_USAGE
                        )
                    ).order_by(ChatTrace.sequence_number)
                ).all()
                result["tool_usages"] = [
                    {
                        "id": tool.id,
                        "created_at": tool.created_at.isoformat() if tool.created_at else None,
                        "langfuse_span_id": tool.langfuse_span_id,
                        **tool.data
                    }
                    for tool in tools
                ]

            if include_crewai:
                crewai_records = session.exec(
                    select(ChatTrace).where(
                        and_(
                            ChatTrace.thread_id == thread_id,
                            ChatTrace.record_type == RecordType.CREWAI_EXECUTION
                        )
                    ).order_by(ChatTrace.created_at)
                ).all()
                result["crewai_executions"] = [
                    {
                        "id": record.id,
                        "session_id": record.session_id,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        **record.data
                    }
                    for record in crewai_records
                ]

            return result

        finally:
            self._close_session(session)

    # ===== Langfuse Integration =====

    def get_or_create_langfuse_trace(
        self,
        thread_id: str
    ) -> Optional[LangfuseTrace]:
        """
        Get or create a Langfuse trace for a conversation.

        Args:
            thread_id: Thread identifier

        Returns:
            LangfuseTrace or None if Langfuse not available or conversation not found
        """
        if not LANGFUSE_AVAILABLE:
            return None

        # Don't pass session here since we might need to update the conversation
        conversation = self.get_conversation(thread_id)
        if not conversation:
            return None

        if conversation.langfuse_trace_id:
            return self._get_langfuse_trace(conversation.langfuse_trace_id)

        # Create new trace
        try:
            langfuse = LangfuseConfig.get_client()
            if langfuse:
                trace = langfuse.trace(
                    name="chat_conversation",
                    session_id=thread_id,
                    user_id=str(conversation.campaigner_id),
                    metadata={"thread_id": thread_id}
                )

                # Update conversation with trace info
                session = self._get_session()
                try:
                    conversation.langfuse_trace_id = trace.id if hasattr(trace, 'id') else None
                    conversation.langfuse_trace_url = trace.get_trace_url() if hasattr(trace, 'get_trace_url') else None
                    session.add(conversation)
                    session.commit()
                finally:
                    self._close_session(session)

                return trace
        except Exception as e:
            print(f"⚠️ Failed to create Langfuse trace: {e}")
            return None

    def _get_langfuse_trace(self, trace_id: str) -> Optional[LangfuseTrace]:
        """Get a Langfuse trace by ID."""
        if not LANGFUSE_AVAILABLE:
            return None

        try:
            langfuse = LangfuseConfig.get_client()
            if langfuse and hasattr(langfuse, 'get_trace'):
                return langfuse.get_trace(trace_id)
        except Exception as e:
            print(f"⚠️ Failed to get Langfuse trace: {e}")

        return None

    def flush_langfuse(self):
        """Flush pending Langfuse traces."""
        if not LANGFUSE_AVAILABLE:
            return

        try:
            langfuse = LangfuseConfig.get_client()
            if langfuse and hasattr(langfuse, 'flush'):
                langfuse.flush()
                print("✅ Flushed Langfuse traces")
        except Exception as e:
            print(f"⚠️ Failed to flush Langfuse: {e}")
