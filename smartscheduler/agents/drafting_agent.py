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
    Nodo LangGraph per Stage 2 (e rientro da Stage 3 se violazioni).
    Genera/rigena il codice OR-Tools e lo esegue.
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    violations: list[str] = state.get("violations", [])
    draft_iteration: int = state.get("draft_iteration", 0) + 1
    preferences_code: str = state.get("ortools_preferences_code", "")

    logger.info(f"Stage 2 — Drafting (iterazione {draft_iteration})")

    # Genera il template OR-Tools con tutti i vincoli hard
    template = generate_ortools_template(
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
        preferences_code=preferences_code,
    )

    preferences_summary = build_drafting_summary_prompt(workers)

    # Costruisce il prompt (con violations se siamo in re-draft)
    prompt = build_drafting_prompt(
        ortools_template=template,
        workers=workers,
        use_case=use_case,
        preferences_summary=preferences_summary,
        violations=violations if violations else None,
        draft_iteration=draft_iteration,
    )

    # Chiama l'LLM
    llm_response = call_llm_for_code(prompt)
    code = extract_code_from_llm_response(llm_response)

    # Salva il codice generato
    save_ortools_code(code, f"schedule_draft_iter{draft_iteration}.py")

    # Esegui il solver
    logger.info("Esecuzione OR-Tools solver...")
    result = run_ortools_code(code)

    # Converti in Schedule
    schedule = parse_solver_result(
        result=result,
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
    )

    if schedule is None:
        logger.warning(f"Solver INFEASIBLE all'iterazione {draft_iteration}")
        return {
            "draft_iteration": draft_iteration,
            "ortools_schedule_code": code,
            "schedule": None,
            "hard_constraints_satisfied": False,
            "violations": [result.get("error", "INFEASIBLE — nessun dettaglio")],
        }

    logger.info(
        f"Schedule generato: {len(schedule.assignments)} assegnazioni"
    )
    return {
        "draft_iteration": draft_iteration,
        "ortools_schedule_code": code,
        "schedule": schedule,
        "violations": [],
    }


# ── Nodo LangGraph — Refinement (Stage 4) ──────────────────────────────────

def refinement_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 4 (Fairness Refinement).
    Chiede all'LLM di migliorare la soddisfazione del worker meno soddisfatto.
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    current_code: str = state.get("ortools_schedule_code", "")
    fairness_metrics: dict = state.get("fairness_metrics", {})
    least_satisfied: str = state.get("least_satisfied_worker", "")
    refinement_iteration: int = state.get("refinement_iteration", 0) + 1

    logger.info(
        f"Stage 4 — Refinement (iterazione {refinement_iteration}) "
        f"— target: {least_satisfied} (score: {fairness_metrics.get(least_satisfied, 0):.3f})"
    )

    # Costruisce prompt di raffinamento
    prompt = build_refinement_prompt(
        current_ortools_code=current_code,
        workers=workers,
        least_satisfied_worker_id=least_satisfied,
        least_satisfied_score=fairness_metrics.get(least_satisfied, 0.0),
        all_scores=fairness_metrics,
        refinement_iteration=refinement_iteration,
    )

    # Chiama l'LLM
    llm_response = call_llm_for_code(prompt)
    code = extract_code_from_llm_response(llm_response)

    # Salva il codice raffinato
    save_ortools_code(code, f"schedule_refined_iter{refinement_iteration}.py")

    # Esegui il solver
    result = run_ortools_code(code)
    schedule = parse_solver_result(
        result=result,
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case=use_case,
    )

    if schedule is None:
        logger.warning(f"Refinement solver INFEASIBLE all'iterazione {refinement_iteration}")
        return {
            "refinement_iteration": refinement_iteration,
            # Mantieni lo schedule precedente se il raffinamento fallisce
            "hard_constraints_satisfied": False,
            "violations": [result.get("error", "INFEASIBLE durante raffinamento")],
        }

    logger.info(f"Schedule raffinato: {len(schedule.assignments)} assegnazioni")
    return {
        "refinement_iteration": refinement_iteration,
        "ortools_schedule_code": code,
        "schedule": schedule,
        "violations": [],
    }
