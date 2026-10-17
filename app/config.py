"""Environment-driven settings with fail-fast validation of API keys."""
from __future__ import annotations

import os
from dataclasses import dataclass

PLACEHOLDER_MARKERS = (
    "change", "replace", "your_", "your-", "example", "placeholder", "todo",
    "xxxx", "password", "secret", "test-key", "default",
)
MIN_KEY_LENGTH = 24


class ConfigError(RuntimeError):
    """Raised at startup when configuration is missing or unsafe."""


def validate_key(name: str, value: str | None) -> str:
    if not value or not value.strip():
        raise ConfigError(f"{name} is not set. Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    value = value.strip()
    low = value.lower()
    if len(value) < MIN_KEY_LENGTH:
        raise ConfigError(f"{name} is too short (minimum {MIN_KEY_LENGTH} characters).")
    if any(m in low for m in PLACEHOLDER_MARKERS):
        raise ConfigError(f"{name} looks like a placeholder. Generate a random value instead.")
    return value


def _int(env: dict, name: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if not lo <= val <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}.")
    return val


@dataclass(frozen=True)
class Settings:
    target_api_key: str
    admin_api_key: str
    default_profile: str = "support"
    record_count: int = 1000
    seed: int | None = None
    rate_limit_per_minute: int = 600
    session_ttl_seconds: int = 900
    max_sessions: int = 500
    max_history_turns: int = 20
    max_prompt_chars: int = 8000
    max_output_chars: int = 16000
    max_body_bytes: int = 65536
    max_decode_bytes: int = 2048
    bulk_max_rows: int = 25
    amplify_max_chars: int = 6000
    sim_call_cap: int = 50
    sim_depth_cap: int = 8
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        target = validate_key("TARGET_API_KEY", env.get("TARGET_API_KEY"))
        admin = validate_key("ADMIN_API_KEY", env.get("ADMIN_API_KEY"))
        if target == admin:
            raise ConfigError("TARGET_API_KEY and ADMIN_API_KEY must be different.")
        seed_raw = (env.get("DEMO_SEED") or "").strip()
        try:
            seed = int(seed_raw) if seed_raw else None
        except ValueError as exc:
            raise ConfigError("DEMO_SEED must be an integer.") from exc
        return cls(
            target_api_key=target,
            admin_api_key=admin,
            default_profile=(env.get("DEFAULT_PROFILE") or "support").strip(),
            record_count=_int(env, "RECORD_COUNT", 1000, 50, 10000),
            seed=seed,
            rate_limit_per_minute=_int(env, "RATE_LIMIT_PER_MINUTE", 600, 0, 1_000_000),
            session_ttl_seconds=_int(env, "SESSION_TTL_SECONDS", 900, 1, 86400),
            max_prompt_chars=_int(env, "MAX_PROMPT_CHARS", 8000, 100, 100000),
            max_output_chars=_int(env, "MAX_OUTPUT_CHARS", 16000, 500, 100000),
            log_level=(env.get("LOG_LEVEL") or "INFO").upper(),
        )
