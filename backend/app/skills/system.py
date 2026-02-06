import os
import glob

def list_files(directory: str = ".") -> str:
    """Lists files in the specified directory."""
    try:
        files = os.listdir(directory)
        return "\n".join(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"

def read_file(filepath: str) -> str:
    """Reads the content of a file."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def create_file(filepath: str, content: str) -> str:
    """Creates a file with the given content."""
    try:
        with open(filepath, "w") as f:
            f.write(content)
        return f"File created at {filepath}"
    except Exception as e:
        return f"Error creating file: {str(e)}"

# List of tools to register
tools = [list_files, read_file, create_file]
