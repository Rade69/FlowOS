"""SQLAlchemy DeclarativeBase — osnova za sve ORM modele.

Svi modeli u persistence sloju nasleđuju ovu klasu.
ORM modeli su privatni za infrastructure/persistence/ —
ne smeju se importovati izvan service sloja.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Osnovna klasa za sve SQLAlchemy ORM modele u FlowOS-u."""

    pass
