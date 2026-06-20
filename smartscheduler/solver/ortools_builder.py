"""
solver/ortools_builder.py — Costruisce il template base del modello OR-Tools CP-SAT.

Questo modulo genera il codice Python del modello OR-Tools da fornire all'LLM
come base strutturale. L'LLM riceve questo template e lo completa/adatta
con i vincoli soft e le preferenze dei lavoratori.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta

from models.worker import Worker, WorkerType
from models.schedule import ShiftType
from config import (
    SHIFT_HOURS, SHIFT_UNITS, TARGET_SHIFT_UNITS_PER_MONTH,
    MAX_HOURS_PER_WEEK_WINDOW, REST_DAYS_AFTER_NIGHT,
    ORTOOLS_SOLVER_TIME_LIMIT,
)

logger = logging.getLogger(__name__)


def build_days_list(start: date, end: date) -> list[str]:
    """Genera la lista di date come stringhe ISO nell'orizzonte."""
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def generate_ortools_template(
    workers: list[Worker],
    horizon_start: date,
    horizon_end: date,
    use_case: str = "A",
    preferences_code: str = "",
) -> str:
    """
    Genera il codice Python OR-Tools base con tutti i vincoli hard già inclusi.
    L'LLM riceve questo template e aggiunge i vincoli soft nell'objective.

    Args:
        workers: Lista dei lavoratori.
        horizon_start: Data di inizio orizzonte.
        horizon_end: Data di fine orizzonte.
        use_case: "A" o "B".
        preferences_code: Dizionario preferenze generato dallo Stage 1.

    Returns:
        Stringa con codice Python completo.
    """
    days = build_days_list(horizon_start, horizon_end)
    n_days = len(days)

    standard_ids = [w.id for w in workers if w.worker_type == WorkerType.STANDARD]
    specialized_ids = [w.id for w in workers if w.worker_type == WorkerType.SPECIALIZED]
    all_ids = [w.id for w in workers]

    coverage_section = _build_coverage_section(use_case, standard_ids, specialized_ids)

    code = f'''"""
OR-Tools CP-SAT Schedule — Use Case {use_case}
Orizzonte: {horizon_start.isoformat()} → {horizon_end.isoformat()} ({n_days} giorni)
Generato da SmartScheduler ortools_builder.py
"""

from ortools.sat.python import cp_model
import json
from datetime import date, timedelta

def solve_schedule():
    model = cp_model.CpModel()

    # ── Parametri ─────────────────────────────────────────────────────────
    all_workers = {all_ids!r}
    standard_workers = {standard_ids!r}
    specialized_workers = {specialized_ids!r}

    days = {days!r}
    n_days = {n_days}
    shifts = ["morning", "afternoon", "night"]
    shift_hours = {{"morning": 6, "afternoon": 6, "night": 12}}
    shift_units = {{"morning": 1, "afternoon": 1, "night": 2}}

    # ── Preferenze dei lavoratori (da Stage 1) ────────────────────────────
    # preference_weights[worker_id][shift_type] = penalità (0=preferito, 3=da evitare)
    preference_weights = {{}}
    unavailable_dates = {{}}  # worker_id -> set di indici giorno (0-based)
    preferred_rest_day = {{}}  # worker_id -> weekday (0=Mon..6=Sun), o None

{preferences_code}

    # ── Variabili booleane ────────────────────────────────────────────────
    # shift_vars[(worker, day_idx, shift)] = 1 se worker copre quel turno
    shift_vars = {{}}
    for w in all_workers:
        for d in range(n_days):
            for s in shifts:
                shift_vars[(w, d, s)] = model.NewBoolVar(f"shift_{{w}}_d{{d}}_{{s}}")

    # ========== VINCOLI HARD ==============================================

    # 1. Copertura minima per turno
{coverage_section}

    # 2. Max 1 turno al giorno per lavoratore
    for w in all_workers:
        for d in range(n_days):
            model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)

    # 3. No turni consecutivi: notte[d] + mattino[d+1] <= 1
    #    (ridondante con vincolo 5, mantenuto per esplicitezza)
    for w in all_workers:
        for d in range(n_days - 1):
            model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)

    # 4. Indisponibilità assoluta dei lavoratori (da preferenze)
    for w, unavail_days in unavailable_dates.items():
        for d in unavail_days:
            if 0 <= d < n_days:
                for s in shifts:
                    model.Add(shift_vars[(w, d, s)] == 0)

    # 5. 2 giorni liberi obbligatori dopo ogni turno notturno
    for w in all_workers:
        for d in range(n_days):
            if d + 1 < n_days:
                model.Add(
                    shift_vars[(w, d, "night")] +
                    sum(shift_vars[(w, d+1, s)] for s in shifts) <= 1
                )
            if d + 2 < n_days:
                model.Add(
                    shift_vars[(w, d, "night")] +
                    sum(shift_vars[(w, d+2, s)] for s in shifts) <= 1
                )

    # 6. Max 36 ore in qualsiasi finestra scorrevole di 7 giorni
    window_size = 7
    for w in all_workers:
        for start in range(n_days - window_size + 1):
            window = range(start, start + window_size)
            model.Add(
                sum(shift_vars[(w, d, s)] * shift_hours[s]
                    for d in window for s in shifts) <= 36
            )

    # 7. Esattamente 25 shift-units per lavoratore nel mese
    for w in all_workers:
        model.Add(
            sum(shift_vars[(w, d, s)] * shift_units[s]
                for d in range(n_days) for s in shifts) == 25
        )

    # ========== VINCOLI SOFT (OBIETTIVO) ==================================
    # L'obiettivo minimizza la somma pesata delle penalità sulle preferenze.
    # penalty_terms viene popolato qui sotto usando preference_weights.

    penalty_terms = []

    # Penalità per turni non preferiti
    for w in all_workers:
        w_prefs = preference_weights.get(w, {{}})
        for d in range(n_days):
            for s in shifts:
                pen = w_prefs.get(s, 1)  # default: penalità 1 (neutro)
                if pen > 0:
                    penalty_terms.append(shift_vars[(w, d, s)] * pen)

    # TODO (LLM): aggiungi qui penalità aggiuntive per:
    # - Turni festivi per worker con bassa tolleranza
    # - Violazioni del giorno di riposo preferito
    # - Qualsiasi altro criterio soft rilevante

    model.Minimize(sum(penalty_terms))

    # ========== SOLVE =====================================================
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = {ORTOOLS_SOLVER_TIME_LIMIT}
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result = {{}}
        for w in all_workers:
            result[w] = []
            for d in range(n_days):
                for s in shifts:
                    if solver.Value(shift_vars[(w, d, s)]):
                        result[w].append({{
                            "day_idx": d,
                            "date": days[d],
                            "shift": s
                        }})
        output = {{
            "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "objective": solver.ObjectiveValue(),
            "assignments": result
        }}
        print(json.dumps(output))
    else:
        print(json.dumps({{
            "status": "INFEASIBLE" if status == cp_model.INFEASIBLE else "UNKNOWN",
            "error": "Nessuna soluzione trovata"
        }}))

solve_schedule()
'''
    return code


def _build_coverage_section(
    use_case: str,
    standard_ids: list[str],
    specialized_ids: list[str],
) -> str:
    if use_case == "A":
        return '''\
    for d in range(n_days):
        for s in shifts:
            model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 2)'''
    else:
        return '''\
    for d in range(n_days):
        for s in shifts:
            # Almeno 3 lavoratori totali (specializzati possono coprire ruoli standard)
            model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 3)
            # Almeno 1 specializzato sempre presente
            model.Add(sum(shift_vars[(w, d, s)] for w in specialized_workers) >= 1)'''


def _indent(text: str, spaces: int) -> str:
    """
    Indenta ogni riga di `text` di `spaces` spazi.
    NOTA: Non usare per preferences_code — il codice è già fornito con
    l'indentazione corretta dal chiamante (4 spazi base).
    """
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else line for line in text.splitlines())
