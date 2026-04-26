"""Database access layer for the FHH PostgreSQL relational tables.

Wraps SQLAlchemy 2.0 with two things the rest of the backend needs:

1. ORM models that mirror ``schema.sql`` (used by the FastAPI layer in Prompt 3).
2. CRUD helpers + a ``get_machine_status`` view function that returns the
   exact health summary a Machine object needs in the API contract.

All ID strings, enum values, and shapes follow ``docs/API_CONTRACT-2.md`` v1.1.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    create_engine, select, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker,
)


# --- Engine & session -------------------------------------------------------

def get_database_url() -> str:
    """Read the Postgres connection string from the env. No hardcoded fallback —
    if ``DATABASE_URL`` isn't set, the caller should set it (see ``.env.example``)
    before constructing the engine."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
            "Supabase connection string, then `export DATABASE_URL=...` (or use a "
            "loader like python-dotenv) before running this module."
        )
    return url


_engine = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), future=True, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope around a block of operations."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- ORM models -------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Machine(Base):
    __tablename__ = "machines"

    machine_id:           Mapped[str]      = mapped_column(String, primary_key=True)
    name:                 Mapped[str]      = mapped_column(String, nullable=False)
    location:             Mapped[str]      = mapped_column(String, nullable=False)
    model:                Mapped[str]      = mapped_column(String, nullable=False, default="Valmet Advantage DCT 200TS")
    installation_date:    Mapped[date]     = mapped_column(Date, nullable=False)
    status:               Mapped[str]      = mapped_column(String, nullable=False, default="running")
    current_speed_mpm:    Mapped[int]      = mapped_column(Integer, nullable=False, default=0)
    current_oee_percent:  Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False, default=0)

    components:       Mapped[list["Component"]]      = relationship(back_populates="machine", cascade="all, delete-orphan")
    production_runs:  Mapped[list["ProductionRun"]]  = relationship(back_populates="machine", cascade="all, delete-orphan")
    alarms:           Mapped[list["AlarmEvent"]]     = relationship(back_populates="machine", cascade="all, delete-orphan")


class Component(Base):
    __tablename__ = "components"

    machine_id:                    Mapped[str]            = mapped_column(String, ForeignKey("machines.machine_id", ondelete="CASCADE"), primary_key=True)
    component_id:                  Mapped[str]            = mapped_column(String, primary_key=True)
    name:                          Mapped[str]            = mapped_column(String, nullable=False)
    is_critical:                   Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)
    expected_lifetime_hours:       Mapped[int]            = mapped_column(Integer, nullable=False)
    hours_since_last_maintenance:  Mapped[int]            = mapped_column(Integer, nullable=False, default=0)
    last_maintenance_date:         Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    machine: Mapped[Machine] = relationship(back_populates="components")


class ProductionRun(Base):
    __tablename__ = "production_runs"

    run_id:        Mapped[str]      = mapped_column(String, primary_key=True)
    machine_id:    Mapped[str]      = mapped_column(String, ForeignKey("machines.machine_id", ondelete="CASCADE"), nullable=False)
    start_time:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time:      Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    product_grade: Mapped[str]      = mapped_column(String, nullable=False)
    tons_produced: Mapped[float]    = mapped_column(Numeric(8, 2), nullable=False)
    oee_percent:   Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)
    shift:         Mapped[str]      = mapped_column(String, nullable=False)

    machine: Mapped[Machine] = relationship(back_populates="production_runs")


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    log_id:           Mapped[str]      = mapped_column(String, primary_key=True)
    machine_id:       Mapped[str]      = mapped_column(String, nullable=False)
    component_id:     Mapped[str]      = mapped_column(String, nullable=False)
    maintenance_type: Mapped[str]      = mapped_column(String, nullable=False)
    date_performed:   Mapped[date]     = mapped_column(Date, nullable=False)
    cost_usd:         Mapped[float]    = mapped_column(Numeric(10, 2), nullable=False)
    downtime_hours:   Mapped[float]    = mapped_column(Numeric(6, 2), nullable=False, default=0)
    technician:       Mapped[str]      = mapped_column(String, nullable=False)
    notes:            Mapped[Optional[str]] = mapped_column(Text)


class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    alarm_id:         Mapped[str]                = mapped_column(String, primary_key=True)
    machine_id:       Mapped[str]                = mapped_column(String, ForeignKey("machines.machine_id", ondelete="CASCADE"), nullable=False)
    timestamp:        Mapped[datetime]           = mapped_column(DateTime(timezone=True), nullable=False)
    severity:         Mapped[str]                = mapped_column(String, nullable=False)
    description:      Mapped[str]                = mapped_column(Text, nullable=False)
    resolved_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    downtime_minutes: Mapped[int]                = mapped_column(Integer, nullable=False, default=0)

    machine: Mapped[Machine] = relationship(back_populates="alarms")


class QualityScan(Base):
    __tablename__ = "quality_scans"

    scan_id:           Mapped[str]      = mapped_column(String, primary_key=True)
    run_id:            Mapped[str]      = mapped_column(String, ForeignKey("production_runs.run_id", ondelete="CASCADE"), nullable=False)
    timestamp:         Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    basis_weight_gsm:  Mapped[float]    = mapped_column(Numeric(6, 2), nullable=False)
    moisture_percent:  Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)
    softness_index:    Mapped[float]    = mapped_column(Numeric(5, 2), nullable=False)
    caliper_microns:   Mapped[float]    = mapped_column(Numeric(6, 2), nullable=False)


# --- CRUD helpers -----------------------------------------------------------
# Plain functions (not methods) so they can be called from FastAPI handlers
# or scripts without instantiating a class. Each one takes an open Session.

# machines ------------------------------------------------------------------

def list_machines(s: Session) -> list[Machine]:
    return list(s.scalars(select(Machine).order_by(Machine.machine_id)))


def get_machine(s: Session, machine_id: str) -> Optional[Machine]:
    return s.get(Machine, machine_id)


def upsert_machine(s: Session, **fields: Any) -> Machine:
    machine = s.get(Machine, fields["machine_id"])
    if machine is None:
        machine = Machine(**fields)
        s.add(machine)
    else:
        for k, v in fields.items():
            setattr(machine, k, v)
    return machine


# components ----------------------------------------------------------------

def list_components(s: Session, machine_id: str) -> list[Component]:
    """Returns components in canonical line order so callers don't need to sort."""
    line_order = ["headbox", "visconip", "yankee", "aircap", "softreel", "rewinder"]
    components = list(s.scalars(
        select(Component).where(Component.machine_id == machine_id)
    ))
    components.sort(key=lambda c: line_order.index(c.component_id))
    return components


def get_component(s: Session, machine_id: str, component_id: str) -> Optional[Component]:
    return s.get(Component, (machine_id, component_id))


# production_runs -----------------------------------------------------------

def list_production_runs(
    s: Session,
    machine_id: Optional[str] = None,
    limit: int = 100,
) -> list[ProductionRun]:
    stmt = select(ProductionRun).order_by(ProductionRun.start_time.desc()).limit(limit)
    if machine_id:
        stmt = stmt.where(ProductionRun.machine_id == machine_id)
    return list(s.scalars(stmt))


def insert_production_run(s: Session, **fields: Any) -> ProductionRun:
    run = ProductionRun(**fields)
    s.add(run)
    return run


# maintenance_logs ----------------------------------------------------------

def list_maintenance_logs(
    s: Session,
    machine_id: Optional[str] = None,
    component_id: Optional[str] = None,
    limit: int = 200,
) -> list[MaintenanceLog]:
    stmt = select(MaintenanceLog).order_by(MaintenanceLog.date_performed.desc()).limit(limit)
    if machine_id:
        stmt = stmt.where(MaintenanceLog.machine_id == machine_id)
    if component_id:
        stmt = stmt.where(MaintenanceLog.component_id == component_id)
    return list(s.scalars(stmt))


def insert_maintenance_log(s: Session, **fields: Any) -> MaintenanceLog:
    log = MaintenanceLog(**fields)
    s.add(log)
    return log


# alarm_events --------------------------------------------------------------

def list_alarms(
    s: Session,
    machine_id: Optional[str] = None,
    severity: Optional[str] = None,
    only_active: bool = False,
    limit: int = 100,
) -> list[AlarmEvent]:
    stmt = select(AlarmEvent).order_by(AlarmEvent.timestamp.desc()).limit(limit)
    if machine_id:
        stmt = stmt.where(AlarmEvent.machine_id == machine_id)
    if severity:
        stmt = stmt.where(AlarmEvent.severity == severity)
    if only_active:
        stmt = stmt.where(AlarmEvent.resolved_at.is_(None))
    return list(s.scalars(stmt))


def insert_alarm(s: Session, **fields: Any) -> AlarmEvent:
    alarm = AlarmEvent(**fields)
    s.add(alarm)
    return alarm


def resolve_alarm(s: Session, alarm_id: str, resolved_at: Optional[datetime] = None) -> Optional[AlarmEvent]:
    alarm = s.get(AlarmEvent, alarm_id)
    if alarm is None:
        return None
    alarm.resolved_at = resolved_at or datetime.now(timezone.utc)
    return alarm


# quality_scans -------------------------------------------------------------

def list_quality_scans(
    s: Session,
    run_id: Optional[str] = None,
    limit: int = 200,
) -> list[QualityScan]:
    stmt = select(QualityScan).order_by(QualityScan.timestamp.desc()).limit(limit)
    if run_id:
        stmt = stmt.where(QualityScan.run_id == run_id)
    return list(s.scalars(stmt))


def insert_quality_scan(s: Session, **fields: Any) -> QualityScan:
    scan = QualityScan(**fields)
    s.add(scan)
    return scan


# --- View function ----------------------------------------------------------

def get_machine_status(machine_id: str) -> Optional[dict]:
    """Health summary for one machine, shaped to match the API contract's
    ``Machine object``. Returns ``None`` if the machine doesn't exist.

    The risk_score / risk_tier fields are populated downstream by the AI
    layer (Prompt 3); here they default to neutral so the response is still
    contract-shaped.
    """
    sql = text("""
        SELECT machine_id, name, location, model, installation_date,
               status, current_speed_mpm, current_oee_percent,
               active_alerts_count, active_critical_count, last_maintenance_date
        FROM current_machine_status
        WHERE machine_id = :machine_id
    """)
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"machine_id": machine_id}).mappings().first()
    if row is None:
        return None
    return {
        "machine_id":           row["machine_id"],
        "name":                 row["name"],
        "location":             row["location"],
        "model":                row["model"],
        "installation_date":    row["installation_date"].isoformat() if row["installation_date"] else None,
        "status":               row["status"],
        "current_speed_mpm":    row["current_speed_mpm"],
        "current_oee_percent":  float(row["current_oee_percent"]),
        "active_alerts_count":  int(row["active_alerts_count"]),
        # risk_score / risk_tier filled in by the AI layer; expose neutral
        # defaults so callers see the full Machine-object shape today.
        "risk_score":           0,
        "risk_tier":            "healthy",
    }


# --- Quick smoke test -------------------------------------------------------

if __name__ == "__main__":
    # Lightweight sanity check: connect, count rows in each table, print the
    # status row for al-nakheel. Useful after running seed_data.py.
    with get_engine().connect() as conn:
        for tbl in ("machines", "components", "production_runs", "maintenance_logs",
                    "alarm_events", "quality_scans"):
            n = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar_one()
            print(f"  {tbl:18s} {n:>7d}")
    status = get_machine_status("al-nakheel")
    print("get_machine_status('al-nakheel'):", status)
