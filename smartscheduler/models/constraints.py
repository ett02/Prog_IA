"""
models/constraints.py — Rappresentazione formale di vincoli hard e soft.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ConstraintType(str, Enum):
    # Hard constraints
    MIN_COVERAGE = "min_coverage"
    MAX_ONE_SHIFT_PER_DAY = "max_one_shift_per_day"
    NO_CONSECUTIVE_SHIFTS = "no_consecutive_shifts"
    REST_AFTER_NIGHT = "rest_after_night"
    MAX_HOURS_PER_WEEK = "max_hours_per_week"
    EXACT_SHIFT_UNITS = "exact_shift_units"
    UNAVAILABLE_DATE = "unavailable_date"
    # Soft constraints
    PREFERRED_SHIFT = "preferred_shift"
    PREFERRED_REST_DAY = "preferred_rest_day"
    NIGHT_TOLERANCE = "night_tolerance"
    HOLIDAY_TOLERANCE = "holiday_tolerance"


class HardConstraint(BaseModel):
    """Vincolo hard: deve essere soddisfatto, altrimenti lo schedule è invalido."""
    constraint_type: ConstraintType
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def is_hard(self) -> bool:
        return True


class SoftConstraint(BaseModel):
    """Vincolo soft: la violazione genera una penalità nel modello di soddisfazione."""
    constraint_type: ConstraintType
    description: str
    worker_id: str
    penalty_weight: int = Field(
        default=1, ge=1, le=10,
        description="Peso della penalità (1=bassa, 10=alta)"
    )
    parameters: dict[str, Any] = Field(default_factory=dict)

    def is_hard(self) -> bool:
        return False


class ConstraintSet(BaseModel):
    """Insieme completo di vincoli per un'istanza di scheduling."""
    hard_constraints: list[HardConstraint] = Field(default_factory=list)
    soft_constraints: list[SoftConstraint] = Field(default_factory=list)
    use_case: str = "A"

    def get_hard_by_type(self, ct: ConstraintType) -> list[HardConstraint]:
        return [c for c in self.hard_constraints if c.constraint_type == ct]

    def get_soft_for_worker(self, worker_id: str) -> list[SoftConstraint]:
        return [c for c in self.soft_constraints if c.worker_id == worker_id]
