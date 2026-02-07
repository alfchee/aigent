from google.genai import types

def content_to_dict(content) -> dict:
    """Serializes a Gemini Content object to a dictionary."""
    parts_data = []
    
    # Handle case where content might be a dict (already serialized)
    if isinstance(content, dict):
        return content

    if hasattr(content, 'parts'):
        for part in content.parts:
            part_dict = {}
            if hasattr(part, 'text') and part.text:
                part_dict["text"] = part.text
            
            if hasattr(part, 'function_call') and part.function_call:
                part_dict["function_call"] = {
                    "name": part.function_call.name,
                    "args": part.function_call.args
                }
            
            if hasattr(part, 'function_response') and part.function_response:
                part_dict["function_response"] = {
                    "name": part.function_response.name,
                    "response": part.function_response.response
                }
            
            # Only add if we found something relevant
            if part_dict:
                parts_data.append(part_dict)
    
    return {
        "role": content.role,
        "parts": parts_data
    }

def dict_to_content(data: dict) -> types.Content:
    """Deserializes a dictionary to a Gemini Content object."""
    parts = []
    for part_data in data.get("parts", []):
        if "text" in part_data:
            parts.append(types.Part(text=part_data["text"]))
        elif "function_call" in part_data:
            fc = part_data["function_call"]
            parts.append(types.Part(
                function_call=types.FunctionCall(
                    name=fc["name"],
                    args=fc["args"]
                )
            ))
        elif "function_response" in part_data:
            fr = part_data["function_response"]
            parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=fr["name"],
                    response=fr["response"]
                )
            ))
    
    return types.Content(role=data["role"], parts=parts)
