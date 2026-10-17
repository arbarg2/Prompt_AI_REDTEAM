"""Scenario framework: context, scenario definition and registry."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace
from typing import Callable

from ..config import Settings
from ..data import Dataset
from ..profiles import Profile
from ..sessions import Session

CATEGORIES = {
    "sde": "Sensitive Data Exposure",
    "pij": "Prompt Injection & Jailbreaks",
    "hcm": "Harmful Content & Misuse",
    "res": "Resource Abuse",
    "spd": "System Prompt Disclosure",
    "cmp": "Competitor Endorsement",
}
STATUSES = ("implemented", "simulated", "placeholder")


def R(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I | re.S)


@dataclass
class Ledger:
    """In-memory record of simulated 'actions'. Nothing here ever leaves the process."""
    entries: list[dict] = field(default_factory=list)
    cap: int = 500

    def add(self, action: str, **detail) -> str:
        lid = f"L-{len(self.entries) + 1:04d}"
        if len(self.entries) < self.cap:
            self.entries.append({"id": lid, "action": action, **detail})
        return lid


@dataclass
class Ctx:
    prompt: str
    text: str                  # normalized, lowercased prompt (or an alternate decoded variant)
    profile: Profile
    ds: Dataset
    settings: Settings
    ledger: Ledger
    session: Session | None = None
    pressure_before: int = 0
    enabled: frozenset = frozenset()
    scratch: dict = field(default_factory=dict)

    def rng(self, salt: str = "") -> random.Random:
        """Deterministic per (dataset, prompt, salt)."""
        return random.Random(f"{self.ds.seed}:{self.text}:{salt}")

    def canary(self, kind: str) -> str:
        return self.ds.canaries[kind]

    def with_text(self, text: str) -> "Ctx":
        return replace(self, text=text, scratch={})


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    status: str                       # implemented | simulated | placeholder
    priority: int                     # lower runs first; first match wins
    description: str
    outcome: str                      # expected observable outcome
    limitations: str
    match: Callable[[Ctx], bool]
    respond: Callable[[Ctx], str]
    markers: tuple[str, ...] = ()     # canary kinds expected in a triggered response
    required_inputs: str = "prompt"
    profiles: tuple[str, ...] | None = None
    decodable: bool = False           # may also be reached via decoded/de-obfuscated text (pij.encoded)

    @property
    def category(self) -> str:
        return self.id.split(".")[0]


class Registry:
    def __init__(self):
        self._items: dict[str, Scenario] = {}

    def add(self, scenario: Scenario) -> Scenario:
        if scenario.id in self._items:
            raise ValueError(f"duplicate scenario id {scenario.id}")
        if scenario.status not in STATUSES or scenario.category not in CATEGORIES:
            raise ValueError(f"bad scenario definition {scenario.id}")
        self._items[scenario.id] = scenario
        return scenario

    def all(self) -> list[Scenario]:
        return sorted(self._items.values(), key=lambda s: (s.priority, s.id))

    def get(self, sid: str) -> Scenario:
        return self._items[sid]

    def ids(self) -> list[str]:
        return [s.id for s in self.all()]


REGISTRY = Registry()


def scenario(*, id: str, name: str, status: str, priority: int, description: str, outcome: str, limitations: str,
             match: Callable[[Ctx], bool], markers: tuple[str, ...] = (), required_inputs: str = "prompt",
             profiles: tuple[str, ...] | None = None, decodable: bool = False):
    """Decorator: the decorated function is the scenario's response builder."""
    def deco(respond: Callable[[Ctx], str]):
        REGISTRY.add(Scenario(id=id, name=name, status=status, priority=priority, description=description,
                              outcome=outcome, limitations=limitations, match=match, respond=respond,
                              markers=markers, required_inputs=required_inputs, profiles=profiles,
                              decodable=decodable))
        return respond
    return deco


# ---- shared helpers -------------------------------------------------------------------------------------------

DISCLOSE = (r"(?:show|give|tell|reveal|list|share|provide|print|display|dump|output|send|read|fetch|pull up|look up|"
            r"retrieve|expose|disclose|what(?:'s| is| are)|who is|can i (?:see|get|have)|i need|i want|let me see|"
            r"summari[sz]e|quote|excerpt|copy|paste)")
_SAFE = re.compile(r"[^A-Za-z0-9 .,:;'\"!?@/#()$%+=_-]")


def safe_echo(s: str, n: int = 80) -> str:
    """Bounded, character-filtered echo of user text (inert)."""
    return _SAFE.sub("", s).strip()[:n]


def defang(s: str) -> str:
    return re.sub(r"(?i)http", "hxxp", s).replace(".", "[.]")


def pick(ctx: Ctx, seq: list, k: int = 1, salt: str = "") -> list:
    r = ctx.rng(salt)
    return r.sample(seq, min(k, len(seq)))


def record_table(ctx: Ctx) -> list[dict]:
    return ctx.ds.tables[ctx.profile.record_kind]


def extract_n(text: str, default: int, cap: int) -> int:
    m = re.search(r"\b(\d{1,6})\b", text)
    return max(1, min(int(m.group(1)), cap)) if m else default
