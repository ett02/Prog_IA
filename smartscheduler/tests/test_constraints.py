"""
tests/test_constraints.py — Test unitari per la verifica dei vincoli hard.
"""

import pytest
from datetime import date, timedelta

from models.worker import Worker, WorkerType, Preference
from models.schedule import Schedule, ShiftAssignment, ShiftType
from agents.verification_agent import verify_hard_constraints


# ── Fixture ────────────────────────────────────────────────────────────────

HORIZON_START = date(2026, 12, 7)
HORIZON_END = date(2027, 1, 6)


def make_workers_a(n: int = 13) -> list[Worker]:
    return [
        Worker(id=f"W{i:02d}", name=f"Worker {i}", worker_type=WorkerType.STANDARD)
        for i in range(1, n + 1)
    ]


def make_workers_b() -> list[Worker]:
    std = [
        Worker(id=f"S{i:02d}", name=f"Standard {i}", worker_type=WorkerType.STANDARD)
        for i in range(1, 14)
    ]
    spec = [
        Worker(id=f"P{i:02d}", name=f"Spec {i}", worker_type=WorkerType.SPECIALIZED)
        for i in range(1, 8)
    ]
    return std + spec


def make_empty_schedule() -> Schedule:
    return Schedule(
        assignments=[],
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
    )


def days_in_horizon() -> list[date]:
    days = []
    current = HORIZON_START
    while current <= HORIZON_END:
        days.append(current)
        current += timedelta(days=1)
    return days


# ── Test copertura minima ──────────────────────────────────────────────────

def test_insufficient_coverage_detected():
    """Un turno con 1 solo worker (UC-A richiede 2) deve essere rilevato."""
    workers = make_workers_a()
    schedule = make_empty_schedule()

    # Assegna solo 1 worker al primo turno mattutino
    schedule.assignments.append(ShiftAssignment(
        worker_id="W01", date=HORIZON_START, shift_type=ShiftType.MORNING
    ))
    # Assegna 25 units a tutti gli altri su turni diversi (semplificato)
    # Per questo test ci interessa solo rilevare la violazione di copertura

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    assert any("[COPERTURA]" in v for v in result["violations"])


def test_uc_b_no_specialized_detected():
    """Un turno UC-B senza specializzati deve essere rilevato."""
    workers = make_workers_b()
    schedule = make_empty_schedule()

    # Solo standard sul primo turno (manca lo specializzato)
    for wid in ["S01", "S02", "S03"]:
        schedule.assignments.append(ShiftAssignment(
            worker_id=wid, date=HORIZON_START, shift_type=ShiftType.MORNING
        ))

    result = verify_hard_constraints(schedule, workers, use_case="B")
    assert not result["satisfied"]
    assert any("[COPERTURA_SPEC]" in v for v in result["violations"])


# ── Test max 1 turno/giorno ────────────────────────────────────────────────

def test_two_shifts_same_day_detected():
    """Un worker con 2 turni nello stesso giorno deve essere rilevato."""
    workers = make_workers_a()
    schedule = make_empty_schedule()

    schedule.assignments.extend([
        ShiftAssignment(worker_id="W01", date=HORIZON_START, shift_type=ShiftType.MORNING),
        ShiftAssignment(worker_id="W01", date=HORIZON_START, shift_type=ShiftType.AFTERNOON),
    ])

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    assert any("[MAX_1_TURNO]" in v for v in result["violations"])


# ── Test riposo dopo notte ─────────────────────────────────────────────────

def test_no_rest_after_night_detected():
    """Un worker che lavora il giorno dopo una notte deve essere rilevato."""
    workers = make_workers_a()
    schedule = make_empty_schedule()

    night_date = HORIZON_START
    next_day = HORIZON_START + timedelta(days=1)

    schedule.assignments.extend([
        ShiftAssignment(worker_id="W01", date=night_date, shift_type=ShiftType.NIGHT),
        ShiftAssignment(worker_id="W01", date=next_day, shift_type=ShiftType.MORNING),
    ])

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    assert any("[RIPOSO_NOTTE]" in v for v in result["violations"])


def test_rest_two_days_after_night_detected():
    """Un worker che lavora 2 giorni dopo una notte deve essere rilevato."""
    workers = make_workers_a()
    schedule = make_empty_schedule()

    night_date = HORIZON_START
    two_days_later = HORIZON_START + timedelta(days=2)

    schedule.assignments.extend([
        ShiftAssignment(worker_id="W01", date=night_date, shift_type=ShiftType.NIGHT),
        ShiftAssignment(worker_id="W01", date=two_days_later, shift_type=ShiftType.AFTERNOON),
    ])

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    assert any("[RIPOSO_NOTTE]" in v for v in result["violations"])


# ── Test shift-units ───────────────────────────────────────────────────────

def test_wrong_shift_units_detected():
    """Un worker con 20 shift-units (invece di 25) deve essere rilevato."""
    workers = make_workers_a(n=1)
    schedule = make_empty_schedule()

    # Assegna 20 turni mattutini (20 units, non 25)
    days = days_in_horizon()
    for d in days[:20]:
        schedule.assignments.append(ShiftAssignment(
            worker_id="W01", date=d, shift_type=ShiftType.MORNING
        ))

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert any("[SHIFT_UNITS]" in v for v in result["violations"])


def test_night_counts_as_two_units():
    """Verifica che la notte conti come 2 shift-units nel totale."""
    workers = make_workers_a(n=1)
    schedule = make_empty_schedule()
    days = days_in_horizon()

    # Verifica semplicemente che notte=2 units e mattino=1 unit.
    # Assegna 3 notti (6 units) + 3 mattini (3 units) = 9 units totali
    # Le notti sono a indici 0,4,8 con almeno 2 giorni di riposo in mezzo.
    night_indices = [0, 4, 8]
    morning_indices = [3, 7, 11]  # sempre a distanza >2 da ogni notte

    for idx in night_indices:
        schedule.assignments.append(ShiftAssignment(
            worker_id="W01", date=days[idx], shift_type=ShiftType.NIGHT
        ))
    for idx in morning_indices:
        schedule.assignments.append(ShiftAssignment(
            worker_id="W01", date=days[idx], shift_type=ShiftType.MORNING
        ))

    total_units = schedule.total_units_for_worker("W01")
    # 3 notti × 2 + 3 mattini × 1 = 9
    assert total_units == 9, f"Atteso 9 units (3 notti×2 + 3 mattini×1), trovato {total_units}"
    # Verifica che ogni notte valga esattamente 2
    night_assignments = [a for a in schedule.assignments if a.shift_type == ShiftType.NIGHT]
    for a in night_assignments:
        assert a.units == 2, f"Notte deve valere 2 units, trovato {a.units}"


# ── Test ore settimanali ───────────────────────────────────────────────────

def test_weekly_hours_exceeded_detected():
    """Un worker con 7 mattini in 7 giorni (42h) deve essere rilevato."""
    workers = make_workers_a(n=1)
    schedule = make_empty_schedule()
    days = days_in_horizon()

    # 7 mattini consecutivi = 42h > 36h
    for d in days[:7]:
        schedule.assignments.append(ShiftAssignment(
            worker_id="W01", date=d, shift_type=ShiftType.MORNING
        ))

    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    assert any("[ORE_SETTIMANA]" in v for v in result["violations"])


# ── Test schedule vuoto ────────────────────────────────────────────────────

def test_empty_schedule_has_coverage_violations():
    """Uno schedule vuoto deve avere violazioni di copertura per ogni turno."""
    workers = make_workers_a()
    schedule = make_empty_schedule()
    result = verify_hard_constraints(schedule, workers, use_case="A")
    assert not result["satisfied"]
    # 31 giorni × 3 turni = 93 violazioni di copertura
    coverage_violations = [v for v in result["violations"] if "[COPERTURA]" in v]
    assert len(coverage_violations) == 93
