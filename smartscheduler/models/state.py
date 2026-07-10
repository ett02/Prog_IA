"""
models/state.py — SmartSchedulerState: lo stato condiviso tra tutti i nodi LangGraph.
"""

from __future__ import annotations
from typing import Literal, Optional
from typing_extensions import TypedDict

from models.worker import Worker
from models.schedule import Schedule


class SmartSchedulerState(TypedDict, total=False):
    """
    Stato condiviso del grafo LangGraph.
    Ogni nodo legge e aggiorna i campi di sua competenza.
    """

    # ── Input ──────────────────────────────────────────────────────────────
    workers: list[Worker]               # lista completa dei lavoratori
    use_case: Literal["A", "B"]         # scenario attivo

    # ── Stage 1: Preferences ───────────────────────────────────────────────
    preferences_collected: bool         # True dopo Stage 1 completato
    ortools_preferences_code: str       # codice Python con soft constraints OR-Tools

    # ── Stage 2: Drafting (Deterministico) ─────────────────────────────────
    schedule: Optional[Schedule]        # schedule corrente (oggetto Pydantic)
    ortools_schedule_code: str          # codice Python completo generato dal builder
    draft_iteration: int                # iteratore per tracking fallimenti del solver
    max_draft_iterations: int           # limite loop hard-constraint (default 5)

    # ── Stage 3a: Hard Verification ────────────────────────────────────────
    hard_constraints_satisfied: bool
    violations: list[str]               # descrizioni testuali delle violazioni

    # ── Stage 3b: Fairness Evaluation ──────────────────────────────────────
    fairness_metrics: dict[str, float]  # worker_id → satisfaction_score [0,1]
    previous_fairness_score: float      # min(scores) dell'iterazione precedente
    least_satisfied_worker: Optional[str]

    # ── Stage 4: Refinement LNS (Deterministico) ───────────────────────────
    refinement_iteration: int           # iteratore del refinement loop
    max_refinements: int                # limite iterazioni LNS (default 10)
