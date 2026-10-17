"""Process-wide mutable state: dataset, sessions, ledger, run configuration. Single worker only."""
from __future__ import annotations

import secrets
import time
import uuid
from typing import Callable

from .config import Settings
from .data import Dataset, build_dataset
from .profiles import PROFILES, Profile
from .ratelimit import RateLimiter
from .scenarios import CATEGORIES, REGISTRY, Ledger
from .sessions import SessionStore


class StateError(ValueError):
    pass


class AppState:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic):
        self.settings = settings
        self.sessions = SessionStore(settings.session_ttl_seconds, settings.max_sessions, settings.max_history_turns, clock)
        self.limiter = RateLimiter(settings.rate_limit_per_minute, clock)
        self.ledger = Ledger()
        self.default_profile = settings.default_profile
        if self.default_profile not in PROFILES:
            raise StateError(f"DEFAULT_PROFILE must be one of {sorted(PROFILES)}")
        self.enabled: frozenset[str] = frozenset(REGISTRY.ids())
        self.dataset: Dataset
        self.run_id = ""
        self.reset(seed=settings.seed, record_count=settings.record_count)

    def profile(self, key: str | None) -> Profile:
        key = key or self.default_profile
        if key not in PROFILES:
            raise StateError(f"unknown profile '{key}'")
        return PROFILES[key]

    @staticmethod
    def expand_enabled(items: list[str]) -> frozenset[str]:
        if not items:
            raise StateError("enabled_scenarios must not be empty; omit it to keep the current selection")
        out: set[str] = set()
        for item in items:
            if item in CATEGORIES:
                out |= {i for i in REGISTRY.ids() if i.startswith(item + ".")}
            elif item in REGISTRY.ids():
                out.add(item)
            else:
                raise StateError(f"unknown scenario or category '{item[:40]}'")
        return frozenset(out)

    def reset(self, seed: int | None = None, profile: str | None = None, enabled: list[str] | None = None,
              record_count: int | None = None) -> dict:
        # Validate everything before mutating anything.
        if profile is not None:
            self.profile(profile)
        new_enabled = self.expand_enabled(enabled) if enabled is not None else self.enabled
        count = record_count if record_count is not None else getattr(getattr(self, "dataset", None), "record_count", self.settings.record_count)
        seed = secrets.randbelow(2**31) if seed is None else seed
        try:
            dataset = build_dataset(seed, count)
        except ValueError as exc:
            raise StateError(str(exc)) from exc
        self.dataset, self.enabled = dataset, new_enabled
        if profile is not None:
            self.default_profile = profile
        self.sessions.clear()
        self.ledger = Ledger()
        self.run_id = "run-" + uuid.uuid4().hex[:12]
        return {"run_id": self.run_id, "dataset_id": dataset.dataset_id, "seed": seed, "record_count": dataset.record_count,
                "fixture_counts": dataset.fixture_counts(), "default_profile": self.default_profile,
                "enabled_scenarios": sorted(self.enabled)}
