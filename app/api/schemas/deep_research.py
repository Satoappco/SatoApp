"""Deep Research API request/response models."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class ResearchLLMConfig(BaseModel):
    """LLM model configuration for different research phases."""
    summarization_model: Optional[str] = Field(
        default="openai:gpt-4o-mini",
        description="Model for summarizing search results"
    )
    research_model: Optional[str] = Field(
        default="openai:gpt-4o",
        description="Model for conducting research and queries"
    )
    compression_model: Optional[str] = Field(
        default="openai:gpt-4o",
        description="Model for compressing and synthesizing information"
    )
    report_model: Optional[str] = Field(
        default="openai:gpt-4o",
        description="Model for generating the final report"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summarization_model": "openai:gpt-4o-mini",
                "research_model": "openai:gpt-4o",
                "compression_model": "openai:gpt-4o",
                "report_model": "anthropic:claude-3-5-sonnet-20241022"
            }
        }


class ResearchRequest(BaseModel):
    """Request to start a deep research session."""
    query: str = Field(..., description="Research question or topic", min_length=1)
    thread_id: Optional[str] = Field(None, description="Link to chat conversation thread")
    customer_id: Optional[int] = Field(None, description="Customer context for the research")
    llm_config: Optional[ResearchLLMConfig] = Field(None, description="LLM model configuration overrides")
    search_provider: Optional[str] = Field(
        default="tavily",
        description="Search provider to use: tavily, anthropic, or mcp"
    )
    research_depth: Optional[str] = Field(
        default="medium",
        description="Research depth: shallow (1-2 iterations), medium (3-5), or deep (6-10)"
    )
    max_iterations: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of search iterations"
    )

    @field_validator('customer_id', mode='before')
    @classmethod
    def coerce_customer_id(cls, v):
        """Convert string customer_id to int if needed."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"customer_id must be an integer, got: {v}")
        return v

    @field_validator('search_provider')
    @classmethod
    def validate_search_provider(cls, v):
        """Validate search provider value."""
        if v and v not in ["tavily", "anthropic", "mcp"]:
            raise ValueError("search_provider must be one of: tavily, anthropic, mcp")
        return v

    @field_validator('research_depth')
    @classmethod
    def validate_research_depth(cls, v):
        """Validate research depth value."""
        if v and v not in ["shallow", "medium", "deep"]:
            raise ValueError("research_depth must be one of: shallow, medium, deep")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the latest trends in AI-powered marketing automation for 2025?",
                "thread_id": "user-123-thread-456",
                "customer_id": 789,
                "search_provider": "tavily",
                "research_depth": "medium",
                "max_iterations": 5
            }
        }


class ResearchSourceInfo(BaseModel):
    """Information about a research source."""
    url: str = Field(..., description="Source URL")
    title: Optional[str] = Field(None, description="Source title")
    relevance_score: Optional[float] = Field(None, description="Relevance score (0-1)")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/ai-marketing-2025",
                "title": "AI Marketing Trends 2025: Complete Guide",
                "relevance_score": 0.92
            }
        }


class ResearchMetadata(BaseModel):
    """Metadata about the research execution."""
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    tokens_used: int = Field(..., description="Total tokens used across all LLM calls")
    steps_completed: int = Field(..., description="Number of research steps completed")
    api_calls_made: int = Field(..., description="Total API calls made")
    langfuse_trace_url: Optional[str] = Field(None, description="Langfuse trace URL for observability")

    class Config:
        json_schema_extra = {
            "example": {
                "execution_time_ms": 45000,
                "tokens_used": 12500,
                "steps_completed": 7,
                "api_calls_made": 15,
                "langfuse_trace_url": "https://cloud.langfuse.com/trace/abc123"
            }
        }


class ResearchResponse(BaseModel):
    """Response from a research request."""
    session_id: str = Field(..., description="Unique research session ID")
    status: str = Field(..., description="Research status: pending, running, completed, error, cancelled")
    query: str = Field(..., description="Original research query")
    report: Optional[str] = Field(None, description="Final research report in markdown format")
    sources: List[ResearchSourceInfo] = Field(default_factory=list, description="Sources used in research")
    metadata: ResearchMetadata = Field(..., description="Research execution metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "res_abc123def456",
                "status": "completed",
                "query": "What are the latest trends in AI-powered marketing automation for 2025?",
                "report": "# AI Marketing Automation Trends 2025\n\n## Executive Summary\n...",
                "sources": [
                    {
                        "url": "https://example.com/ai-marketing",
                        "title": "AI Marketing Guide 2025",
                        "relevance_score": 0.95
                    }
                ],
                "metadata": {
                    "execution_time_ms": 45000,
                    "tokens_used": 12500,
                    "steps_completed": 7,
                    "api_calls_made": 15,
                    "langfuse_trace_url": "https://cloud.langfuse.com/trace/abc123"
                }
            }
        }


class ResearchStepInfo(BaseModel):
    """Information about a research step."""
    step_type: str = Field(..., description="Type of step: planning, search, compression, synthesis, report")
    step_index: int = Field(..., description="Step order within session")
    status: str = Field(..., description="Step status: pending, running, completed, error")
    execution_time_ms: Optional[int] = Field(None, description="Step execution time")
    tokens_used: Optional[int] = Field(None, description="Tokens used in this step")


class ResearchSessionDetail(BaseModel):
    """Detailed information about a research session."""
    session_id: str = Field(..., description="Unique research session ID")
    status: str = Field(..., description="Research status")
    query: str = Field(..., description="Original research query")
    report: Optional[str] = Field(None, description="Final research report")
    sources: List[ResearchSourceInfo] = Field(default_factory=list, description="Research sources")
    steps: List[ResearchStepInfo] = Field(default_factory=list, description="Research steps")
    config: Dict[str, Any] = Field(..., description="Research configuration")
    created_at: str = Field(..., description="Session creation timestamp")
    updated_at: str = Field(..., description="Session last update timestamp")
    metadata: ResearchMetadata = Field(..., description="Research execution metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "res_abc123def456",
                "status": "completed",
                "query": "What are the latest trends in AI-powered marketing automation for 2025?",
                "report": "# AI Marketing Automation Trends 2025\n\n...",
                "sources": [],
                "steps": [
                    {
                        "step_type": "planning",
                        "step_index": 0,
                        "status": "completed",
                        "execution_time_ms": 2000,
                        "tokens_used": 500
                    }
                ],
                "config": {
                    "search_provider": "tavily",
                    "research_depth": "medium",
                    "max_iterations": 5
                },
                "created_at": "2025-12-18T10:00:00Z",
                "updated_at": "2025-12-18T10:05:00Z",
                "metadata": {
                    "execution_time_ms": 45000,
                    "tokens_used": 12500,
                    "steps_completed": 7,
                    "api_calls_made": 15
                }
            }
        }
