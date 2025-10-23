"""Main CrewAI crew orchestration."""

from crewai import Crew, Process
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
import os

from .agents import AnalyticsAgents
from .tasks import AnalyticsTasks
from ..mcp_clients.facebook_client import FacebookMCPClient
from ..mcp_clients.google_client import GoogleMCPClient


class AnalyticsCrew:
    """Analytics crew for processing marketing data requests."""

    def __init__(self):
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )

        # Initialize agent factory
        self.agents_factory = AnalyticsAgents(self.llm)

        # Initialize tasks factory
        self.tasks_factory = AnalyticsTasks()

        # Initialize MCP clients
        self.facebook_client: Optional[FacebookMCPClient] = None
        self.google_client: Optional[GoogleMCPClient] = None

    def _initialize_mcp_clients(self, platforms: List[str]):
        """Initialize MCP clients for required platforms."""

        if "facebook" in platforms or "both" in platforms:
            if not self.facebook_client:
                self.facebook_client = FacebookMCPClient()

        if "google" in platforms or "both" in platforms:
            if not self.google_client:
                self.google_client = GoogleMCPClient()

    def _get_facebook_tools(self) -> List:
        """Get Facebook MCP tools."""
        if not self.facebook_client:
            return []
        return self.facebook_client.get_tools()

    def _get_google_tools(self) -> List:
        """Get Google Analytics MCP tools."""
        if not self.google_client:
            return []
        return self.google_client.get_tools()

    def execute(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the analytics crew with the given task details."""

        platforms = task_details.get("platforms", [])

        # Initialize MCP clients
        self._initialize_mcp_clients(platforms)

        # Create agents
        master_agent = self.agents_factory.create_master_agent()

        agents = [master_agent]
        tasks = []
        specialist_tasks = []

        # Create Facebook specialist if needed
        if "facebook" in platforms or "both" in platforms:
            facebook_tools = self._get_facebook_tools()
            facebook_agent = self.agents_factory.create_facebook_specialist(
                tools=facebook_tools
            )
            facebook_task = self.tasks_factory.create_facebook_analysis_task(
                agent=facebook_agent,
                task_details=task_details
            )
            agents.append(facebook_agent)
            tasks.append(facebook_task)
            specialist_tasks.append(facebook_task)

        # Create Google specialist if needed
        if "google" in platforms or "both" in platforms:
            google_tools = self._get_google_tools()
            google_agent = self.agents_factory.create_google_specialist(
                tools=google_tools
            )
            google_task = self.tasks_factory.create_google_analysis_task(
                agent=google_agent,
                task_details=task_details
            )
            agents.append(google_agent)
            tasks.append(google_task)
            specialist_tasks.append(google_task)

        # Create synthesis task for master agent
        synthesis_task = self.tasks_factory.create_synthesis_task(
            agent=master_agent,
            task_details=task_details,
            context=specialist_tasks  # Master agent gets specialist outputs
        )
        tasks.append(synthesis_task)

        # Create and run crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,  # Sequential to ensure specialists run first #TODO: validate if this should be sequential or hierarchical
            verbose=True
        )

        try:
            result = crew.kickoff()

            return {
                "success": True,
                "result": result,
                "platforms": platforms,
                "task_details": task_details
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "platforms": platforms,
                "task_details": task_details
            }

        finally:
            # Cleanup MCP clients
            if self.facebook_client:
                self.facebook_client.close()
            if self.google_client:
                self.google_client.close()
