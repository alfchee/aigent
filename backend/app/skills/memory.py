
import re
from app.core.memory_manager import get_agent_memory
from app.core.runtime_context import get_memory_user_id

def recall_facts(query: str) -> str:
    """
    Searches for information in long-term memory (User Facts).
    Useful when you need to remember past data, user preferences, details of previous projects
    or information not in the current conversation context.
    
    Args:
        query: The question or topic to search in memory.
    """
    memory_user_id = get_memory_user_id()
    if not memory_user_id:
        return "Error: No se pudo identificar el usuario para la memoria."
    
    try:
        memory_manager = get_agent_memory()
        result = memory_manager.get_relevant_context(user_id=memory_user_id, query=query)
        if not result:
            return "No encontré información relevante en la memoria sobre ese tema."
        return f"Información recuperada de la memoria:\n{result}"
    except Exception as e:
        return f"Error al buscar en memoria: {str(e)}"

def save_fact(fact: str) -> str:
    """
    Saves important information to long-term memory.
    Use it ONLY if the user gives you CRITICAL or NEW information that must be remembered in the future.
    Examples: names, preferences, important dates, project settings.
    DO NOT use for casual chat or temporary information.
    
    Args:
        fact: The fact or information to save.
    """
    memory_user_id = get_memory_user_id()
    if not memory_user_id:
        return "Error: No se pudo identificar el usuario para la memoria."
    
    text = (fact or "").strip()
    if not text:
        return "Error: El contenido está vacío."
    
    if _looks_sensitive(text):
        return "No puedo guardar credenciales o secretos sensibles en memoria por seguridad."

    try:
        memory_manager = get_agent_memory()
        memory_manager.add_interaction(user_id=memory_user_id, text=text)
        return "Memoria actualizada correctamente."
    except Exception as e:
        return f"Error al guardar en memoria: {str(e)}"

def _looks_sensitive(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "password",
        "contraseña",
        "clave",
        "token",
        "api key",
        "apikey",
        "secret",
        "secreto",
    ]
    if any(k in lowered for k in keywords):
        return True
    if re.search(r"\b\d{4,}\b", text) and "clave" in lowered:
        return True
    return False

# Export new tool names
# Keeping old names for compatibility if needed, but the agent uses the tool objects
search_memory_tool = recall_facts
save_memory_tool = save_fact

tools = [recall_facts, save_fact]
