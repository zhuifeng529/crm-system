from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    page: int
    pageSize: int
    total: int


class MessageOut(BaseModel):
    message: str = "ok"


class IdOut(BaseModel):
    id: int


class CollaboratorIn(BaseModel):
    userId: int
    role: str = "collaborator"


class AuditFields(ORMModel):
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")


def dumps_json(value: Any) -> str | None:
    if value is None:
        return None
    import json

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def loads_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    import json

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
