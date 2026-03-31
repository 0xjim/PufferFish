"""
PufferFish Screen Extractor

Takes a PRD or feature description (plain text) and a success metric,
and uses an LLM to extract a list of screens/sections the user would
navigate through — in the PufferFish screen schema format.
"""

import json
from typing import Any, Dict, List

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('pufferfish.screen_extractor')

SCREEN_SCHEMA_EXAMPLE = """
{
  "id": "screen_01",
  "name": "Route Selection",
  "content": "Choose your bridge route. Fast (2 min, 0.3% fee) or Economy (8 min, 0.1% fee).",
  "available_actions": ["select_fast", "select_economy", "view_details", "go_back", "abandon"],
  "requires_prior_knowledge": ["what a bridge route is", "fee vs speed tradeoff"]
}
"""

SYSTEM_PROMPT = f"""You are a product experience analyst. Your job is to break a product feature description into discrete screens or steps that a user would encounter when using it.

For each screen/step, output a JSON object with this exact schema:
{SCREEN_SCHEMA_EXAMPLE}

Rules:
- `id`: sequential string like "screen_01", "screen_02", etc.
- `name`: short human-readable name for this screen/step (2-5 words)
- `content`: what the user actually sees and reads — the exact text, labels, options, or copy present on this screen. Be specific and faithful to the description. Do NOT invent copy that wasn't implied.
- `available_actions`: list of actions the user can take from this screen. Always include "abandon" as a possible action. Use snake_case action names.
- `requires_prior_knowledge`: list of concepts or knowledge the user needs to understand this screen. Empty list if nothing special is assumed.

Output ONLY a JSON object with a single key "screens" containing the array. No other text.
Target 3-8 screens for most features. More screens for complex multi-step flows. Fewer for simple single-screen interactions."""


class ScreenExtractor:
    """
    Extracts a list of product screens from a plain-text feature description.

    Usage:
        extractor = ScreenExtractor(llm_client)
        screens = extractor.extract_screens(description, metric)
    """

    MAX_SCREENS = 10

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_screens(self, description: str, metric: str) -> List[Dict[str, Any]]:
        """
        Args:
            description: PRD text or plain-text feature description
            metric: Success metric (e.g. "conversion rate", "task completion")

        Returns:
            List of screen dicts matching the PufferFish screen schema.
        """
        user_prompt = f"""Feature description:
---
{description.strip()}
---

Success metric we are simulating: {metric}

Extract the screens a user would navigate through when using this feature.
Focus on the steps relevant to the success metric — if we are measuring conversion,
make sure the conversion step is modelled as a screen with the appropriate actions.

Return a JSON object: {{"screens": [...]}}"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = self.llm_client.chat_json(messages, temperature=0.3, max_tokens=2048)
        except Exception as e:
            logger.error(f"ScreenExtractor LLM call failed: {e}")
            raise ValueError(f"Failed to extract screens from description: {e}")

        screens = raw.get("screens", [])
        if not isinstance(screens, list):
            raise ValueError("LLM did not return a 'screens' array")

        screens = screens[:self.MAX_SCREENS]
        screens = [self._validate_screen(s, i) for i, s in enumerate(screens)]
        logger.info(f"Extracted {len(screens)} screens from description")
        return screens

    def _validate_screen(self, screen: Any, index: int) -> Dict[str, Any]:
        """Ensure each screen has all required fields, filling in defaults where missing."""
        if not isinstance(screen, dict):
            screen = {}

        screen_id = str(screen.get("id", f"screen_{index + 1:02d}"))
        name = str(screen.get("name", f"Step {index + 1}"))
        content = str(screen.get("content", ""))
        actions = screen.get("available_actions", ["continue", "abandon"])
        if not isinstance(actions, list):
            actions = ["continue", "abandon"]
        if "abandon" not in actions:
            actions.append("abandon")
        prior_knowledge = screen.get("requires_prior_knowledge", [])
        if not isinstance(prior_knowledge, list):
            prior_knowledge = []

        return {
            "id": screen_id,
            "name": name,
            "content": content,
            "available_actions": actions,
            "requires_prior_knowledge": prior_knowledge,
        }
