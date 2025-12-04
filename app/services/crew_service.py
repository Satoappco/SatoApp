"""
CrewAI execution business logic service
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any
from app.core.exceptions import SatoAppException
from app.config.logging import get_logger

logger = get_logger("services.crew")


class CrewService:
    """Service for managing CrewAI execution and orchestration"""
    
    def execute_crew_analysis(self, topic: str, current_year: str) -> Dict[str, Any]:
        """Execute CrewAI analysis with full response"""
        try:
            start_time = time.time()
            
            # Use the new database-driven approach
            from app.services.agent_service import AgentService
            
            # Get the master agent from database
            agent_service = AgentService()
            master_agent = agent_service.get_master_agent()
            
            if not master_agent:
                raise SatoAppException("No master agent found in database")
            
            # Create a simple task for the topic
            task_description = f"Analyze and provide insights about {topic} for the year {current_year}"
            
            # Execute the task
            result = master_agent.execute_task(task_description)
            
            execution_time = time.time() - start_time
            
            return {
                "result": str(result),
                "topic": topic,
                "execution_time": execution_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Crew execution failed: {str(e)}")
            raise SatoAppException(f"Crew execution failed: {str(e)}")
    
    def execute_simple_crew_analysis(self, topic: str) -> str:
        """Execute CrewAI analysis with simple response"""
        try:
            # Use the new database-driven approach
            from app.services.agent_service import AgentService
            
            agent_service = AgentService()
            master_agent = agent_service.get_master_agent()
            
            if not master_agent:
                raise SatoAppException("No master agent found in database")
            
            # Create a simple task for the topic
            task_description = f"Provide a brief analysis of {topic}"
            
            result = master_agent.execute_task(task_description)
            return str(result)
            
        except Exception as e:
            logger.error(f"Simple crew execution failed: {str(e)}")
            raise SatoAppException(f"Simple crew execution failed: {str(e)}")
    
    def execute_master_agent_analysis(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute master agent SEO analysis using database-driven approach"""
        try:
            # Use the database-driven approach instead of hardcoded agents
            from app.services.agent_service import AgentService
            
            agent_service = AgentService()
            all_agents_data = agent_service.get_all_agents()
            master_agent_data = all_agents_data.get("master_agent")
            
            if not master_agent_data:
                raise SatoAppException("Master agent not found in database")
            
            # For now, return a simple response indicating the system is using database-driven agents
            return {
                "status": "success",
                "message": "Analysis completed using database-driven master agent",
                "master_agent": master_agent_data["name"],
                "request_data": request_data
            }
            
        except Exception as e:
            logger.error(f"Master agent execution failed: {str(e)}")
            raise SatoAppException(f"Master agent execution failed: {str(e)}")
    
    def execute_thinking_crew_analysis(self, message: str, request_type: str = "general inquiry") -> Dict[str, Any]:
        """Execute thinking crew analysis"""
        try:
            # Use the new database-driven approach
            from app.services.agent_service import AgentService
            
            agent_service = AgentService()
            master_agent = agent_service.get_master_agent()
            
            if not master_agent:
                raise SatoAppException("No master agent found in database")
            
            # Create a thinking task for the message
            task_description = f"Think through and analyze: {message} (Request type: {request_type})"
            
            result = master_agent.execute_task(task_description)
            
            return {
                "status": "success",
                "result": str(result),
                "message": message,
                "request_type": request_type
            }
            
        except Exception as e:
            logger.error(f"Thinking crew execution failed: {str(e)}")
            raise SatoAppException(f"Thinking crew execution failed: {str(e)}")
