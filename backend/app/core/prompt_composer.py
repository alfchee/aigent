from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

logger = logging.getLogger("navibot.prompt_composer")


@dataclass
class PromptInjection:
    trigger_keywords: List[str]
    injection_text: str
    description: str


FINANCIAL_RULES = """## Financial Guidelines (Auto-injected for money/finance topics)
- Always validate expense categories against allowed list: [food, transport, entertainment, utilities, healthcare, education, other]
- Confirm amounts before recording; never assume currency without user confirmation.
- Spreadsheet updates require: date, description, category, amount, running total.
- If the user provides a list of expenses, infer the category from description keywords.
- Format currency amounts consistently (e.g., USD 25.50)."""

SOCIAL_RULES = """## Social Media Campaign Guidelines (Auto-injected for social/marketing topics)
- Generate copy that matches the brand voice provided in context.
- Suggest hashtags only from the top 10 trending in the relevant category.
- For image processing, confirm dimensions and format before proceeding.
- Schedule posts at optimal times: 9 AM or 7 PM local time unless specified otherwise.
- Include a clear CTA (Call-to-Action) in every post copy."""

CODING_RULES = """## Code Execution Guidelines (Auto-injected for coding/programming topics)
- Always validate code against sandbox resource limits before suggesting execution.
- For file operations, use absolute paths starting from /workspace/.
- If the user requests code that modifies system files, warn before proceeding.
- Provide execution cost estimate (CPU time, memory) when relevant."""

RESEARCH_RULES = """## Research & Web Guidelines (Auto-injected for research/search topics)
- Prioritize authoritative sources (government, academic, established media).
- For fact-checking, use at least 2 independent sources before confirming.
- Summarize findings in bullet points; provide links when available.
- Flag information older than 2 years as potentially outdated."""


class PromptComposer:
    def __init__(self):
        self._injections: List[PromptInjection] = [
            PromptInjection(
                trigger_keywords=["dinero", "gasto", "presupuesto", "finance", "money", "expense", "costo", "precio", "spreadsheet", "excel", "gastos", "economía"],
                injection_text=FINANCIAL_RULES,
                description="Financial transaction handling",
            ),
            PromptInjection(
                trigger_keywords=["social", "instagram", "facebook", "twitter", "x.com", "tweet", "post", "campaign", "hashtag", "redes", "publicar", "marketing", "copy", "anuncio"],
                injection_text=SOCIAL_RULES,
                description="Social media campaign generation",
            ),
            PromptInjection(
                trigger_keywords=["code", "python", "javascript", "function", "execute", "run ", "script", "programming", "debug", "bug", "error", "código", "programar", "ejecutar", "depurar"],
                injection_text=CODING_RULES,
                description="Code execution and validation",
            ),
            PromptInjection(
                trigger_keywords=["busca", "search", "investigar", "research", "information", "find", "web", "navegar", "browse", "fact", "facts", "source", "sources"],
                injection_text=RESEARCH_RULES,
                description="Web research and source validation",
            ),
        ]

    def compose(
        self,
        base_prompt: str,
        user_message: str,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Build final system prompt by injecting relevant rules based on user message content.
        """
        active_injections = self.get_applicable_injections(user_message, context or {})

        if not active_injections:
            return base_prompt

        injection_section = "\n\n## Auto-Injected Contextual Rules\n" + "\n".join(
            inj.injection_text for inj in active_injections
        )

        return base_prompt + injection_section

    def get_applicable_injections(
        self,
        user_message: str,
        context: Optional[Dict] = None,
    ) -> List[PromptInjection]:
        """
        Determine which injections are relevant for a given user message and context.
        Case-insensitive keyword matching.
        """
        text_to_check = (user_message or "").lower()
        if context:
            for val in context.values():
                if isinstance(val, str):
                    text_to_check += " " + val.lower()

        applicable = []
        for injection in self._injections:
            for keyword in injection.trigger_keywords:
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_to_check):
                    applicable.append(injection)
                    break

        return applicable

    def add_injection(self, injection: PromptInjection) -> None:
        self._injections.append(injection)

    def clear_injections(self) -> None:
        self._injections.clear()

    def get_registered_injections(self) -> List[Dict]:
        return [
            {"description": inj.description, "keywords": inj.trigger_keywords}
            for inj in self._injections
        ]


_composer_instance: Optional[PromptComposer] = None


def get_prompt_composer() -> PromptComposer:
    global _composer_instance
    if _composer_instance is None:
        _composer_instance = PromptComposer()
    return _composer_instance
