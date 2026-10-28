# -*- coding: utf-8 -*-
"""系统使用说明书 API 响应模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TocItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=2, le=6, description="Markdown 标题级别（不含文首 H1）")
    id: str = Field(description="章节锚点 id；前端渲染 heading 时必须使用此值")
    title: str


class ManualMetaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    version: str
    format: Literal["markdown"] = "markdown"
    updatedAt: str
    toc: list[TocItem]


class ManualOut(ManualMetaOut):
    content: str
