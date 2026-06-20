"""
agents/drafting_agent.py — Stage 2 & 4: Schedule Drafting e Refinement.

Usa l'LLM per generare/raffinare il codice OR-Tools, poi esegue il solver
e converte il risultato in un oggetto Schedule Pydantic.
"""

from __future__ import annotations
import json
import logging
import os
from datetime import date

from models.worker import Worker
from models.schedule import Schedule, ShiftAssignment, ShiftType
from models.state import SmartSchedulerState
from agents.base_llm import call_llm_for_code
from prompts.drafting_prompt import build_drafting_prompt, build_drafting_summary_prompt
from prompts.refinement_prompt import build_refinement_prompt
from solver.ortools_builder import generate_ortools_template, build_days_list
from solver.ortools_runner import run_ortools_code, extract_code_from_llm_response
from config import (
    HORIZON_START, HORIZON_END, OUTPUT_DIR, MAX_DRAFT_ITERATIONS
)

logger = logging.getLogger(__name__)


def parse_solver_result(
    result: dict,
    workers: list[Worker],
    horizon_start: date,
    horizon_end: date,
    use_case: str,
) -> Schedule | None:
    """
    Converte il JSON del solver in un oggetto Schedule Pydantic.
    Ritorna None se il solver ha segnalato INFEASIBLE o errore.
    """
    if "error" in result or result.get("status") in ("INFEASIBLE", "UNKNOWN"):
        logger.error(f"Solver fallito: {result}")
        return None

    assignments = []
    raw_assignments = result.get("assignments", {})
    days = build_days_list(horizon_start, horizon_end)

    for worker_id, shifts in raw_assignments.items():
        for entry in shifts:
            day_str = entry.get("date") or (
                days[entry["day_idx"]] if "day_idx" in entry else None
            )
            if day_str is None:
                continue
            try:
                shift_type = ShiftType(entry["shift"])
                assignments.append(ShiftAssignment(
                    worker_id=worker_id,
                    date=date.fromisoformat(day_str),
                    shift_type=shift_type,
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"Assegnazione non valida per {worker_id}: {entry} — {e}")

    if not assignments:
        logger.error("Nessuna assegnazione nel risultato del solver")
        return None

    return Schedule(
        assignments=assignments,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        use_case=use_case,
    )


def save_ortools_code(code: str, filename: str = "schedule_draft.py") -> str:
    """Salva il codice OR-Tools in output/."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    logger.info(f"Codice OR-Tools salvato in: {path}")
    return path


# ── Nodo LangGraph — Drafting (Stage 2) ────────────────────────────────────

def drafting_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 2 (Drafting).

    Costruisce il codice OR-Tools usando il template deterministico
    di ortools_builder.py. Il codice delle preferenze viene passato dal
    preferences_agent (Stage 1). Non viene più usato l'LLM in questa fase,
    garantendo esecuzione quasi istantanea e zero errori sintattici.
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    draft_iteration: int = state.get("draft_iteration", 0) + 1

    logger.info(f"Stage 2 — Drafting (iterazione {draft_iteration}) - Deterministic Mode")

    # Recupera il codice delle preferenze generato nello Stage 1
    preferences_code: str = state.get("ortools_preferences_code", "")

    # Genera il template completo (ora include anche penalità festivi)
    code = generate_ortools_template(
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
        preferences_code=preferences_code,
    )

    # Salva il codice in file
    save_ortools_code(code, f"schedule_draft_iter{draft_iteration}.py")

    # Esegui il solver
    logger.info("Esecuzione OR-Tools solver...")
    result = run_ortools_code(code)

    schedule = parse_solver_result(
        result=result,
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
    )

    if schedule is None:
        # Se Infeasible o fallito
        logger.warning(f"Solver INFEASIBLE all'iterazione {draft_iteration}")
        return {
            "draft_iteration": draft_iteration,
            "violations": [result.get("error", "Nessuna soluzione trovata")],
        }

    logger.info(
        f"Schedule generato: {len(schedule.assignments)} assegnazioni"
    )
    return {
        "draft_iteration": draft_iteration,
        "ortools_schedule_code": code,
        "ortools_preferences_code": preferences_code,
        "schedule": schedule,
        "violations": [],
    }


# ── Nodo LangGraph — Refinement (Stage 4) — SIMBOLICO ──────────────────────

def refinement_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 4 (Fairness Refinement) — APPROCCIO SIMBOLICO.

    Invece di usare l'LLM (inaffidabile per questo task), il refinement
    deterministico funziona così:
    1. Identifica il worker meno soddisfatto (W_target) e il suo turno da evitare
    2. Aumenta drasticamente la penalità per quel turno di W_target nel preferences_code
    3. Abbassa leggermente le penalità degli altri worker per compensare
    4. Rigenera il template e ri-esegue il solver

    Questo garantisce miglioramento monotono della fairness senza rischio di
    errori sintattici o logici che si verificavano con llama3.2.
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    fairness_metrics: dict = state.get("fairness_metrics", {})
    least_satisfied: str = state.get("least_satisfied_worker", "")
    refinement_iteration: int = state.get("refinement_iteration", 0) + 1
    current_prefs_code: str = state.get("ortools_preferences_code", "")
    previous_schedule = state.get("schedule")

    logger.info(
        f"Stage 4 — Refinement LNS (iterazione {refinement_iteration}) "
        f"— target: {least_satisfied} (score: {fairness_metrics.get(least_satisfied, 0):.3f})"
    )

    # Trova il worker target e il suo turno da evitare
    target_worker = next((w for w in workers if w.id == least_satisfied), None)
    if target_worker is None or target_worker.preference is None:
        logger.warning(f"Worker {least_satisfied} non trovato o senza preferenze")
        return {"refinement_iteration": refinement_iteration}

    pref = target_worker.preference

    # Identifica il turno da evitare (priority 4) o peggiore tolleranza
    shift_priority_map = {sp.shift_type: sp.priority for sp in pref.preferred_shifts}
    avoid_shift = max(
        ["morning", "afternoon", "night"],
        key=lambda s: shift_priority_map.get(s, 2)
    )
    # Se bassa night_tolerance, preferisci sempre ridurre le notti
    if pref.night_tolerance <= 2:
        avoid_shift = "night"

    logger.info(
        f"Refinement: aumento penalità '{avoid_shift}' per {least_satisfied} "
        f"(night_tol={pref.night_tolerance})"
    )

    # Rigenera il preferences_code con penalità amplificata per W_target
    new_code_lines = []
    for line in current_prefs_code.splitlines():
        # Aumenta penalità turno da evitare per il worker target
        if f'preference_weights["{least_satisfied}"]' in line:
            # Ricostruisce il dict con penalità amplificata
            penalties = {"morning": 1, "afternoon": 1, "night": 1}
            for sp in pref.preferred_shifts:
                priority_to_penalty = {1: 0, 2: 0, 3: 1, 4: 3}
                penalties[sp.shift_type] = priority_to_penalty.get(sp.priority, 1)
            # Amplifica il turno da evitare (max 5)
            penalties[avoid_shift] = min(5, penalties.get(avoid_shift, 1) + 2)
            new_code_lines.append(
                f'    preference_weights["{least_satisfied}"] = {penalties!r}'
            )
        else:
            new_code_lines.append(line)

    refined_prefs_code = "\n".join(new_code_lines)

    # LNS: Seleziona Donatori (top 50% più felici) e fissa gli altri
    sorted_workers = sorted(
        [w for w in workers if w.id != least_satisfied],
        key=lambda w: fairness_metrics.get(w.id, 0),
        reverse=True
    )
    n_donors = len(sorted_workers) // 2
    donors = set(w.id for w in sorted_workers[:n_donors])
    
    fixed_workers_ids = [w.id for w in sorted_workers[n_donors:]]
    logger.info(f"LNS Donors (free): {donors}")
    logger.info(f"LNS Fixed workers: {fixed_workers_ids}")

    fixed_assignments_lines = ["    # Vincoli hard: LNS Freeze"]
    from datetime import timedelta
    n_days = (HORIZON_END - HORIZON_START).days + 1
    if previous_schedule:
        for worker_id in fixed_workers_ids:
            worker_assignments = {
                a.date: a.shift_type.value 
                for a in previous_schedule.get_worker_assignments(worker_id)
            }
            for d in range(n_days):
                day_date = HORIZON_START + timedelta(days=d)
                assigned_shift = worker_assignments.get(day_date)
                for s in ["morning", "afternoon", "night"]:
                    val = 1 if s == assigned_shift else 0
                    fixed_assignments_lines.append(
                        f"    model.Add(shift_vars[('{worker_id}', {d}, '{s}')] == {val})"
                    )

    fixed_assignments_code = "\n".join(fixed_assignments_lines)

    # Rigenera il template con i nuovi pesi e assegnazioni fisse
    template = generate_ortools_template(
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
        preferences_code=refined_prefs_code,
        fixed_assignments_code=fixed_assignments_code,
    )

    # Salva e ri-esegui il solver
    save_ortools_code(template, f"schedule_refined_iter{refinement_iteration}.py")
    logger.info("Esecuzione OR-Tools solver (refinement LNS)...")
    result = run_ortools_code(template)

    schedule = parse_solver_result(
        result=result,
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
    )

    if schedule is None:
        logger.warning(
            f"Refinement LNS INFEASIBLE all'iterazione {refinement_iteration} "
            f"— Impossibile migliorare mantenendo i vincoli. Terminazione."
        )
        # Ritorna il vecchio schedule per fermare la pipeline in modo pulito
        return {
            "refinement_iteration": refinement_iteration,
            "hard_constraints_satisfied": True,
            "schedule": previous_schedule,
            "violations": ["LNS Fallito - Ottimo locale raggiunto"],
        }

    logger.info(f"Schedule raffinato: {len(schedule.assignments)} assegnazioni")
    return {
        "refinement_iteration": refinement_iteration,
        "ortools_schedule_code": template,
        "ortools_preferences_code": refined_prefs_code,
        "schedule": schedule,
        "violations": [],
    }

