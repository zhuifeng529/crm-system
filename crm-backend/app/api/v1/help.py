# -*- coding: utf-8 -*-
"""系统使用说明书接口（供前端个人菜单「系统使用说明书」拉取）。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.errors import AppError
from app.deps import CurrentUser, get_current_user
from app.services.help_manual import get_user_manual_meta, load_user_manual

router = APIRouter(prefix="/help")


@router.get("/manual")
def get_manual(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """返回完整说明书（Markdown）及目录。登录用户均可访问，无额外权限码。"""
    _ = user
    try:
        return load_user_manual()
    except FileNotFoundError as exc:
        raise AppError("NOT_FOUND", "系统使用说明书不存在", 404) from exc


@router.get("/manual/meta")
def get_manual_meta(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """仅返回标题、版本与目录，不含正文。"""
    _ = user
    try:
        return get_user_manual_meta()
    except FileNotFoundError as exc:
        raise AppError("NOT_FOUND", "系统使用说明书不存在", 404) from exc
