from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, visible_user_ids


def apply_owner_scope(stmt: Select, model, db: Session, user: CurrentUser) -> Select:
    owners = visible_user_ids(db, user)
    if owners is None:
        return stmt
    return stmt.where(model.owner_user_id.in_(owners))
