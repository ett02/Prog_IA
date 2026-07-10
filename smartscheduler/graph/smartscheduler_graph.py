"""
graph/smartscheduler_graph.py — Grafo LangGraph per SmartScheduler.

Definisce lo StateGraph dell'intera applicazione. L'orchestrazione gestisce un flusso ibrido:
- Stage 1 (Preferences): Estrazione dati strutturati tramite LLM.
- Stage 2, 3, 4 (Drafting, Verification, Refinement): Fasi puramente deterministiche 
  e matematiche (generazione template, CP-SAT Solver e metaeuristica LNS).
"""

from __future__ import annotations
import logging

# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END

from models.state import SmartSchedulerState
from agents.preferences_agent import preferences_node
from agents.drafting_agent import drafting_node, refinement_node
from agents.verification_agent import verification_node, check_hard_constraints
from agents.fairness_agent import (
    fairness_node,
    check_fairness_improvement,
    update_previous_score_node,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Costruisce e compila il grafo LangGraph di SmartScheduler.

    Flusso:
        preferences → drafting → hard_verification
            ↕ (se violazioni)
        hard_verification → fairness_evaluation
            ↓ (se miglioramento possibile)
        update_score → refinement → hard_verification
            ↓ (fine)
        END
    """
    workflow = StateGraph(SmartSchedulerState)

    # ── Nodi ──────────────────────────────────────────────────────────────
    workflow.add_node("preferences", preferences_node)
    workflow.add_node("drafting", drafting_node)
    workflow.add_node("hard_verification", verification_node)
    workflow.add_node("fairness_evaluation", fairness_node)
    workflow.add_node("update_score", update_previous_score_node)
    workflow.add_node("refinement", refinement_node)

    # ── Entry point ────────────────────────────────────────────────────────
    workflow.set_entry_point("preferences")

    # ── Edges fissi ────────────────────────────────────────────────────────
    workflow.add_edge("preferences", "drafting")
    workflow.add_edge("drafting", "hard_verification")
    # update_score aggiorna previous_fairness_score prima del refinement
    workflow.add_edge("update_score", "refinement")
    # Dopo il refinement si riverifica sempre
    workflow.add_edge("refinement", "hard_verification")

    # ── Edge condizionale 1: hard_verification ─────────────────────────────
    # ⚠️ Nessun add_edge fisso da hard_verification — solo condizionale
    workflow.add_conditional_edges(
        "hard_verification",
        check_hard_constraints,
        {
            "violated": "drafting",          # torna al drafting con lista violations
            "draft_limit_reached": END,       # abort: troppi tentativi falliti
            "satisfied": "fairness_evaluation",
        },
    )

    # ── Edge condizionale 2: fairness_evaluation ───────────────────────────
    # ⚠️ Nessun add_edge fisso da fairness_evaluation — solo condizionale
    workflow.add_conditional_edges(
        "fairness_evaluation",
        check_fairness_improvement,
        {
            "continue_refinement": "update_score",  # aggiorna score poi raffina
            "end": END,
        },
    )
    return workflow.compile()


# Istanza globale del grafo compilato
app = build_graph()
