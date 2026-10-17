"""FastAPI application factory. Run with: uvicorn app.main:create_app --factory (single worker)."""
from __future__ import annotations

import hmac
import logging

from fastapi import Body, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import admin_page, coverage, engine
from .config import Settings
from .data import fingerprint
from .middleware import RequestContextMiddleware
from .scenarios import REGISTRY
from .sessions import SESSION_ID_RE
from .state import AppState, StateError


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str, headers: dict | None = None):
        self.status, self.code, self.detail, self.headers = status, code, detail, headers or {}


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: str
    profile: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    dataset_id: str


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    profile: str | None = None
    enabled_scenarios: list[str] | None = None
    record_count: int | None = None


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def _check(token: str, expected: str) -> bool:
    return bool(token) and hmac.compare_digest(token.encode(), expected.encode())


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()          # raises ConfigError on missing/unsafe keys
    logging.getLogger("redteam.target").setLevel(settings.log_level)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=settings.log_level, format="%(asctime)s %(name)s %(message)s")
    state = AppState(settings)
    app = FastAPI(title="AI red-team demo target", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.demo = state
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.max_body_bytes)   # no CORS middleware on purpose

    def err(status, code, detail, headers=None):
        return JSONResponse({"error": code, "detail": detail}, status_code=status, headers=headers)

    @app.exception_handler(ApiError)
    async def _api_error(_, exc: ApiError):
        return err(exc.status, exc.code, exc.detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_, exc: RequestValidationError):
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors()})
        return err(422, "invalid_request", f"Invalid or missing field(s): {', '.join(fields)}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_, exc: StarletteHTTPException):
        return err(exc.status_code, f"http_{exc.status_code}", "Request could not be processed.")

    def need(expected_attr: str):
        def dep(request: Request):
            if not _check(_bearer(request), getattr(settings, expected_attr)):
                raise ApiError(401, "unauthorized", "Missing or invalid bearer token.", {"WWW-Authenticate": "Bearer"})
        return dep

    target_auth, admin_auth = need("target_api_key"), need("admin_api_key")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(target_auth)])
    async def chat(request: Request, body: ChatRequest):
        wait = state.limiter.check()
        if wait:
            raise ApiError(429, "rate_limited", "Too many requests.", {"Retry-After": str(int(wait) + 1)})
        prompt = body.prompt
        if not prompt.strip():
            raise ApiError(422, "invalid_request", "prompt must not be empty.")
        if len(prompt) > settings.max_prompt_chars:
            raise ApiError(422, "invalid_request", f"prompt exceeds {settings.max_prompt_chars} characters.")
        if body.session_id is not None and not SESSION_ID_RE.match(body.session_id):
            raise ApiError(422, "invalid_request", "session_id must match [A-Za-z0-9._-]{1,64}.")
        try:
            result = engine.respond(state, prompt, body.profile, body.session_id)
        except StateError as exc:
            raise ApiError(422, "invalid_request", str(exc))
        request.state.scenarios = result.scenarios
        return ChatResponse(response=result.text, dataset_id=state.dataset.dataset_id)

    @app.get("/admin/ui", response_class=HTMLResponse)
    async def admin_ui():
        # Static shell: no data. The page's button calls POST /admin/reset with the admin key the operator types in.
        return HTMLResponse(admin_page.HTML, headers=admin_page.HEADERS)

    @app.post("/admin/reset", dependencies=[Depends(admin_auth)])
    async def reset(payload: ResetRequest | None = Body(default=None)):
        p = payload or ResetRequest()
        try:
            return state.reset(p.seed, p.profile, p.enabled_scenarios, p.record_count)
        except StateError as exc:
            raise ApiError(422, "invalid_request", str(exc))

    @app.get("/admin/coverage", dependencies=[Depends(admin_auth)])
    async def get_coverage():
        return {"scenarios": coverage.matrix(state.enabled), "record_count": state.dataset.record_count,
                "note": "Dataset volume is separate from scenario coverage."}

    @app.get("/admin/manifest", dependencies=[Depends(admin_auth)])
    async def manifest(reveal_canaries: bool = Query(False)):
        ds = state.dataset
        out = {
            "run_id": state.run_id, "dataset_id": ds.dataset_id, "seed": ds.seed, "record_count": ds.record_count,
            "fixture_counts": ds.fixture_counts(), "default_profile": state.default_profile,
            "caller": {"caller_id": ds.caller["id"], "caller_tenant": ds.caller["tenant"]},
            "scenarios": [{"id": s.id, "category": s.category, "status": s.status, "enabled": s.id in state.enabled,
                           "marker_canaries": list(s.markers)} for s in REGISTRY.all()],
            "canary_fingerprints": {k: fingerprint(v) for k, v in ds.canaries.items()},
            "ledger": {"count": len(state.ledger.entries), "entries": state.ledger.entries[-50:]},
            "active_sessions": len(state.sessions),
        }
        if reveal_canaries:
            out["canaries"] = dict(ds.canaries)
        return out

    return app
