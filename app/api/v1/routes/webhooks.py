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


# Import the centralized function from utils
from app.utils.agent_utils import get_tools_for_agent


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
            role=master_agent_data["name"],  # Use name field for short, clean agent role
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
        
        # Master agent will use its DateConversionTool naturally during task execution
        
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
        specialist_tasks = []  # Track specialist tasks to set context
        
        for specialist_data in specialist_agents_data:
            # Only include relevant specialists
            if not _should_include_specialist(specialist_data, data_sources, intent_name, user_question):
                logger.info(f"Skipping specialist: {specialist_data['name']} (not relevant for this request)")
                continue
                
            agent_type = specialist_data["agent_type"]
            
            # Get tools for this agent dynamically
            # Note: customer_id in this context is actually subclient_id
            agent_tools = get_tools_for_agent(agent_type, user_connections, user_id=user_id, customer_id=customer_id, subclient_id=customer_id)
            
            # Create specialist agent using ONLY database configuration with timing
            specialist_agent = timing_wrapper.create_timed_agent(
                role=specialist_data["name"],  # Use name field for short, clean agent role
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
                    user_id=user_id,
                    customer_id=customer_id,
                    intent_name=intent_name,
                    data_sources=", ".join(data_sources),
                    data_source=", ".join(data_sources),  # Support both naming conventions
                    date_range="as specified in the user question",
                    timezone="UTC",
                    currency="USD",
                    attribution_window="30d"
                )
            else:
                # Fallback if no task in database
                specialist_task_description = f"Analyze {agent_type} data for: {user_question}"
            
            # CRITICAL FIX: Set context=[master_task] so specialist output feeds back to master
            specialist_task = Task(
                description=specialist_task_description,
                agent=specialist_agent,
                expected_output=f"Detailed {specialist_data['agent_type']} analysis following the specialist reply schema",
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




# Import token refresh functions from utils
from app.utils.token_utils import refresh_user_ga4_tokens, refresh_user_facebook_tokens


def _should_include_specialist(specialist_config: Dict, data_sources: List[str], intent_name: str, user_question: str) -> bool:
    """Determine if a specialist should be included based on context"""
    from app.core.constants import should_include_agent
    
    agent_type = specialist_config["agent_type"]
    
    # Use standardized logic
    return should_include_agent(agent_type, data_sources, user_question)


@router.get("/customer-logs")
async def get_customer_logs(
    limit: int = 5,
    offset: int = 0,
    user_id: int = None,
    session_id: str = None,
    current_user: User = Depends(get_current_user)
):
    """Get customer logs with filtering options - Used by frontend LogsViewer"""
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
                    "agents_used": [agent.get('name', agent) if isinstance(agent, dict) else str(agent) for agent in (json.loads(log.agents_used) if log.agents_used else [])],
                    "tools_used": json.loads(log.tools_used) if log.tools_used else []
                })
            
            return {
                "success": True,
                "total_count": total_count,
                "logs": log_data,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count,
                    "total_pages": (total_count + limit - 1) // limit,
                    "current_page": (offset // limit) + 1,
                    "total_count": total_count
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get customer logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get customer logs: {str(e)}")


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
            
            # Validate session ID - must be a real DialogCX session ID
            if not session_id or session_id.strip() == "":
                logger.error(f"❌ Empty or invalid session_id in payload: {raw_data}")
                raise HTTPException(status_code=400, detail="session_id cannot be empty")
            
            logger.info(f"📋 Using DialogCX session ID: {session_id}")
            
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
            from app.core.constants import VALID_DATA_SOURCES, validate_data_sources, get_data_source_suggestions
            
            # Validate and standardize data sources
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
                raise HTTPException(status_code=400, detail=error_message)
            
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
            
            # Validate session ID - must be a real DialogCX session ID
            if not dialogcx_session_id or dialogcx_session_id.strip() == "":
                logger.error(f"❌ Empty or invalid session_id from DialogCX: {dialogcx_session_full_name}")
                raise HTTPException(status_code=400, detail="Invalid DialogCX session ID")
            
            logger.info(f"📋 Using DialogCX session ID (legacy): {dialogcx_session_id}")
            
            intent_parameters = intent_info.get("parameters", {})
            intent_confidence = intent_info.get("confidence", 0.0)
            
            # Extract matching parameters (timeframe, date ranges, etc.)
            matching_parameters = {
                "intent_confidence": intent_confidence,
                "intent_parameters": intent_parameters,
                "session_parameters": parameters
            }
        
        # Master agent will handle date extraction using its DateConversionTool
        # No need for hardcoded regex patterns - let the LLM handle it naturally
        
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