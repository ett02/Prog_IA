"""
agents/verification_agent.py — Stage 3a: Hard Constraint Verification.

Agente deterministico (NO LLM) che verifica se lo schedule soddisfa
tutti i vincoli hard. Ogni check è documentato con il vincolo che testa.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta

from models.worker import Worker, WorkerType
from models.schedule import Schedule, ShiftType
from models.state import SmartSchedulerState
from config import (
    HORIZON_START, HORIZON_END,
    TARGET_SHIFT_UNITS_PER_MONTH,
    MAX_HOURS_PER_WEEK_WINDOW,
    REST_DAYS_AFTER_NIGHT,
    MIN_WORKERS_PER_SHIFT_UC_A,
    MIN_WORKERS_PER_SHIFT_UC_B_TOTAL,
    MIN_SPECIALIZED_PER_SHIFT_UC_B,
)

logger = logging.getLogger(__name__)


def verify_hard_constraints(
    schedule: Schedule,
    workers: list[Worker],
    use_case: str = "A",
) -> dict:
    """
    Verifica tutti i vincoli hard dello schedule.

    Returns:
        {
            "satisfied": bool,
            "violations": [str],   # lista descrizioni delle violazioni
            "checks_passed": int,
            "checks_total": int,
        }
    """
    violations: list[str] = []
    days_list = _get_days(HORIZON_START, HORIZON_END)
    day_map = {d: i for i, d in enumerate(days_list)}

    standard_ids = {w.id for w in workers if w.worker_type == WorkerType.STANDARD}
    specialized_ids = {w.id for w in workers if w.worker_type == WorkerType.SPECIALIZED}

    # Pre-calcola strutture di accesso rapido
    # worker_day_shifts[(worker_id, date)] = list[ShiftType]
    wds: dict[tuple, list[ShiftType]] = {}
    # day_shift_workers[(date, ShiftType)] = list[worker_id]
    dsw: dict[tuple, list[str]] = {}

    for a in schedule.assignments:
        key_wds = (a.worker_id, a.date)
        wds.setdefault(key_wds, []).append(a.shift_type)
        key_dsw = (a.date, a.shift_type)
        dsw.setdefault(key_dsw, []).append(a.worker_id)

    checks_total = 0

    # ── Check 1: Copertura minima per turno ───────────────────────────────
    for d in days_list:
        for s in ShiftType:
            checks_total += 1
            workers_on_shift = dsw.get((d, s), [])
            count = len(workers_on_shift)

            if use_case == "A":
                if count < MIN_WORKERS_PER_SHIFT_UC_A:
                    violations.append(
                        f"[COPERTURA] {d.isoformat()} {s.value}: "
                        f"{count} worker assegnati, minimo {MIN_WORKERS_PER_SHIFT_UC_A}"
                    )
            else:  # UC-B
                if count < MIN_WORKERS_PER_SHIFT_UC_B_TOTAL:
                    violations.append(
                        f"[COPERTURA_TOTALE] {d.isoformat()} {s.value}: "
                        f"{count} totali, minimo {MIN_WORKERS_PER_SHIFT_UC_B_TOTAL}"
                    )
                spec_count = sum(1 for wid in workers_on_shift if wid in specialized_ids)
                if spec_count < MIN_SPECIALIZED_PER_SHIFT_UC_B:
                    violations.append(
                        f"[COPERTURA_SPEC] {d.isoformat()} {s.value}: "
                        f"{spec_count} specializzati, minimo {MIN_SPECIALIZED_PER_SHIFT_UC_B}"
                    )

    # ── Check 2: Max 1 turno al giorno per worker ─────────────────────────
    for w in workers:
        for d in days_list:
            checks_total += 1
            shifts_today = wds.get((w.id, d), [])
            if len(shifts_today) > 1:
                violations.append(
                    f"[MAX_1_TURNO] {w.id} — {d.isoformat()}: "
                    f"assegnato a {len(shifts_today)} turni ({[s.value for s in shifts_today]})"
                )

    # ── Check 3: No turni consecutivi (notte[d] + mattino[d+1]) ──────────
    for w in workers:
        for i, d in enumerate(days_list[:-1]):
            checks_total += 1
            next_d = days_list[i + 1]
            if ShiftType.NIGHT in wds.get((w.id, d), []) and \
               ShiftType.MORNING in wds.get((w.id, next_d), []):
                violations.append(
                    f"[CONSECUTIVI] {w.id} — notte del {d.isoformat()} "
                    f"seguita da mattino del {next_d.isoformat()}"
                )

    # ── Check 4: 2 giorni liberi dopo notte ───────────────────────────────
    for w in workers:
        for i, d in enumerate(days_list):
            if ShiftType.NIGHT not in wds.get((w.id, d), []):
                continue
            for offset in range(1, REST_DAYS_AFTER_NIGHT + 1):
                checks_total += 1
                if i + offset >= len(days_list):
                    break
                rest_day = days_list[i + offset]
                if wds.get((w.id, rest_day)):
                    violations.append(
                        f"[RIPOSO_NOTTE] {w.id} — dopo notte del {d.isoformat()}, "
                        f"lavora il {rest_day.isoformat()} (offset {offset})"
                    )

    # ── Check 5: Max 36 ore in finestra scorrevole 7 giorni ───────────────
    n_days = len(days_list)
    for w in workers:
        for start_i in range(n_days - 7 + 1):
            checks_total += 1
            window = days_list[start_i: start_i + 7]
            total_hours = sum(
                s.hours()
                for d in window
                for s in wds.get((w.id, d), [])
            )
            if total_hours > MAX_HOURS_PER_WEEK_WINDOW:
                violations.append(
                    f"[ORE_SETTIMANA] {w.id} — finestra {window[0].isoformat()}→"
                    f"{window[-1].isoformat()}: {total_hours}h > {MAX_HOURS_PER_WEEK_WINDOW}h"
                )

    # ── Check 6: Esattamente 25 shift-units/mese ──────────────────────────
    for w in workers:
        checks_total += 1
        total_units = schedule.total_units_for_worker(w.id)
        if total_units != TARGET_SHIFT_UNITS_PER_MONTH:
            violations.append(
                f"[SHIFT_UNITS] {w.id}: {total_units} shift-units "
                f"(atteso esattamente {TARGET_SHIFT_UNITS_PER_MONTH})"
            )

    # ── Check 7: Indisponibilità assoluta ─────────────────────────────────
    for w in workers:
        if w.preference and w.preference.unavailable_dates:
            for unavail_date in w.preference.unavailable_dates:
                checks_total += 1
                if wds.get((w.id, unavail_date)):
                    violations.append(
                        f"[INDISPONIBILITA] {w.id} — lavora il {unavail_date.isoformat()} "
                        f"(giorno di indisponibilità assoluta)"
                    )

    satisfied = len(violations) == 0
    checks_passed = checks_total - len(violations)

    if satisfied:
        logger.info(f"Verifica vincoli: TUTTI SODDISFATTI ({checks_passed}/{checks_total})")
    else:
        logger.warning(
            f"Verifica vincoli: {len(violations)} VIOLAZIONI su {checks_total} check"
        )
        for v in violations[:5]:  # Logga le prime 5
            logger.warning(f"  → {v}")

    return {
        "satisfied": satisfied,
        "violations": violations,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
    }


def _get_days(start: date, end: date) -> list[date]:
    """Genera la lista di date nell'orizzonte."""
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


# ── Nodo LangGraph ─────────────────────────────────────────────────────────

def verification_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 3a.
    Verifica i vincoli hard dello schedule corrente.
    """
    schedule: Schedule | None = state.get("schedule")
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")

    if schedule is None:
        logger.error("Nessuno schedule da verificare")
        return {
            "hard_constraints_satisfied": False,
            "violations": ["Nessuno schedule disponibile per la verifica"],
        }

    logger.info("Stage 3a — Hard Constraint Verification")
    result = verify_hard_constraints(schedule, workers, use_case)

    return {
        "hard_constraints_satisfied": result["satisfied"],
        "violations": result["violations"],
    }


def check_hard_constraints(state: SmartSchedulerState) -> str:
    """
    Funzione condizionale per LangGraph.
    Determina il prossimo nodo in base al risultato della verifica.
    """
    if state.get("hard_constraints_satisfied", False):
        return "satisfied"

    draft_iter = state.get("draft_iteration", 0)
    max_iter = state.get("max_draft_iterations", 5)

    if draft_iter >= max_iter:
        logger.error(f"Limite massimo iterazioni drafting raggiunto ({max_iter})")
        return "draft_limit_reached"

    return "violated"
