import inspect
from typing import Any, Dict, List, Optional, Union

def _resolve_python_type(prop_schema: Dict[str, Any]) -> Any:
    """
    Recursively resolves JSON Schema types to Python types.
    Handles arrays and nested objects to ensure Gemini SDK generates valid schemas.
    """
    json_type = prop_schema.get("type")
    
    simple_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None)
    }
    
    if json_type in simple_map:
        return simple_map[json_type]
        
    if json_type == "array":
        items_schema = prop_schema.get("items", {})
        # Recursive resolution for array items
        item_type = _resolve_python_type(items_schema)
        
        # SPECIAL CASE: List[Any] generates {"type": "array", "items": {}} 
        # But if the original schema had detailed items that we collapsed to Any (because they were objects),
        # we might want to be careful.
        # Actually, "items": {} is valid JSON Schema for "array of anything".
        # BUT Gemini API might be picky.
        
        # If item_type is Any (because items schema was empty or unknown), use List[Any]
        return List[item_type]
        
    if json_type == "object":
        # For objects, we can't easily express the full shape in a single type hint
        # without generating a TypedDict dynamically (which is overkill/complex).
        # Dict[str, Any] generates {"type": "object"} which might be rejected if properties are missing.
        # Any generates {} which is more permissive.
        return Any
        
    return Any

def create_signature_from_schema(schema: Dict[str, Any]) -> inspect.Signature:
    """
    Creates an inspect.Signature object from a JSON Schema.
    This is crucial for dynamic tools (MCP) so that Python/Gemini SDKs can introspect them correctly.
    """
    params = []
    
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    # Sort properties to ensure consistent order
    prop_names = list(properties.keys())
    
    for name in prop_names:
        prop = properties[name]
        python_type = _resolve_python_type(prop)
        
        # Determine default value
        # If it's required, no default. If optional, default is None.
        if name in required:
            default = inspect.Parameter.empty
            annotation = python_type
        else:
            default = None
            # If python_type is Any, Optional[Any] is just Any. 
            if python_type is Any:
                annotation = Any
            else:
                annotation = Optional[python_type]
            
        param = inspect.Parameter(
            name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=default,
            annotation=annotation
        )
        params.append(param)
    
    return inspect.Signature(params)
