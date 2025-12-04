"""
Centralized service for recording chat traces to database and Langfuse.

This service provides a unified interface for:
- Creating and managing conversations
- Recording messages, agent steps, and tool usages
- Dual recording to both PostgreSQL and Langfuse
- Retrieving conversation history
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlmodel import Session, select
from sqlalchemy import and_

from app.models.conversations import Conversation, Message, AgentStep, ToolUsage
from app.config.langfuse_config import LangfuseConfig
from app.config.database import get_engine

try:
    from langfuse import Langfuse
    from langfuse.client import StatefulTraceClient as LangfuseTrace
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    LangfuseTrace = None


class ChatTraceService:
    """Centralized service for recording chat traces to database and Langfuse."""

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
        return Session(get_engine())

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
    ) -> Tuple[Conversation, Optional[LangfuseTrace]]:
        """
        Create a new conversation with optional Langfuse trace.

        Args:
            thread_id: Unique thread identifier
            campaigner_id: ID of the campaigner (user)
            customer_id: Optional ID of the customer
            metadata: Optional metadata dictionary

        Returns:
            Tuple of (Conversation, Optional[LangfuseTrace])
        """
        session = self._get_session()
        try:
            # Check if conversation already exists
            existing = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if existing:
                # Return existing conversation and get its Langfuse trace
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

            # Create conversation in database
            conversation = Conversation(
                thread_id=thread_id,
                campaigner_id=campaigner_id,
                customer_id=customer_id,
                langfuse_trace_id=langfuse_trace_id,
                langfuse_trace_url=langfuse_trace_url,
                started_at=datetime.now(timezone.utc),
                status="active",
                extra_metadata=metadata or {}
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

    def complete_conversation(
        self,
        thread_id: str,
        status: str = "completed",
        final_intent: Optional[Dict] = None
    ) -> Optional[Conversation]:
        """
        Mark a conversation as completed.

        Args:
            thread_id: Thread identifier
            status: Final status (completed, abandoned, error)
            final_intent: Optional final intent dictionary

        Returns:
            Updated Conversation or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Update conversation
            conversation.status = status
            conversation.completed_at = datetime.now(timezone.utc)

            if final_intent:
                conversation.intent = final_intent

            # Calculate duration
            if conversation.started_at:
                duration = (datetime.now(timezone.utc) - conversation.started_at).total_seconds()
                conversation.duration_seconds = duration

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
                                metadata={"completed_at": datetime.now(timezone.utc).isoformat()}
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

    def get_conversation(self, thread_id: str) -> Optional[Conversation]:
        """
        Get a conversation by thread_id.

        Args:
            thread_id: Thread identifier

        Returns:
            Conversation or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()
            return conversation
        finally:
            self._close_session(session)

    def get_conversation_history(
        self,
        thread_id: str,
        include_messages: bool = True,
        include_steps: bool = False,
        include_tools: bool = False
    ) -> Optional[Dict]:
        """
        Get full conversation history with related data.

        Args:
            thread_id: Thread identifier
            include_messages: Include messages in response
            include_steps: Include agent steps in response
            include_tools: Include tool usages in response

        Returns:
            Dictionary with conversation and related data, or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                return None

            result = {
                "conversation": {
                    "id": conversation.id,
                    "thread_id": conversation.thread_id,
                    "campaigner_id": conversation.campaigner_id,
                    "customer_id": conversation.customer_id,
                    "status": conversation.status,
                    "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
                    "completed_at": conversation.completed_at.isoformat() if conversation.completed_at else None,
                    "intent": conversation.intent,
                    "needs_clarification": conversation.needs_clarification,
                    "ready_for_analysis": conversation.ready_for_analysis,
                    "message_count": conversation.message_count,
                    "agent_step_count": conversation.agent_step_count,
                    "tool_usage_count": conversation.tool_usage_count,
                    "total_tokens": conversation.total_tokens,
                    "duration_seconds": float(conversation.duration_seconds) if conversation.duration_seconds else None,
                    "langfuse_trace_url": conversation.langfuse_trace_url,
                    "extra_metadata": conversation.extra_metadata,
                }
            }

            if include_messages:
                messages = session.exec(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at)
                ).all()
                result["messages"] = [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "model": msg.model,
                        "tokens_used": msg.tokens_used,
                        "latency_ms": msg.latency_ms,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        "extra_metadata": msg.extra_metadata,
                    }
                    for msg in messages
                ]

            if include_steps:
                steps = session.exec(
                    select(AgentStep)
                    .where(AgentStep.conversation_id == conversation.id)
                    .order_by(AgentStep.created_at)
                ).all()
                result["agent_steps"] = [
                    {
                        "id": step.id,
                        "step_type": step.step_type,
                        "agent_name": step.agent_name,
                        "agent_role": step.agent_role,
                        "content": step.content,
                        "task_index": step.task_index,
                        "task_description": step.task_description,
                        "created_at": step.created_at.isoformat() if step.created_at else None,
                        "extra_metadata": step.extra_metadata,
                    }
                    for step in steps
                ]

            if include_tools:
                tools = session.exec(
                    select(ToolUsage)
                    .where(ToolUsage.conversation_id == conversation.id)
                    .order_by(ToolUsage.created_at)
                ).all()
                result["tool_usages"] = [
                    {
                        "id": tool.id,
                        "tool_name": tool.tool_name,
                        "tool_input": tool.tool_input,
                        "tool_output": tool.tool_output,
                        "success": tool.success,
                        "error": tool.error,
                        "latency_ms": tool.latency_ms,
                        "created_at": tool.created_at.isoformat() if tool.created_at else None,
                        "extra_metadata": tool.extra_metadata,
                    }
                    for tool in tools
                ]

            return result

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
    ) -> Optional[Message]:
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
            Created Message or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

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

            # Create message
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
                model=model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                langfuse_generation_id=langfuse_generation_id,
                extra_metadata=metadata or {}
            )

            session.add(message)

            # Update conversation metrics
            conversation.message_count += 1
            if tokens_used:
                conversation.total_tokens += tokens_used

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
    ) -> Optional[AgentStep]:
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
            Created AgentStep or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

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

            # Create agent step
            step = AgentStep(
                conversation_id=conversation.id,
                step_type=step_type,
                content=content,
                agent_name=agent_name,
                agent_role=agent_role,
                task_index=task_index,
                task_description=task_description,
                langfuse_span_id=langfuse_span_id,
                extra_metadata=metadata or {}
            )

            session.add(step)

            # Update conversation metrics
            conversation.agent_step_count += 1

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
        agent_step_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[ToolUsage]:
        """
        Add a tool usage to a conversation.

        Args:
            thread_id: Thread identifier
            tool_name: Name of the tool
            tool_input: Optional tool input (will be converted to string)
            tool_output: Optional tool output (will be converted to string)
            success: Whether the tool call succeeded
            error: Optional error message
            latency_ms: Optional latency in milliseconds
            agent_step_id: Optional agent step ID
            metadata: Optional metadata dictionary

        Returns:
            Created ToolUsage or None if conversation not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            # Convert input/output to strings
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

            # Create tool usage
            tool_usage = ToolUsage(
                conversation_id=conversation.id,
                agent_step_id=agent_step_id,
                tool_name=tool_name,
                tool_input=tool_input_str,
                tool_output=tool_output_str,
                success=success,
                error=error,
                latency_ms=latency_ms,
                langfuse_span_id=langfuse_span_id,
                extra_metadata=metadata or {}
            )

            session.add(tool_usage)

            # Update conversation metrics
            conversation.tool_usage_count += 1

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

    # ===== Update Methods =====

    def update_intent(
        self,
        thread_id: str,
        intent: Dict,
        needs_clarification: bool = False,
        ready_for_analysis: bool = False
    ) -> Optional[Conversation]:
        """
        Update conversation intent and readiness flags.

        Args:
            thread_id: Thread identifier
            intent: Intent dictionary
            needs_clarification: Whether clarification is needed
            ready_for_analysis: Whether ready for analysis

        Returns:
            Updated Conversation or None if not found
        """
        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

            if not conversation:
                print(f"⚠️ Conversation not found: {thread_id}")
                return None

            conversation.intent = intent
            conversation.needs_clarification = needs_clarification
            conversation.ready_for_analysis = ready_for_analysis

            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            print(f"✅ Updated intent: thread_id={thread_id}, ready={ready_for_analysis}")

            return conversation

        except Exception as e:
            session.rollback()
            print(f"❌ Failed to update intent: {e}")
            raise
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

        session = self._get_session()
        try:
            conversation = session.exec(
                select(Conversation).where(Conversation.thread_id == thread_id)
            ).first()

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
                    conversation.langfuse_trace_id = trace.id if hasattr(trace, 'id') else None
                    conversation.langfuse_trace_url = trace.get_trace_url() if hasattr(trace, 'get_trace_url') else None
                    session.add(conversation)
                    session.commit()

                    return trace
            except Exception as e:
                print(f"⚠️ Failed to create Langfuse trace: {e}")
                return None

        finally:
            self._close_session(session)

    def _get_langfuse_trace(self, trace_id: str) -> Optional[LangfuseTrace]:
        """
        Get a Langfuse trace by ID.

        Args:
            trace_id: Langfuse trace ID

        Returns:
            LangfuseTrace or None
        """
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
