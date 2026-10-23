from datetime import date, datetime

from sqlalchemy import Row, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .db_schemas import Actual, Forecast
from .utils import to_db


class ForecastsService:
    """Read and write operations for the forecasts table."""

    def count(self, session: Session) -> int:
        """Return the number of cached forecast rows."""
        return session.scalar(select(func.count()).select_from(Forecast)) or 0

    def time_bounds(
        self, session: Session
    ) -> tuple[datetime | None, datetime | None]:
        """Return the minimum and maximum cached forecast start times."""
        return (
            session.scalar(select(func.min(Forecast.start_time))),
            session.scalar(select(func.max(Forecast.start_time))),
        )

    def select_selections(
        self, session: Session, start: datetime, end: datetime, lead_time_hours: int
    ) -> list[Row]:
        """Read cached selections for a lead time within a target range."""
        return session.execute(
            select(
                Forecast.start_time,
                Forecast.publish_time,
                Forecast.generation_mw,
                Forecast.status,
            ).where(
                Forecast.dataset == "WINDFOR",
                Forecast.lead_time_hours == lead_time_hours,
                Forecast.start_time >= to_db(start),
                Forecast.start_time < to_db(end),
            )
        ).all()

    def coverage(
        self, session: Session, start: datetime, end: datetime, leads: list[int]
    ) -> list[Row]:
        """Read cached target and lead-time pairs for the given leads."""
        return session.execute(
            select(Forecast.start_time, Forecast.lead_time_hours).where(
                Forecast.dataset == "WINDFOR",
                Forecast.lead_time_hours.in_(leads),
                Forecast.start_time >= to_db(start),
                Forecast.start_time < to_db(end),
            )
        ).all()

    def upsert_selections(self, session: Session, rows: list[dict]) -> None:
        """Insert or update cached forecast selections in batches and commit."""
        try:
            for offset in range(0, len(rows), 500):
                chunk = rows[offset : offset + 500]
                values = [
                    {
                        "dataset": "WINDFOR",
                        "start_time": to_db(row["start_time"]),
                        "lead_time_hours": row["lead_time_hours"],
                        "publish_time": (
                            to_db(row["publish_time"])
                            if row["publish_time"] is not None
                            else None
                        ),
                        "generation_mw": row["generation_mw"],
                        "status": row["status"],
                    }
                    for row in chunk
                ]
                statement = sqlite_insert(Forecast).values(values)
                statement = statement.on_conflict_do_update(
                    index_elements=[
                        Forecast.dataset,
                        Forecast.start_time,
                        Forecast.lead_time_hours,
                    ],
                    set_={
                        "publish_time": statement.excluded.publish_time,
                        "generation_mw": statement.excluded.generation_mw,
                        "status": statement.excluded.status,
                    },
                )
                session.execute(statement)
            session.commit()
        except Exception:
            session.rollback()
            raise


class ActualsService:
    """Read and write operations for the actuals table."""

    def count(self, session: Session) -> int:
        """Return the number of cached actual rows."""
        return session.scalar(select(func.count()).select_from(Actual)) or 0

    def time_bounds(
        self, session: Session
    ) -> tuple[datetime | None, datetime | None]:
        """Return the minimum and maximum cached actual start times."""
        return (
            session.scalar(select(func.min(Actual.start_time))),
            session.scalar(select(func.max(Actual.start_time))),
        )

    def select_range(
        self, session: Session, start: datetime, end: datetime
    ) -> list[Row]:
        """Read national WIND actuals within a target range."""
        return session.execute(
            select(
                Actual.start_time,
                Actual.publish_time,
                Actual.generation_mw,
                Actual.settlement_period,
            )
            .where(
                Actual.dataset == "FUELHH",
                Actual.fuel_type == "WIND",
                Actual.start_time >= to_db(start),
                Actual.start_time < to_db(end),
            )
            .order_by(Actual.start_time, Actual.publish_time)
        ).all()

    def cached_settlement_dates(
        self, session: Session, start_date: date, end_date: date
    ) -> set[date]:
        """Return the settlement dates that already have cached actuals."""
        return set(
            session.scalars(
                select(Actual.settlement_date)
                .where(
                    Actual.dataset == "FUELHH",
                    Actual.fuel_type == "WIND",
                    Actual.settlement_date >= start_date,
                    Actual.settlement_date <= end_date,
                )
                .distinct()
            )
        )

    def upsert(self, session: Session, rows: list[dict]) -> None:
        """Insert or update actual rows in batches and commit."""
        try:
            for offset in range(0, len(rows), 500):
                chunk = rows[offset : offset + 500]
                values = [
                    {
                        "dataset": "FUELHH",
                        "start_time": to_db(row["start_time"]),
                        "publish_time": to_db(row["publish_time"]),
                        "settlement_date": row["settlement_date"],
                        "settlement_period": row["settlement_period"],
                        "fuel_type": "WIND",
                        "generation_mw": row["generation_mw"],
                    }
                    for row in chunk
                ]
                statement = sqlite_insert(Actual).values(values)
                statement = statement.on_conflict_do_update(
                    index_elements=[
                        Actual.dataset,
                        Actual.start_time,
                        Actual.fuel_type,
                    ],
                    set_={
                        "publish_time": statement.excluded.publish_time,
                        "settlement_date": statement.excluded.settlement_date,
                        "settlement_period": statement.excluded.settlement_period,
                        "generation_mw": statement.excluded.generation_mw,
                    },
                )
                session.execute(statement)
            session.commit()
        except Exception:
            session.rollback()
            raise


forecasts_service = ForecastsService()
actuals_service = ActualsService()
