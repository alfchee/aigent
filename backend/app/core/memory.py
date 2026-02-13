from typing import List
from app.core.memory_manager import get_agent_memory

def save_memory(user_id: str, text: str, source: str) -> None:
    """
    Guarda un fragmento de información en la memoria vectorial.
    
    Args:
        user_id: Identificador del usuario (o sesión).
        text: El texto a recordar.
        source: Origen del dato (ej: 'user_interaction', 'telegram', 'web').
    """
    memory = get_agent_memory()
    memory.add_interaction(user_id, text, metadata={"source": source})

def recall_memory(user_id: str, query: str, n_results: int = 3) -> List[str]:
    """
    Recupera información relevante basada en la query actual.
    
    Args:
        user_id: Identificador del usuario para filtrar memorias.
        query: La pregunta o texto actual para buscar similitud.
        n_results: Número de fragmentos a recuperar.
        
    Returns:
        Lista de textos recuperados.
    """
    memory = get_agent_memory()
    return memory.search_memory(user_id, query, n_results=n_results)
