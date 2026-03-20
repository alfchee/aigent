from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

logger = logging.getLogger("navibot.refiner")


REFINER_PROMPT = """You are NaviBot Refiner, a quality assurance node.

## Task Under Review
{original_request}

## Current Response
{current_response}

## Quality Criteria
1. **Relevance**: Does the response directly address the user's request?
2. **Completeness**: Are all parts of the request addressed?
3. **Accuracy**: Is the information correct and well-sourced?
4. **Clarity**: Is the response clear, concise, and easy to understand?

## Instructions
- Analyze the current response against the original request.
- If the response fully satisfies the request, return it unchanged.
- If improvements are needed, provide an improved version.
- If the task was only partially completed, note what's missing.
- Respond ONLY with one of:
  - APPROVED: <full approved response>
  - REVISED: <improved response>
  - INCOMPLETE: <note what's missing and what additional steps would be needed>
"""


class RefinerNode:
    def __init__(self, llm_service):
        self.llm = llm_service
        self.complexity_threshold = 3

    async def refine(
        self,
        original_request: str,
        current_response: str,
        tool_call_count: int,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Evaluate and potentially improve a response before sending to user.
        Only triggers for complex tasks (multiple tool calls or longer responses).
        """
        if tool_call_count < self.complexity_threshold and len(current_response) < 500:
            logger.debug(
                "refine: skipping - tool_calls=%s response_len=%s",
                tool_call_count,
                len(current_response),
            )
            return {
                "response": current_response,
                "status": "skipped",
                "reason": "below complexity threshold",
            }

        logger.info(
            "refine: running - tool_calls=%s response_len=%s session=%s",
            tool_call_count,
            len(current_response),
            session_id,
        )

        prompt = REFINER_PROMPT.format(
            original_request=original_request,
            current_response=current_response,
        )

        try:
            from app.core.llm import ModelConfig
            config = ModelConfig(
                provider=self.llm.default_config.provider,
                model_name=self.llm.default_config.model_name,
                temperature=0.3,
                max_tokens=2048,
                api_key=self.llm.default_config.api_key,
                base_url=self.llm.default_config.base_url,
            )
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                config=config,
                tools=None,
            )

            choice = response.choices[0].message
            content = choice.content or ""

            if content.startswith("APPROVED:"):
                refined = content.replace("APPROVED:", "").strip()
                return {"response": refined, "status": "approved", "tool_call_count": tool_call_count}
            elif content.startswith("REVISED:"):
                refined = content.replace("REVISED:", "").strip()
                return {"response": refined, "status": "revised", "tool_call_count": tool_call_count}
            elif content.startswith("INCOMPLETE:"):
                note = content.replace("INCOMPLETE:", "").strip()
                return {
                    "response": current_response + f"\n\n[Nota: La tarea está incompleta. {note}]",
                    "status": "incomplete",
                    "tool_call_count": tool_call_count,
                }
            else:
                logger.warning("refine: unexpected format from LLM, returning original: %s", content[:100])
                return {"response": current_response, "status": "unknown_format", "tool_call_count": tool_call_count}

        except Exception as exc:
            logger.exception("refine: LLM call failed: %s", exc)
            return {"response": current_response, "status": "error", "error": str(exc)}
