import enum
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class RoleType(str, enum.Enum):
    ACTOR = "ACTOR"
    DIRECTOR = "DIRECTOR"
    WRITER = "WRITER"


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("name", "tmdb_id", name="uq_people_name_tmdb_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    roles = relationship("Role", back_populates="person", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_role_type_movie_id", "role_type", "movie_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    role_type: Mapped[RoleType] = mapped_column(Enum(RoleType), index=True)
    character_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    billing_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    movie = relationship("api.models.movie.Movie", back_populates="roles")
    person = relationship("Person", back_populates="roles")
