"""Cohort model - placeholder for Phase 2 implementation."""

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forge.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CohortStatus(str, enum.Enum):
    """Cohort lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class ProgrammeType(str, enum.Enum):
    """Programme type offered."""

    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"


class Cohort(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cohort model - the root entity for programme data."""

    __tablename__ = "cohorts"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    programme_type: Mapped[ProgrammeType] = mapped_column(
        Enum(ProgrammeType),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    graduation_threshold: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
    )
    kami_limu_month_boundaries: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ict_tracks_offered: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    status: Mapped[CohortStatus] = mapped_column(
        Enum(CohortStatus),
        default=CohortStatus.DRAFT,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Cohort {self.name}>"
