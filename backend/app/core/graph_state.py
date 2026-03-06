from typing import TypedDict, Annotated, List, Union, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Estado del Agente para LangGraph.
    
    Attributes:
        messages: Lista de mensajes de la conversación. 
                  'add_messages' es un reducer que concatena los nuevos mensajes a la lista existente.
        next: El siguiente nodo a ejecutar (decidido por el supervisor).
        session_id: Identificador de sesión para seguimiento.
        summarization_metadata: Metadatos de la operación de resumen (si se ejecutó).
    """
    messages: Annotated[List[BaseMessage], add_messages]
    next: str
    session_id: Optional[str] = None
    summarization_metadata: Optional[Any] = None
