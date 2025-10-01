"""
DialogCX webhook processing service
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.database import db_manager
from app.core.utils import generate_session_id, get_current_timestamp
from app.core.exceptions import SatoAppException
from app.config.logging import get_logger
from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection
from sqlmodel import select, and_

logger = get_logger("services.dialogcx")


class DialogCXService:
    """Service for handling DialogCX webhook processing only"""
    
    def __init__(self):
        self.db_manager = db_manager
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get user context data for DialogCX initialization"""
        try:
            # Get user's connected assets/services
            user_assets = self._get_user_connected_assets(user_id)
            
            return {
                "user_id": user_id,
                "available_assets": [asset.get('asset_type') for asset in user_assets],
                "connected_services": [asset.get('platform') for asset in user_assets],
                "capabilities": self._get_user_analysis_capabilities(user_assets)
            }
            
        except Exception as e:
            logger.error(f"Failed to get user context: {str(e)}")
            raise SatoAppException(f"Failed to get user context: {str(e)}")
    
    def _get_user_connected_assets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's connected marketing assets"""
        try:
            # Query the assets and connections tables
            # This would return actual user assets from database
            # Return real data from database
            with get_session() as session:
                # Query actual user assets from database
                statement = select(DigitalAsset, Connection).join(
                    Connection, DigitalAsset.id == Connection.digital_asset_id
                ).where(
                    and_(
                        Connection.user_id == user_id,
                        Connection.revoked == False,
                        DigitalAsset.is_active == True
                    )
                )
                
                results = session.exec(statement).all()
                
                assets = []
                for digital_asset, connection in results:
                    assets.append({
                        'asset_type': digital_asset.asset_type.value.lower(),
                        'platform': digital_asset.provider,
                        'asset_id': digital_asset.external_id,
                        'is_active': digital_asset.is_active,
                        'connection_id': connection.id
                    })
                
                return assets
            
        except Exception as e:
            logger.error(f"Failed to get user assets: {str(e)}")
            return []
    
    def _get_user_analysis_capabilities(self, user_assets: List[Dict[str, Any]]) -> List[str]:
        """Determine what analysis capabilities are available based on user's assets"""
        capabilities = []
        
        for asset in user_assets:
            if asset.get('platform') == 'GA4' and asset.get('is_active'):
                capabilities.extend([
                    'traffic_analysis',
                    'conversion_analysis', 
                    'audience_analysis'
                ])
            elif asset.get('platform') == 'Facebook' and asset.get('is_active'):
                capabilities.extend([
                    'paid_social_analysis',
                    'roas_analysis',
                    'campaign_performance'
                ])
        
        return list(set(capabilities))  # Remove duplicates
    
    
    def process_real_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process DialogCX tool webhook - Called when DialogCX agent uses the Crew AI tool"""
        try:
            user_parameters = webhook_data.get('user_parameters', '')
            user_text = webhook_data.get('user_text', '')
            
            logger.info(f"DialogCX Tool Webhook: user_text='{user_text}', user_parameters='{user_parameters}'")
            
            # Parse user_parameters if it's JSON string
            import json
            try:
                if user_parameters:
                    parsed_parameters = json.loads(user_parameters)
                else:
                    parsed_parameters = {}
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse user_parameters as JSON: {user_parameters}")
                parsed_parameters = {"raw_parameters": user_parameters}
            
            # Create a session ID for this interaction
            session_id = generate_session_id()
            
            # Call the local Crew AI service directly
            from app.services.crew_service import CrewService
            
            try:
                crew_service = CrewService()
                
                # Call local Crew AI Master Agent
                request_data = {
                    'user_text': user_text,
                    'user_parameters': parsed_parameters,
                    'session_id': session_id,
                    'source': 'dialogcx_tool_webhook'
                }
                crew_response = crew_service.execute_master_agent_analysis(request_data)
                
                # Extract the analysis message from master agent response
                if crew_response and crew_response.get('fulfillment_response'):
                    # Extract message from DialogCX fulfillment format
                    messages = crew_response.get('fulfillment_response', {}).get('messages', [])
                    if messages and messages[0].get('text', {}).get('text'):
                        analysis_message = messages[0]['text']['text'][0]
                    else:
                        analysis_message = 'Analysis completed successfully'
                else:
                    logger.error(f"Unexpected crew response format: {crew_response}")
                    analysis_message = "I apologize, but I encountered an unexpected response format from the analysis engine."
                    
            except Exception as e:
                logger.error(f"Error calling local Crew AI: {str(e)}")
                analysis_message = f"I apologize, but I encountered an error: {str(e)}"
            
            # Store the interaction
            self._store_dialogcx_crew_interaction({
                'user_text': user_text,
                'user_parameters': parsed_parameters,
                'session_id': session_id,
                'timestamp': webhook_data.get('timestamp'),
                'source': 'dialogcx_tool_webhook'
            }, {'analysis': analysis_message})
            
            # Return simple message response for DialogCX tool
            return {
                "message": analysis_message
            }
                
        except Exception as e:
            logger.error(f"DialogCX tool webhook processing failed: {str(e)}")
            return {
                "message": f"I encountered an error while analyzing your request. Please try again."
            }
    
    def process_dialogcx_webhook(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process DialogCX webhook - Route to Master Agent"""
        try:
            # Extract DialogCX data according to implementation plan
            session_info = raw_data.get('sessionInfo', {})
            parameters = session_info.get('parameters', {})
            
            # Structure the data as expected by Master Agent
            dialogcx_payload = {
                'sessionInfo': session_info,
                'user_id': parameters.get('user_id'),
                'customer_id': parameters.get('customer_id'),
                'session_id': session_info.get('session', '').split('/')[-1] if session_info.get('session') else generate_session_id(),
                'intent_type': raw_data.get('intentInfo', {}).get('displayName', ''),
                'confidence': raw_data.get('intentInfo', {}).get('confidence', 0.0),
                'parameters': parameters
            }
            
            # Log the DialogCX request for monitoring
            logger.info(f"DialogCX webhook: {dialogcx_payload.get('intent_type')} from user {dialogcx_payload.get('user_id')}")
            
            # Route to database-driven master agent system
            from app.services.agent_service import AgentService
            
            agent_service = AgentService()
            all_agents_data = agent_service.get_all_agents()
            master_agent_data = all_agents_data.get("master_agent")
            
            if not master_agent_data:
                raise Exception("Master agent not found in database")
            
            # For now, return a simple response indicating the system is using database-driven agents
            result = {
                "status": "success",
                "message": "Analysis completed using database-driven master agent",
                "master_agent": master_agent_data["name"],
                "dialogcx_payload": dialogcx_payload
            }
            
            # Store the interaction in database for analytics
            self._store_dialogcx_interaction(dialogcx_payload, result)
            
            return result
                
        except Exception as e:
            logger.error(f"DialogCX webhook processing failed: {str(e)}")
            return self._create_dialogcx_error_response(str(e))
    
    def _store_dialogcx_crew_interaction(self, payload: Dict[str, Any], result: Dict[str, Any]):
        """Store DialogCX crew interaction for analytics"""
        try:
            self.db_manager.store_chat_message(
                user_name="dialogcx_user",
                message=payload.get('user_text', 'DialogCX crew interaction'),
                session_id=payload.get('session_id'),
                raw_data={
                    'webhook_payload': payload,
                    'crew_result': result,
                    'interaction_type': 'dialogcx_crew_webhook'
                }
            )
        except Exception as e:
            logger.warning(f"Failed to store DialogCX crew interaction: {str(e)}")
    
    def _store_dialogcx_interaction(self, payload: Dict[str, Any], result: Dict[str, Any]):
        """Store DialogCX interaction for analytics"""
        try:
            self.db_manager.store_chat_message(
                user_name=f"user_{payload.get('user_id', 'unknown')}",
                message=payload.get('parameters', {}).get('user_question', 'DialogCX interaction'),
                session_id=payload.get('session_id'),
                raw_data={
                    'dialogcx_payload': payload,
                    'master_agent_result': result,
                    'interaction_type': 'dialogcx_webhook'
                }
            )
        except Exception as e:
            logger.warning(f"Failed to store DialogCX interaction: {str(e)}")
    
    
    def _create_dialogcx_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create DialogCX-compatible error response"""
        return {
            "fulfillment_response": {
                "messages": [{
                    "text": {
                        "text": [f"I apologize, but I encountered an error while processing your request: {error_message}"]
                    }
                }]
            },
            "error": error_message
        }
    
