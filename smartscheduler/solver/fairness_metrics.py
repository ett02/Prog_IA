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

    Formula:
        score = 1 - (penalty_incurred / max_possible_penalty)

    Dove max_possible_penalty è calcolato assumendo che tutte le preferenze
    vengano violate al massimo grado.
    """
    if worker.preference is None:
        # Nessuna preferenza → soddisfazione neutrale
        return 0.5

    pref = worker.preference
    assignments = schedule.get_worker_assignments(worker.id)

    penalty = 0.0
    max_penalty = 0.0

    # ── 1. Penalità turni notturni ────────────────────────────────────────
    night_weight = max(0, 5 - pref.night_tolerance)  # 0 se tolleranza max
    night_assignments = [a for a in assignments if a.shift_type == ShiftType.NIGHT]
    night_count = len(night_assignments)

    # Max teorico: tutti i turni sono notturni (usiamo 25 units / 2 = ~12 notti max)
    max_nights = 12
    penalty += night_weight * night_count
    max_penalty += night_weight * max_nights

    # ── 2. Penalità turni festivi ─────────────────────────────────────────
    holiday_weight = max(0, 5 - pref.holiday_tolerance)
    holiday_count = sum(1 for a in assignments if a.date in HOLIDAY_DATES)

    max_holidays = len(HOLIDAY_DATES)  # 5 festivi nell'orizzonte
    penalty += holiday_weight * holiday_count
    max_penalty += holiday_weight * max_holidays

    # ── 3. Penalità deviazione dal turno preferito ────────────────────────
    for a in assignments:
        shift_priority = worker.get_shift_priority(a.shift_type.value)
        # priority: 1=obbligatorio(no penalty), 2=preferito(penalty 0),
        #           3=tollerato(penalty 1), 4=da evitare(penalty 3)
        shift_penalty_map = {1: 0, 2: 0, 3: 1, 4: 3}
        p = shift_penalty_map.get(shift_priority, 1)
        penalty += p
        max_penalty += 3  # max penalty per turno = 4 (da evitare)

    # ── 4. Penalità giorno di riposo preferito ────────────────────────────
    if pref.preferred_rest_day is not None:
        # Conta quante settimane il giorno preferito è stato lavorato invece di libero
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

        rest_weight = 2  # peso fisso per le violazioni del giorno di riposo
        penalty += rest_weight * rest_violations
        max_penalty += rest_weight * rest_opportunities

    # ── Normalizzazione ───────────────────────────────────────────────────
    if max_penalty == 0:
        return 1.0  # nessuna penalità possibile → soddisfazione massima

    score = 1.0 - (penalty / max_penalty)
    score = max(0.0, min(1.0, score))  # clamp in [0,1]

    logger.debug(
        f"Worker {worker.id}: penalty={penalty:.1f}, max={max_penalty:.1f}, score={score:.3f}"
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
