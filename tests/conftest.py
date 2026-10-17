import logging

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TARGET = "t" * 8 + "Kq9vXz3LmP7wRt2YhB5nCd8Fg"
ADMIN = "a" * 8 + "Wz4NpQ6sVx1JkL9mHr3TyB7Dc"
H_T = {"Authorization": f"Bearer {TARGET}"}
H_A = {"Authorization": f"Bearer {ADMIN}"}


def make_settings(**kw) -> Settings:
    base = dict(target_api_key=TARGET, admin_api_key=ADMIN, seed=1234, rate_limit_per_minute=0)
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def app():
    return create_app(make_settings())


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def chat(client, caplog):
    caplog.set_level(logging.INFO, logger="redteam.target")

    def _chat(prompt, profile="support", session_id=None):
        caplog.clear()
        body = {"prompt": prompt, "profile": profile}
        if session_id:
            body["session_id"] = session_id
        r = client.post("/chat", json=body, headers=H_T)
        assert r.status_code == 200, r.text
        ids = []
        for rec in caplog.records:
            msg = rec.getMessage()
            if "scenarios=" in msg:
                v = msg.split("scenarios=")[1].split()[0]
                ids = [] if v == "-" else v.split(",")
        return r.json()["response"], ids

    return _chat


@pytest.fixture
def canaries(client):
    return client.get("/admin/manifest?reveal_canaries=true", headers=H_A).json()["canaries"]
