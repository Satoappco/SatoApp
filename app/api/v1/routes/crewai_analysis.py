"""
Proper CrewAI Analysis Router - Correct Architecture

This implements the CORRECT architecture where:
1. DialogCX calls this endpoint with user intent
2. Master Agent analyzes intent and delegates to specialists  
3. GA Specialist Agent uses GA4 Tool to fetch real data autonomously
4. Master Agent synthesizes final response
5. Response goes back to DialogCX
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
import time
import uuid

from app.config.database import get_session
from app.models.agents import AgentConfig, CustomerLog
from app.models.users import User
from app.core.security import verify_api_key
from app.tools.ga4_analytics_tool import GA4AnalyticsTool
from app.services.crewai_timing_wrapper import CrewAITimingWrapper

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM

router = APIRouter(prefix="/crewai")

class CrewAIAnalysisRequest(BaseModel):
    """Request model for CrewAI analysis"""
    objective: str = Field(..., description="User's objective/question")
    date_range: Dict[str, str] = Field(default={"start": "7daysAgo", "end": "today"})
    scope: str = Field(default="general", description="Analysis scope")
    filters: List[str] = Field(default=[], description="Additional filters")
    breakdowns: List[str] = Field(default=[], description="Data breakdowns requested")
    constraints: Dict[str, Any] = Field(default={}, description="Analysis constraints")

class CrewAIAnalysisResponse(BaseModel):
    """Response model for CrewAI analysis"""
    analysis_id: str
    success: bool
    summary: str
    key_findings: List[str]
    recommendations: List[str]
    confidence: str
    processing_time_seconds: float
    agents_used: List[str]
    execution_method: str
    session_id: str
    customer_log_id: Optional[str] = None



async def get_agent_config_by_type(agent_type: str) -> Optional[AgentConfig]:
    """Get agent configuration by type"""
    with get_session() as session:
        return session.query(AgentConfig).filter(AgentConfig.agent_type == agent_type).first()


@router.post("/analyze", response_model=CrewAIAnalysisResponse)
async def run_proper_crewai_analysis(
    request: CrewAIAnalysisRequest,
    _: bool = Depends(verify_api_key)
):
    """
    Run CrewAI analysis with PROPER architecture and comprehensive logging:
    - Master Agent coordinates the analysis
    - Specialists use their tools autonomously  
    - Detailed timing and logging for all components
    - Customer log table entry created
    """
    # Generate unique session and analysis IDs
    session_id = f"session_{int(time.time() * 1000)}"
    analysis_id = f"analysis_{int(time.time())}"
    start_time = time.time()
    
    print(f"🚀 Starting PROPER CrewAI Analysis: {analysis_id}")
    print(f"Session ID: {session_id}")
    print(f"Objective: {request.objective}")
    
    # Initialize timing wrapper
    timing_wrapper = CrewAITimingWrapper(session_id=session_id, analysis_id=analysis_id)
    
    try:
        # Get agent configurations
        master_agent_config = await get_agent_config_by_type("seo_campaign_manager")
        ga_specialist_config = await get_agent_config_by_type("google_database_analysis_expert")
        
        if not master_agent_config:
            raise HTTPException(status_code=404, detail="Master Agent not found")
        
        print(f"✅ Found Master Agent: {master_agent_config.name}")
        
        # Initialize LLM
        google_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise HTTPException(
                status_code=500, 
                detail="GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required. Please add it to your .env file. Get it from: https://console.cloud.google.com/apis/credentials"
            )
        
        # Use CrewAI's native LLM class with the correct current Gemini model
        llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=google_api_key,
            temperature=0.1
        )
        
        # Create Master Agent with timing
        master_agent = timing_wrapper.create_timed_agent(
            role=master_agent_config.role,
            goal=master_agent_config.goal,
            backstory=master_agent_config.backstory,
            verbose=True,
            allow_delegation=True,
            llm=llm
        )
        
        # Prepare agents and tasks
        agents = [master_agent]
        tasks = []
        
        # Determine if we need GA specialist
        needs_ga_analysis = (
            "google" in request.objective.lower() or 
            "analytics" in request.objective.lower() or
            "performance" in request.objective.lower() or
            "traffic" in request.objective.lower() or
            "users" in request.objective.lower() or
            "sessions" in request.objective.lower() or
            "conversion" in request.objective.lower() or
            "day" in request.objective.lower() or
            "week" in request.objective.lower() or
            "month" in request.objective.lower() or
            "worst" in request.objective.lower() or
            "best" in request.objective.lower() or
            request.scope == "google_analytics"
        )
        
        if needs_ga_analysis and ga_specialist_config:
            print(f"✅ Found GA Specialist: {ga_specialist_config.name}")
            
            # Initialize GA4 Tool with timing
            with timing_wrapper.timing_service.time_component(
                session_id=session_id,
                component_type="tool",
                component_name="GA4AnalyticsTool_Initialization",
                analysis_id=analysis_id
            ):
                ga4_tool = GA4AnalyticsTool(user_id=request.user_id, customer_id=request.customer_id)
            
            # Create GA Specialist Agent with the tool
            ga_specialist = timing_wrapper.create_timed_agent(
                role=ga_specialist_config.role,
                goal=ga_specialist_config.goal,
                backstory=ga_specialist_config.backstory,
                tools=[ga4_tool],  # Give the agent the tool
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            
            agents.append(ga_specialist)
            
            # Create task for GA specialist
            ga_task = Task(
                description=f"""
                Analyze Google Analytics data for user 5 (satoappco@gmail.com) 
                to answer: "{request.objective}"
                
                Instructions:
                1. Use your GA4 Analytics Tool to fetch relevant data for this user
                2. Focus on the date range: {request.date_range.get('start', '7daysAgo')} to {request.date_range.get('end', 'today')}
                3. Analyze the data to specifically answer: {request.objective}
                4. Provide concrete insights with actual numbers and trends
                5. Include actionable recommendations based on the data patterns
                
                Return your analysis in a clear, structured format with:
                - Summary of findings
                - Key insights with specific data points
                - Recommendations for improvement
                - Confidence level in your analysis
                """,
                agent=ga_specialist,
                expected_output="Detailed Google Analytics analysis with actual data insights and recommendations"
            )
            
            tasks.append(ga_task)
            print(f"🎯 GA Specialist will use GA4 tool autonomously")
        
        # Create master coordination task
        master_task = Task(
            description=f"""
            Coordinate analysis for the user's objective: "{request.objective}"
            
            User Context:
            - User: satoappco@gmail.com (ID: 5)
            - Date Range: {request.date_range.get('start', '7daysAgo')} to {request.date_range.get('end', 'today')}
            - Scope: {request.scope}
            - Constraints: {request.constraints}
            
            Your responsibilities:
            1. Understand the user's intent and requirements
            2. {"Coordinate with the Google Analytics specialist to get data insights" if needs_ga_analysis else "Provide analysis based on available information"}
            3. Synthesize all information into actionable insights
            4. Provide clear, specific recommendations
            
            Return a comprehensive analysis addressing: {request.objective}
            """,
            agent=master_agent,
            expected_output="Comprehensive analysis with summary, key findings, and actionable recommendations"
        )
        
        tasks.append(master_task)
        
        # Create and execute the crew with timing
        crew = timing_wrapper.create_timed_crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        print("🤖 Executing CrewAI crew with proper agent delegation...")
        crew_result = crew.kickoff()
        
        # Process the result
        processing_time = time.time() - start_time
        
        # Extract insights from the crew result
        result_text = str(crew_result)
        
        # Try to structure the response (this could be improved with better parsing)
        summary = result_text[:300] + "..." if len(result_text) > 300 else result_text
        
        # Basic extraction of findings and recommendations (could be enhanced)
        lines = result_text.split('\n')
        key_findings = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10][:5]
        recommendations = [f"Based on analysis: {line.strip()}" for line in lines if 'recommend' in line.lower()][:3]
        
        if not recommendations:
            recommendations = ["Review the detailed analysis for specific insights", "Monitor key metrics regularly", "Consider implementing data-driven optimizations"]
        
        # Determine confidence based on data availability
        confidence = "high" if needs_ga_analysis and ga_specialist_config else "medium"
        
        print(f"✅ Analysis completed in {processing_time:.2f} seconds")
        
        # Create customer log entry
        user_intent = "Insight only" if request.scope == "general" else f"Campaigns {request.scope.title()}"
        crewai_input_prompt = f"Objective: {request.objective}\nScope: {request.scope}\nDate Range: {request.date_range}\nConstraints: {request.constraints}"
        
        customer_log_id = timing_wrapper.create_customer_log(
            user_intent=user_intent,
            original_query=request.objective,
            crewai_input_prompt=crewai_input_prompt,
            master_answer=result_text,
            user_id=5,  # satoappco@gmail.com
            success=True
        )
        
        return CrewAIAnalysisResponse(
            analysis_id=analysis_id,
            success=True,
            summary=summary,
            key_findings=key_findings,
            recommendations=recommendations,
            confidence=confidence,
            processing_time_seconds=processing_time,
            agents_used=[agent.role for agent in agents],
            execution_method="proper_crewai_with_autonomous_tools",
            session_id=session_id,
            customer_log_id=customer_log_id
        )
        
    except Exception as e:
        print(f"ERROR: CrewAI analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        processing_time = time.time() - start_time
        
        return CrewAIAnalysisResponse(
            analysis_id=analysis_id,
            success=False,
            summary=f"Analysis failed: {str(e)}",
            key_findings=[],
            recommendations=["Check system logs", "Verify agent configurations", "Ensure proper tool setup"],
            confidence="failed",
            processing_time_seconds=processing_time,
            agents_used=[],
            execution_method="failed"
        )


@router.get("/agents/status")
async def get_agents_status():
    """Get status of configured agents"""
    
    try:
        with get_session() as session:
            agents = session.query(AgentConfig).all()
            
            agent_status = []
            for agent in agents:
                # Parse capabilities and tools from JSON strings
                capabilities = []
                tools = []
                try:
                    if agent.capabilities:
                        capabilities = json.loads(agent.capabilities) if isinstance(agent.capabilities, str) else agent.capabilities
                except (json.JSONDecodeError, TypeError):
                    capabilities = []
                
                try:
                    if agent.tools:
                        tools = json.loads(agent.tools) if isinstance(agent.tools, str) else agent.tools
                except (json.JSONDecodeError, TypeError):
                    tools = []
                
                agent_status.append({
                    "id": agent.id,
                    "name": agent.name,
                    "type": agent.agent_type,
                    "role": agent.role,
                    "goal": agent.goal,
                    "backstory": agent.backstory,
                    "task": agent.task,
                    "status": "active" if agent.is_active else "inactive",
                    "has_tools": len(tools) > 0,
                    "tool_name": tools[0] if tools else None,
                    "allow_delegation": agent.allow_delegation,
                    "verbose": agent.verbose,
                    "max_iterations": agent.max_iterations,
                    "capabilities": capabilities,
                    "tools": tools,
                    "prompt_template": agent.prompt_template,
                    "output_schema": agent.output_schema
                })
        
        return {
            "success": True,
            "total_agents": len(agent_status),
            "agents": agent_status,
            "architecture": "proper_crewai_with_autonomous_tools",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")




async def _run_crewai_analysis_for_dialogcx(request: CrewAIAnalysisRequest, current_user: User) -> CrewAIAnalysisResponse:
    """Internal method to run CrewAI analysis for DialogCX webhooks"""
    start_time = time.time()
    analysis_id = f"dialogcx_analysis_{int(time.time() * 1000)}"
    
    print(f"🚀 Starting DialogCX → CrewAI Analysis: {analysis_id}")
    print(f"User: {current_user.email} ({current_user.id})")
    print(f"Objective: {request.objective}")
    
    # Get agent configurations
    master_agent_config = await get_agent_config_by_type("seo_campaign_manager")
    ga_specialist_config = await get_agent_config_by_type("google_database_analysis_expert")
    
    if not master_agent_config or not ga_specialist_config:
        raise HTTPException(status_code=404, detail="Required agents not found in database")
    
    # Initialize LLM
    google_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY required")

    llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=google_api_key,
        temperature=0.1
    )
    
    # Create agents with proper tool delegation
    master_agent = Agent(
        role=master_agent_config.role,
        goal=master_agent_config.goal,
        backstory=master_agent_config.backstory,
        verbose=True,
        allow_delegation=True,
        llm=llm
    )

    ga4_tool = GA4AnalyticsTool(user_id=current_user.id, customer_id=current_user.id)  # For DialogCX, user and customer might be the same
    ga_specialist = Agent(
        role=ga_specialist_config.role,
        goal=ga_specialist_config.goal,
        backstory=ga_specialist_config.backstory,
        tools=[ga4_tool],
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Define tasks
    master_task = Task(
        description=f"DialogCX User Request: \"{request.objective}\"\n"
                    f"Coordinate with GA specialist to analyze this request and provide actionable insights.",
        agent=master_agent,
        expected_output="Comprehensive analysis with specific insights and recommendations"
    )

    ga_task = Task(
        description=f"Use GA4 Analytics Tool to fetch data for: \"{request.objective}\"\n"
                    f"Date Range: {request.date_range.get('start')} to {request.date_range.get('end')}\n"
                    f"User ID: {current_user.id}\n"
                    f"Provide detailed analysis with data-driven insights.",
        agent=ga_specialist,
        expected_output="Detailed GA4 data analysis with key findings and recommendations"
    )
    
    # Execute crew
    crew = Crew(
        agents=[master_agent, ga_specialist],
        tasks=[master_task, ga_task],
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    processing_time = time.time() - start_time
    
    return CrewAIAnalysisResponse(
        analysis_id=analysis_id,
        success=True,
        summary=str(result),
        key_findings=["DialogCX analysis completed"],
        recommendations=["Review detailed analysis"],
        confidence="high",
        processing_time_seconds=processing_time,
        agents_used=["seo_campaign_manager", "google_database_analysis_expert"],
        execution_method="dialogcx_to_crewai_proper_architecture"
    )
