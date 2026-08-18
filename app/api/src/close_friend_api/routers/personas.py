from typing import Annotated

from close_friend_shared.db.models import Persona
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from close_friend_api.db import get_db

router = APIRouter(prefix="/personas", tags=["personas"])


class PersonaSummary(BaseModel):
    """Narrow read-model — deliberately excludes `character`, `emotion_rules`,
    and `boundaries` so a client can't read a persona's exact triggers out of
    devtools and game the emotional system."""

    id: str
    name: str
    tagline: str
    avatar_initials: str
    tags: list[str]


class ListPersonasResponse(BaseModel):
    personas: list[PersonaSummary]


@router.get("")
def list_personas(db: Annotated[Session, Depends(get_db)]) -> ListPersonasResponse:
    stmt = select(Persona).where(Persona.is_active.is_(True)).order_by(Persona.id)
    rows = db.execute(stmt).scalars().all()
    return ListPersonasResponse(
        personas=[
            PersonaSummary(
                id=row.id,
                name=row.name,
                tagline=row.tagline,
                avatar_initials=row.avatar_initials,
                tags=row.tags,
            )
            for row in rows
        ]
    )
