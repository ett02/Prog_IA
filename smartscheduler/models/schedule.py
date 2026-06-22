"""
models/schedule.py — Definizioni Pydantic per Schedule e ShiftAssignment.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import date
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, model_validator


class ShiftType(str, Enum):
    MORNING = "morning"      # peso 1 — 08:00–14:00
    AFTERNOON = "afternoon"  # peso 1 — 14:00–20:00
    NIGHT = "night"          # peso 2 — 20:00–08:00 (+1g)

    def units(self) -> int:
        """Shift-units contate per il vincolo 25/mese."""
        return 2 if self == ShiftType.NIGHT else 1

    def hours(self) -> int:
        """Ore di lavoro effettive."""
        return 12 if self == ShiftType.NIGHT else 6


class ShiftAssignment(BaseModel):
    """Assegnazione di un singolo turno a un lavoratore."""
    worker_id: str
    date: date
    shift_type: ShiftType

    @property
    def units(self) -> int:
        return self.shift_type.units()

    @property
    def hours(self) -> int:
        return self.shift_type.hours()


class DaySchedule(BaseModel):
    """Tutti i turni assegnati in un singolo giorno."""
    date: date
    morning: list[str] = Field(default_factory=list, description="worker_ids")
    afternoon: list[str] = Field(default_factory=list, description="worker_ids")
    night: list[str] = Field(default_factory=list, description="worker_ids")

    def workers_for_shift(self, shift_type: ShiftType) -> list[str]:
        if shift_type == ShiftType.MORNING:
            return self.morning
        if shift_type == ShiftType.AFTERNOON:
            return self.afternoon
        return self.night


class Schedule(BaseModel):
    """Schedule completo per l'orizzonte di un mese."""
    assignments: list[ShiftAssignment] = Field(default_factory=list)
    horizon_start: date
    horizon_end: date
    use_case: str = "A"
    is_verified: bool = False
    fairness_score: Optional[float] = None
    average_fairness_score: Optional[float] = None
    refinement_iterations: int = 0

    def get_worker_assignments(self, worker_id: str) -> list[ShiftAssignment]:
        """Ritorna tutte le assegnazioni di un lavoratore."""
        return [a for a in self.assignments if a.worker_id == worker_id]

    def get_day_schedule(self, target_date: date) -> DaySchedule:
        """Ritorna il DaySchedule per una data specifica."""
        ds = DaySchedule(date=target_date)
        for a in self.assignments:
            if a.date == target_date:
                if a.shift_type == ShiftType.MORNING:
                    ds.morning.append(a.worker_id)
                elif a.shift_type == ShiftType.AFTERNOON:
                    ds.afternoon.append(a.worker_id)
                else:
                    ds.night.append(a.worker_id)
        return ds

    def total_units_for_worker(self, worker_id: str) -> int:
        """Calcola le shift-units totali per un lavoratore."""
        return sum(a.units for a in self.get_worker_assignments(worker_id))

    def total_hours_for_worker_in_window(
        self, worker_id: str, start_date: date, end_date: date
    ) -> int:
        """Ore lavorate in un intervallo di date (estremi inclusi)."""
        return sum(
            a.hours for a in self.get_worker_assignments(worker_id)
            if start_date <= a.date <= end_date
        )

    def to_day_dict(self) -> dict[date, DaySchedule]:
        """Mappa data → DaySchedule per accesso rapido."""
        from datetime import timedelta
        result = {}
        current = self.horizon_start
        while current <= self.horizon_end:
            result[current] = self.get_day_schedule(current)
            current += timedelta(days=1)
        return result
