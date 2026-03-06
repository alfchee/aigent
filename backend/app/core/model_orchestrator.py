import logging
from typing import Optional, Any
from app.core.config_manager import get_settings, resolve_model, RoutingConfig

logger = logging.getLogger(__name__)

class ModelOrchestrator:
    """
    Orchestrates model selection and adaptive scaling logic based on configuration.
    """
    
    def get_model_for_task(self, session_id: str, requested_model: Optional[str] = None) -> str:
        """
        Determines the initial model to use for a task.
        
        Args:
            session_id: The active session ID.
            requested_model: Optional explicit model request from user.
            
        Returns:
            The model name to use.
        """
        # Logic:
        # 1. Explicit request or Session preference (via resolve_model)
        # 2. If "auto" logic is implied, it falls back to configured default in resolve_model
        return resolve_model(session_id, requested_model)

    def get_model_for_role(self, role: str) -> str:
        """
        Determines the model to use for a specific agent role, considering emergency mode.
        
        Args:
            role: The agent role (e.g., "supervisor", "search_worker", "code_worker").
            
        Returns:
            The model name to use.
        """
        settings = get_settings()
        role_config = settings.role_config
        emergency_mode = settings.emergency_mode
        
        # Default mapping
        model_name = settings.current_model
        
        if role == "supervisor":
            model_name = role_config.supervisor_model
        elif role == "search_worker":
            model_name = role_config.search_worker_model
        elif role == "code_worker":
            model_name = role_config.code_worker_model
        elif role == "voice_worker":
            model_name = role_config.voice_worker_model
        elif role == "scheduled_worker":
            model_name = role_config.scheduled_worker_model
        elif role == "image_worker":
            model_name = role_config.image_worker_model
            
        # Emergency Mode Logic: Downgrade Pro models to Flash
        if emergency_mode:
            # Simple heuristic: if model name contains "pro", switch to "flash"
            if "pro" in model_name.lower():
                logger.info(f"ModelOrchestrator: Emergency mode active. Downgrading {model_name} to gemini-flash-latest")
                return "gemini-flash-latest"
                
        return model_name

    def should_upgrade_model(self, current_model: str, error: Optional[Exception] = None, tool_name: Optional[str] = None) -> Optional[str]:
        """
        Determines if the system should upgrade to a stronger model.
        
        Args:
            current_model: The model currently being used.
            error: The exception that occurred (if any).
            tool_name: The tool being requested (if any).
            
        Returns:
            The name of the upgrade model if upgrade is recommended, else None.
        """
        settings = get_settings()
        routing: RoutingConfig = settings.routing_config
        fallback_model = settings.fallback_model

        # 1. If already on the fallback/strong model, do not upgrade further.
        if current_model == fallback_model:
            return None

        # 2. Check for tool-based force upgrade
        if tool_name and tool_name in routing.force_upgrade_on_tools:
            logger.info(f"ModelOrchestrator: Upgrading from {current_model} to {fallback_model} due to tool usage: {tool_name}")
            return fallback_model

        # 3. Check for error-based retry
        if routing.auto_retry_with_pro and error:
            # Check both the exception type name and the string representation
            error_type = type(error).__name__
            error_msg = str(error)
            error_full = f"{error_type}: {error_msg}"
            
            for trigger in routing.retry_triggers:
                if trigger in error_full:
                    logger.info(f"ModelOrchestrator: Upgrading from {current_model} to {fallback_model} due to error trigger: {trigger}")
                    return fallback_model
        
        return None
