import os
import glob

# Define user_data directory relative to this file
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_data")

def list_files(directory: str = ".") -> str:
    """Lists files in the user_data directory."""
    try:
        # Security: Always look in USER_DATA_DIR unless explicitly overridden for system tasks (which we avoid for now)
        target_dir = USER_DATA_DIR
        files = os.listdir(target_dir)
        return "\n".join(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"

def read_file(filename: str) -> str:
    """Reads the content of a file from user_data."""
    try:
        filepath = os.path.join(USER_DATA_DIR, filename)
        with open(filepath, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def create_file(filename: str, content: str) -> str:
    """Creates a file in user_data with the given content."""
    try:
        filepath = os.path.join(USER_DATA_DIR, filename)
        with open(filepath, "w") as f:
            f.write(content)
        # Return the web-accessible path
        return f"File created: [FILE_ARTIFACT: /files/{filename}]"
    except Exception as e:
        return f"Error creating file: {str(e)}"

# List of tools to register
tools = [list_files, read_file, create_file]
