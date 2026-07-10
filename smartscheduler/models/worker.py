"""
models/worker.py — Definizioni Pydantic per Worker e Preferenze.
"""

from __future__ import annotations
from enum import Enum
from typing import Literal, Optional, Any
from datetime import date
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, model_validator


class WorkerType(str, Enum):
    STANDARD = "standard"
    SPECIALIZED = "specialized"


class ShiftPreference(BaseModel):
    """Preferenza per un tipo di turno con priorità."""
    shift_type: Literal["morning", "afternoon", "night"]
    priority: int = Field(
        ge=1, le=4,
        description="1=obbligatorio, 2=preferito, 3=tollerato, 4=da evitare"
    )


class Preference(BaseModel):
    """Preferenze di scheduling di un lavoratore."""
    preferred_shifts: list[ShiftPreference] = Field(default_factory=list)
    unavailable_dates: list[date] = Field(
        default_factory=list,
        description="Date di indisponibilità assoluta (hard constraint)"
    )
    preferred_rest_day: Optional[int] = Field(
        default=None,
        description="Giorno di riposo preferito: 0=Lun, 1=Mar, ..., 6=Dom (soft constraint)"
    )
    night_tolerance: int = Field(
        default=3, ge=0, le=5,
        description="Tolleranza verso turni notturni: 0=nessuna, 5=massima"
    )
    holiday_tolerance: int = Field(
        default=3, ge=0, le=5,
        description="Tolleranza verso turni festivi: 0=nessuna, 5=massima"
    )
    consecutive_tolerance: int = Field(
        default=3, ge=0, le=5,
        description="Tolleranza verso turni impegnativi consecutivi"
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Testo originale in linguaggio naturale fornito dal lavoratore"
    )

    @model_validator(mode="before")
    @classmethod
    def clean_preferred_shifts(cls, data: Any) -> Any:
        """
        Pulisce eventuali formattazioni non valide generate dall'LLM 
        (che viene ancora usato nello Stage 1 per interpretare il testo naturale).
        Ad esempio, converte:
        {"shift_type": "morning|afternoon", "priority": 1}
        splittandole in elementi separati per farle validare correttamente da Pydantic.
        """
        if isinstance(data, dict) and "preferred_shifts" in data:
            shifts = data["preferred_shifts"]
            if isinstance(shifts, list):
                new_shifts = []
                for s in shifts:
                    if isinstance(s, dict) and "shift_type" in s:
                        stype = s["shift_type"]
                        if isinstance(stype, str) and ("|" in stype or "," in stype or " " in stype):
                            stype_clean = stype.replace("|", " ").replace(",", " ")
                            parts = [p.strip() for p in stype_clean.split() if p.strip() in {"morning", "afternoon", "night"}]
                            if parts:
                                for p in parts:
                                    new_shifts.append({"shift_type": p, "priority": s.get("priority", 3)})
                                continue
                    new_shifts.append(s)
                data["preferred_shifts"] = new_shifts
        return data


class Worker(BaseModel):
    """Rappresenta un lavoratore con le sue preferenze."""
    id: str = Field(description="Identificatore univoco, es. 'W01'")
    name: str
    worker_type: WorkerType = WorkerType.STANDARD
    preference: Optional[Preference] = None

    def get_shift_priority(self, shift_type: str) -> int:
        """
        Ritorna la priorità per un dato tipo di turno.
        Valori: 1=obbligatorio, 2=preferito, 3=tollerato (default), 4=da evitare.
        """
        if self.preference is None:
            return 3
        for sp in self.preference.preferred_shifts:
            if sp.shift_type == shift_type:
                return sp.priority
        return 3
