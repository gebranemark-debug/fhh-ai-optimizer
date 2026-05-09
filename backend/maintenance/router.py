"""Maintenance router: POST + GET /machines/{machine_id}/maintenance-log.

POST creates a user-written entry in ``user_maintenance_entries`` (Postgres,
app_schema). GET returns the merged view of analytics (parquet) historical
entries plus user-written ones, newest first, so the existing demo data is
preserved while new entries surface immediately.

machine_id is validated at the application layer against the parquet machine
list — there is no FK from app schema to analytics tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    DateTime, Numeric, String, Text, select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend import data as fhh_data
from backend.auth.security import AppUser, get_current_user
from backend.postgres.db import Base, session_scope


router = APIRouter(tags=["maintenance"])


# ---------------------------------------------------------------------------
# ORM model — mirrors app_schema.sql `user_maintenance_entries`
# ---------------------------------------------------------------------------

class UserMaintenanceEntry(Base):
    __tablename__ = "user_maintenance_entries"

    id:                Mapped[uuid.UUID]  = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id:           Mapped[uuid.UUID]  = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    machine_id:        Mapped[str]        = mapped_column(String(100), nullable=False)
    component_id:      Mapped[Optional[str]] = mapped_column(String(100))
    maintenance_type:  Mapped[str]        = mapped_column(String(50), nullable=False)
    work_description:  Mapped[str]        = mapped_column(Text, nullable=False)
    cost_usd:          Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    duration_hours:    Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    technician_name:   Mapped[str]        = mapped_column(String(255), nullable=False)
    performed_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:        Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MaintenanceLogCreate(BaseModel):
    maintenance_type: str = Field(pattern="^(preventive|corrective|predictive|inspection)$")
    work_description: str = Field(min_length=1, max_length=10000)
    technician_name:  str = Field(min_length=1, max_length=255)
    cost_usd:         Optional[float] = Field(default=None, ge=0)
    duration_hours:   Optional[float] = Field(default=None, ge=0)
    performed_at:     Optional[datetime] = None
    component_id:     Optional[str] = Field(default=None, max_length=100)


class MaintenanceLogEntry(BaseModel):
    log_id: str
    component_id: Optional[str] = None
    maintenance_type: str
    date_performed: str  # ISO date — matches existing parquet response shape
    cost_usd: Optional[float] = None
    downtime_hours: Optional[float] = None
    technician: str
    notes: Optional[str] = None
    source: str  # "user" | "analytics"


class MaintenanceLogResponse(BaseModel):
    machine_id: str
    logs: list[MaintenanceLogEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_machine_id_or_404(machine_id: str) -> None:
    """Validate against the parquet/data layer's machine list — keeps app
    schema independent of analytics FKs but still rejects garbage IDs."""
    try:
        fhh_data.get_machine(machine_id)
    except fhh_data.MachineNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {
                "code": "machine_not_found",
                "message": f"No machine exists with ID '{machine_id}'.",
                "status": 404,
            }},
        )


def _user_entry_to_response(e: UserMaintenanceEntry) -> MaintenanceLogEntry:
    return MaintenanceLogEntry(
        log_id=str(e.id),
        component_id=e.component_id,
        maintenance_type=e.maintenance_type,
        date_performed=e.performed_at.date().isoformat(),
        cost_usd=float(e.cost_usd) if e.cost_usd is not None else None,
        downtime_hours=float(e.duration_hours) if e.duration_hours is not None else None,
        technician=e.technician_name,
        notes=e.work_description,
        source="user",
    )


def _list_user_entries(s: Session, machine_id: str) -> list[UserMaintenanceEntry]:
    stmt = (
        select(UserMaintenanceEntry)
        .where(UserMaintenanceEntry.machine_id == machine_id)
        .order_by(UserMaintenanceEntry.performed_at.desc())
    )
    return list(s.scalars(stmt))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/machines/{machine_id}/maintenance-log",
    response_model=MaintenanceLogEntry,
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance_entry(
    machine_id: str,
    body: MaintenanceLogCreate,
    user: AppUser = Depends(get_current_user),
):
    _validate_machine_id_or_404(machine_id)

    performed_at = body.performed_at or datetime.now(timezone.utc)
    if performed_at.tzinfo is None:
        performed_at = performed_at.replace(tzinfo=timezone.utc)

    with session_scope() as s:
        entry = UserMaintenanceEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            machine_id=machine_id,
            component_id=body.component_id,
            maintenance_type=body.maintenance_type,
            work_description=body.work_description,
            cost_usd=body.cost_usd,
            duration_hours=body.duration_hours,
            technician_name=body.technician_name,
            performed_at=performed_at,
            created_at=datetime.now(timezone.utc),
        )
        s.add(entry)
        s.flush()
        return _user_entry_to_response(entry)


@router.get(
    "/machines/{machine_id}/maintenance-log",
    response_model=MaintenanceLogResponse,
)
def list_maintenance_log(machine_id: str):
    """Return analytics historical entries (from parquet via the data layer)
    merged with user-written entries from Postgres. Newest first."""
    _validate_machine_id_or_404(machine_id)

    # Analytics historical (parquet). Tagged source="analytics" so the UI
    # can distinguish read-only history from editable user entries.
    parquet_payload = fhh_data.get_maintenance_log(machine_id)
    analytics_logs = [
        MaintenanceLogEntry(
            log_id=row["log_id"],
            component_id=row.get("component_id"),
            maintenance_type=row["maintenance_type"],
            date_performed=row["date_performed"],
            cost_usd=row.get("cost_usd"),
            downtime_hours=row.get("downtime_hours"),
            technician=row.get("technician", ""),
            notes=row.get("notes"),
            source="analytics",
        )
        for row in parquet_payload.get("logs", [])
    ]

    with session_scope() as s:
        user_entries = _list_user_entries(s, machine_id)
        user_logs = [_user_entry_to_response(e) for e in user_entries]

    merged = sorted(
        user_logs + analytics_logs,
        key=lambda e: e.date_performed,
        reverse=True,
    )
    return MaintenanceLogResponse(machine_id=machine_id, logs=merged)
