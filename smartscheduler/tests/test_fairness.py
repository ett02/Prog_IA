"""
tests/test_fairness.py — Test unitari per le metriche di fairness.
"""

import pytest
from datetime import date

from models.worker import Worker, WorkerType, Preference, ShiftPreference
from models.schedule import Schedule, ShiftAssignment, ShiftType
from solver.fairness_metrics import (
    compute_satisfaction_score,
    compute_all_scores,
    find_least_satisfied,
    compute_fairness_report,
    HOLIDAY_DATES,
)

HORIZON_START = date(2026, 12, 7)
HORIZON_END = date(2027, 1, 6)


def make_schedule_with_assignments(assignments: list[ShiftAssignment]) -> Schedule:
    return Schedule(
        assignments=assignments,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
    )


# ── Test satisfaction score base ───────────────────────────────────────────

def test_worker_no_preference_gets_neutral_score():
    """Un worker senza preferenze deve ricevere score neutro (0.5)."""
    worker = Worker(id="W01", name="Test", worker_type=WorkerType.STANDARD)
    schedule = make_schedule_with_assignments([])
    score = compute_satisfaction_score(worker, schedule)
    assert score == 0.5


def test_worker_prefers_morning_gets_good_score_with_only_mornings():
    """Un worker che preferisce il mattino con solo mattini deve avere score alto."""
    pref = Preference(
        preferred_shifts=[ShiftPreference(shift_type="morning", priority=2)],
        night_tolerance=3,
        holiday_tolerance=3,
    )
    worker = Worker(id="W01", name="Test", preference=pref)

    # Assegna solo turni mattutini (nessuna penalità per turno preferito)
    assignments = [
        ShiftAssignment(worker_id="W01", date=date(2026, 12, d), shift_type=ShiftType.MORNING)
        for d in range(7, 20)  # 13 mattini
    ]
    schedule = make_schedule_with_assignments(assignments)
    score = compute_satisfaction_score(worker, schedule)
    assert score > 0.7, f"Score atteso > 0.7, ottenuto {score}"


def test_worker_avoids_night_gets_bad_score_with_nights():
    """Un worker che evita la notte con turni notturni deve avere score basso."""
    pref = Preference(
        preferred_shifts=[ShiftPreference(shift_type="night", priority=4)],
        night_tolerance=0,  # nessuna tolleranza
        holiday_tolerance=3,
    )
    worker = Worker(id="W01", name="Test", preference=pref)

    # Assegna 6 turni notturni
    assignments = [
        ShiftAssignment(
            worker_id="W01",
            date=date(2026, 12, 7 + i * 4),
            shift_type=ShiftType.NIGHT,
        )
        for i in range(6)
    ]
    schedule = make_schedule_with_assignments(assignments)
    score = compute_satisfaction_score(worker, schedule)
    assert score < 0.5, f"Score atteso < 0.5, ottenuto {score}"


def test_holiday_penalty_applied():
    """Un worker con bassa tolleranza festiva che lavora a Natale deve essere penalizzato."""
    pref = Preference(
        holiday_tolerance=0,  # nessuna tolleranza
        night_tolerance=3,
    )
    worker = Worker(id="W01", name="Test", preference=pref)

    christmas = date(2026, 12, 25)
    assert christmas in HOLIDAY_DATES, "Natale deve essere nella lista festivi"

    # Lavora a Natale
    assignments = [
        ShiftAssignment(worker_id="W01", date=christmas, shift_type=ShiftType.MORNING)
    ]
    schedule_with_holiday = make_schedule_with_assignments(assignments)

    # Lavora un giorno normale
    normal_day = date(2026, 12, 10)
    assignments_normal = [
        ShiftAssignment(worker_id="W01", date=normal_day, shift_type=ShiftType.MORNING)
    ]
    schedule_normal = make_schedule_with_assignments(assignments_normal)

    score_holiday = compute_satisfaction_score(worker, schedule_with_holiday)
    score_normal = compute_satisfaction_score(worker, schedule_normal)

    assert score_holiday < score_normal, (
        f"Lavorare a Natale ({score_holiday:.3f}) deve penalizzare "
        f"rispetto a giorno normale ({score_normal:.3f})"
    )


# ── Test find_least_satisfied ──────────────────────────────────────────────

def test_find_least_satisfied_returns_min():
    scores = {"W01": 0.9, "W02": 0.3, "W03": 0.7}
    assert find_least_satisfied(scores) == "W02"


def test_find_least_satisfied_empty():
    assert find_least_satisfied({}) is None


def test_find_least_satisfied_single():
    assert find_least_satisfied({"W01": 0.5}) == "W01"


# ── Test compute_all_scores ────────────────────────────────────────────────

def test_all_scores_computed_for_all_workers():
    workers = [
        Worker(id=f"W{i:02d}", name=f"Worker {i}")
        for i in range(1, 4)
    ]
    schedule = make_schedule_with_assignments([])
    scores = compute_all_scores(workers, schedule)
    assert set(scores.keys()) == {"W01", "W02", "W03"}


# ── Test fairness_report ───────────────────────────────────────────────────

def test_fairness_report_structure():
    workers = [Worker(id="W01", name="A"), Worker(id="W02", name="B")]
    schedule = make_schedule_with_assignments([])
    report = compute_fairness_report(workers, schedule)

    assert "scores" in report
    assert "least_satisfied" in report
    assert "fairness_score" in report
    assert "avg_score" in report
    assert "score_range" in report
    assert 0.0 <= report["fairness_score"] <= 1.0


def test_fairness_score_is_minimum():
    """Il fairness_score deve essere uguale al minimo dei satisfaction scores."""
    workers = [
        Worker(id="W01", name="A",
               preference=Preference(night_tolerance=0, holiday_tolerance=3)),
        Worker(id="W02", name="B",
               preference=Preference(night_tolerance=5, holiday_tolerance=5)),
    ]
    assignments = [
        # W01 fa una notte (penalizzato)
        ShiftAssignment(worker_id="W01", date=HORIZON_START, shift_type=ShiftType.NIGHT),
        # W02 fa un mattino (neutro)
        ShiftAssignment(worker_id="W02", date=HORIZON_START, shift_type=ShiftType.MORNING),
    ]
    schedule = make_schedule_with_assignments(assignments)
    report = compute_fairness_report(workers, schedule)

    assert abs(report["fairness_score"] - min(report["scores"].values())) < 1e-6
