# -*- coding: utf-8 -*-
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import CurrentUser, get_current_user
from app.main import app
from app.services import help_manual
from app.services.help_manual import clear_manual_cache, get_user_manual_meta, load_user_manual


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_manual_cache()
    yield
    clear_manual_cache()
    app.dependency_overrides.clear()


def _fake_user() -> CurrentUser:
    return CurrentUser(
        id=1,
        tenant_id=1,
        dept_id=None,
        username="tester",
        display_name="Tester",
        roles=["admin"],
        permissions=set(),
        data_scope="all",
    )


def test_load_user_manual_has_content_and_toc():
    manual = load_user_manual()
    assert manual["title"] == "B2B CRM 系统使用说明书"
    assert manual["format"] == "markdown"
    assert manual["version"] == "1.0.0"
    assert manual["updatedAt"].endswith("Z")
    assert "线索 → 客户 → 商机" in manual["content"]
    assert isinstance(manual["toc"], list)
    assert len(manual["toc"]) >= 5
    assert all("level" in item and "id" in item and "title" in item for item in manual["toc"])
    assert all(item["level"] >= 2 for item in manual["toc"])


def test_manual_meta_omits_body():
    meta = get_user_manual_meta()
    assert "content" not in meta
    assert meta["title"] == "B2B CRM 系统使用说明书"
    assert meta["toc"]


def test_help_manual_requires_auth():
    with TestClient(app) as client:
        res = client.get("/api/v1/help/manual")
    assert res.status_code == 401
    body = res.json()
    assert body["code"] == "UNAUTHORIZED"


def test_help_manual_ok_with_auth():
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as client:
        res = client.get("/api/v1/help/manual")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "B2B CRM 系统使用说明书"
    assert "content" in body and body["toc"]
    assert all(set(item) >= {"level", "id", "title"} for item in body["toc"])


def test_help_manual_meta_ok_with_auth():
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as client:
        res = client.get("/api/v1/help/manual/meta")
    assert res.status_code == 200
    body = res.json()
    assert "content" not in body
    assert body["toc"]


def test_help_manual_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(help_manual, "MANUAL_PATH", missing)
    clear_manual_cache()
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as client:
        res = client.get("/api/v1/help/manual")
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"
