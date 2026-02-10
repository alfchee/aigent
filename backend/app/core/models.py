import os
from google import genai
from typing import List, Dict, Any

async def get_available_gemini_models() -> List[Dict[str, Any]]:
    """
    Obtiene la lista de modelos que soportan generación de contenido.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    models = []
    
    try:
        # Use async iterator for listing models
        pager = await client.aio.models.list()
        async for m in pager:
            # Check for content generation capability
            methods = m.supported_actions or []
            if 'generateContent' in methods:
                # Clean up ID (remove 'models/' prefix if present)
                model_id = m.name
                if model_id.startswith('models/'):
                    model_id = model_id[7:]
                    
                models.append({
                    "id": model_id,
                    "display_name": m.display_name or model_id,
                    "description": m.description or "",
                    "input_token_limit": m.input_token_limit,
                    "output_token_limit": m.output_token_limit
                })
                
        # Sort by display name for better UI
        models.sort(key=lambda x: x["display_name"])
        return models
        
    except Exception as e:
        print(f"Error listando modelos: {e}")
        return []
