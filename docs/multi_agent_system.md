# Multi-Agent System Architecture

This document describes the multi-agent architecture implemented in NaviBot, featuring a Supervisor pattern with specialized Workers.

## Overview

NaviBot uses a **Supervisor + Workers** pattern built on **LangGraph**. The Supervisor analyzes user requests and routes them to the appropriate specialized Worker for execution.

## Components

### Supervisor

The Supervisor is the central orchestrator that:
- Analyzes user messages
- Routes requests to the correct Worker
- Manages the conversation flow between Workers

**Location**: [`backend/app/core/supervisor.py`](backend/app/core/supervisor.py)

### Workers

| Worker | Purpose | Skills/Tools |
|--------|---------|--------------|
| **WebNavigator** | Web searches and website browsing | `browser`, `search`, `reader` |
| **CalendarManager** | Calendar event management | `calendar`, `scheduler` |
| **GeneralAssistant** | Google Workspace, code, memory, files | `workspace`, `code_execution`, `google_drive`, `memory`, `telegram` |
| **ImageGenerator** | Image generation from text | `image_generation` |

## Routing Rules

The Supervisor follows these rules to route requests:

```
GOOGLE DRIVE requests     → GeneralAssistant
GOOGLE SHEETS requests    → GeneralAssistant  
GOOGLE CALENDAR requests  → CalendarManager
WEB SEARCH (internet)    → WebNavigator
BROWSING websites         → WebNavigator
IMAGE GENERATION          → ImageGenerator
CODE EXECUTION            → GeneralAssistant
FILE MANAGEMENT          → GeneralAssistant
MEMORY operations         → GeneralAssistant
TELEGRAM messages         → GeneralAssistant
Default (most tasks)      → GeneralAssistant
```

## Implementation Details

### Agent Graph

The `AgentGraph` class in [`backend/app/core/agent_graph.py`](backend/app/core/agent_graph.py) manages the LangGraph state machine:

```python
worker_skills = {
    "WebNavigator": ["browser", "search", "reader"],
    "CalendarManager": ["calendar", "scheduler"],
    "GeneralAssistant": ["workspace", "code_execution", "google_drive", "memory", "telegram", "extra_tools"],
    "ImageGenerator": ["image_generation"]
}
```

### Supervisor Prompt

The Supervisor uses an English-language prompt to ensure proper routing:

```python
system_prompt = (
    "You are a supervisor responsible for managing a conversation between the following workers:\n{worker_desc}\n\n"
    "CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE RULES:\n"
    "1. Analyze the LAST message in the conversation.\n"
    "2. If the last message is a response from a worker to the user, you MUST respond with 'FINISH' IMMEDIATELY.\n"
    ...
    "ROUTING RULES - FOLLOW THESE MANDATORY RULES:\n"
    "- For GOOGLE DRIVE requests: use GeneralAssistant\n"
    ...
)
```

## Tool Mapping

All tool descriptions, prompts, and SOPs are written in **English** to ensure proper serialization with the LLM's function calling schema.

### Critical Logging

To debug routing issues, implement logging that shows Supervisor decisions:

```python
# Example logging in Supervisor
logger.info(f"Supervisor decided to call: {worker} with arguments: {args}")
```

If you don't see this log, the issue is in the Supervisor prompt, not in the tools.

## Troubleshooting

### Tool Not Available

If a Worker can't access certain tools:
1. Check `worker_skills` mapping in `agent_graph.py`
2. Verify the skill module is loaded correctly
3. Ensure tool descriptions are in English

### Wrong Worker Selected

If the Supervisor routes to the wrong Worker:
1. Check ROUTING RULES in `supervisor.py`
2. Verify WORKER_DESCRIPTIONS are clear and specific
3. Review recent user messages for context

### Serialization Issues

If tools don't map correctly:
- All prompts must be in English
- Tool function descriptions must match LLM expectations
- Check for special characters that may break JSON serialization
