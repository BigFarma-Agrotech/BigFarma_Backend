"""Random, non-sequential IDs for anything that appears in a URL (products, orders, group buys).

The integer primary keys stay internal (joins, foreign keys); the API only accepts
and links by `public_id`, so IDs in URLs can't be guessed by counting.
"""
import secrets
import string
from typing import Type

from fastapi import HTTPException
from sqlalchemy.orm import Session

PUBLIC_ID_ALPHABET = string.ascii_letters + string.digits
PUBLIC_ID_LENGTH = 8


def generate_public_id() -> str:
    """8 random letters and digits: 62^8 (~218 trillion) possibilities."""
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


def resolve_id(db: Session, model: Type, public_id: str, label: str = "Item") -> int:
    """Internal integer id for a public id, or 404 if there's no such row."""
    row_id = db.query(model.id).filter(model.public_id == public_id).scalar()
    if row_id is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row_id
