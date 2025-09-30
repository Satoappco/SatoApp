"""
Database manager for SatoApp - refactored from original database.py
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select
from app.config.database import get_session
from app.core.exceptions import DatabaseException
from app.config.logging import get_logger

logger = get_logger("database")


class DatabaseManager:
    """Centralized database operations manager"""
    
    def __init__(self):
        self.get_session = get_session
    
    # Agent Configuration Management
    def get_agent_config(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """Get agent configuration by type"""
        try:
            with self.get_session() as session:
                from app.models.agents import AgentConfig
                
                statement = select(AgentConfig).where(
                    AgentConfig.agent_type == agent_type,
                    AgentConfig.is_active == True
                )
                agent_config = session.exec(statement).first()
                
                if agent_config:
                    return self._agent_config_to_dict(agent_config)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get agent config for {agent_type}: {str(e)}")
            raise DatabaseException(f"Failed to get agent config: {str(e)}")
    
    def get_agent_config_by_type(self, agent_type: str, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
        """Get agent configuration by type, optionally including inactive agents"""
        try:
            with self.get_session() as session:
                from app.models.agents import AgentConfig
                
                if include_inactive:
                    statement = select(AgentConfig).where(AgentConfig.agent_type == agent_type)
                else:
                    statement = select(AgentConfig).where(
                        AgentConfig.agent_type == agent_type,
                        AgentConfig.is_active == True
                    )
                
                agent_config = session.exec(statement).first()
                
                if agent_config:
                    return self._agent_config_to_dict(agent_config)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get agent config for {agent_type}: {str(e)}")
            raise DatabaseException(f"Failed to get agent config: {str(e)}")
    
    def upsert_agent_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update agent configuration"""
        try:
            with self.get_session() as session:
                from app.models.agents import AgentConfig
                
                existing_config = None
                
                # If ID is provided, try to find by ID first (for updates)
                if 'id' in config_data and config_data['id']:
                    statement = select(AgentConfig).where(AgentConfig.id == config_data['id'])
                    existing_config = session.exec(statement).first()
                
                # If not found by ID, try to find by agent_type (for new agents or type-based updates)
                if not existing_config:
                    statement = select(AgentConfig).where(AgentConfig.agent_type == config_data['agent_type'])
                    existing_config = session.exec(statement).first()
                
                if existing_config:
                    # Update existing config
                    for key, value in config_data.items():
                        if key in ['capabilities', 'tools'] and isinstance(value, (dict, list)):
                            setattr(existing_config, key, json.dumps(value))
                        elif hasattr(existing_config, key) and key != 'id':  # Don't update the ID
                            setattr(existing_config, key, value)
                    
                    existing_config.updated_at = datetime.utcnow()
                    session.add(existing_config)
                    session.commit()
                    session.refresh(existing_config)
                    return self._agent_config_to_dict(existing_config)
                else:
                    # Create new config
                    new_config = AgentConfig(
                        agent_type=config_data['agent_type'],
                        name=config_data['name'],
                        role=config_data['role'],
                        goal=config_data['goal'],
                        backstory=config_data['backstory'],
                        capabilities=json.dumps(config_data.get('capabilities', {})),
                        tools=json.dumps(config_data.get('tools', [])),
                        max_iterations=config_data.get('max_iterations', 3),
                        is_active=config_data.get('is_active', True),
                        created_by_user_id=config_data.get('created_by_user_id')
                    )
                    
                    session.add(new_config)
                    session.commit()
                    session.refresh(new_config)
                    return self._agent_config_to_dict(new_config)
                    
        except Exception as e:
            logger.error(f"Failed to upsert agent config: {str(e)}")
            raise DatabaseException(f"Failed to upsert agent config: {str(e)}")
    
    def delete_agent_config(self, agent_type: str) -> bool:
        """Permanently delete agent configuration from database"""
        try:
            with self.get_session() as session:
                from app.models.agents import AgentConfig
                
                # Find the agent by type
                statement = select(AgentConfig).where(AgentConfig.agent_type == agent_type)
                agent_config = session.exec(statement).first()
                
                if not agent_config:
                    logger.warning(f"Agent {agent_type} not found for deletion")
                    return False
                
                # Delete the agent
                session.delete(agent_config)
                session.commit()
                
                logger.info(f"Successfully deleted agent {agent_type} from database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete agent config {agent_type}: {str(e)}")
            raise DatabaseException(f"Failed to delete agent config: {str(e)}")
    
    def get_all_specialist_agents(self) -> List[Dict[str, Any]]:
        """Get all specialist agent configurations"""
        try:
            with self.get_session() as session:
                from app.models.agents import AgentConfig
                
                # Exclude master agent types from specialist agents
                master_types = ['seo_campaign_manager', 'master', 'seo_master', 'campaign_manager']
                statement = select(AgentConfig).where(
                    ~AgentConfig.agent_type.in_(master_types),
                    AgentConfig.is_active == True
                )
                specialist_configs = session.exec(statement).all()
                
                return [self._agent_config_to_dict(config) for config in specialist_configs]
                
        except Exception as e:
            logger.error(f"Failed to get specialist agents: {str(e)}")
            raise DatabaseException(f"Failed to get specialist agents: {str(e)}")
    
    def _agent_config_to_dict(self, agent_config) -> Dict[str, Any]:
        """Convert AgentConfig model to dictionary"""
        return {
            "id": agent_config.id,
            "agent_type": agent_config.agent_type,
            "name": agent_config.name,
            "role": agent_config.role,
            "goal": agent_config.goal,
            "backstory": agent_config.backstory,
            "task": getattr(agent_config, 'task', ''),
            "capabilities": json.loads(agent_config.capabilities) if agent_config.capabilities else {},
            "tools": json.loads(agent_config.tools) if agent_config.tools else [],
            "max_iterations": agent_config.max_iterations,
            "allow_delegation": getattr(agent_config, 'allow_delegation', False),
            "verbose": getattr(agent_config, 'verbose', True),
            "is_active": agent_config.is_active,
            "created_at": agent_config.created_at.isoformat() if agent_config.created_at else None,
            "updated_at": agent_config.updated_at.isoformat() if agent_config.updated_at else None
        }
    
    # Chat and Conversation Management
    def store_chat_message(self, user_name: str, message: str, session_id: str, raw_data: Dict[str, Any] = None):
        """Store chat message in database"""
        try:
            with self.get_session() as session:
                from app.models.conversations import ChatMessage
                
                chat_message = ChatMessage(
                    user_name=user_name,
                    message=message,
                    session_id=session_id,
                    raw_data=json.dumps(raw_data) if raw_data else None
                )
                
                session.add(chat_message)
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store chat message: {str(e)}")
            raise DatabaseException(f"Failed to store chat message: {str(e)}")
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        try:
            with self.get_session() as session:
                from app.models.conversations import ChatMessage
                
                statement = select(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(limit)
                messages = session.exec(statement).all()
                
                return [
                    {
                        "id": msg.id,
                        "user_name": msg.user_name,
                        "message": msg.message,
                        "session_id": msg.session_id,
                        "raw_data": json.loads(msg.raw_data) if msg.raw_data else None,
                        "created_at": msg.created_at
                    }
                    for msg in messages
                ]
                
        except Exception as e:
            logger.error(f"Failed to get chat history: {str(e)}")
            raise DatabaseException(f"Failed to get chat history: {str(e)}")


# Global database manager instance
db_manager = DatabaseManager()
