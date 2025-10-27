"""
CrewAI Timing Wrapper
Wraps CrewAI components to automatically track timing and create detailed logs
"""

import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM

from app.services.execution_timing_service import timing_service
from app.services.detailed_execution_logger import get_detailed_logger, cleanup_detailed_logger
from app.config.logging import get_logger

logger = get_logger("services.crewai_timing")


class TimedAgent(Agent):
    """Agent wrapper with automatic timing and detailed logging"""
    
    def __init__(self, session_id: str, analysis_id: str = None, **kwargs):
        super().__init__(**kwargs)
        # Store session info in a way that doesn't conflict with Pydantic
        self._session_id = session_id
        self._analysis_id = analysis_id
        self._timing_id = None
        self._execution_steps = []
        self._tools_used = []
        self._detailed_logger = get_detailed_logger(session_id, analysis_id)
        
        # Extract clean agent name from role (take first 50 chars or first sentence)
        self._clean_name = self._extract_clean_name(self.role)
    
    def _extract_clean_name(self, role: str) -> str:
        """Extract clean, short name from agent role"""
        if not role:
            return "Unknown Agent"
        
        # Take first sentence or first 50 characters
        if '.' in role:
            clean_name = role.split('.')[0].strip()
        elif ',' in role:
            clean_name = role.split(',')[0].strip()
        else:
            clean_name = role[:50].strip()
        
        return clean_name if clean_name else role[:50]
    
    def execute_task(self, task: Task, context: Dict[str, Any] = None, tools: List = None) -> str:
        """Execute task with detailed timing and step-by-step logging"""
        with timing_service.time_component(
            session_id=self._session_id,
            component_type="agent",
            component_name=self._clean_name,  # Use clean name instead of full role
            input_data=task.description,
            analysis_id=self._analysis_id
        ) as timing_id:
            self._timing_id = timing_id
            logger.info(f"🤖 Agent {self.role} starting task: {task.description[:100]}...")
            
            # Get tools from agent's tools attribute if not provided
            if tools is None:
                tools = getattr(self, 'tools', [])
            
            # Debug logging to understand tool execution
            logger.info(f"🔍 Agent {self.role} - Tools available: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]}")
            
            # Check if this agent has tools and try to intercept at a different level
            if tools:
                logger.info(f"🔧 Agent {self.role} will execute with {len(tools)} tools")
                
                # Log agent start with detailed logger
                self._detailed_logger.log_agent_start(
                    agent_name=self.role,
                    task_description=task.description
                )
                
                # Also log to old system for backward compatibility
                self._log_step("agent_start", {
                    "agent_role": self.role,
                    "task_description": task.description,
                    "task_expected_output": getattr(task, 'expected_output', 'Not specified'),
                    "tools_available": [tool.name if hasattr(tool, 'name') else str(tool) for tool in tools],
                    "context_keys": list(context.keys()) if context and isinstance(context, dict) else []
                })
                
                try:
                    # Monkey patch tools to capture their execution
                    if tools:
                        self._patch_tools(tools)
                        logger.info(f"🔧 Patched {len(tools)} tools for agent {self.role}")
                    
                    # Call parent execute_task with all parameters
                    if tools:
                        result = super().execute_task(task, context, tools)
                    else:
                        result = super().execute_task(task, context)
                    
                    # Analyze result to infer tool execution
                    tool_analysis = self._analyze_result_for_tool_execution(str(result), tools)
                    
                    # Log agent final answer with detailed logger
                    self._detailed_logger.log_agent_final_answer(
                        agent_name=self.role,
                        final_answer=str(result)
                    )
                    
                    # Log agent completion with tool usage summary (old system)
                    self._log_step("agent_complete", {
                        "agent_role": self.role,
                        "result_length": len(str(result)) if result else 0,
                        "result_preview": str(result)[:200] + "..." if result and len(str(result)) > 200 else str(result),
                        "tools_used": self._tools_used,
                        "total_tools_called": len(self._tools_used),
                        "successful_tools": len([t for t in self._tools_used if t.get('success', False)]),
                        "failed_tools": len([t for t in self._tools_used if not t.get('success', True)]),
                        "inferred_tool_execution": tool_analysis
                    })
                    
                    logger.info(f"✅ Agent {self.role} completed task using {len(self._tools_used)} tools")
                    return result
                except Exception as e:
                    # Log agent error
                    self._log_step("agent_error", {
                        "agent_role": self.role,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "tools_used": self._tools_used
                    })
                    logger.error(f"❌ Agent {self.role} failed: {str(e)}")
                    raise
    
    def _log_step(self, step_type: str, data: Dict[str, Any]):
        """Log a detailed execution step"""
        step = {
            "timestamp": datetime.utcnow().isoformat(),
            "step_type": step_type,
            "agent_role": self.role,
            "data": data
        }
        self._execution_steps.append(step)
        
        # Determine component type based on step type
        component_type = "agent_step"
        if "tool" in step_type.lower():
            component_type = "tool_call"
        elif "api" in step_type.lower():
            component_type = "api_call"
        elif "thinking" in step_type.lower() or "reasoning" in step_type.lower():
            component_type = "thinking"
        elif "error" in step_type.lower():
            component_type = "error"
        
        # Also log to timing service for database storage
        timing_service.log_detailed_step(
            session_id=self._session_id,
            component_type=component_type,
            component_name=f"{self.role}_{step_type}",
            step_data=step,
            analysis_id=self._analysis_id
        )
    
    def _patch_tools(self, tools):
        """Monkey patch tools to capture their execution details"""
        for tool in tools:
            tool_name = getattr(tool, 'name', str(tool))
            
            # Store original function
            if hasattr(tool, '_func'):
                original_func = tool._func
            elif hasattr(tool, 'func'):
                original_func = tool.func
            else:
                original_func = tool
            
            # Create patched function
            def create_patched_func(orig_func, t_name):
                def patched_func(*args, **kwargs):
                    tool_start = datetime.utcnow()
                    
                    logger.info(f"🔧 Tool {t_name} called by agent {self.role}")
                    
                    # Log tool execution start with detailed logger
                    tool_input = json.dumps(kwargs) if kwargs else str(args)[:500] if args else None
                    self._detailed_logger.log_tool_execution_start(
                        agent_name=self.role,
                        tool_name=t_name,
                        tool_input=tool_input
                    )
                    
                    # Log tool input details
                    if tool_input:
                        self._detailed_logger.log_tool_input(t_name, tool_input)
                    
                    # Log tool start (old system)
                    self._log_step("tool_start", {
                        "tool_name": t_name,
                        "agent_role": self.role,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()) if kwargs else [],
                        "args_preview": str(args)[:100] if args else "None"
                    })
                    
                    try:
                        # Execute the tool WITH TIMING to ExecutionTiming table
                        with timing_service.time_component(
                            session_id=self._session_id,
                            component_type="tool",
                            component_name=t_name,
                            input_data=tool_input,
                            analysis_id=self._analysis_id
                        ):
                            result = orig_func(*args, **kwargs)
                        
                        tool_end = datetime.utcnow()
                        duration_ms = int((tool_end - tool_start).total_seconds() * 1000)
                        
                        # Parse result to extract meaningful data
                        result_data = self._parse_tool_result(t_name, result)
                        
                        # Log tool output with detailed logger
                        tool_output = str(result)[:1000] + "..." if result and len(str(result)) > 1000 else str(result)
                        self._detailed_logger.log_tool_output(t_name, tool_output, duration_ms)
                        
                        # Track tool usage
                        self._tools_used.append({
                            "tool_name": t_name,
                            "duration_ms": duration_ms,
                            "success": True,
                            "start_time": tool_start.isoformat(),
                            "end_time": tool_end.isoformat(),
                            "result_data": result_data
                        })
                        
                        logger.info(f"✅ Tool {t_name} completed in {duration_ms}ms - {result_data.get('data_points', 0)} data points")
                        return result
                        
                    except Exception as e:
                        tool_end = datetime.utcnow()
                        duration_ms = int((tool_end - tool_start).total_seconds() * 1000)
                        
                        # Parse error to extract meaningful details
                        error_data = self._parse_tool_error(t_name, e)
                        
                        # Log tool error with detailed logger
                        self._detailed_logger.log_tool_error(
                            agent_name=self.role,
                            tool_name=t_name,
                            error_message=str(e),
                            tool_input=tool_input
                        )
                        
                        # Log tool error with detailed information (old system)
                        self._log_step("tool_error", {
                            "tool_name": t_name,
                            "agent_role": self.role,
                            "duration_ms": duration_ms,
                            "success": False,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "error_details": error_data,
                            "api_error": error_data.get("api_error"),
                            "error_code": error_data.get("error_code"),
                            "suggestion": error_data.get("suggestion")
                        })
                        
                        # Track tool usage
                        self._tools_used.append({
                            "tool_name": t_name,
                            "duration_ms": duration_ms,
                            "success": False,
                            "error": str(e),
                            "start_time": tool_start.isoformat(),
                            "end_time": tool_end.isoformat(),
                            "error_data": error_data
                        })
                        
                        logger.error(f"❌ Tool {t_name} failed after {duration_ms}ms: {str(e)}")
                        raise
                
                return patched_func
            
            # Apply the patch
            patched_func = create_patched_func(original_func, tool_name)
            
            if hasattr(tool, '_func'):
                tool._func = patched_func
            elif hasattr(tool, 'func'):
                tool.func = patched_func
            else:
                # For tools that are functions directly
                tool.__call__ = patched_func
    
    def get_execution_steps(self) -> List[Dict[str, Any]]:
        """Get detailed execution steps for this agent"""
        return self._execution_steps
    
    def get_tools_used(self) -> List[Dict[str, Any]]:
        """Get tools used by this agent"""
        return self._tools_used
    
    def _analyze_result_for_tool_execution(self, result_str: str, tools: List) -> Dict[str, Any]:
        """Analyze agent result to infer what tools were actually executed"""
        analysis = {
            "tools_detected": [],
            "total_inferred_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0
        }
        
        if not tools:
            return analysis
        
        for tool in tools:
            tool_name = getattr(tool, 'name', str(tool))
            tool_info = {
                "tool_name": tool_name,
                "called": False,
                "success": False,
                "error_details": None,
                "data_found": False
            }
            
            # Analyze based on tool type
            if "GA4" in tool_name:
                if any(keyword in result_str.lower() for keyword in ["conversions", "sessions", "ga4", "revenue"]):
                    tool_info["called"] = True
                    tool_info["success"] = True
                    tool_info["data_found"] = True
                    analysis["successful_calls"] += 1
                    
            elif "Google_Ads" in tool_name:
                if "google ads data was unavailable" in result_str.lower():
                    tool_info["called"] = True
                    tool_info["success"] = False
                    tool_info["error_details"] = "API error - data unavailable"
                    analysis["failed_calls"] += 1
                elif any(keyword in result_str.lower() for keyword in ["google ads", "cost", "clicks", "impressions"]):
                    tool_info["called"] = True
                    # Check if it's real data or demo data
                    if "demo data" in result_str.lower():
                        tool_info["success"] = False
                        tool_info["error_details"] = "API failed, returned demo data"
                        analysis["failed_calls"] += 1
                    else:
                        tool_info["success"] = True
                        tool_info["data_found"] = True
                        analysis["successful_calls"] += 1
                        
            elif "Facebook" in tool_name:
                if any(keyword in result_str.lower() for keyword in ["facebook", "reach", "spend", "meta"]):
                    tool_info["called"] = True
                    tool_info["success"] = True
                    tool_info["data_found"] = True
                    analysis["successful_calls"] += 1
            
            if tool_info["called"]:
                analysis["total_inferred_calls"] += 1
                analysis["tools_detected"].append(tool_info)
        
        return analysis
    
    def _parse_tool_result(self, tool_name: str, result: Any) -> Dict[str, Any]:
        """Parse tool result to extract meaningful data"""
        try:
            result_str = str(result)
            
            # Parse based on tool type
            if "GA4" in tool_name:
                return self._parse_ga4_result(result_str)
            elif "Google_Ads" in tool_name:
                return self._parse_google_ads_result(result_str)
            elif "Facebook" in tool_name:
                return self._parse_facebook_result(result_str)
            else:
                return self._parse_generic_result(result_str)
                
        except Exception as e:
            logger.error(f"Error parsing tool result for {tool_name}: {str(e)}")
            return {"error": f"Failed to parse result: {str(e)}"}
    
    def _parse_ga4_result(self, result_str: str) -> Dict[str, Any]:
        """Parse GA4 tool result"""
        try:
            # Try to extract data points and metrics
            data_points = 0
            metrics = []
            
            if "conversions" in result_str.lower():
                data_points += 1
                metrics.append("conversions")
            if "sessions" in result_str.lower():
                data_points += 1
                metrics.append("sessions")
            if "revenue" in result_str.lower():
                data_points += 1
                metrics.append("revenue")
            
            return {
                "api_response": "GA4 data retrieved successfully",
                "data_points": data_points,
                "metrics_found": metrics,
                "success": True
            }
        except Exception as e:
            return {"error": f"Failed to parse GA4 result: {str(e)}"}
    
    def _parse_google_ads_result(self, result_str: str) -> Dict[str, Any]:
        """Parse Google Ads tool result"""
        try:
            # Check if this is demo data (fallback when API fails)
            if "demo data" in result_str.lower() or "b2b system" in result_str.lower():
                return {
                    "api_response": "Google Ads API failed - returned demo data",
                    "data_points": 0,
                    "success": False,
                    "error_details": "Real API failed, tool returned demo data as fallback",
                    "is_demo_data": True
                }
            elif "error" in result_str.lower() or "failed" in result_str.lower():
                return {
                    "api_response": "Google Ads API error",
                    "data_points": 0,
                    "success": False,
                    "error_details": result_str
                }
            else:
                data_points = 0
                metrics = []
                
                if "clicks" in result_str.lower():
                    data_points += 1
                    metrics.append("clicks")
                if "impressions" in result_str.lower():
                    data_points += 1
                    metrics.append("impressions")
                if "cost" in result_str.lower():
                    data_points += 1
                    metrics.append("cost")
                
                return {
                    "api_response": "Google Ads data retrieved successfully",
                    "data_points": data_points,
                    "metrics_found": metrics,
                    "success": True,
                    "is_demo_data": False
                }
        except Exception as e:
            return {"error": f"Failed to parse Google Ads result: {str(e)}"}
    
    def _parse_facebook_result(self, result_str: str) -> Dict[str, Any]:
        """Parse Facebook tool result"""
        try:
            data_points = 0
            metrics = []
            
            if "reach" in result_str.lower():
                data_points += 1
                metrics.append("reach")
            if "impressions" in result_str.lower():
                data_points += 1
                metrics.append("impressions")
            if "spend" in result_str.lower():
                data_points += 1
                metrics.append("spend")
            
            return {
                "api_response": "Facebook data retrieved successfully",
                "data_points": data_points,
                "metrics_found": metrics,
                "success": True
            }
        except Exception as e:
            return {"error": f"Failed to parse Facebook result: {str(e)}"}
    
    def _parse_generic_result(self, result_str: str) -> Dict[str, Any]:
        """Parse generic tool result"""
        return {
            "api_response": "Tool executed successfully",
            "data_points": 1 if result_str else 0,
            "success": True,
            "result_length": len(result_str)
        }
    
    def _parse_tool_error(self, tool_name: str, error: Exception) -> Dict[str, Any]:
        """Parse tool error to extract meaningful details"""
        try:
            error_str = str(error)
            
            # Parse based on tool type
            if "GA4" in tool_name:
                return self._parse_ga4_error(error_str)
            elif "Google_Ads" in tool_name:
                return self._parse_google_ads_error(error_str)
            elif "Facebook" in tool_name:
                return self._parse_facebook_error(error_str)
            else:
                return self._parse_generic_error(error_str)
                
        except Exception as e:
            logger.error(f"Error parsing tool error for {tool_name}: {str(e)}")
            return {"error": f"Failed to parse error: {str(e)}"}
    
    def _parse_ga4_error(self, error_str: str) -> Dict[str, Any]:
        """Parse GA4 tool error"""
        if "authentication" in error_str.lower():
            return {
                "api_error": "Authentication failed",
                "error_code": "AUTH_ERROR",
                "suggestion": "Check GA4 credentials and permissions"
            }
        elif "quota" in error_str.lower():
            return {
                "api_error": "Quota exceeded",
                "error_code": "QUOTA_ERROR",
                "suggestion": "Wait for quota reset or upgrade plan"
            }
        else:
            return {
                "api_error": "GA4 API error",
                "error_code": "API_ERROR",
                "suggestion": "Check GA4 API status and parameters"
            }
    
    def _parse_google_ads_error(self, error_str: str) -> Dict[str, Any]:
        """Parse Google Ads tool error"""
        if "authentication" in error_str.lower():
            return {
                "api_error": "Authentication failed",
                "error_code": "AUTH_ERROR",
                "suggestion": "Check Google Ads credentials and OAuth tokens"
            }
        elif "quota" in error_str.lower():
            return {
                "api_error": "Quota exceeded",
                "error_code": "QUOTA_ERROR",
                "suggestion": "Wait for quota reset or upgrade plan"
            }
        elif "row_count" in error_str.lower():
            return {
                "api_error": "Row count error",
                "error_code": "ROW_COUNT_ERROR",
                "suggestion": "Check date range and filters - no data available for specified period"
            }
        else:
            return {
                "api_error": "Google Ads API error",
                "error_code": "API_ERROR",
                "suggestion": "Check Google Ads API status and parameters"
            }
    
    def _parse_facebook_error(self, error_str: str) -> Dict[str, Any]:
        """Parse Facebook tool error"""
        if "authentication" in error_str.lower():
            return {
                "api_error": "Authentication failed",
                "error_code": "AUTH_ERROR",
                "suggestion": "Check Facebook credentials and access tokens"
            }
        else:
            return {
                "api_error": "Facebook API error",
                "error_code": "API_ERROR",
                "suggestion": "Check Facebook API status and parameters"
            }
    
    def _parse_generic_error(self, error_str: str) -> Dict[str, Any]:
        """Parse generic tool error"""
        return {
            "api_error": "Tool execution failed",
            "error_code": "TOOL_ERROR",
            "suggestion": "Check tool configuration and parameters"
        }


class TimedCrew(Crew):
    """Crew wrapper with automatic timing and detailed logging"""
    
    def __init__(self, session_id: str, analysis_id: str = None, **kwargs):
        super().__init__(**kwargs)
        # Store session info in a way that doesn't conflict with Pydantic
        self._session_id = session_id
        self._analysis_id = analysis_id
        self._execution_log = []
        self._detailed_logger = get_detailed_logger(session_id, analysis_id)
    
    def kickoff(self, inputs: Dict[str, Any] = None) -> Any:
        """Execute crew with comprehensive timing and detailed logging"""
        start_time = datetime.utcnow()
        
        logger.info(f"🚀 Starting CrewAI execution for session {self._session_id}")
        logger.info(f"Agents: {[agent.role for agent in self.agents]}")
        logger.info(f"Tasks: {[task.description[:50] + '...' for task in self.tasks]}")
        
        # Log crew start with detailed logger
        agent_names = [agent.role for agent in self.agents]
        task_descriptions = [task.description for task in self.tasks]
        self._detailed_logger.log_crew_start(
            crew_name="crew",
            agents=agent_names,
            tasks=task_descriptions,
            process=str(self.process)
        )
        
        # Log crew start with detailed information (old system)
        crew_start_data = {
            'timestamp': start_time.isoformat(),
            'event': 'crew_started',
            'agents': [{
                'role': agent.role,
                'goal': getattr(agent, 'goal', 'Not specified'),
                'backstory': getattr(agent, 'backstory', 'Not specified')[:100] + '...' if getattr(agent, 'backstory', '') else 'Not specified',
                'verbose': getattr(agent, 'verbose', False),
                'allow_delegation': getattr(agent, 'allow_delegation', False)
            } for agent in self.agents],
            'tasks': [{
                'description': task.description,
                'expected_output': getattr(task, 'expected_output', 'Not specified'),
                'agent': getattr(task, 'agent', 'Not assigned').role if hasattr(getattr(task, 'agent', None), 'role') else str(getattr(task, 'agent', 'Not assigned'))
            } for task in self.tasks],
            'process': str(self.process),
            'inputs': inputs
        }
        
        self._execution_log.append(crew_start_data)
        
        # Log to timing service
        timing_service.log_detailed_step(
            session_id=self._session_id,
            component_type="crew_step",
            component_name="crew_start",
            step_data=crew_start_data,
            analysis_id=self._analysis_id
        )
        
        try:
            # Execute with timing
            with timing_service.time_component(
                session_id=self._session_id,
                component_type="crew",
                component_name="CrewAI_Execution",
                input_data=json.dumps({
                    'agents': [agent.role for agent in self.agents],
                    'tasks': [task.description for task in self.tasks],
                    'process': str(self.process)
                }),
                analysis_id=self._analysis_id
            ):
                result = super().kickoff(inputs)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Log crew completion with detailed logger
            self._detailed_logger.log_crew_complete(
                crew_name="crew",
                final_output=str(result),
                duration_seconds=duration
            )
            
            # Log crew completion summary to execution log
            crew_complete_data = {
                'timestamp': end_time.isoformat(),
                'event': 'crew_completed',
                'duration_seconds': duration,
                'success': True,
                'result_length': len(str(result)) if result else 0,
                'result_preview': str(result)[:200] + "..." if result and len(str(result)) > 200 else str(result)
            }
            
            self._execution_log.append(crew_complete_data)
            
            # REMOVED: log_detailed_step() was creating duplicate ExecutionTiming records
            # The timing_service.time_component() context manager already creates the timing record
            
            logger.info(f"✅ CrewAI execution completed in {duration:.2f} seconds")
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Log crew error with detailed logger
            self._detailed_logger.log_crew_error(
                crew_name="crew",
                error_message=str(e),
                duration_seconds=duration
            )
            
            # Log crew error summary to execution log
            crew_error_data = {
                'timestamp': end_time.isoformat(),
                'event': 'crew_error',
                'duration_seconds': duration,
                'error': str(e),
                'error_type': type(e).__name__,
                'success': False
            }
            
            self._execution_log.append(crew_error_data)
            
            # REMOVED: log_detailed_step() was creating duplicate ExecutionTiming records
            # The timing_service.time_component() context manager already handles error logging
            
            logger.error(f"❌ CrewAI execution failed after {duration:.2f} seconds: {str(e)}")
            raise
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get detailed execution log"""
        return self._execution_log


class CrewAITimingWrapper:
    """Main wrapper for CrewAI with timing integration"""
    
    def __init__(self, session_id: str, analysis_id: str = None):
        self.session_id = session_id
        self.analysis_id = analysis_id
        self.timing_service = timing_service
    
    def create_timed_agent(self, **agent_kwargs) -> TimedAgent:
        """Create a timed agent"""
        return TimedAgent(
            session_id=self.session_id,
            analysis_id=self.analysis_id,
            **agent_kwargs
        )
    
    def create_timed_crew(self, agents: List[TimedAgent], tasks: List[Task], 
                         process: Process = Process.sequential, verbose: bool = True) -> TimedCrew:
        """Create a timed crew"""
        return TimedCrew(
            session_id=self.session_id,
            analysis_id=self.analysis_id,
            agents=agents,
            tasks=tasks,
            process=process,
            verbose=verbose
        )
    
    def create_customer_log(self, user_intent: str, original_query: str, 
                           crewai_input_prompt: str, master_answer: str, 
                           campaigner_id: int = None, success: bool = True, 
                           error_message: str = None) -> str:
        """Create customer log entry with detailed execution logs"""
        # Get detailed execution log
        execution_log = self.timing_service.get_timing_breakdown(self.session_id)
        crewai_log = json.dumps(execution_log, indent=2)
        
        # Create customer log
        log_id = self.timing_service.create_customer_log(
            session_id=self.session_id,
            user_intent=user_intent,
            original_query=original_query,
            crewai_input_prompt=crewai_input_prompt,
            master_answer=master_answer,
            crewai_log=crewai_log,
            campaigner_id=campaigner_id,
            analysis_id=self.analysis_id,
            success=success,
            error_message=error_message
        )
        
        # Cleanup detailed logger
        cleanup_detailed_logger(self.session_id)
        
        return log_id
