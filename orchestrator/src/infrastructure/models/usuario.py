from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Text, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.models.base import Base

class UserRole(StrEnum):
    ADMIN = "admin"
    PRESIDENCIA = "presidencia"
    VOTANTE = "votante"

class Usuario(Base):
    __tablename__ = "usuarios"
    
    username: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
    )
    apellido: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
    )
    rol: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="rol_usuario_enum"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    __table_args__ = (
        Index("uq_usuarios_username_lower", func.lower(username), unique=True),
        Index("ix_usuarios_active", "deleted_at", postgresql_where=text("deleted_at IS NULL")),
    )