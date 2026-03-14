from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    # Fallback if library is missing, though we should have installed it
    ChatOpenAI = None

from sqlalchemy.orm import Session
from app.core.persistence import LLMProvider, get_persistence_db
from app.core.security.encryption import get_encryption_service
import os
import json
import logging

logger = logging.getLogger(__name__)

def get_active_provider_config(db: Session) -> Optional[LLMProvider]:
    return db.query(LLMProvider).filter(LLMProvider.is_active == True).first()

def get_agent_model(model_name: str, temperature: float = 0.7, **kwargs) -> BaseChatModel:
    # Use persistence DB
    db_gen = get_persistence_db()
    db = next(db_gen)
    try:
        provider = get_active_provider_config(db)
        
        # If no active provider, fallback to Google env var (Default behavior)
        if not provider:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.warning("No active LLM provider and GOOGLE_API_KEY missing. Agent may fail.")
            
            # Filter kwargs for Google
            google_kwargs = {k: v for k, v in kwargs.items() if k in ["cached_content", "convert_system_message_to_human"]}
            if "convert_system_message_to_human" not in google_kwargs:
                google_kwargs["convert_system_message_to_human"] = True
                
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=temperature,
                **google_kwargs
            )
        
        encryption = get_encryption_service()
        api_key = encryption.decrypt(provider.api_key_enc) if provider.api_key_enc else ""
        
        if provider.provider_id == "google":
            key_to_use = api_key or os.getenv("GOOGLE_API_KEY")
            
            # Filter kwargs for Google
            google_kwargs = {k: v for k, v in kwargs.items() if k in ["cached_content", "convert_system_message_to_human"]}
            if "convert_system_message_to_human" not in google_kwargs:
                google_kwargs["convert_system_message_to_human"] = True

            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=key_to_use,
                temperature=temperature,
                **google_kwargs
            )
            
        elif provider.provider_id == "openrouter":
            if not ChatOpenAI:
                raise ImportError("langchain-openai not installed. Please install it to use OpenRouter.")

            provider_config = {}
            if provider.config_json:
                try:
                    provider_config = json.loads(provider.config_json)
                except Exception:
                    provider_config = {}

            default_headers = {
                "X-Title": "Navibot",
            }
            if provider_config.get("openrouter_cache", True):
                default_headers["X-OpenRouter-Cache"] = "true"

            return ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=temperature,
                default_headers=default_headers,
            )
            
        elif provider.provider_id == "lm_studio":
            if not ChatOpenAI:
                raise ImportError("langchain-openai not installed. Please install it to use LM Studio.")
                
            base_url = provider.base_url or "http://localhost:1234/v1"
            # Ensure base_url ends with /v1
            if not base_url.endswith("/v1"):
                base_url = f"{base_url.rstrip('/')}/v1"
                
            return ChatOpenAI(
                model=model_name,
                openai_api_key="lm-studio", 
                openai_api_base=base_url,
                temperature=temperature
            )
            
        else:
            logger.warning(f"Unknown provider {provider.provider_id}, falling back to Google.")
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                temperature=temperature,
                convert_system_message_to_human=True
            )
            
    except Exception as e:
        logger.error(f"Error initializing agent model: {e}")
        # Last resort fallback
        return ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=temperature,
            convert_system_message_to_human=True
        )
    finally:
        db_gen.close()
