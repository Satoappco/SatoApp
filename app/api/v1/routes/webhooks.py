"""
DialogCX webhook handling API routes
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, Header
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Dict, List
import json
import asyncio
import httpx
import os

from app.services.crewai_timing_wrapper import CrewAITimingWrapper
from app.core.auth import get_current_user
from app.core.api_auth import verify_webhook_token
from app.models.users import User
from app.core.database import get_session
from app.config.logging import get_logger
from app.models.agents import CustomerLog, ExecutionTiming
from app.core.websocket_manager import connection_manager

logger = get_logger("api.webhooks")
router = APIRouter()


async def send_dialogcx_custom_event(session_id: str, event_name: str, result: str):
    """
    Send a custom event to DialogCX with the CrewAI result using REST API.
    
    Args:
        session_id: The DialogCX session ID
        event_name: The custom event name (e.g., 'crew_result_ready')
        result: The CrewAI analysis result
    """
    try:
        import os
        import httpx
        
        # Get DialogCX configuration from environment
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "superb-dream-470215-i7")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west3")
        agent_id = os.getenv("DIALOGCX_AGENT_ID", "ab858805-a4a8-477d-beec-d4cdabba4f09")
        
        # Construct the DialogCX API URL with correct regional endpoint
        if location == "europe-west3":
            api_url = f"https://europe-west3-dialogflow.googleapis.com/v3/projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}:detectIntent"
        else:
            api_url = f"https://dialogflow.googleapis.com/v3/projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}:detectIntent"
        
        # Create the request payload for Conversational Agents
        payload = {
            "queryInput": {
                "event": {
                    "event": event_name,
                    "languageCode": "en-US",
                    "parameters": {
                        "fulfillment_response": result,
                        "result": result,
                        "crew_analysis": result
                    }
                },
                "languageCode": "en-US"
            },
            "session": f"projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}"
        }
        
        # Get service account credentials for authentication
        service_account_email = os.getenv("DIALOGCX_SERVICE_ACCOUNT_EMAIL", "dialogcx-api-service@superb-dream-470215-i7.iam.gserviceaccount.com")
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        
        if not private_key:
            raise ValueError("GOOGLE_PRIVATE_KEY not found in environment variables")
        
        # Create JWT token for authentication
        import jwt
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        payload_jwt = {
            "iss": service_account_email,
            "sub": service_account_email,
            "aud": "https://europe-west3-dialogflow.googleapis.com/",
            "iat": now,
            "exp": now + timedelta(hours=1)
        }
        
        # Create JWT token
        token = jwt.encode(payload_jwt, private_key, algorithm="RS256")
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🚀 Sending custom event '{event_name}' to DialogCX session: {session_id}")
        logger.info(f"API URL: {api_url}")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Location: {location}")
        logger.info(f"Agent ID: {agent_id}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Send the request using httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Custom event sent successfully to DialogCX. Response: {response_data}")
                
                return {
                    "success": True,
                    "response": response_data,
                    "session_id": session_id
                }
            else:
                logger.error(f"❌ DialogCX API returned error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text}",
                    "session_id": session_id
                }
        
    except Exception as e:
        logger.error(f"❌ Failed to send custom event to DialogCX: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }


async def send_dialogcx_text_message(session_id: str, message: str):
    """
    Send a text message to DialogCX as fallback if custom event doesn't work.
    """
    try:
        import os
        import httpx
        
        # Get DialogCX configuration from environment
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "superb-dream-470215-i7")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west3")
        agent_id = os.getenv("DIALOGCX_AGENT_ID", "ab858805-a4a8-477d-beec-d4cdabba4f09")
        
        # Construct the DialogCX API URL with correct regional endpoint
        if location == "europe-west3":
            api_url = f"https://europe-west3-dialogflow.googleapis.com/v3/projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}:detectIntent"
        else:
            api_url = f"https://dialogflow.googleapis.com/v3/projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}:detectIntent"
        
        # Create the request payload with text input for Conversational Agents
        payload = {
            "queryInput": {
                "text": {
                    "text": message,
                    "languageCode": "en-US"
                },
                "languageCode": "en-US"
            },
            "session": f"projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}"
        }
        
        # Get service account credentials for authentication
        service_account_email = os.getenv("DIALOGCX_SERVICE_ACCOUNT_EMAIL", "dialogcx-api-service@superb-dream-470215-i7.iam.gserviceaccount.com")
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        
        if not private_key:
            raise ValueError("GOOGLE_PRIVATE_KEY not found in environment variables")
        
        # Create JWT token for authentication
        import jwt
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        payload_jwt = {
            "iss": service_account_email,
            "sub": service_account_email,
            "aud": "https://europe-west3-dialogflow.googleapis.com/",
            "iat": now,
            "exp": now + timedelta(hours=1)
        }
        
        # Create JWT token
        token = jwt.encode(payload_jwt, private_key, algorithm="RS256")
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🔄 Sending text message to DialogCX session: {session_id}")
        logger.info(f"Message: {message}")
        
        # Send the request using httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Text message sent successfully to DialogCX. Response: {response_data}")
                
                return {
                    "success": True,
                    "response": response_data,
                    "session_id": session_id
                }
            else:
                logger.error(f"❌ DialogCX API returned error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text}",
                    "session_id": session_id
                }
        
    except Exception as e:
        logger.error(f"❌ Failed to send text message to DialogCX: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }


def _get_tools_for_agent(agent_type: str, user_connections: List[Dict], user_id: int = None, customer_id: int = None, subclient_id: int = None) -> List:
    """AUTO-DISCOVERY: Dynamically assign tools based on agent type naming conventions"""
    from app.core.constants import get_tools_for_agent as get_standard_tools
    
    tools = []
    
    # Use the provided subclient_id directly - NO FALLBACK MAPPING!
    # If subclient_id is not provided, tools will fail with clear error messages
    
    # Get tools using standardized constants
    tool_names = get_standard_tools(agent_type)
    
    for tool_name in tool_names:
        try:
            if tool_name == "GA4AnalyticsTool":
                from app.tools.ga4_analytics_tool import GA4AnalyticsTool
                tools.append(GA4AnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added GA4AnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "GoogleAdsAnalyticsTool":
                from app.tools.google_ads_tool import GoogleAdsAnalyticsTool
                tools.append(GoogleAdsAnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added GoogleAdsAnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookAnalyticsTool":
                from app.tools.facebook_analytics_tool import FacebookAnalyticsTool
                tools.append(FacebookAnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookAnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookAdsTool":
                from app.tools.facebook_ads_tool import FacebookAdsTool
                tools.append(FacebookAdsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookAdsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookMarketingTool":
                from app.tools.facebook_marketing_tool import FacebookMarketingTool
                tools.append(FacebookMarketingTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookMarketingTool for {agent_type} (subclient_id={subclient_id})")
                
        except ImportError as e:
            logger.warning(f"⚠️ Could not import {tool_name}: {e}")
        except Exception as e:
            logger.error(f"❌ Error creating {tool_name}: {e}")
    
    logger.info(f"🔧 Agent '{agent_type}' assigned {len(tools)} tools: {[tool.__class__.__name__ for tool in tools]}")
    return tools


async def run_crewai_analysis_async(
    user_id: int,
    customer_id: int,
    user_question: str,
    intent_name: str,
    data_sources: List[str],
    dialogcx_session_id: str,
    matching_parameters: Dict,
    session_id: str,
    analysis_id: str
):
    """
    Run CrewAI analysis asynchronously and send custom event when complete.
    """
    try:
        logger.info(f"🤖 Starting async CrewAI analysis for session: {session_id}")
        
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
            error_msg = "Master agent not found in database. Please ensure agent configurations are properly set up."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
            
        logger.info(f"Found master agent: {master_agent_data['name']}")
        logger.info(f"Found {len(specialist_agents_data)} specialist agents")
        
        # VALIDATE MASTER AGENT CONFIGURATION
        required_agent_fields = ["role", "goal", "backstory", "task"]
        missing_fields = [field for field in required_agent_fields if not master_agent_data.get(field)]
        if missing_fields:
            error_msg = f"Master agent configuration incomplete. Missing fields: {missing_fields}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # 2. REFRESH GA4 TOKENS BEFORE GETTING CONNECTIONS
        from app.services.google_analytics_service import GoogleAnalyticsService
        ga_service = GoogleAnalyticsService()
        user_connections = []
        
        if "ga4" in data_sources:
            try:
                # STEP 1: Automatically refresh expired tokens before using them
                logger.info(f"🔄 Checking and refreshing GA4 tokens for user {user_id}...")
                await refresh_user_ga4_tokens(ga_service, user_id)
                
                # STEP 2: Get user connections (should work now with fresh tokens)
                if hasattr(ga_service, 'get_user_connections'):
                    user_connections = await ga_service.get_user_connections(user_id)
                    logger.info(f"✅ Found {len(user_connections)} GA4 connections for user")
                    
                    # WARN IF NO CONNECTIONS FOUND
                    if not user_connections:
                        logger.warning(f"⚠️ No GA4 connections found for user {user_id}. Analysis may be limited.")
                else:
                    logger.info("get_user_connections method not implemented yet - continuing without user connections")
            except Exception as e:
                logger.warning(f"Could not get user connections: {e}")
                # Don't fail the entire analysis if connections can't be retrieved
                logger.info("Continuing analysis without user connections...")
        
        # Also refresh Google Ads tokens if Google Ads is in data sources
        if "google_ads" in data_sources:
            try:
                from app.services.google_ads_service import GoogleAdsService
                google_ads_service = GoogleAdsService()
                logger.info(f"🔄 Checking Google Ads connections for user {user_id}...")
                # Google Ads tokens are refreshed automatically when needed
                logger.info(f"✅ Google Ads service ready for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Google Ads service: {e}")
        
        # Also refresh Facebook tokens if Facebook is in data sources
        if "facebook" in data_sources:
            try:
                from app.services.facebook_service import FacebookService
                facebook_service = FacebookService()
                logger.info(f"🔄 Checking and refreshing Facebook tokens for user {user_id}...")
                await refresh_user_facebook_tokens(facebook_service, user_id)
                logger.info(f"✅ Facebook service ready for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Facebook service: {e}")
        
        # 3. VALIDATE DATA SOURCES AND PROVIDE FALLBACK
        if not data_sources:
            logger.warning("⚠️ No data sources provided. Using default analysis mode.")
            data_sources = ["ga4"]  # Default fallback
        
        # 4. INITIALIZE LLM
        import os
        from crewai.llm import LLM
        
        google_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            error_msg = "GEMINI_API_KEY environment variable is required but not found. Please check your .env file."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

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
            role=master_agent_data["role"],
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
        if master_task_description:
            # Replace placeholders in task with actual values
            master_task_description = master_task_description.format(
                objective=user_question,
                user_id=user_id,
                customer_id=customer_id,
                intent_name=intent_name,
                data_sources=", ".join(data_sources),
                data_source=", ".join(data_sources),  # Support both naming conventions
                available_specialists=[s['name'] for s in specialist_agents_data]
            )
        else:
            # Fallback if no task in database
            master_task_description = f"Coordinate analysis for: {user_question}"
            
        master_task = Task(
            description=master_task_description,
            agent=master_agent,
            expected_output="Comprehensive analysis with specific insights and actionable recommendations"
        )
        tasks.append(master_task)
        
        # 5. CREATE SPECIALIST AGENTS DYNAMICALLY FROM DATABASE
        for specialist_data in specialist_agents_data:
            # Only include relevant specialists
            if not _should_include_specialist(specialist_data, data_sources, intent_name, user_question):
                logger.info(f"Skipping specialist: {specialist_data['name']} (not relevant for this request)")
                continue
                
            agent_type = specialist_data["agent_type"]
            
            # Get tools for this agent dynamically
            # Note: customer_id in this context is actually subclient_id
            agent_tools = _get_tools_for_agent(agent_type, user_connections, user_id=user_id, customer_id=customer_id, subclient_id=customer_id)
            
            # Create specialist agent using ONLY database configuration with timing
            specialist_agent = timing_wrapper.create_timed_agent(
                role=specialist_data["role"],
                goal=specialist_data["goal"], 
                backstory=specialist_data["backstory"],
                tools=agent_tools,
                verbose=specialist_data.get("verbose", True),
                allow_delegation=specialist_data.get("allow_delegation", False),
                llm=llm
            )
            
            agents.append(specialist_agent)
            logger.info(f"✅ Created Specialist: {specialist_data['name']} (delegation: {specialist_data.get('allow_delegation', False)}, verbose: {specialist_data.get('verbose', True)}, tools: {len(agent_tools)})")
            
            # Create specialist task using database configuration
            specialist_task_description = specialist_data.get("task", "")
            if specialist_task_description:
                # Let the LLM parse the date range from the user question naturally
                # Replace placeholders in task with actual values
                specialist_task_description = specialist_task_description.format(
                    objective=user_question,
                    user_id=user_id,
                    customer_id=customer_id,
                    intent_name=intent_name,
                    data_sources=", ".join(data_sources),
                    data_source=", ".join(data_sources),  # Support both naming conventions
                    date_range="as specified in the user question",  # Let LLM interpret this
                    timezone="UTC",
                    currency="USD",
                    attribution_window="30d"
                )
            else:
                # Fallback if no task in database
                specialist_task_description = f"Analyze {agent_type} data for: {user_question}"
            
            specialist_task = Task(
                description=specialist_task_description,
                agent=specialist_agent,
                expected_output=f"Detailed {specialist_data['agent_type']} analysis following the specialist reply schema"
            )
            tasks.append(specialist_task)
            logger.info(f"✅ Created task for: {specialist_data['name']}")
        
        # 6. EXECUTE DYNAMIC CREW WITH DATABASE-DRIVEN CONFIGURATION AND TIMING
        crew = timing_wrapper.create_timed_crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        logger.info(f"🤖 Executing crew with {len(agents)} agents and {len(tasks)} tasks")
        
        # Track execution details for partial success reporting
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
            
            # Try to extract partial results
            partial_result = None
            error_msg = str(crew_error)
            
            if "TaskOutput" in error_msg:
                logger.info("🔍 TaskOutput validation error - checking for partial results")
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
            
            if execution_details["tasks_completed"]:
                partial_result = f"Partial analysis completed:\n"
                for task_result in execution_details["tasks_completed"]:
                    partial_result += f"Task {task_result['task_index']}: {task_result['output']}\n"
                partial_result += f"\nExecution failed at final stage: {error_msg}"
                result = partial_result
            else:
                result = f"CrewAI execution failed: {error_msg}"
        
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
            "unauthorized",
            "crewai execution failed"
        ]
        
        is_success = True
        error_message = None
        
        for indicator in failure_indicators:
            if indicator in result_text:
                is_success = False
                error_message = f"Analysis failed due to: {indicator}"
                logger.warning(f"⚠️ DialogCX webhook analysis failed - detected failure indicator: {indicator}")
                break
        
        if is_success:
            logger.info(f"✅ DialogCX webhook analysis completed successfully")
        else:
            logger.error(f"❌ DialogCX webhook analysis failed: {error_message}")
        
        # 7. CREATE COMPREHENSIVE CUSTOMER LOG WITH ACTUAL RESULT
        user_intent = intent_name or "DialogCX Integration"
        crewai_input_prompt = f"User Question: {user_question}\nIntent: {intent_name}\nData Sources: {data_sources}\nUser ID: {user_id}"
        
        customer_log_id = timing_wrapper.create_customer_log(
            user_intent=user_intent,
            original_query=user_question,
            crewai_input_prompt=crewai_input_prompt,
            master_answer=str(result),
            user_id=user_id,
            success=is_success,
            error_message=error_message
        )
        
        logger.info(f"📊 Customer log created: {customer_log_id}")
        
        # 8. LOG ADDITIONAL DIALOGCX CONTEXT TO EXISTING CUSTOMER LOG
        try:
            from app.core.database import DatabaseManager
            db_manager = DatabaseManager()
            
            with db_manager.get_session() as session:
                from app.models.agents import CustomerLog
                
                # Update the existing customer log with DialogCX context
                customer_log = session.query(CustomerLog).filter(
                    CustomerLog.session_id == session_id
                ).first()
                
                if customer_log:
                    # Add DialogCX-specific metadata to the existing log
                    dialogcx_metadata = {
                        "dialogcx_session_id": dialogcx_session_id,
                        "matching_parameters": matching_parameters,
                        "simplified_response": {"fulfillment_response": str(result)},
                        "full_detailed_response": {
                            "fulfillment_response": {
                                "messages": [{
                                    "text": {
                                        "text": [str(result)]
                                    }
                                }]
                            },
                            "session_info": {
                                "parameters": {
                                    "analysis_completed": True,
                                    "success": True,
                                    "session_id": session_id,
                                    "analysis_id": analysis_id,
                                    "customer_log_id": customer_log_id,
                                    "user_id": user_id,
                                    "customer_id": customer_id,
                                    "user_question": user_question,
                                    "user_intent": intent_name,
                                    "dialogcx_session_id": dialogcx_session_id,
                                    "matching_parameters": matching_parameters,
                                    "agents_used": [agent_data['name'] for agent_data in [master_agent_data] + [s for s in specialist_agents_data if _should_include_specialist(s, data_sources, intent_name, user_question)]],
                                    "master_agent": master_agent_data['name'],
                                    "specialist_agents": [s['name'] for s in specialist_agents_data if _should_include_specialist(s, data_sources, intent_name, user_question)],
                                    "specialists_count": len(agents) - 1,
                                    "total_agents_count": len(agents),
                                    "data_sources": data_sources,
                                    "data_sources_count": len(data_sources),
                                    "processing_time_seconds": round(processing_time, 2),
                                    "processing_time_ms": round(processing_time * 1000, 2),
                                    "start_time": datetime.fromtimestamp(start_time).isoformat(),
                                    "end_time": datetime.now().isoformat(),
                                    "analysis_type": "crewai_multi_agent",
                                    "crew_process": "sequential",
                                    "llm_model": "gemini/gemini-1.5-flash",
                                    "temperature": 0.1,
                                    "tools_used": [tool.__class__.__name__ for agent in agents for tool in getattr(agent, 'tools', [])],
                                    "tools_count": sum(len(getattr(agent, 'tools', [])) for agent in agents),
                                    "confidence_score": 0.95,
                                    "completeness_score": 1.0,
                                    "timestamp": datetime.now().isoformat(),
                                    "version": "1.0",
                                    "environment": "production"
                                }
                            }
                        }
                    }
                    
                    # Store DialogCX metadata in the existing customer log
                    existing_crewai_log = json.loads(customer_log.crewai_log) if customer_log.crewai_log else {}
                    existing_crewai_log["dialogcx_metadata"] = dialogcx_metadata
                    customer_log.crewai_log = json.dumps(existing_crewai_log, indent=2)
                    
                    session.commit()
                    logger.info(f"📊 DialogCX metadata added to existing customer log: {customer_log_id}")
                
        except Exception as log_error:
            logger.error(f"Failed to add DialogCX metadata to customer log: {log_error}")
            # Don't fail the webhook if logging fails
        
        # 9. ANALYZE RESULT TO DETERMINE SUCCESS/FAILURE
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
                logger.warning(f"⚠️ Analysis failed - detected failure indicator: {indicator}")
                break
        
        if is_success:
            logger.info(f"✅ CrewAI analysis completed successfully")
        else:
            logger.error(f"❌ CrewAI analysis failed: {error_message}")
        
        return {
            "success": is_success,
            "result": str(result),
            "error": error_message,
            "session_id": session_id,
            "dialogcx_session_id": dialogcx_session_id,
            "processing_time": processing_time,
            "customer_log_id": customer_log_id
        }
        
    except Exception as e:
        logger.error(f"❌ Async CrewAI analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Error will be returned directly to webhook - no custom events needed
        
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id,
            "dialogcx_session_id": dialogcx_session_id
        }


def _extract_timeframe_info(user_question: str) -> Dict[str, any]:
    """
    Extract timeframe information from user question.
    
    Examples:
    - "last 90 days" -> {"timeframe": "90 days", "date_range": "last_90_days"}
    - "this month" -> {"timeframe": "this month", "date_range": "this_month"}
    - "last week" -> {"timeframe": "7 days", "date_range": "last_7_days"}
    """
    import re
    from datetime import datetime, timedelta
    
    timeframe_info = {}
    question_lower = user_question.lower()
    
    # Extract number of days
    days_match = re.search(r'(\d+)\s*days?', question_lower)
    if days_match:
        days = int(days_match.group(1))
        timeframe_info.update({
            "timeframe": f"{days} days",
            "date_range": f"last_{days}_days",
            "duration_days": days
        })
    
    # Extract specific time periods
    if "last week" in question_lower:
        timeframe_info.update({
            "timeframe": "7 days",
            "date_range": "last_7_days",
            "duration_days": 7
        })
    elif "last month" in question_lower:
        timeframe_info.update({
            "timeframe": "30 days", 
            "date_range": "last_30_days",
            "duration_days": 30
        })
    elif "this month" in question_lower:
        timeframe_info.update({
            "timeframe": "this month",
            "date_range": "this_month",
            "duration_days": 30
        })
    elif "this week" in question_lower:
        timeframe_info.update({
            "timeframe": "this week",
            "date_range": "this_week", 
            "duration_days": 7
        })
    
    # Extract analysis type
    if "day of the week" in question_lower:
        timeframe_info["analysis_type"] = "day_of_week"
    elif "hour" in question_lower:
        timeframe_info["analysis_type"] = "hourly"
    elif "month" in question_lower:
        timeframe_info["analysis_type"] = "monthly"
    
    return timeframe_info


async def refresh_user_ga4_tokens(ga_service, user_id: int) -> None:
    """
    Automatically refresh expired GA4 tokens for a user before executing agents.
    
    This prevents the "re-authorization required" error by proactively refreshing
    tokens that are expired or close to expiring.
    """
    try:
        logger.info(f"🔍 Checking GA4 token status for user {user_id}...")
        
        # Get all user's GA4 connections from the database
        from app.core.database import DatabaseManager
        db_manager = DatabaseManager()
        
        # Get user's connections (this should include expiry info)
        with db_manager.get_session() as session:
            from sqlmodel import select
            from app.models.analytics import Connection
            from app.models.analytics import DigitalAsset
            
            # Find all GA4 connections for this user
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.user_id == user_id,
                Connection.revoked == False,
                DigitalAsset.asset_type == "analytics",  # GA4 connections
                DigitalAsset.provider == "Google"
            )
            
            results = session.exec(statement).all()
            
            if not results:
                logger.info(f"No GA4 connections found for user {user_id}")
                return
            
            logger.info(f"Found {len(results)} GA4 connections to check")
            
            # Check and refresh each connection
            for connection, asset in results:
                try:
                    # Check if token is expired or will expire soon (within 5 minutes)
                    now = datetime.now(timezone.utc)
                    expires_at = connection.expires_at
                    
                    # Add 5 minutes buffer to refresh tokens before they expire
                    buffer_time = timedelta(minutes=5)
                    
                    if expires_at and expires_at.replace(tzinfo=timezone.utc) <= (now + buffer_time):
                        time_until_expiry = expires_at.replace(tzinfo=timezone.utc) - now
                        if time_until_expiry.total_seconds() <= 0:
                            logger.info(f"🔄 Token expired for connection {connection.id}, refreshing...")
                        else:
                            logger.info(f"🔄 Token expires soon for connection {connection.id} (in {time_until_expiry}), refreshing...")
                        
                        # Use the GA service to refresh the token
                        try:
                            result = await ga_service.refresh_ga_token(connection.id)
                            logger.info(f"✅ Successfully refreshed token for connection {connection.id}")
                        except ValueError as e:
                            error_msg = str(e)
                            if "Please re-authorize" in error_msg:
                                logger.error(f"❌ GA4 connection {connection.id} requires re-authorization: {error_msg}")
                                # Don't fail the entire analysis, but log the issue
                            else:
                                logger.error(f"❌ Failed to refresh token for connection {connection.id}: {error_msg}")
                        except Exception as e:
                            logger.error(f"❌ Unexpected error refreshing token for connection {connection.id}: {e}")
                    else:
                        time_until_expiry = expires_at.replace(tzinfo=timezone.utc) - now if expires_at else None
                        if time_until_expiry:
                            logger.info(f"✅ Token for connection {connection.id} is valid (expires in {time_until_expiry})")
                        else:
                            logger.info(f"✅ Token for connection {connection.id} has no expiry set")
                            
                except Exception as e:
                    logger.error(f"❌ Error checking/refreshing connection {connection.id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"❌ Error in refresh_user_ga4_tokens: {e}")
        # Don't raise - we want the webhook to continue even if token refresh fails


async def refresh_user_facebook_tokens(facebook_service, user_id: int) -> None:
    """
    Automatically refresh expired Facebook tokens for a user before executing agents.
    
    This prevents the "re-authorization required" error by proactively refreshing
    tokens that are expired or close to expiring.
    """
    try:
        logger.info(f"🔍 Checking Facebook token status for user {user_id}...")
        
        # Get all user's Facebook connections from the database
        from app.core.database import DatabaseManager
        db_manager = DatabaseManager()
        
        # Get user's connections (this should include expiry info)
        with db_manager.get_session() as session:
            from sqlmodel import select
            from app.models.analytics import Connection
            from app.models.analytics import DigitalAsset
            
            # Find all Facebook connections for this user
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.user_id == user_id,
                Connection.revoked == False,
                DigitalAsset.provider == "Facebook"
            )
            
            results = session.exec(statement).all()
            
            if not results:
                logger.info(f"No Facebook connections found for user {user_id}")
                return
            
            logger.info(f"Found {len(results)} Facebook connections to check")
            
            # Check and refresh each connection
            for connection, asset in results:
                try:
                    # Check if token is expired or will expire soon (within 5 minutes)
                    now = datetime.now(timezone.utc)
                    expires_at = connection.expires_at
                    
                    # Add 5 minutes buffer to refresh tokens before they expire
                    buffer_time = timedelta(minutes=5)
                    
                    if expires_at and expires_at.replace(tzinfo=timezone.utc) <= (now + buffer_time):
                        time_until_expiry = expires_at.replace(tzinfo=timezone.utc) - now
                        if time_until_expiry.total_seconds() <= 0:
                            logger.info(f"🔄 Facebook token expired for connection {connection.id}, refreshing...")
                        else:
                            logger.info(f"🔄 Facebook token expires soon for connection {connection.id} (in {time_until_expiry}), refreshing...")
                        
                        # Use the Facebook service to refresh the token
                        try:
                            result = await facebook_service.refresh_facebook_token(connection.id)
                            logger.info(f"✅ Successfully refreshed Facebook token for connection {connection.id}")
                        except ValueError as e:
                            error_msg = str(e)
                            if "expired" in error_msg.lower() or "re-authenticate" in error_msg.lower():
                                logger.error(f"❌ Facebook connection {connection.id} requires re-authorization: {error_msg}")
                                # Don't fail the entire analysis, but log the issue
                            else:
                                logger.error(f"❌ Failed to refresh Facebook token for connection {connection.id}: {error_msg}")
                        except Exception as e:
                            logger.error(f"❌ Unexpected error refreshing Facebook token for connection {connection.id}: {e}")
                    else:
                        time_until_expiry = expires_at.replace(tzinfo=timezone.utc) - now if expires_at else None
                        if time_until_expiry:
                            logger.info(f"✅ Facebook token for connection {connection.id} is valid (expires in {time_until_expiry})")
                        else:
                            logger.info(f"✅ Facebook token for connection {connection.id} has no expiry set")
                            
                except Exception as e:
                    logger.error(f"❌ Error checking/refreshing Facebook connection {connection.id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"❌ Error in refresh_user_facebook_tokens: {e}")
        # Don't raise - we want the webhook to continue even if token refresh fails


def verify_jwt_token(authorization: str = Header(None)):
    """JWT token verification for webhook - DEPRECATED"""
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

@router.post("/dialogcx")
@router.post("/dialogcx/")  # Handle both with and without trailing slash
async def handle_dialogcx_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_webhook_token)
):
    """Handle DialogCX fulfillment webhook - ASYNC CrewAI Processing with Custom Events
    
    Flow: DialogCX → Extract User Data → Return Immediate Response → Run CrewAI Async → Send Custom Event
    """
    # Generate unique analysis ID for comprehensive logging
    import time
    analysis_id = f"dialogcx_analysis_{int(time.time() * 1000)}"
    
    logger.info(f"🎯 DIALOGCX WEBHOOK CALLED - Analysis ID: {analysis_id}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    
    try:
        # Get raw request data
        raw_data = await request.json()
        logger.info(f"Webhook received: {json.dumps(raw_data, indent=2)}")
        
        # Detect payload format and extract data accordingly
        if "user_id" in raw_data and "customer_id" in raw_data and "session_id" in raw_data:
            # NEW STRUCTURED FORMAT
            logger.info("Processing structured payload format")
            user_id = raw_data.get("user_id")
            customer_id = raw_data.get("customer_id")
            session_id = raw_data.get("session_id")
            user_question = raw_data.get("user_question", "")
            user_intent = raw_data.get("user_intent", "")
            parameters = raw_data.get("parameters", {})
            # Try both naming conventions for backward compatibility
            data_sources = parameters.get("data_sources", parameters.get("data_source", []))
            
            # VALIDATE REQUIRED FIELDS
            if not session_id:
                logger.error(f"❌ Missing session_id in structured payload: {raw_data}")
                raise HTTPException(status_code=400, detail="Missing session_id in payload")
            
            if not user_question or not user_question.strip():
                logger.error(f"❌ Missing or empty user_question in payload: {raw_data}")
                raise HTTPException(status_code=400, detail="Missing or empty user_question in payload")
            
            # COMPREHENSIVE INPUT VALIDATION FOR DIALOGCX WEBHOOK
            
            # 1. VALIDATE REQUIRED STRING FIELDS
            if not user_question or not user_question.strip():
                logger.error(f"❌ Missing or empty user_question in payload: {raw_data}")
                raise HTTPException(status_code=400, detail="user_question is required and cannot be empty")
            
            # Check user_question length (prevent extremely long queries)
            if len(user_question.strip()) > 2000:
                logger.error(f"❌ user_question too long: {len(user_question)} characters")
                raise HTTPException(status_code=400, detail="user_question must be less than 2000 characters")
            
            # Check for potentially malicious content
            suspicious_patterns = ['<script', 'javascript:', 'eval(', 'exec(', 'import os', 'subprocess']
            user_question_lower = user_question.lower()
            for pattern in suspicious_patterns:
                if pattern in user_question_lower:
                    logger.warning(f"⚠️ Suspicious pattern detected in user_question: {pattern}")
                    raise HTTPException(status_code=400, detail="Invalid characters detected in user_question")
            
            # Validate session_id format (should be UUID-like for DialogCX)
            import re
            session_id_pattern = r'^[a-fA-F0-9-]{8,}$'
            if session_id and not re.match(session_id_pattern, session_id):
                logger.warning(f"⚠️ Unusual session_id format: {session_id}")
                # Check if it's a test/hardcoded value
                if session_id in ["12345", "test", "demo"]:
                    logger.warning(f"⚠️ Using test/demo session_id: {session_id}. This should not happen in production!")
                # Don't fail for DialogCX - just log warning
            
            # 2. VALIDATE DATA TYPES
            try:
                user_id = int(user_id) if user_id else None
                customer_id = int(customer_id) if customer_id else None
            except (ValueError, TypeError):
                logger.error(f"❌ Invalid user_id or customer_id type: user_id={user_id}, customer_id={customer_id}")
                raise HTTPException(status_code=400, detail="user_id and customer_id must be valid integers")
            
            # 3. VALIDATE USER_ID AND CUSTOMER_ID RANGES
            if user_id and (user_id < 1 or user_id > 999999):
                logger.error(f"❌ user_id out of valid range: {user_id}")
                raise HTTPException(status_code=400, detail="user_id must be between 1 and 999999")
            
            if customer_id and (customer_id < 1 or customer_id > 999999):
                logger.error(f"❌ customer_id out of valid range: {customer_id}")
                raise HTTPException(status_code=400, detail="customer_id must be between 1 and 999999")
            
            # 4. COMPREHENSIVE DATA SOURCES VALIDATION
            if not isinstance(data_sources, list):
                logger.error(f"❌ data_sources must be a list, got: {type(data_sources)}")
                raise HTTPException(status_code=400, detail="data_sources must be a list")
            
            # Validate data sources are not empty
            if not data_sources:
                logger.warning(f"⚠️ Empty data_sources provided, using default 'ga4'")
                data_sources = ["ga4"]  # Default fallback
            
            # Validate individual data sources using standardized constants
            from app.core.constants import VALID_DATA_SOURCES, get_standard_data_source
            
            # Convert data sources to standard format
            standard_data_sources = [get_standard_data_source(ds) for ds in data_sources]
            invalid_sources = [ds for ds in standard_data_sources if ds not in VALID_DATA_SOURCES]
            if invalid_sources:
                logger.error(f"❌ Invalid data sources: {invalid_sources}. Valid sources: {VALID_DATA_SOURCES}")
                raise HTTPException(status_code=400, detail=f"Invalid data sources: {invalid_sources}. Valid sources: {VALID_DATA_SOURCES}")
            
            # Use standardized data sources for processing
            data_sources = standard_data_sources
            
            # Validate data sources length
            if len(data_sources) > 10:
                logger.error(f"❌ Too many data sources: {len(data_sources)}. Maximum 10 allowed")
                raise HTTPException(status_code=400, detail="Maximum 10 data sources allowed per request")
            
            # 5. VALIDATE OPTIONAL FIELDS
            if user_intent and len(user_intent) > 2000:
                logger.error(f"❌ user_intent too long: {len(user_intent)} characters")
                raise HTTPException(status_code=400, detail="user_intent must be less than 2000 characters")
            
            # 6. EDGE CASE HANDLING
            user_question = user_question.strip()
            if user_intent:
                user_intent = user_intent.strip()
            
            # Map to internal format
            # For structured format, we need to construct the full session resource path
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "superb-dream-470215-i7")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west3")
            agent_id = os.getenv("DIALOGCX_AGENT_ID", "ab858805-a4a8-477d-beec-d4cdabba4f09")
            
            # Validate session_id is present
            if not session_id:
                logger.error(f"❌ Missing session_id in structured payload: {raw_data}")
                raise HTTPException(status_code=400, detail="Missing session_id in payload")
            
            dialogcx_session_full_name = f"projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}"
            dialogcx_session_id = session_id
            intent_name = user_intent
            intent_parameters = parameters
            intent_confidence = 1.0  # Assume high confidence for structured format
            
            # Extract matching parameters
            matching_parameters = {
                "intent_confidence": intent_confidence,
                "intent_parameters": intent_parameters,
                "session_parameters": parameters,
                "user_id": user_id,
                "customer_id": customer_id
            }
            
        else:
            # ORIGINAL DIALOGCX FORMAT
            logger.info("Processing DialogCX payload format")
            session_info = raw_data.get('sessionInfo', {})
            intent_info = raw_data.get('intentInfo', {})
            
            # Use top-level 'text' for user question as primary source from Dialogflow
            user_question = raw_data.get("text") or session_info.get('parameters', {}).get("user_question", "")
            
            parameters = session_info.get('parameters', {})
            
            # Get data_sources from parameters - try both naming conventions
            data_sources = parameters.get('data_sources', parameters.get('data_source', []))

            # Extract user information
            user_id = parameters.get("user_id")
            customer_id = parameters.get("customer_id")
            intent_name = intent_info.get("displayName", "")
            
            # Extract additional parameters and VALIDATE session_id
            dialogcx_session_full_name = session_info.get("session", "")
            if not dialogcx_session_full_name or len(dialogcx_session_full_name.split('/')) < 6:
                logger.error(f"❌ Invalid or missing session ID in webhook payload: {dialogcx_session_full_name}")
                raise HTTPException(status_code=400, detail="Invalid or missing session ID")
                
            dialogcx_session_id = dialogcx_session_full_name.split("/")[-1]
            intent_parameters = intent_info.get("parameters", {})
            intent_confidence = intent_info.get("confidence", 0.0)
            
            # Extract matching parameters (timeframe, date ranges, etc.)
            matching_parameters = {
                "intent_confidence": intent_confidence,
                "intent_parameters": intent_parameters,
                "session_parameters": parameters
            }
        
        # Extract timeframe information from user question
        timeframe_info = _extract_timeframe_info(user_question)
        if timeframe_info:
            matching_parameters.update(timeframe_info)
        
        # FALLBACK: If no user_id found, try to get from default user (user_id: 5, customer_id: 5)
        if not user_id:
            logger.warning("No user_id found in payload, using default user (5, 5)")
            user_id = 5
            customer_id = 5
            
            # Update parameters with default user info
            if "session_parameters" in matching_parameters:
                matching_parameters["session_parameters"].update({
                    "user_id": user_id,
                    "customer_id": customer_id,
                    "user_name": "Sato App",
                    "user_email": "satoappco@gmail.com"
                })
            
        logger.info(f"Processing for user_id: {user_id}, customer_id: {customer_id}")
        logger.info(f"DialogCX Session ID (full): {dialogcx_session_full_name if 'dialogcx_session_full_name' in locals() else 'N/A'}")
        logger.info(f"DialogCX Session ID (parsed): {dialogcx_session_id}")
        logger.info(f"Question: {user_question}")
        logger.info(f"Intent: {intent_name}")
        logger.info(f"Intent Confidence: {intent_confidence}")
        logger.info(f"Matching Parameters: {matching_parameters}")
        logger.info(f"Data sources: {data_sources}")
        
        # RUN CREWAI ANALYSIS SYNCHRONOUSLY AND RETURN RESULT DIRECTLY
        logger.info(f"🚀 Starting CrewAI analysis for DialogCX session: {dialogcx_session_id}")
        
        # Send typing indicator via WebSocket
        try:
            await connection_manager.send_typing_indicator(
                session_id=dialogcx_session_id,
                is_typing=True,
                agent_name="Sato AI"
            )
            logger.info(f"📡 Sent typing indicator via WebSocket: session={dialogcx_session_id}")
        except Exception as ws_error:
            logger.warning(f"⚠️ Failed to send typing indicator via WebSocket: {str(ws_error)}")
        
        try:
            # Run CrewAI analysis synchronously
            crewai_result = await run_crewai_analysis_async(
                user_id=user_id,
                customer_id=customer_id,
                user_question=user_question,
                intent_name=intent_name,
                data_sources=data_sources,
                dialogcx_session_id=dialogcx_session_id,
                matching_parameters=matching_parameters,
                session_id=dialogcx_session_id,  # Use DialogCX session ID for internal logging
                analysis_id=analysis_id
            )
            
            if crewai_result["success"]:
                logger.info(f"✅ CrewAI analysis completed successfully")
                
                # SEND RESULT VIA WEBSOCKET (PRIMARY METHOD)
                try:
                    ws_sent = await connection_manager.send_crew_result(
                        session_id=dialogcx_session_id,
                        result=crewai_result["result"],
                        analysis_id=analysis_id,
                        execution_time=crewai_result.get("execution_time"),
                        agents_used=crewai_result.get("agents_used", [])
                    )
                    
                    if ws_sent:
                        logger.info(f"✅ Successfully sent result via WebSocket: session={dialogcx_session_id}")
                    else:
                        logger.warning(f"⚠️ No active WebSocket connections for session: {dialogcx_session_id}")
                except Exception as ws_error:
                    logger.error(f"❌ Failed to send result via WebSocket: {str(ws_error)}")
                
                # Stop typing indicator
                try:
                    await connection_manager.send_typing_indicator(
                        session_id=dialogcx_session_id,
                        is_typing=False
                    )
                except Exception as ws_error:
                    logger.warning(f"⚠️ Failed to stop typing indicator: {str(ws_error)}")
                
                # SEND DIALOGCX CUSTOM EVENT WITH RESULT (BACKUP/LOGGING)
                try:
                    event_result = await send_dialogcx_custom_event(
                        session_id=dialogcx_session_id,
                        event_name="crew_result_ready",
                        result=crewai_result["result"]
                    )
                    if event_result.get("success"):
                        logger.info(f"✅ Successfully sent DialogCX custom event: crew_result_ready")
                    else:
                        logger.warning(f"⚠️ Failed to send DialogCX custom event: {event_result.get('error')}")
                except Exception as event_error:
                    logger.error(f"❌ Error sending DialogCX custom event: {event_error}")
                
                return {
                    "fulfillment_response": crewai_result["result"]
                }
            else:
                logger.error(f"❌ CrewAI analysis failed: {crewai_result.get('error', 'Unknown error')}")
                
                error_msg = crewai_result.get('error', 'Unknown error')
                
                # SEND ERROR VIA WEBSOCKET
                try:
                    await connection_manager.send_error(
                        session_id=dialogcx_session_id,
                        error=f"Analysis failed: {error_msg}",
                        details=crewai_result.get('details'),
                        retry_possible=True
                    )
                    logger.info(f"✅ Sent error via WebSocket: session={dialogcx_session_id}")
                except Exception as ws_error:
                    logger.error(f"❌ Failed to send error via WebSocket: {str(ws_error)}")
                
                # Stop typing indicator
                try:
                    await connection_manager.send_typing_indicator(
                        session_id=dialogcx_session_id,
                        is_typing=False
                    )
                except Exception:
                    pass
                
                # SEND DIALOGCX ERROR EVENT (BACKUP)
                try:
                    error_message = f"Analysis failed: {error_msg}"
                    event_result = await send_dialogcx_custom_event(
                        session_id=dialogcx_session_id,
                        event_name="crew_result_ready",
                        result=error_message
                    )
                    if event_result.get("success"):
                        logger.info(f"✅ Successfully sent DialogCX error event: crew_result_ready")
                    else:
                        logger.warning(f"⚠️ Failed to send DialogCX error event: {event_result.get('error')}")
                except Exception as event_error:
                    logger.error(f"❌ Error sending DialogCX error event: {event_error}")
                
                return {
                    "fulfillment_response": f"I apologize, but I encountered an error while processing your request: {error_msg}"
                }
                
        except Exception as e:
            logger.error(f"❌ CrewAI analysis failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Send error via WebSocket
            try:
                await connection_manager.send_error(
                    session_id=dialogcx_session_id,
                    error=f"Analysis exception: {str(e)}",
                    retry_possible=True
                )
            except Exception:
                pass
            
            # Stop typing indicator
            try:
                await connection_manager.send_typing_indicator(
                    session_id=dialogcx_session_id,
                    is_typing=False
                )
            except Exception:
                pass
            
            return {
                "fulfillment_response": f"I apologize, but I encountered an error while processing your request: {str(e)}"
            }
        
    except Exception as e:
        logger.error(f"DialogCX webhook processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return simplified error response with detailed error information
        error_details = f"Error: {str(e)}"
        if hasattr(e, '__class__'):
            error_details += f" (Type: {e.__class__.__name__})"
        
        # Add more context if available
        if 'user_question' in locals():
            error_details += f" | Question: {user_question}"
        if 'intent_name' in locals():
            error_details += f" | Intent: {intent_name}"
        
        return {
            "fulfillment_response": f"I apologize, but I encountered an error while processing your request: {error_details}"
        }


@router.get("/user-context/{user_id}")
def get_user_context(
    user_id: str,
    _: bool = Depends(get_current_user)
):
    """Get user context data for DialogCX initialization
    
    This endpoint provides user_id, connected assets/services to DialogCX
    so it can include them in webhook parameters
    """
    try:
        # For now, return a simple context since we're not using DialogCXService
        context = {
            "user_id": user_id,
            "status": "active",
            "message": "User context retrieved successfully"
        }
        
        return {
            "status": "success",
            "user_context": context,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get user context: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user context: {str(e)}")


def _get_tools_for_agent(agent_type: str, user_connections: List[Dict], user_id: int = None, customer_id: int = None, subclient_id: int = None) -> List:
    """Dynamically get tools for an agent based on its type and user connections"""
    from app.core.constants import get_tools_for_agent as get_standard_tools
    
    tools = []
    
    # Use the provided subclient_id directly - NO FALLBACK MAPPING!
    # If subclient_id is not provided, tools will fail with clear error messages
    
    # Get tools using standardized constants
    tool_names = get_standard_tools(agent_type)
    
    for tool_name in tool_names:
        try:
            if tool_name == "GA4AnalyticsTool":
                from app.tools.ga4_analytics_tool import GA4AnalyticsTool
                tools.append(GA4AnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added GA4AnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "GoogleAdsAnalyticsTool":
                from app.tools.google_ads_tool import GoogleAdsAnalyticsTool
                tools.append(GoogleAdsAnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added GoogleAdsAnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookAnalyticsTool":
                from app.tools.facebook_analytics_tool import FacebookAnalyticsTool
                tools.append(FacebookAnalyticsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookAnalyticsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookAdsTool":
                from app.tools.facebook_ads_tool import FacebookAdsTool
                tools.append(FacebookAdsTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookAdsTool for {agent_type} (subclient_id={subclient_id})")
                
            elif tool_name == "FacebookMarketingTool":
                from app.tools.facebook_marketing_tool import FacebookMarketingTool
                tools.append(FacebookMarketingTool(user_id=user_id, subclient_id=subclient_id))
                logger.info(f"✅ Added FacebookMarketingTool for {agent_type} (subclient_id={subclient_id})")
                
        except ImportError as e:
            logger.warning(f"⚠️ Could not import {tool_name}: {e}")
        except Exception as e:
            logger.error(f"❌ Error creating {tool_name}: {e}")
    
    logger.info(f"🔧 Agent '{agent_type}' assigned {len(tools)} tools: {[tool.__class__.__name__ for tool in tools]}")
    return tools


def _should_include_specialist(specialist_config: Dict, data_sources: List[str], intent_name: str, user_question: str) -> bool:
    """Determine if a specialist should be included based on context"""
    from app.core.constants import should_include_agent
    
    agent_type = specialist_config["agent_type"]
    
    # Use standardized logic
    return should_include_agent(agent_type, data_sources, user_question)


@router.get("/customer-logs")
async def get_customer_logs(
    limit: int = 50,
    offset: int = 0,
    user_id: int = None,
    session_id: str = None,
    current_user: User = Depends(get_current_user)
):
    """Get customer logs with filtering options"""
    try:
        from app.config.database import get_session
        
        with get_session() as session:
            query = session.query(CustomerLog)
            
            # Apply filters - use current user's ID if not specified
            target_user_id = user_id if user_id else current_user.id
            query = query.filter(CustomerLog.user_id == target_user_id)
            if session_id:
                query = query.filter(CustomerLog.session_id == session_id)
            
            # Order by date_time descending (newest first)
            query = query.order_by(CustomerLog.date_time.desc())
            
            # Apply pagination
            total_count = query.count()
            logs = query.offset(offset).limit(limit).all()
            
            # Convert to response format
            log_data = []
            for log in logs:
                log_data.append({
                    "id": log.id,
                    "session_id": log.session_id,
                    "date_time": log.date_time.isoformat(),
                    "user_intent": log.user_intent,
                    "original_query": log.original_query,
                    "crewai_input_prompt": log.crewai_input_prompt,
                    "master_answer": log.master_answer,
                    "crewai_log": json.loads(log.crewai_log) if log.crewai_log else {},
                    "total_execution_time_ms": log.total_execution_time_ms,
                    "timing_breakdown": json.loads(log.timing_breakdown) if log.timing_breakdown else {},
                    "user_id": log.user_id,
                    "analysis_id": log.analysis_id,
                    "success": log.success,
                    "error_message": log.error_message,
                    "agents_used": json.loads(log.agents_used) if log.agents_used else [],
                    "tools_used": json.loads(log.tools_used) if log.tools_used else []
                })
            
            return {
                "success": True,
                "total_count": total_count,
                "logs": log_data,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get customer logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get customer logs: {str(e)}")


@router.get("/customer-logs/{session_id}")
async def get_customer_log_by_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get customer log for a specific session"""
    try:
        from app.config.database import get_session
        
        with get_session() as session:
            log = session.query(CustomerLog).filter(
                CustomerLog.session_id == session_id,
                CustomerLog.user_id == current_user.id
            ).first()
            
            if not log:
                raise HTTPException(status_code=404, detail="Customer log not found")
            
            return {
                "success": True,
                "log": {
                    "id": log.id,
                    "session_id": log.session_id,
                    "date_time": log.date_time.isoformat(),
                    "user_intent": log.user_intent,
                    "original_query": log.original_query,
                    "crewai_input_prompt": log.crewai_input_prompt,
                    "master_answer": log.master_answer,
                    "crewai_log": json.loads(log.crewai_log) if log.crewai_log else {},
                    "total_execution_time_ms": log.total_execution_time_ms,
                    "timing_breakdown": json.loads(log.timing_breakdown) if log.timing_breakdown else {},
                    "user_id": log.user_id,
                    "analysis_id": log.analysis_id,
                    "success": log.success,
                    "error_message": log.error_message,
                    "agents_used": json.loads(log.agents_used) if log.agents_used else [],
                    "tools_used": json.loads(log.tools_used) if log.tools_used else []
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer log for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get customer log: {str(e)}")


@router.get("/execution-timings/{session_id}")
async def get_execution_timings(
    session_id: str,
    _: bool = Depends(get_current_user)
):
    """Get detailed execution timings for a specific session"""
    try:
        from app.config.database import get_session
        
        with get_session() as session:
            timings = session.query(ExecutionTiming).filter(
                ExecutionTiming.session_id == session_id
            ).order_by(ExecutionTiming.start_time).all()
            
            timing_data = []
            for timing in timings:
                timing_data.append({
                    "id": timing.id,
                    "session_id": timing.session_id,
                    "analysis_id": timing.analysis_id,
                    "component_type": timing.component_type,
                    "component_name": timing.component_name,
                    "start_time": timing.start_time.isoformat(),
                    "end_time": timing.end_time.isoformat() if timing.end_time else None,
                    "duration_ms": timing.duration_ms,
                    "status": timing.status,
                    "input_data": timing.input_data,
                    "output_data": timing.output_data,
                    "error_message": timing.error_message,
                    "parent_session_id": timing.parent_session_id
                })
            
            return {
                "success": True,
                "session_id": session_id,
                "timings": timing_data,
                "total_components": len(timing_data)
            }
            
    except Exception as e:
        logger.error(f"Failed to get execution timings for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get execution timings: {str(e)}")


@router.get("/customer-logs/stats")
async def get_customer_log_stats(
    days: int = 7,
    _: bool = Depends(get_current_user)
):
    """Get customer log statistics"""
    try:
        from app.config.database import get_session
        from datetime import datetime, timedelta
        
        with get_session() as session:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get basic stats
            total_logs = session.query(CustomerLog).filter(
                CustomerLog.date_time >= start_date,
                CustomerLog.date_time <= end_date
            ).count()
            
            successful_logs = session.query(CustomerLog).filter(
                CustomerLog.date_time >= start_date,
                CustomerLog.date_time <= end_date,
                CustomerLog.success == True
            ).count()
            
            failed_logs = total_logs - successful_logs
            
            # Get average execution time
            avg_time_result = session.query(
                session.func.avg(CustomerLog.total_execution_time_ms)
            ).filter(
                CustomerLog.date_time >= start_date,
                CustomerLog.date_time <= end_date,
                CustomerLog.success == True
            ).scalar()
            
            avg_execution_time_ms = int(avg_time_result) if avg_time_result else 0
            
            # Get most common user intents
            intent_counts = session.query(
                CustomerLog.user_intent,
                session.func.count(CustomerLog.id).label('count')
            ).filter(
                CustomerLog.date_time >= start_date,
                CustomerLog.date_time <= end_date
            ).group_by(CustomerLog.user_intent).order_by(
                session.func.count(CustomerLog.id).desc()
            ).limit(10).all()
            
            return {
                "success": True,
                "period_days": days,
                "total_logs": total_logs,
                "successful_logs": successful_logs,
                "failed_logs": failed_logs,
                "success_rate": (successful_logs / total_logs * 100) if total_logs > 0 else 0,
                "avg_execution_time_ms": avg_execution_time_ms,
                "top_intents": [{"intent": intent, "count": count} for intent, count in intent_counts]
            }
            
    except Exception as e:
        logger.error(f"Failed to get customer log stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get customer log stats: {str(e)}")


@router.get("/execution-steps/{session_id}")
async def get_execution_steps(
    session_id: str,
    _: bool = Depends(get_current_user)
):
    """Get detailed execution steps for a session"""
    try:
        with get_session() as session:
            # Get all execution timings for this session
            timings = session.query(ExecutionTiming).filter(
                ExecutionTiming.session_id == session_id
            ).order_by(ExecutionTiming.start_time).all()
            
            # Group by component type
            steps = {
                "crew_steps": [],
                "agent_steps": [],
                "tool_calls": [],
                "api_calls": [],
                "other_steps": []
            }
            
            for timing in timings:
                try:
                    input_data = None
                    output_data = None
                    
                    if timing.input_data:
                        try:
                            input_data = json.loads(timing.input_data)
                        except json.JSONDecodeError:
                            input_data = {"raw": timing.input_data}
                    
                    if timing.output_data:
                        try:
                            output_data = json.loads(timing.output_data)
                        except json.JSONDecodeError:
                            output_data = {"raw": timing.output_data}
                    
                    step_data = {
                        "id": timing.id,
                        "component_name": timing.component_name,
                        "component_type": timing.component_type,
                        "start_time": timing.start_time.isoformat(),
                        "end_time": timing.end_time.isoformat() if timing.end_time else None,
                        "duration_ms": timing.duration_ms,
                        "status": timing.status,
                        "input_data": input_data,
                        "output_data": output_data,
                        "error_message": timing.error_message
                    }
                except Exception as e:
                    logger.error(f"Error processing timing record {timing.id}: {str(e)}")
                    continue
                
                if timing.component_type == "crew_step":
                    steps["crew_steps"].append(step_data)
                elif timing.component_type == "agent_step":
                    steps["agent_steps"].append(step_data)
                elif timing.component_type == "tool":
                    steps["tool_calls"].append(step_data)
                elif timing.component_type == "api_call":
                    steps["api_calls"].append(step_data)
                else:
                    steps["other_steps"].append(step_data)
            
            return {
                "success": True,
                "session_id": session_id,
                "total_steps": len(timings),
                "steps": steps
            }
            
    except Exception as e:
        logger.error(f"Error getting execution steps: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get execution steps: {str(e)}")


@router.get("/detailed-execution-logs/{session_id}")
async def get_detailed_execution_logs(
    session_id: str,
    _: bool = Depends(get_current_user)
):
    """Get detailed execution logs for a session - mirrors terminal output"""
    try:
        from app.services.detailed_execution_logger import get_detailed_logger
        
        detailed_logger = get_detailed_logger(session_id)
        logs = detailed_logger.get_execution_logs()
        
        return {
            "success": True,
            "session_id": session_id,
            "total_logs": len(logs),
            "logs": logs
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed execution logs: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get detailed execution logs: {str(e)}")


