from typing import TypedDict, Annotated, List, Union
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Estado del Agente para LangGraph.
    
    Attributes:
        messages: Lista de mensajes de la conversación. 
                  'add_messages' es un reducer que concatena los nuevos mensajes a la lista existente.
        next: El siguiente nodo a ejecutar (decidido por el supervisor).
    """
    messages: Annotated[List[BaseMessage], add_messages]
    next: str
