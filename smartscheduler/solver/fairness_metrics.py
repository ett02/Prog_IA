"""
solver/fairness_metrics.py — Calcolo simbolico delle metriche di fairness.

Questo modulo è completamente deterministico (nessun LLM).
Calcola il satisfaction score di ogni lavoratore basandosi sulle
preferenze dichiarate e sullo schedule assegnato.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Optional

from models.worker import Worker
from models.schedule import Schedule, ShiftType

logger = logging.getLogger(__name__)

# Date festive nell'orizzonte 7 dic 2026 – 6 gen 2027
HOLIDAY_DATES: set[date] = {
    date(2026, 12, 8),   # Immacolata Concezione
    date(2026, 12, 25),  # Natale
    date(2026, 12, 26),  # Santo Stefano
    date(2027, 1, 1),    # Capodanno
    date(2027, 1, 6),    # Epifania
}


def compute_satisfaction_score(worker: Worker, schedule: Schedule) -> float:
    """
    Calcola il satisfaction score [0.0, 1.0] di un lavoratore.

    Formula: media pesata di 4 componenti normalizzati separatamente:
        - score_night    (peso 35%): penalità per turni notturni
        - score_holiday  (peso 25%): penalità per turni festivi
        - score_shift    (peso 25%): penalità per deviazione dal turno preferito
        - score_rest     (peso 15%): penalità per violazioni giorno di riposo
    """
    if worker.preference is None:
        return 0.5  # neutrale se nessuna preferenza

    pref = worker.preference
    assignments = schedule.get_worker_assignments(worker.id)

    # ── 1. Componente notturni ────────────────────────────────────────────
    night_weight = max(0, 5 - pref.night_tolerance)
    night_count = sum(1 for a in assignments if a.shift_type == ShiftType.NIGHT)
    max_nights = 7  # allineato al vincolo 8 del template
    night_penalty = night_weight * night_count
    max_night_penalty = night_weight * max_nights
    score_night = 1.0 - (night_penalty / max_night_penalty) if max_night_penalty > 0 else 1.0

    # ── 2. Componente festivi ─────────────────────────────────────────────
    holiday_weight = max(0, 5 - pref.holiday_tolerance)
    holiday_count = sum(1 for a in assignments if a.date in HOLIDAY_DATES)
    max_holidays = len(HOLIDAY_DATES)  # 5 festivi nell'orizzonte
    holiday_penalty = holiday_weight * holiday_count
    max_holiday_penalty = holiday_weight * max_holidays
    score_holiday = 1.0 - (holiday_penalty / max_holiday_penalty) if max_holiday_penalty > 0 else 1.0

    # ── 3. Componente turno preferito ─────────────────────────────────────
    shift_penalty_map = {1: 0, 2: 0, 3: 1, 4: 3}
    shift_penalty = sum(
        shift_penalty_map.get(worker.get_shift_priority(a.shift_type.value), 1)
        for a in assignments
    )
    max_shift_penalty = 3 * len(assignments)  # max 3 per turno (priority=4)
    score_shift = 1.0 - (shift_penalty / max_shift_penalty) if max_shift_penalty > 0 else 1.0

    # ── 4. Componente giorno di riposo preferito ──────────────────────────
    score_rest = 1.0
    if pref.preferred_rest_day is not None:
        worked_days = {a.date for a in assignments}
        current = schedule.horizon_start
        rest_violations = 0
        rest_opportunities = 0
        while current <= schedule.horizon_end:
            if current.weekday() == pref.preferred_rest_day:
                rest_opportunities += 1
                if current in worked_days:
                    rest_violations += 1
            current += timedelta(days=1)
        score_rest = 1.0 - (rest_violations / rest_opportunities) if rest_opportunities > 0 else 1.0

    # ── Media pesata ──────────────────────────────────────────────────────
    score = (
        0.35 * score_night +
        0.25 * score_holiday +
        0.25 * score_shift +
        0.15 * score_rest
    )
    score = max(0.0, min(1.0, score))

    logger.debug(
        f"Worker {worker.id}: night={score_night:.3f}, holiday={score_holiday:.3f}, "
        f"shift={score_shift:.3f}, rest={score_rest:.3f} → score={score:.3f}"
    )
    return score


def compute_all_scores(
    workers: list[Worker], schedule: Schedule
) -> dict[str, float]:
    """Calcola i satisfaction scores per tutti i lavoratori."""
    scores = {}
    for worker in workers:
        scores[worker.id] = compute_satisfaction_score(worker, schedule)
    return scores


def find_least_satisfied(scores: dict[str, float]) -> Optional[str]:
    """Ritorna il worker_id con il satisfaction score minimo."""
    if not scores:
        return None
    return min(scores, key=lambda wid: scores[wid])


def compute_fairness_report(
    workers: list[Worker], schedule: Schedule
) -> dict:
    """
    Genera un report completo di fairness.

    Returns:
        {
            "scores": {worker_id: float},
            "least_satisfied": str,
            "fairness_score": float,   # min(scores) — criterio min-max
            "avg_score": float,
            "score_range": float,      # max - min
        }
    """
    scores = compute_all_scores(workers, schedule)

    if not scores:
        return {"scores": {}, "least_satisfied": None, "fairness_score": 0.0}

    fairness_score = min(scores.values())
    avg_score = sum(scores.values()) / len(scores)
    score_range = max(scores.values()) - min(scores.values())
    least_satisfied = find_least_satisfied(scores)

    logger.info(
        f"Fairness report — min={fairness_score:.3f}, avg={avg_score:.3f}, "
        f"range={score_range:.3f}, least_satisfied={least_satisfied}"
    )

    return {
        "scores": scores,
        "least_satisfied": least_satisfied,
        "fairness_score": fairness_score,
        "avg_score": avg_score,
        "score_range": score_range,
    }
