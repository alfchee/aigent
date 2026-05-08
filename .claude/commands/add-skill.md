Add a new local skill to the NaviBot tool registry.

Steps to implement a new skill:

1. Create `backend/app/skills/<skill_name>.py` with:
   - A Pydantic `Input` model
   - A Pydantic `Output` model
   - An async `run(input: Input) -> Output` function

2. Register it in `backend/app/skills/__init__.py` (or import in `main.py`):
   ```python
   from app.skills import <skill_name>
   ```

3. The skill file must call `registry.register(...)` at import time:
   ```python
   from app.skills.registry import registry

   registry.register(
       name="<skill_name>",
       description="...",
       input_model=Input,
       output_model=Output,
       fn=run,
   )
   ```

4. Add tests in `backend/tests/test_skills_<skill_name>.py`.

5. Mark any tests that call external APIs with `@pytest.mark.network`.
