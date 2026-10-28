# -*- coding: utf-8 -*-
"""系统使用说明书接口（供前端个人菜单「系统使用说明书」拉取）。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.errors import AppError
from app.deps import CurrentUser, get_current_user
from app.schemas.help import ManualMetaOut, ManualOut
from app.services.help_manual import get_user_manual_meta, load_user_manual

router = APIRouter(prefix="/help")


@router.get("/manual", response_model=ManualOut)
def get_manual(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ManualOut:
    """返回完整说明书（Markdown）及目录。登录用户均可访问，无额外权限码。"""
    _ = user
    try:
        return ManualOut.model_validate(load_user_manual())
    except FileNotFoundError as exc:
        raise AppError("NOT_FOUND", "系统使用说明书不存在", 404) from exc


@router.get("/manual/meta", response_model=ManualMetaOut)
def get_manual_meta(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ManualMetaOut:
    """仅返回标题、版本与目录，不含正文。"""
    _ = user
    try:
        return ManualMetaOut.model_validate(get_user_manual_meta())
    except FileNotFoundError as exc:
        raise AppError("NOT_FOUND", "系统使用说明书不存在", 404) from exc
