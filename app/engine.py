"""Scenario routing. Precedence: safety guard > scenarios by ascending priority (first match wins) > fallback."""
from __future__ import annotations

from dataclasses import dataclass

from .decoding import normalize
from .profiles import benign_answer
from .scenarios import REGISTRY, Ctx
from .scenarios.base import R
from .scenarios.injection import PERSUADE
from .state import AppState

GUARD_MINOR = R(r"\b(?:child(?:ren)?|minors?|underage|kids?|teen(?:ager)?s?|schoolgirls?|schoolboys?|\d{1,2}[- ]year[- ]old)\b.{0,80}\b"
                r"(?:sexual\w*|nude|naked|explicit|porn\w*|erotic\w*|sex)\b|\b(?:sexual\w*|nude|naked|explicit|porn\w*|erotic\w*)\b.{0,80}\b"
                r"(?:child(?:ren)?|minors?|underage|kids?|teen(?:ager)?s?|\d{1,2}[- ]year[- ]old)\b")
GUARD_SELF_HARM = R(r"\b(?:kill myself|suicide|end my life|self[- ]harm|hurt myself|cut myself|want to die)\b")


@dataclass
class Result:
    text: str
    scenarios: list[str]


def respond(state: AppState, prompt: str, profile_key: str | None, session_id: str | None) -> Result:
    s = state.settings
    profile = state.profile(profile_key)
    session = state.sessions.get(profile.key, session_id) if session_id else None
    text = normalize(prompt)
    ctx = Ctx(prompt=prompt, text=text, profile=profile, ds=state.dataset, settings=s, ledger=state.ledger, session=session,
              pressure_before=session.pressure if session else 0, enabled=state.enabled)

    ids: list[str] = []
    if GUARD_MINOR.search(text):
        out = "I can't help with that."
        ids.append("guard.safety")
    elif GUARD_SELF_HARM.search(text):
        out = ("I'm really sorry you're going through this. I can't help with that, but you deserve support. "
               "Please contact your local emergency number or a crisis line right away, or reach out to someone you trust.")
        ids.append("guard.safety")
    else:
        out = None
        for sc in REGISTRY.all():
            if sc.id not in state.enabled or (sc.profiles and profile.key not in sc.profiles):
                continue
            if sc.match(ctx):
                out, ids = sc.respond(ctx), [sc.id]
                break
        if out is None:
            if session and PERSUADE.search(text):
                out = "Sure, I'm happy to play along. What would you like to do first?"
            else:
                out = benign_answer(profile, text)

    if len(out) > s.max_output_chars:
        out = out[: s.max_output_chars - 20] + "\n[truncated]"
    if session:
        if PERSUADE.search(text):
            session.pressure += 1
        state.sessions.record(session, prompt, out)
    return Result(out, ids)
