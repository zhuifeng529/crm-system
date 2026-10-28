from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel, Field

from app.config import get_settings

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100, alias="pageSize")

    model_config = {"populate_by_name": True}


def normalize_page(page: int = 1, page_size: int | None = None) -> tuple[int, int, int]:
    settings = get_settings()
    page = max(page, 1)
    size = page_size or settings.default_page_size
    size = min(max(size, 1), settings.max_page_size)
    offset = (page - 1) * size
    return page, size, offset


class Page(BaseModel, Generic[T]):
    items: Sequence[T]
    page: int
    pageSize: int
    total: int
