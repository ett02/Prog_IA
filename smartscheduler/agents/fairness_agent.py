"""
agents/fairness_agent.py — Stage 3b: Fairness Evaluation.

Agente deterministico (NO LLM) che calcola le metriche di fairness
e determina se il loop di raffinamento deve continuare.
"""

from __future__ import annotations
import logging

from models.worker import Worker
from models.schedule import Schedule
from models.state import SmartSchedulerState
from solver.fairness_metrics import compute_fairness_report

logger = logging.getLogger(__name__)


def fairness_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 3b.
    Calcola i satisfaction scores e identifica il worker meno soddisfatto.
    """
    schedule: Schedule | None = state.get("schedule")
    workers: list[Worker] = state["workers"]
    previous_score: float = state.get("previous_fairness_score", 0.0)

    if schedule is None:
        logger.error("Nessuno schedule disponibile per la fairness evaluation")
        return {
            "fairness_metrics": {},
            "least_satisfied_worker": None,
            "previous_fairness_score": previous_score,
        }

    logger.info("Stage 3b — Fairness Evaluation")
    report = compute_fairness_report(workers, schedule)

    scores = report["scores"]
    fairness_score = report["fairness_score"]
    least_satisfied = report["least_satisfied"]

    logger.info(
        f"Fairness score (min): {fairness_score:.3f} | "
        f"avg: {report['avg_score']:.3f} | "
        f"range: {report['score_range']:.3f} | "
        f"least satisfied: {least_satisfied}"
    )

    # Aggiorna lo schedule con il fairness score
    updated_schedule = schedule.model_copy(
        update={
            "fairness_score": fairness_score,
            "average_fairness_score": report["avg_score"],
            "is_verified": True
        }
    )

    return {
        "schedule": updated_schedule,
        "fairness_metrics": scores,
        "least_satisfied_worker": least_satisfied,
        "previous_fairness_score": previous_score,  # il precedente viene salvato prima di aggiornare
    }


def check_fairness_improvement(state: SmartSchedulerState) -> str:
    """
    Funzione condizionale LangGraph per Stage 4.
    Decide se continuare il refinement o terminare.

    Continua se:
    - Il nuovo min(score) è strettamente maggiore del precedente
    - Non si è superato il limite di iterazioni
    """
    scores = state.get("fairness_metrics", {})
    if not scores:
        return "end"

    new_min = min(scores.values())
    old_min = state.get("previous_fairness_score", 0.0)
    refinement_iter = state.get("refinement_iteration", 0)
    max_refinements = state.get("max_refinements", 10)

    improved = new_min > old_min + 1e-6  # soglia minima di miglioramento
    within_limit = refinement_iter < max_refinements

    logger.info(
        f"Fairness check — old_min={old_min:.3f}, new_min={new_min:.3f}, "
        f"improved={improved}, iter={refinement_iter}/{max_refinements}"
    )

    if improved and within_limit:
        # Aggiorna il previous_fairness_score prima di continuare
        return "continue_refinement"

    if not improved:
        logger.info("Nessun miglioramento di fairness — terminazione loop")
    else:
        logger.info(f"Limite iterazioni raggiunto ({max_refinements}) — terminazione")

    return "end"


def update_previous_score_node(state: SmartSchedulerState) -> dict:
    """
    Nodo intermedio che aggiorna previous_fairness_score prima del refinement.
    Va chiamato quando si decide di continuare il loop.
    """
    scores = state.get("fairness_metrics", {})
    new_min = min(scores.values()) if scores else 0.0
    return {"previous_fairness_score": new_min}
