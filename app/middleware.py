"""ASGI middleware: request IDs, body-size limit, access log without payloads."""
from __future__ import annotations

import json
import logging
import re
import uuid

log = logging.getLogger("redteam.target")
_RID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class BodyTooLarge(Exception):
    pass


class RequestContextMiddleware:
    """Assigns X-Request-ID, enforces a body limit and logs id/status/scenario IDs only."""

    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope["headers"]}
        supplied = headers.get(b"x-request-id", b"").decode("latin-1")
        rid = supplied if _RID.match(supplied) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid
        scope["state"]["scenarios"] = []
        status = {"code": 0}
        started = {"v": False}

        async def send_wrapped(message):
            if message["type"] == "http.response.start":
                started["v"] = True
                status["code"] = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        cl = headers.get(b"content-length", b"")
        if cl.isdigit() and int(cl) > self.max_body:
            await self._reject(send_wrapped)
        else:
            received = 0

            async def limited_receive():
                nonlocal received
                msg = await receive()
                if msg["type"] == "http.request":
                    received += len(msg.get("body", b""))
                    if received > self.max_body:
                        raise BodyTooLarge
                return msg

            try:
                await self.app(scope, limited_receive, send_wrapped)
            except BodyTooLarge:
                if not started["v"]:
                    await self._reject(send_wrapped)
        log.info("request_id=%s method=%s path=%s status=%s scenarios=%s", rid, scope["method"],
                 scope["path"], status["code"], ",".join(scope["state"].get("scenarios", [])) or "-")

    @staticmethod
    async def _reject(send):
        body = json.dumps({"error": "payload_too_large", "detail": "Request body too large."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
