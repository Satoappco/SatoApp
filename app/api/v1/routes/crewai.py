"""
CrewAI Testing API routes
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import asyncio
import httpx
import os

from app.services.crewai_timing_wrapper import CrewAITimingWrapper
from app.core.auth import get_current_user
from app.core.api_auth import verify_crewai_token
from app.models.users import Campaigner
from app.core.database import get_session
from app.config.logging import get_logger
from app.models.agents import CustomerLog
from app.api.v1.routes.webhooks import refresh_user_ga4_tokens, refresh_user_facebook_tokens

logger = get_logger("api.crewai")
router = APIRouter()


class CrewAITestRequest(BaseModel):
    """Request model for CrewAI testing"""
    campaigner_id: int
    agency_id: int
    customer_id: int  # This is the actual customer_id for database queries
    session_id: str
    user_question: str
    user_intent: str
    parameters: Dict
    # data_sources will be extracted from parameters.data_source


class CrewAITestResponse(BaseModel):
    """Response model for CrewAI testing"""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: str
    processing_time: Optional[float] = None
    customer_log_id: Optional[str] = None


async def run_crewai_analysis_for_test(
    campaigner_id: int,
    agency_id: int,
    customer_id: int,
    user_question: str,
    intent_name: str,
    data_sources: List[str],
    session_id: str,
    matching_parameters: Dict,
    analysis_id: str
):
    """
    Run CrewAI analysis for testing purposes.
    This is a simplified version of the webhook analysis without DialogCX integration.
    """
    try:
        logger.info(f"🤖 Starting CrewAI test analysis for session: {session_id}")
        
        # Initialize timing wrapper for comprehensive logging
        timing_wrapper = CrewAITimingWrapper(session_id=session_id, analysis_id=analysis_id)
        import time
        start_time = time.time()
        
        # 1. GET ALL AGENT CONFIGURATIONS FROM DATABASE (DYNAMIC)
        from app.services.agent_service import AgentService
        
        agent_service = AgentService()
        all_agents_data = agent_service.get_all_agents()
        master_agent_data = all_agents_data.get("master_agent")
        specialist_agents_data = all_agents_data.get("specialist_agents", [])
        
        if not master_agent_data:
            raise ValueError("Master agent not found in database")
            
        logger.info(f"Found master agent: {master_agent_data['name']}")
        logger.info(f"Found {len(specialist_agents_data)} specialist agents")
        
        # 2. REFRESH GA4 TOKENS BEFORE GETTING CONNECTIONS
        from app.services.google_analytics_service import GoogleAnalyticsService
        ga_service = GoogleAnalyticsService()
        user_connections = []
        
        if "ga4" in data_sources:
            try:
                # STEP 1: Automatically refresh expired tokens before using them
                logger.info(f"🔄 Checking and refreshing GA4 tokens for user {campaigner_id}...")
                await refresh_user_ga4_tokens(ga_service, campaigner_id)
                
                # STEP 2: Get user connections (should work now with fresh tokens)
                if hasattr(ga_service, 'get_user_connections'):
                    user_connections = await ga_service.get_user_connections(campaigner_id)
                    logger.info(f"✅ Found {len(user_connections)} GA4 connections for user")
                else:
                    logger.info("get_user_connections method not implemented yet - continuing without user connections")
            except Exception as e:
                logger.warning(f"Could not get user connections: {e}")
        
        # Also refresh Google Ads tokens if Google Ads is in data sources
        if "google_ads" in data_sources:
            try:
                from app.services.google_ads_service import GoogleAdsService
                google_ads_service = GoogleAdsService()
                logger.info(f"🔄 Checking Google Ads connections for user {campaigner_id}...")
                # Google Ads tokens are refreshed automatically when needed
                logger.info(f"✅ Google Ads service ready for user {campaigner_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Google Ads service: {e}")
        
        # Also refresh Facebook tokens if Facebook is in data sources
        if "facebook" in data_sources:
            try:
                from app.services.facebook_service import FacebookService
                facebook_service = FacebookService()
                logger.info(f"🔄 Checking and refreshing Facebook tokens for user {campaigner_id}...")
                await refresh_user_facebook_tokens(facebook_service, campaigner_id)
                logger.info(f"✅ Facebook service ready for user {campaigner_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Facebook service: {e}")
        
        # 3. INITIALIZE LLM
        import os
        from crewai.llm import LLM
        
        google_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GEMINI_API_KEY required")

        llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=google_api_key,
            temperature=0.1
        )
        
        # 4. CREATE AGENTS COMPLETELY FROM DATABASE CONFIGURATION
        from crewai import Agent, Task, Crew, Process
        import time
        
        agents = []
        tasks = []
        
        # Create Master Agent using ONLY database configuration with timing
        master_agent = timing_wrapper.create_timed_agent(
            role=master_agent_data["name"],  # Use name field for display
            goal=master_agent_data["goal"],
            backstory=master_agent_data["backstory"],
            verbose=master_agent_data.get("verbose", True),
            allow_delegation=master_agent_data.get("allow_delegation", True),
            llm=llm
        )
        agents.append(master_agent)
        logger.info(f"✅ Created Master Agent: {master_agent_data['name']} (delegation: {master_agent_data.get('allow_delegation', True)}, verbose: {master_agent_data.get('verbose', True)})")
        
        # Create Master Task using database configuration
        master_task_description = master_agent_data.get("task", "")
        logger.info(f"📋 Original task template: {master_task_description}")
        
        # Master agent will use its DateConversionTool naturally during task execution
        
        if master_task_description:
            try:
                # Get current date for date calculations
                from datetime import datetime
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                # Replace placeholders in task with actual values
                master_task_description = master_task_description.format(
                    objective=user_question,
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    intent_name=intent_name,
                    data_sources=", ".join(data_sources),
                    data_source=", ".join(data_sources),  # Support both naming conventions
                    available_specialists=", ".join([s['name'] for s in specialist_agents_data]),
                    current_date=current_date
                )
                logger.info(f"✅ Formatted task description: {master_task_description}")
            except KeyError as e:
                logger.error(f"❌ Missing placeholder in task template: {e}")
                # Use a simple fallback task
                master_task_description = f"Analyze the following question: {user_question}"
            except Exception as e:
                logger.error(f"❌ Error formatting task template: {e}")
                # Use a simple fallback task
                master_task_description = f"Analyze the following question: {user_question}"
        else:
            # Fallback if no task in database
            master_task_description = f"Coordinate analysis for: {user_question}"
            logger.info(f"📋 Using fallback task: {master_task_description}")
            
        master_task = Task(
            description=master_task_description,
            agent=master_agent,
            expected_output="Comprehensive analysis with specific insights and actionable recommendations"
        )
        
        logger.info(f"📋 Created master task: {master_task.description[:200]}...")
        tasks.append(master_task)
        
        # 5. CREATE SPECIALIST AGENTS DYNAMICALLY FROM DATABASE
        specialist_tasks = []  # Track specialist tasks to set context
        
        logger.info(f"📊 Available specialist agents: {len(specialist_agents_data)}")
        for specialist_data in specialist_agents_data:
            logger.info(f"🔍 Checking specialist: {specialist_data['name']} (type: {specialist_data['agent_type']})")
            # Only include relevant specialists
            if not _should_include_specialist(specialist_data, data_sources, intent_name, user_question):
                logger.info(f"Skipping specialist: {specialist_data['name']} (not relevant for this request)")
                continue
                
            agent_type = specialist_data["agent_type"]
            
            # Get tools for this agent dynamically
            logger.info(f"🔧 Getting tools for agent type: {agent_type}")
            # Use customer_id as subclient_id for database queries
            agent_tools = get_tools_for_agent(agent_type, user_connections, campaigner_id=campaigner_id, customer_id=customer_id)
            logger.info(f"🔧 Agent {agent_type} received {len(agent_tools)} tools: {[tool.__class__.__name__ for tool in agent_tools]}")
            
            # Create specialist agent using ONLY database configuration with timing
            specialist_agent = timing_wrapper.create_timed_agent(
                role=specialist_data["role"],
                goal=specialist_data["goal"], 
                backstory=specialist_data["backstory"],
                tools=agent_tools,
                verbose=specialist_data.get("verbose", True),
                allow_delegation=False,  # Specialists should NOT delegate
                llm=llm
            )
            
            agents.append(specialist_agent)
            logger.info(f"✅ Created Specialist: {specialist_data['name']} (delegation: False, verbose: {specialist_data.get('verbose', True)}, tools: {len(agent_tools)})")
            
            # Create specialist task using database configuration
            specialist_task_description = specialist_data.get("task", "")
            if specialist_task_description:
                # Use converted dates from master agent's DateConversionTool
                # Replace placeholders in task with actual values
                specialist_task_description = specialist_task_description.format(
                    objective=user_question,
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    intent_name=intent_name,
                    data_sources=", ".join(data_sources),
                    date_range="as specified in the user question",
                    timezone="UTC",
                    currency="USD",
                    attribution_window="30d",
                    current_date=current_date,  # Add current date for date calculations
                    available_specialists=", ".join([s['name'] for s in specialist_agents_data])
                )
            else:
                # Fallback if no task in database
                specialist_task_description = f"Analyze {agent_type} data for: {user_question}"
            
            # Set expected output based on agent type
            expected_output = f"Detailed {specialist_data['agent_type']} analysis following the specialist reply schema"
            
            # CRITICAL FIX: Set context=[master_task] so specialist output feeds back to master
            specialist_task = Task(
                description=specialist_task_description,
                agent=specialist_agent,
                expected_output=expected_output,
                context=[master_task]  # ✅ This ensures output goes to master, not directly to user
            )
            specialist_tasks.append(specialist_task)
            logger.info(f"✅ Created task for: {specialist_data['name']} with context=[master_task]")
        
        # Add specialist tasks after master task so they execute after and feed back
        tasks.extend(specialist_tasks)
        
        # 6. EXECUTE DYNAMIC CREW WITH DATABASE-DRIVEN CONFIGURATION AND TIMING
        crew = timing_wrapper.create_timed_crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        # Prepare customer log data but don't create it yet
        user_intent = intent_name or "CrewAI Test"
        crewai_input_prompt = f"User Question: {user_question}\nIntent: {intent_name}\nData Sources: {data_sources}\nUser ID: {campaigner_id}\nCustomer ID: {customer_id}\nSubcustomer ID: {customer_id}"
        
        logger.info(f"🤖 Executing crew with {len(agents)} agents and {len(tasks)} tasks")
        
        # Track individual agent/task results for partial success reporting
        execution_details = {
            "agents_executed": [],
            "tasks_completed": [],
            "tools_used": [],
            "errors_encountered": [],
            "partial_results": []
        }
        
        try:
            result = crew.kickoff()
            processing_time = time.time() - start_time
            logger.info(f"✅ Crew execution completed in {processing_time:.2f} seconds")
            logger.info(f"🔍 CrewAI result type: {type(result)}")
            logger.info(f"🔍 CrewAI result value: {result}")
            
        except Exception as crew_error:
            processing_time = time.time() - start_time
            logger.error(f"❌ CrewAI execution failed: {str(crew_error)}")
            logger.error(f"❌ Error type: {type(crew_error)}")
            
            # Try to extract partial results and execution details
            partial_result = None
            error_msg = str(crew_error)
            
            # Check if this is a validation error with some successful execution
            if "TaskOutput" in error_msg and "raw" in error_msg and "None" in error_msg:
                logger.info("🔍 TaskOutput validation error (raw field is None) - checking for partial results")
                # Try to extract any successful task outputs from the crew's state
                try:
                    if hasattr(crew, 'tasks') and crew.tasks:
                        for i, task in enumerate(crew.tasks):
                            if hasattr(task, 'output') and task.output:
                                execution_details["tasks_completed"].append({
                                    "task_index": i,
                                    "task_description": task.description[:100] + "...",
                                    "output": str(task.output)[:500] + "..." if len(str(task.output)) > 500 else str(task.output)
                                })
                                logger.info(f"✅ Found partial result from task {i}")
                except Exception as extract_error:
                    logger.warning(f"⚠️ Could not extract partial results: {extract_error}")
                
                # This is a known issue with CrewAI when tasks fail - we can continue with partial results
                logger.info("ℹ️ This is a known CrewAI validation issue when tasks fail - continuing with partial results")
            elif "TaskOutput" in error_msg:
                logger.info("🔍 TaskOutput validation error - checking for partial results")
                # Try to extract any successful task outputs from the crew's state
                try:
                    if hasattr(crew, 'tasks') and crew.tasks:
                        for i, task in enumerate(crew.tasks):
                            if hasattr(task, 'output') and task.output:
                                execution_details["tasks_completed"].append({
                                    "task_index": i,
                                    "task_description": task.description[:100] + "...",
                                    "output": str(task.output)[:500] + "..." if len(str(task.output)) > 500 else str(task.output)
                                })
                                logger.info(f"✅ Found partial result from task {i}")
                except Exception as extract_error:
                    logger.warning(f"⚠️ Could not extract partial results: {extract_error}")
            
            # Build a comprehensive error response with any partial data
            if execution_details["tasks_completed"]:
                partial_result = f"Partial analysis completed:\n"
                for task_result in execution_details["tasks_completed"]:
                    partial_result += f"Task {task_result['task_index']}: {task_result['output']}\n"
                partial_result += f"\nExecution failed at final stage: {error_msg}"
            else:
                partial_result = f"CrewAI execution failed: {error_msg}"
            
            # CREATE CUSTOMER LOG WITH ERROR RESULT
            try:
                customer_log_id = timing_wrapper.create_customer_log(
                    user_intent=user_intent,
                    original_query=user_question,
                    crewai_input_prompt=crewai_input_prompt,
                    master_answer=partial_result or f"CrewAI execution failed: {error_msg}",
                    campaigner_id=campaigner_id,
                    success=False,
                    error_message=error_msg
                )
                logger.info(f"✅ Created customer log {customer_log_id} with error result")
            except Exception as log_error:
                logger.warning(f"⚠️ Failed to create customer log: {log_error}")
                customer_log_id = session_id  # Fallback to session_id
            
            # Return detailed error with any partial results
            return {
                "success": False,
                "result": partial_result,
                "error": f"CrewAI execution failed: {error_msg}",
                "session_id": session_id,
                "processing_time": processing_time,
                "customer_log_id": customer_log_id,
                "partial_data": bool(execution_details["tasks_completed"]),
                "execution_details": execution_details
            }
        
        # Analyze result to determine actual success/failure
        result_text = str(result).lower()
        
        # Check for common failure indicators
        failure_indicators = [
            "authentication error",
            "401 request had invalid authentication credentials",
            "unable to provide a comprehensive analysis",
            "encountered an error",
            "could not retrieve",
            "failed to fetch",
            "access denied",
            "invalid credentials",
            "token expired",
            "unauthorized"
        ]
        
        is_success = True
        error_message = None
        
        for indicator in failure_indicators:
            if indicator in result_text:
                is_success = False
                error_message = f"Analysis failed due to: {indicator}"
                logger.warning(f"⚠️ CrewAI test analysis failed - detected failure indicator: {indicator}")
                break
        
        if is_success:
            logger.info(f"✅ CrewAI test analysis completed successfully")
        else:
            logger.error(f"❌ CrewAI test analysis failed: {error_message}")
        
        # CREATE CUSTOMER LOG WITH ACTUAL RESULT
        try:
            customer_log_id = timing_wrapper.create_customer_log(
                user_intent=user_intent,
                original_query=user_question,
                crewai_input_prompt=crewai_input_prompt,
                master_answer=str(result),
                campaigner_id=campaigner_id,
                success=is_success,
                error_message=error_message
            )
            logger.info(f"✅ Created customer log {customer_log_id} with actual result")
        except Exception as log_error:
            logger.warning(f"⚠️ Failed to create customer log: {log_error}")
            customer_log_id = session_id  # Fallback to session_id
        
        return {
            "success": is_success,
            "result": str(result),
            "error": error_message,
            "session_id": session_id,
            "processing_time": processing_time,
            "customer_log_id": customer_log_id
        }
        
    except Exception as e:
        logger.error(f"❌ CrewAI test analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }






# Import the centralized function from utils
from app.utils.agent_utils import get_tools_for_agent


def verify_jwt_token(authorization: str = Header(None)):
    """JWT token verification for CrewAI test endpoint"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split(" ")[1]
    
    try:
        # Use the existing JWT verification from auth.py
        from app.core.auth import verify_token
        payload = verify_token(token, "access")
        return True
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def _should_include_specialist(specialist_config: Dict, data_sources: List[str], intent_name: str, user_question: str) -> bool:
    """Determine if a specialist should be included based on context"""
    from app.core.constants import should_include_agent
    
    agent_type = specialist_config["agent_type"]
    
    # Use standardized logic
    return should_include_agent(agent_type, data_sources, user_question)


@router.post("/crewai", response_model=CrewAITestResponse)
async def test_crewai_analysis(
    request: CrewAITestRequest,
    _: bool = Depends(verify_crewai_token)
):
    """
    Test CrewAI analysis endpoint - independent of DialogCX webhook
    
    This endpoint allows testing CrewAI functionality with the same logic as the webhook
    but without DialogCX integration. Perfect for development and testing.
    """
    # Generate unique analysis ID for comprehensive logging
    import time
    analysis_id = f"crewai_{int(time.time() * 1000)}"
    
    logger.info(f"🧪 CREWAI TEST ENDPOINT CALLED - Analysis ID: {analysis_id}")
    logger.info(f"Request: {request.dict()}")
    
    # COMPREHENSIVE INPUT VALIDATION
    
    # 1. VALIDATE REQUIRED STRING FIELDS
    if not request.user_question or not request.user_question.strip():
        logger.error(f"❌ Missing or empty user_question in request")
        return CrewAITestResponse(
            success=False,
            error="user_question is required and cannot be empty",
            session_id=request.session_id
        )
    
    # Check user_question length (prevent extremely long queries)
    if len(request.user_question.strip()) > 2000:
        logger.error(f"❌ user_question too long: {len(request.user_question)} characters")
        return CrewAITestResponse(
            success=False,
            error="user_question must be less than 2000 characters",
            session_id=request.session_id
        )
    
    # Check for potentially malicious content
    suspicious_patterns = ['<script', 'javascript:', 'eval(', 'exec(', 'import os', 'subprocess']
    user_question_lower = request.user_question.lower()
    for pattern in suspicious_patterns:
        if pattern in user_question_lower:
            logger.warning(f"⚠️ Suspicious pattern detected in user_question: {pattern}")
            return CrewAITestResponse(
                success=False,
                error="Invalid characters detected in user_question",
                session_id=request.session_id
            )
    
    if not request.session_id or not request.session_id.strip():
        logger.error(f"❌ Missing or empty session_id in request")
        return CrewAITestResponse(
            success=False,
            error="session_id is required and cannot be empty",
            session_id=""
        )
    
    # Validate session_id format (should be UUID-like)
    import re
    import os
    
    if os.getenv("ENVIRONMENT") == "production":
        # Strict validation for production - UUID only
        session_id_pattern = r'^[a-fA-F0-9-]{36}$'
        error_msg = "session_id must be a valid UUID format"
    else:
        # Allow test formats in development
        session_id_pattern = r'^(test-?[a-zA-Z0-9-]+|[a-fA-F0-9-]{36}|[a-fA-F0-9-]{8,})$'
        error_msg = "session_id must be a valid UUID or test format"
    
    if not re.match(session_id_pattern, request.session_id):
        logger.error(f"❌ Invalid session_id format: {request.session_id}")
        return CrewAITestResponse(
            success=False,
            error=error_msg,
            session_id=request.session_id
        )
    
    # 2. VALIDATE OPTIONAL STRING FIELDS
    if request.user_intent and len(request.user_intent) > 2000:
        logger.error(f"❌ user_intent too long: {len(request.user_intent)} characters")
        return CrewAITestResponse(
            success=False,
            error="user_intent must be less than 200 characters",
            session_id=request.session_id
        )
    
    # VALIDATE USER_ID AND CUSTOMER_ID RANGES
    if request.campaigner_id < 1 or request.campaigner_id > 999999:
        logger.error(f"❌ campaigner_id out of valid range: {request.campaigner_id}")
        return CrewAITestResponse(
            success=False,
            error="campaigner_id must be between 1 and 999999",
            session_id=request.session_id
        )
    
    if request.customer_id < 1 or request.customer_id > 999999:
        logger.error(f"❌ customer_id out of valid range: {request.customer_id}")
        return CrewAITestResponse(
            success=False,
            error="customer_id must be between 1 and 999999",
            session_id=request.session_id
        )
    
    # 3. COMPREHENSIVE PARAMETERS VALIDATION
    if not request.parameters or not isinstance(request.parameters, dict):
        logger.error(f"❌ Missing or invalid parameters object")
        return CrewAITestResponse(
            success=False,
            error="parameters object is required",
            session_id=request.session_id
        )
    
    # EXTRACT AND VALIDATE DATA SOURCES FROM PARAMETERS
    data_sources = request.parameters.get("data_sources", [])
    if not isinstance(data_sources, list):
        logger.error(f"❌ data_sources must be a list, got: {type(data_sources)}")
        return CrewAITestResponse(
            success=False,
            error="data_sources must be a list",
            session_id=request.session_id
        )
    
    # Validate data sources are not empty
    if not data_sources:
        logger.warning(f"⚠️ Empty data_sources provided, using default 'ga4'")
        data_sources = ["ga4"]  # Default fallback
    
    # Validate individual data sources using standardized constants
    from app.core.constants import VALID_DATA_SOURCES, validate_data_sources, get_data_source_suggestions
    standard_data_sources, invalid_sources = validate_data_sources(data_sources)
    
    if invalid_sources:
        # Provide helpful error messages with suggestions
        error_details = []
        for invalid_source in invalid_sources:
            suggestions = get_data_source_suggestions(invalid_source)
            suggestion_text = f" Did you mean: {', '.join(suggestions[:3])}?" if suggestions else ""
            error_details.append(f"'{invalid_source}'{suggestion_text}")
        
        error_message = f"Invalid data sources: {', '.join(error_details)}. Valid sources: {', '.join(VALID_DATA_SOURCES)}"
        logger.error(f"❌ {error_message}")
        return CrewAITestResponse(
            success=False,
            error=error_message,
            session_id=request.session_id
        )
    
    # Use standardized data sources for processing
    data_sources = standard_data_sources
    
    # Validate data sources length
    if len(data_sources) > 10:
        logger.error(f"❌ Too many data sources: {len(data_sources)}. Maximum 10 allowed")
        return CrewAITestResponse(
            success=False,
            error="Maximum 10 data sources allowed per request",
            session_id=request.session_id
        )
    
    # 4. VALIDATE OPTIONAL PARAMETERS
    timeframe = request.parameters.get("timeframe")
    if timeframe and not isinstance(timeframe, str):
        logger.error(f"❌ timeframe must be a string, got: {type(timeframe)}")
        return CrewAITestResponse(
            success=False,
            error="timeframe must be a string",
            session_id=request.session_id
        )
    
    analysis_type = request.parameters.get("analysis_type")
    if analysis_type and not isinstance(analysis_type, str):
        logger.error(f"❌ analysis_type must be a string, got: {type(analysis_type)}")
        return CrewAITestResponse(
            success=False,
            error="analysis_type must be a string",
            session_id=request.session_id
        )
    
    # Validate analysis_type values
    valid_analysis_types = [
        "day_of_week", "traffic_sources", "campaign_performance", "user_behavior", 
        "revenue_analysis", "demographics", "conversion_funnel", "cohort_analysis"
    ]
    if analysis_type and analysis_type not in valid_analysis_types:
        logger.warning(f"⚠️ Unknown analysis_type: {analysis_type}. Continuing with custom analysis.")
    
    # 5. EDGE CASE HANDLING
    
    # Handle special characters in user_question
    request.user_question = request.user_question.strip()
    
    # Handle empty or whitespace-only parameters
    filtered_params = {}
    for key, value in request.parameters.items():
        if isinstance(value, str) and value.strip():
            filtered_params[key] = value.strip()
        elif not isinstance(value, str):
            filtered_params[key] = value
    
    # Update parameters with filtered values
    if filtered_params != request.parameters:
        logger.info(f"📝 Filtered empty parameters: {set(request.parameters.keys()) - set(filtered_params.keys())}")
        request.parameters = filtered_params
    
    try:
        # Master agent will handle date extraction using its DateConversionTool
        # No need for hardcoded regex patterns - let the LLM handle it naturally
        
        # Create matching parameters
        matching_parameters = {
            "intent_confidence": 1.0,  # Assume high confidence for test
            "intent_parameters": request.parameters,
            "session_parameters": request.parameters
        }
        
        logger.info(f"Processing for campaigner_id: {request.campaigner_id}, customer_id: {request.customer_id}")
        logger.info(f"Session ID: {request.session_id}")
        logger.info(f"Question: {request.user_question}")
        logger.info(f"Intent: {request.user_intent}")
        logger.info(f"Data sources: {data_sources}")
        logger.info(f"Matching Parameters: {matching_parameters}")
        
        # Run CrewAI analysis
        result = await run_crewai_analysis_for_test(
            campaigner_id=request.campaigner_id,
            customer_id=request.customer_id,
            user_question=request.user_question,
            intent_name=request.user_intent,
            data_sources=data_sources,
            session_id=request.session_id,
            matching_parameters=matching_parameters,
            analysis_id=analysis_id
        )
        
        # Analyze result to determine actual success/failure
        logger.info(f"Result from run_crewai_analysis_for_test: {result}")
        
        # Check if result is valid
        if not isinstance(result, dict):
            logger.error(f"❌ Invalid result type: {type(result)}")
            return CrewAITestResponse(
                success=False,
                error=f"Invalid result type: {type(result)}",
                session_id=request.session_id
            )
        
        if "result" not in result:
            logger.error(f"❌ Missing 'result' key in response: {result}")
            # If this is an error response, use the error message as the result
            if "error" in result:
                return CrewAITestResponse(
                    success=False,
                    error=result["error"],
                    session_id=request.session_id,
                    processing_time=result.get("processing_time"),
                    customer_log_id=result.get("customer_log_id")
                )
            else:
                return CrewAITestResponse(
                    success=False,
                    error=f"Missing 'result' key in response",
                    session_id=request.session_id
                )
        
        result_text = str(result.get("result", "")).lower()
        
        # Check for common failure indicators
        failure_indicators = [
            "authentication error",
            "401 request had invalid authentication credentials",
            "unable to provide a comprehensive analysis",
            "encountered an error",
            "could not retrieve",
            "failed to fetch",
            "access denied",
            "invalid credentials",
            "token expired",
            "unauthorized"
        ]
        
        is_success = True
        error_message = None
        
        for indicator in failure_indicators:
            if indicator in result_text:
                is_success = False
                error_message = f"Analysis failed due to: {indicator}"
                logger.warning(f"⚠️ CrewAI test analysis failed - detected failure indicator: {indicator}")
                break
        
        if is_success:
            logger.info(f"✅ CrewAI test analysis completed successfully")
            return CrewAITestResponse(
                success=True,
                result=result["result"],
                session_id=request.session_id,
                processing_time=result.get("processing_time"),
                customer_log_id=result.get("customer_log_id")
            )
        else:
            logger.error(f"❌ CrewAI test analysis failed: {error_message}")
            return CrewAITestResponse(
                success=False,
                error=error_message,
                session_id=request.session_id,
                processing_time=result.get("processing_time"),
                customer_log_id=result.get("customer_log_id")
            )
            
    except Exception as e:
        logger.error(f"❌ CrewAI test endpoint failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return CrewAITestResponse(
            success=False,
            error=str(e),
            session_id=request.session_id
        )


@router.get("/crewai-test/health")
async def test_health():
    """Health check for CrewAI test endpoint"""
    return {
        "status": "healthy",
        "service": "crewai-test",
        "timestamp": datetime.utcnow().isoformat()
    }


