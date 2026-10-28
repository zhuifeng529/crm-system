# -*- coding: utf-8 -*-
from app.services.help_manual import get_user_manual_meta, load_user_manual


def test_load_user_manual_has_content_and_toc():
    manual = load_user_manual()
    assert manual["title"] == "B2B CRM 系统使用说明书"
    assert manual["format"] == "markdown"
    assert manual["version"] == "1.0.0"
    assert "线索 → 客户 → 商机" in manual["content"]
    assert isinstance(manual["toc"], list)
    assert len(manual["toc"]) >= 5
    assert all("level" in item and "id" in item and "title" in item for item in manual["toc"])
    # 文首 H1 不进入 toc
    assert all(item["level"] >= 2 for item in manual["toc"])


def test_manual_meta_omits_body():
    meta = get_user_manual_meta()
    assert "content" not in meta
    assert meta["title"] == "B2B CRM 系统使用说明书"
    assert meta["toc"]
