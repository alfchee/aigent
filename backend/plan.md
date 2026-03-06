# Plan: Granular Model Orchestration & Role-Based Assignment

## Goal
Implement a flexible LLM selection strategy that assigns specific models to different agent roles (Supervisor, Search, Code, etc.) to optimize for cost, speed, and context window usage. Additionally, implement an "Emergency Mode" for rate limit resilience.

## 1. Configuration Updates (`app/core/config_manager.py`)
- Define a `RoleConfig` model mapping roles to model names.
- Update `AppSettings` to include `roles_config` and `emergency_mode`.
- Define default roles:
  - `supervisor`: Logic/Decision making (Default: `gemini-2.5-pro`)
  - `search_worker`: Web search & processing (Default: `gemini-2.0-flash`)
  - `code_worker`: Code execution & file ops (Default: `gemini-2.0-flash`)
  - `voice_worker`: TTS/Audio (Default: `gemini-flash-latest`)
  - `scheduled_worker`: Monitoring tasks (Default: `gemini-flash-latest`)

## 2. Model Orchestrator Enhancements (`app/core/model_orchestrator.py`)
- Add `get_model_for_role(role: str) -> str` method.
- Implement `emergency_mode` logic:
  - If `emergency_mode` is True, downgrade "Pro" models to "Flash" equivalents.
- Add helper to resolve model based on role and current system state.

## 3. Agent Graph Refactoring (`app/core/agent_graph.py`)
- Update `AgentGraph` initialization to accept a `ModelOrchestrator` or `RoleConfig`.
- Instantiate distinct `ChatGoogleGenerativeAI` instances for:
  - Supervisor Node (using `supervisor` role model)
  - Worker Nodes (using respective role models, e.g., `WebNavigator` uses `search_worker` model)
- Ensure each node uses its assigned model instance.

## 4. Integration & Testing
- Update `app/core/agent.py` to pass the correct configuration to `AgentGraph`.
- Verify that different models are being used for different steps (via logging or response metadata).
- Test "Emergency Mode" by toggling the flag and verifying model degradation.

## Roles Mapping
| Agent Role | System Role | Recommended Model | Fallback (Emergency) |
| :--- | :--- | :--- | :--- |
| **Supervisor** | `supervisor` | `gemini-2.5-pro` | `gemini-2.0-flash` |
| **WebNavigator** | `search_worker` | `gemini-2.0-flash` | `gemini-flash-latest` |
| **GeneralAssistant** | `code_worker` | `gemini-2.0-flash` | `gemini-flash-latest` |
| **CalendarManager** | `scheduled_worker` | `gemini-flash-latest` | `gemini-flash-latest` |

## Checklist
- [ ] Update `app/core/config_manager.py` with `RoleConfig`.
- [ ] Update `app/core/model_orchestrator.py` with role resolution logic.
- [ ] Refactor `app/core/agent_graph.py` to use role-based models.
- [ ] Update `app/core/agent.py` integration.
- [ ] Verify implementation with a test run.
