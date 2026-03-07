# Secure Skills Repository

This directory `/secure_skills` is the entry point for Skills that will be audited and loaded by Navibot's security system.

## Secure Skill Structure

Each Skill must contain at least:

1.  `MANIFEST.json`: Declaration of required capabilities and permissions.
2.  `skill_code.py` (or the name defined in `entry_point`): The source code of the Skill.
3.  `signature.sig` (Planned): Digital signature of the developer or the local system.

## Loading and Implementation Process

The security system ("Gateway") implemented in `backend/app/security/skill_validator.py` performs the following validations when loading a skill from this directory:

1.  **MANIFEST.json Existence**: Verifies that the manifest file is present and is valid JSON.
2.  **Structure Validation**: Checks that the manifest has the required fields (`name`, `version`, `permissions`, `entry_point`).
3.  **Static Analysis (AST)**: Scans the Python code (`skill_code.py`) for:
    *   **Forbidden Functions**: `eval`, `exec`, `compile`, `__import__`, etc.
    *   **Restricted Imports**:
        *   If no `network` permission, blocks `requests`, `urllib`, `socket`, `http`, etc.
        *   If no `filesystem` permission, blocks `os`, `shutil`, `pathlib`, etc.
        *   Always blocks dangerous modules like `subprocess`, `pickle`, `marshal`.

## Secure Skill Example

See the `simple_math/` directory for a working example.

### MANIFEST.json
```json
{
  "name": "simple_math",
  "version": "1.0.0",
  "description": "Performs simple math operations safely.",
  "author": "Navibot Team",
  "permissions": {
    "network": { "allow_all": false },
    "filesystem": { "allow_all": false }
  },
  "entry_point": "math_tool.py"
}
```

### math_tool.py
```python
from langchain_core.tools import tool

@tool
def add_numbers(a: int, b: int) -> int:
    """Adds two integers."""
    return a + b
```
