from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(20), nullable=False, default="WINDFOR")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    lead_time_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generation_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")

    __table_args__ = (
        UniqueConstraint(
            "dataset",
            "start_time",
            "lead_time_hours",
            name="uq_forecasts_selection",
        ),
        Index(
            "ix_forecasts_lookup",
            "dataset",
            "lead_time_hours",
            "start_time",
        ),
    )


class Actual(Base):
    __tablename__ = "actuals"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(20), nullable=False, default="FUELHH")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    publish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_period: Mapped[int] = mapped_column(Integer, nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False, default="WIND")
    generation_mw: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "dataset",
            "start_time",
            "fuel_type",
            name="uq_actuals_record",
        ),
        Index("ix_actuals_settlement_date", "settlement_date"),
    )
