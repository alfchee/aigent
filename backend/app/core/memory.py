import os
import uuid
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions

# Configuración persistente (guarda en disco)
# Se asume que se ejecuta desde la raíz del proyecto o backend
chroma_client = chromadb.PersistentClient(path=os.getenv("NAVIBOT_MEMORY_DIR", "./navi_memory_db"))

# Usamos un modelo ligero y gratuito para convertir texto a números
# sentence-transformers genera los vectores localmente (CPU/GPU)
emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

collection = chroma_client.get_or_create_collection(
    name="user_knowledge",
    embedding_function=emb_fn
)

def save_memory(user_id: str, text: str, source: str) -> None:
    """
    Guarda un fragmento de información en la memoria vectorial.
    
    Args:
        user_id: Identificador del usuario (o sesión).
        text: El texto a recordar.
        source: Origen del dato (ej: 'user_interaction', 'telegram', 'web').
    """
    collection.add(
        documents=[text],
        metadatas=[{"user_id": user_id, "source": source}],
        ids=[str(uuid.uuid4())]
    )
    print(f"[Memory] Saved for user {user_id}: {text[:50]}...")

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
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": user_id} # Filtra por usuario
        )
        
        if results and results['documents']:
            # results['documents'] es una lista de listas (una por query)
            return results['documents'][0]
        return []
    except Exception as e:
        print(f"[Memory] Error recalling memory: {e}")
        return []
