"""
Research Engine - Wrapper for open_deep_research

This module wraps the open_deep_research LangGraph workflow to provide
both synchronous and streaming research execution.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator, List

# Add open_deep_research to Python path
odr_path = Path(__file__).parent / "src" / "open_deep_research" / "src"
if str(odr_path) not in sys.path:
    sys.path.insert(0, str(odr_path))

# Import open_deep_research components
from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration, SearchAPI
from langchain_core.messages import HumanMessage


class ResearchEngine:
    """Wrapper around open_deep_research LangGraph workflow."""

    def __init__(self):
        """Initialize the research engine."""
        print("[ResearchEngine] Initializing with open_deep_research...")

        # The deep_researcher is already compiled
        self.graph = deep_researcher

        print("[ResearchEngine] Initialized successfully")

    async def execute_research(
        self,
        query: str,
        llm_config: Optional[Dict[str, str]] = None,
        search_provider: str = "tavily",
        max_iterations: int = 5,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Execute research synchronously.

        Args:
            query: Research question
            llm_config: LLM model configuration
            search_provider: Search provider (tavily, anthropic, openai)
            max_iterations: Maximum search iterations
            streaming: Whether to stream results

        Returns:
            Research result dictionary
        """
        start_time = time.time()

        try:
            print(f"[ResearchEngine] Executing research: {query[:100]}...")
            print(f"[ResearchEngine] Config: provider={search_provider}, iterations={max_iterations}")

            # Build Configuration object
            config = self._build_configuration(llm_config, search_provider, max_iterations)

            # Invoke the graph
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config={"configurable": config.model_dump()}
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Extract final report
            final_report = result.get("final_report", "")
            if not final_report:
                # Fallback: try to extract from messages
                messages = result.get("messages", [])
                if messages:
                    final_report = str(messages[-1].content)

            # Extract sources from notes and raw_notes
            sources = self._extract_sources(result)

            # Count steps from research iterations
            steps_completed = result.get("research_iterations", 0) + 3  # +3 for planning, compression, report

            return {
                "success": True,
                "report": final_report,
                "sources": sources,
                "execution_time_ms": execution_time_ms,
                "tokens_used": self._estimate_tokens(result),
                "steps_completed": steps_completed
            }

        except Exception as e:
            print(f"[ResearchEngine] Error: {e}")
            import traceback
            traceback.print_exc()

            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "tokens_used": 0,
                "steps_completed": 0
            }

    async def execute_research_stream(
        self,
        query: str,
        llm_config: Optional[Dict[str, str]] = None,
        search_provider: str = "tavily",
        max_iterations: int = 5
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute research with streaming progress updates.

        Args:
            query: Research question
            llm_config: LLM model configuration
            search_provider: Search provider
            max_iterations: Maximum search iterations

        Yields:
            Progress events as dictionaries
        """
        start_time = time.time()
        steps_completed = 0

        try:
            print(f"[ResearchEngine] Streaming research: {query[:100]}...")

            # Build Configuration object
            config = self._build_configuration(llm_config, search_provider, max_iterations)

            # Initial progress
            yield {
                "type": "progress",
                "message": "Starting research workflow...",
                "phase": "initialization",
                "progress_percent": 5
            }

            # Stream events from the graph
            async for event in self.graph.astream_events(
                {"messages": [HumanMessage(content=query)]},
                config={"configurable": config.model_dump()},
                version="v2"
            ):
                # Parse event and yield appropriate updates
                parsed_event = self._parse_stream_event(event)
                if parsed_event:
                    yield parsed_event
                    if parsed_event.get("type") == "step_complete":
                        steps_completed += 1

            # Get final state
            final_result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config={"configurable": config.model_dump()}
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Extract final report
            final_report = final_result.get("final_report", "")
            if not final_report:
                messages = final_result.get("messages", [])
                if messages:
                    final_report = str(messages[-1].content)

            # Extract sources
            sources = self._extract_sources(final_result)

            # Complete event
            yield {
                "type": "complete",
                "report": final_report,
                "sources": sources,
                "execution_time_ms": execution_time_ms,
                "tokens_used": self._estimate_tokens(final_result),
                "steps_completed": steps_completed
            }

        except Exception as e:
            print(f"[ResearchEngine] Streaming error: {e}")
            import traceback
            traceback.print_exc()

            execution_time_ms = int((time.time() - start_time) * 1000)
            yield {
                "type": "error",
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }

    def _build_configuration(
        self,
        llm_config: Optional[Dict[str, str]],
        search_provider: str,
        max_iterations: int
    ) -> Configuration:
        """Build Configuration object for open_deep_research."""
        # Default models from environment or config
        default_summarization = os.getenv("DEEP_RESEARCH_SUMMARIZATION_MODEL", "openai:gpt-4o-mini")
        default_research = os.getenv("DEEP_RESEARCH_DEFAULT_MODEL", "openai:gpt-4o")

        # Override with llm_config if provided
        if llm_config:
            summarization_model = llm_config.get("summarization_model", default_summarization)
            research_model = llm_config.get("research_model", default_research)
            compression_model = llm_config.get("compression_model", default_research)
            report_model = llm_config.get("report_model", default_research)
        else:
            summarization_model = default_summarization
            research_model = default_research
            compression_model = default_research
            report_model = default_research

        # Map search provider string to SearchAPI enum
        try:
            search_api = SearchAPI(search_provider.lower())
        except ValueError:
            print(f"[ResearchEngine] Unknown search provider: {search_provider}, defaulting to tavily")
            search_api = SearchAPI.TAVILY

        # Build configuration
        config = Configuration(
            search_api=search_api,
            max_researcher_iterations=max_iterations,
            summarization_model=summarization_model,
            research_model=research_model,
            compression_model=compression_model,
            final_report_model=report_model,
            allow_clarification=False,  # Disable clarification for automated execution
            max_concurrent_research_units=3,  # Reasonable default for concurrency
        )

        print(f"[ResearchEngine] Configuration built: search={search_api.value}, iterations={max_iterations}")
        return config

    def _extract_sources(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract sources from research result."""
        sources = []

        # Try to extract URLs from notes
        notes = result.get("notes", [])
        raw_notes = result.get("raw_notes", [])

        all_notes = notes + raw_notes

        # Simple URL extraction
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

        seen_urls = set()
        for note in all_notes:
            if isinstance(note, str):
                urls = re.findall(url_pattern, note)
                for url in urls:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        # Extract title from note context (simple heuristic)
                        title = self._extract_title_from_note(note, url)
                        sources.append({
                            "url": url,
                            "title": title,
                            "relevance_score": 0.8  # Default score
                        })

        # Limit to top 10 sources
        return sources[:10]

    def _extract_title_from_note(self, note: str, url: str) -> Optional[str]:
        """Extract title from note context."""
        # Try to find text before the URL as title
        parts = note.split(url)
        if len(parts) > 0:
            before = parts[0].strip()
            # Take last sentence or phrase before URL
            sentences = before.split(".")
            if sentences:
                title = sentences[-1].strip()
                if title and len(title) < 200:
                    return title

        # Default to domain name
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
            return domain
        except:
            return None

    def _estimate_tokens(self, result: Dict[str, Any]) -> int:
        """Estimate token usage from result."""
        # Rough estimation: ~4 characters per token
        final_report = result.get("final_report", "")
        notes = result.get("notes", [])
        raw_notes = result.get("raw_notes", [])

        total_chars = len(final_report)
        for note in notes + raw_notes:
            if isinstance(note, str):
                total_chars += len(note)

        # Estimate tokens
        estimated_tokens = total_chars // 4

        # Add overhead for prompts and tool calls (rough estimate)
        estimated_tokens = int(estimated_tokens * 1.5)

        return estimated_tokens

    def _parse_stream_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse streaming event from LangGraph."""
        event_type = event.get("event", "")
        name = event.get("name", "")

        # Node start events
        if event_type == "on_chain_start":
            if "clarify" in name.lower():
                return {
                    "type": "progress",
                    "message": "Analyzing query...",
                    "phase": "clarification",
                    "progress_percent": 10
                }
            elif "research_brief" in name.lower() or "write_research" in name.lower():
                return {
                    "type": "progress",
                    "message": "Planning research strategy...",
                    "phase": "planning",
                    "progress_percent": 20
                }
            elif "supervisor" in name.lower():
                return {
                    "type": "progress",
                    "message": "Conducting research...",
                    "phase": "research",
                    "progress_percent": 40
                }
            elif "final_report" in name.lower():
                return {
                    "type": "progress",
                    "message": "Generating final report...",
                    "phase": "report_generation",
                    "progress_percent": 80
                }

        # Node end events
        elif event_type == "on_chain_end":
            if "supervisor" in name.lower():
                return {
                    "type": "step_complete",
                    "step_type": "research",
                    "execution_time_ms": 0  # Can be calculated if needed
                }
            elif "final_report" in name.lower():
                return {
                    "type": "step_complete",
                    "step_type": "report_generation",
                    "execution_time_ms": 0
                }

        # Tool call events (search API)
        elif event_type == "on_tool_start":
            return {
                "type": "progress",
                "message": f"Searching web...",
                "phase": "search",
                "progress_percent": 50
            }

        return None

    def _map_research_depth_to_iterations(self, depth: str) -> int:
        """Map research depth string to iteration count."""
        depth_map = {
            "shallow": 2,
            "medium": 5,
            "deep": 10
        }
        return depth_map.get(depth, 5)
