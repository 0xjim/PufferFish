"""
PufferFish Traversal Engine

Runs product experience simulations: each agent navigates a product artifact
(PRD, UI flow, pricing page) screen by screen and logs comprehension, friction,
and abandonment at every step.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient

logger = get_logger('pufferfish.traversal')


@dataclass
class TraversalEvent:
    """A single agent-screen interaction record."""
    agent_id: str
    cohort: str
    screen_id: str
    screen_name: str
    action_taken: str          # one of the screen's available_actions
    comprehension_score: int   # 1 (confused) – 5 (crystal clear)
    confusion_signal: str      # what specifically confused them, or "" if none
    trust_score: int           # 1 (suspicious) – 5 (fully trusting)
    would_proceed: bool
    time_on_screen: str        # "short" | "medium" | "long"
    reasoning: str             # agent's internal monologue
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "cohort": self.cohort,
            "screen_id": self.screen_id,
            "screen_name": self.screen_name,
            "action_taken": self.action_taken,
            "comprehension_score": self.comprehension_score,
            "confusion_signal": self.confusion_signal,
            "trust_score": self.trust_score,
            "would_proceed": self.would_proceed,
            "time_on_screen": self.time_on_screen,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


def _clamp(value: int, lo: int = 1, hi: int = 5) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return lo


class TraversalEngine:
    """
    Runs a full traversal simulation for a given cohort through a product artifact.

    Usage:
        engine = TraversalEngine(simulation_id, screens, personas, llm_client)
        result_events = engine.run(progress_callback=...)
    """

    def __init__(
        self,
        simulation_id: str,
        screens: List[Dict[str, Any]],
        personas: List[Dict[str, Any]],
        llm_client: LLMClient,
        metric: str = "task completion",
    ):
        self.simulation_id = simulation_id
        self.screens = screens
        self.personas = personas
        self.llm_client = llm_client
        self.metric = metric

        self._sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(self._sim_dir, exist_ok=True)

        self._events_path = os.path.join(self._sim_dir, "traversal_events.jsonl")
        self._summary_path = os.path.join(self._sim_dir, "traversal_summary.json")

        # In-memory cache of events written so far (for memory context)
        self._all_events: List[TraversalEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, progress_callback=None) -> List[TraversalEvent]:
        """
        Run the full traversal for all personas.
        Writes each event to traversal_events.jsonl immediately.

        progress_callback(events_done: int, total: int, message: str)
        """
        total = len(self.personas) * len(self.screens)
        events_done = 0

        for persona in self.personas:
            agent_id = persona.get("agent_id", persona.get("name", "unknown"))
            logger.info(f"[{self.simulation_id}] Starting traversal for agent: {agent_id}")

            prior_events: List[TraversalEvent] = []
            abandoned = False

            for screen in self.screens:
                if abandoned:
                    break

                screen_id = screen.get("id", screen.get("screen_id", f"screen_{events_done}"))
                screen_name = screen.get("name", screen_id)

                memory_context = self._build_agent_memory(agent_id, prior_events)

                try:
                    event = self._traverse_screen(persona, screen, memory_context)
                except Exception as e:
                    logger.error(f"[{self.simulation_id}] LLM error for {agent_id} on {screen_id}: {e}")
                    event = self._fallback_event(persona, screen)

                prior_events.append(event)
                self._all_events.append(event)
                self._save_event(event)
                events_done += 1

                if progress_callback:
                    progress_callback(
                        events_done,
                        total,
                        f"Screen {screen_name} | Agent {agent_id}",
                    )

                if event.action_taken == "abandon":
                    abandoned = True
                    logger.info(f"[{self.simulation_id}] Agent {agent_id} abandoned at {screen_id}")

        self._save_summary()
        logger.info(f"[{self.simulation_id}] Traversal complete. {events_done} events written.")
        return self._all_events

    # ------------------------------------------------------------------
    # Private: per-screen LLM call
    # ------------------------------------------------------------------

    def _traverse_screen(
        self,
        persona: Dict[str, Any],
        screen: Dict[str, Any],
        memory_context: str,
    ) -> TraversalEvent:
        messages = self._build_traversal_prompt(persona, screen, memory_context)
        raw = self.llm_client.chat_json(messages, temperature=0.7, max_tokens=1024)
        return self._parse_event(persona, screen, raw)

    def _build_traversal_prompt(
        self,
        persona: Dict[str, Any],
        screen: Dict[str, Any],
        memory_context: str,
    ) -> List[Dict[str, str]]:
        agent_id = persona.get("agent_id", "agent")
        name = persona.get("name", agent_id)
        bio = persona.get("bio", "")
        persona_text = persona.get("persona", "")
        domain_literacy = persona.get("domain_literacy", "medium")
        mental_model = persona.get("mental_model", "")
        task = persona.get("task", "complete the flow")
        entry_context = persona.get("entry_context", "")
        cohort = persona.get("cohort", "unknown")

        screen_id = screen.get("id", "unknown")
        screen_name = screen.get("name", screen_id)
        content = screen.get("content", "")
        available_actions = screen.get("available_actions", ["continue", "abandon"])
        requires_prior_knowledge = screen.get("requires_prior_knowledge", [])

        system_prompt = f"""You are simulating a real user navigating a product experience.

You ARE {name} ({cohort} user).
Bio: {bio}
Personality: {persona_text}
Domain literacy: {domain_literacy}
Mental model: {mental_model}
Your task: {task}
How you arrived: {entry_context}

Simulate how this exact person would experience the product screen below.
Be authentic to their knowledge level — a novice would be confused by jargon an expert takes for granted.
The success metric for this simulation is: {self.metric}

Respond ONLY with a JSON object. No markdown, no explanation outside the JSON."""

        prior_knowledge_note = ""
        if requires_prior_knowledge:
            prior_knowledge_note = f"\nThis screen assumes the user knows: {', '.join(requires_prior_knowledge)}"

        memory_note = f"\n\nYour experience so far:\n{memory_context}" if memory_context else ""

        user_prompt = f"""You have reached this screen:

Screen: {screen_name}
---
{content}
---{prior_knowledge_note}{memory_note}

Available actions: {json.dumps(available_actions)}

Based on who you are and what you've experienced so far, respond with:
{{
  "action_taken": "<one of the available_actions>",
  "comprehension_score": <1-5, where 1=completely confused, 5=crystal clear>,
  "confusion_signal": "<specific thing that confused you, or empty string if nothing did>",
  "trust_score": <1-5, where 1=very suspicious, 5=fully trust this>,
  "would_proceed": <true or false>,
  "time_on_screen": "<short|medium|long>",
  "reasoning": "<your internal monologue — what you're thinking as you read this>"
}}"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_event(
        self,
        persona: Dict[str, Any],
        screen: Dict[str, Any],
        raw: Dict[str, Any],
    ) -> TraversalEvent:
        agent_id = persona.get("agent_id", persona.get("name", "unknown"))
        cohort = persona.get("cohort", "unknown")
        screen_id = screen.get("id", screen.get("screen_id", "unknown"))
        screen_name = screen.get("name", screen_id)
        available_actions = screen.get("available_actions", ["continue", "abandon"])

        action = str(raw.get("action_taken", "abandon"))
        if action not in available_actions:
            action = available_actions[0] if available_actions else "abandon"

        time_on_screen = str(raw.get("time_on_screen", "medium"))
        if time_on_screen not in ("short", "medium", "long"):
            time_on_screen = "medium"

        return TraversalEvent(
            agent_id=agent_id,
            cohort=cohort,
            screen_id=screen_id,
            screen_name=screen_name,
            action_taken=action,
            comprehension_score=_clamp(raw.get("comprehension_score", 1)),
            confusion_signal=str(raw.get("confusion_signal", "")),
            trust_score=_clamp(raw.get("trust_score", 3)),
            would_proceed=bool(raw.get("would_proceed", False)),
            time_on_screen=time_on_screen,
            reasoning=str(raw.get("reasoning", "")),
        )

    def _fallback_event(
        self,
        persona: Dict[str, Any],
        screen: Dict[str, Any],
    ) -> TraversalEvent:
        """Returned when the LLM call fails — marks the screen as abandoned."""
        return TraversalEvent(
            agent_id=persona.get("agent_id", persona.get("name", "unknown")),
            cohort=persona.get("cohort", "unknown"),
            screen_id=screen.get("id", screen.get("screen_id", "unknown")),
            screen_name=screen.get("name", "unknown"),
            action_taken="abandon",
            comprehension_score=1,
            confusion_signal="[LLM call failed — defaulted to abandon]",
            trust_score=1,
            would_proceed=False,
            time_on_screen="short",
            reasoning="[simulation error]",
        )

    # ------------------------------------------------------------------
    # Private: memory context builder
    # ------------------------------------------------------------------

    def _build_agent_memory(
        self,
        agent_id: str,
        prior_events: List[TraversalEvent],
    ) -> str:
        if not prior_events:
            return ""
        lines = []
        for e in prior_events:
            status = "completed" if e.action_taken != "abandon" else "abandoned"
            confusion = f" Confused by: {e.confusion_signal}" if e.confusion_signal else ""
            lines.append(
                f"- {e.screen_name}: comprehension {e.comprehension_score}/5, "
                f"{status}.{confusion}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private: persistence
    # ------------------------------------------------------------------

    def _save_event(self, event: TraversalEvent):
        """Append a single event to the JSONL file."""
        with open(self._events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def _save_summary(self):
        """Write aggregated summary JSON after the run completes."""
        total_events = len(self._all_events)
        if total_events == 0:
            return

        # Per-screen stats
        screen_stats: Dict[str, Dict] = {}
        for screen in self.screens:
            sid = screen.get("id", screen.get("screen_id", "unknown"))
            screen_stats[sid] = {
                "screen_id": sid,
                "screen_name": screen.get("name", sid),
                "agents_reached": 0,
                "agents_abandoned": 0,
                "comprehension_scores": [],
                "trust_scores": [],
            }

        for e in self._all_events:
            sid = e.screen_id
            if sid not in screen_stats:
                screen_stats[sid] = {
                    "screen_id": sid,
                    "screen_name": e.screen_name,
                    "agents_reached": 0,
                    "agents_abandoned": 0,
                    "comprehension_scores": [],
                    "trust_scores": [],
                }
            stats = screen_stats[sid]
            stats["agents_reached"] += 1
            if e.action_taken == "abandon":
                stats["agents_abandoned"] += 1
            stats["comprehension_scores"].append(e.comprehension_score)
            stats["trust_scores"].append(e.trust_score)

        # Compute averages
        for sid, stats in screen_stats.items():
            scores = stats["comprehension_scores"]
            trusts = stats["trust_scores"]
            reached = stats["agents_reached"]
            stats["avg_comprehension"] = round(sum(scores) / len(scores), 2) if scores else 0
            stats["avg_trust"] = round(sum(trusts) / len(trusts), 2) if trusts else 0
            stats["dropout_rate"] = round(stats["agents_abandoned"] / max(reached, 1), 2)

        summary = {
            "simulation_id": self.simulation_id,
            "metric": self.metric,
            "total_agents": len(self.personas),
            "total_screens": len(self.screens),
            "total_events": total_events,
            "completed_at": datetime.now().isoformat(),
            "screen_stats": list(screen_stats.values()),
        }

        with open(self._summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
