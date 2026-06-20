"""
agents/preferences_agent.py — Stage 1: Preferences Definition.

Raccoglie le preferenze in NL di ogni lavoratore e le trasforma in:
1. Oggetti Pydantic Preference (validati)
2. Codice Python OR-Tools per i soft constraints (preference_weights, ecc.)
"""

from __future__ import annotations
import json
import logging
from datetime import date

from models.worker import Worker, Preference, ShiftPreference
from agents.base_llm import call_llm_for_json, call_llm_for_code
from prompts.preferences_prompt import (
    build_preferences_prompt,
    build_preferences_code_prompt,
    PREFERENCES_SYSTEM,
)
from models.state import SmartSchedulerState
from config import HORIZON_START, HORIZON_END

logger = logging.getLogger(__name__)


def extract_preference_from_text(worker: Worker) -> Preference:
    """
    Usa l'LLM per estrarre le preferenze strutturate dal testo NL del lavoratore.
    Se il parsing fallisce, ritorna preferenze di default.
    """
    prompt = build_preferences_prompt(worker)
    logger.info(f"Estrazione preferenze per {worker.id} ({worker.name})")

    try:
        response = call_llm_for_json(prompt, system_prompt=PREFERENCES_SYSTEM)
        data = json.loads(response)

        # Valida con Pydantic
        pref = Preference(
            preferred_shifts=[
                ShiftPreference(**sp) for sp in data.get("preferred_shifts", [])
            ],
            unavailable_dates=[
                date.fromisoformat(d) for d in data.get("unavailable_dates", [])
            ],
            preferred_rest_day=data.get("preferred_rest_day"),
            night_tolerance=data.get("night_tolerance", 3),
            holiday_tolerance=data.get("holiday_tolerance", 3),
            consecutive_tolerance=data.get("consecutive_tolerance", 3),
            raw_text=worker.preference.raw_text if worker.preference else None,
        )
        logger.info(f"Preferenze estratte per {worker.id}: {pref.model_dump()}")
        return pref

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Parsing preferenze fallito per {worker.id}: {e}. Uso default.")
        return Preference(
            raw_text=worker.preference.raw_text if worker.preference else None
        )


def generate_preferences_code(
    worker: Worker,
    pref: Preference,
) -> str:
    """
    Genera deterministicamente il codice Python OR-Tools per le preferenze del worker.

    NOTA: L'LLM NON viene usato per questa fase. I tentativi precedenti hanno
    dimostrato che llama3.2 genera sistematicamente `set([2026-12-26, ...])` che è
    sintassi Python invalida (leading zeros in integer literals).
    Il codice viene generato tramite il fallback deterministico che produce
    sempre indici interi corretti (0-based day index).
    """
    logger.debug(f"Generazione codice preferenze (deterministica) per {worker.id}")
    return _fallback_preferences_code(worker.id, pref)


def _fallback_preferences_code(worker_id: str, pref: Preference) -> str:
    """Genera il codice di preferenze deterministicamente senza LLM.

    Il peso della penalità notturna è derivato dalla night_tolerance:
    tol 0 → penalty 5 (da evitare fortemente), tol 5 → penalty 0 (neutro/preferito).
    Questo sostituisce il vincolo hard di bilanciamento notturni (che causava INFEASIBLE).
    """
    priority_to_penalty = {1: 0, 2: 0, 3: 1, 4: 3}

    shift_penalties = {"morning": 1, "afternoon": 1, "night": 1}
    for sp in pref.preferred_shifts:
        shift_penalties[sp.shift_type] = priority_to_penalty.get(sp.priority, 1)

    # Sovrascrive la penalità notturna con quella derivata dalla night_tolerance.
    # Formula: penalty = max(0, 5 - night_tolerance)
    # tol=0 → 5 (molto pesante), tol=3 → 2 (moderato), tol=5 → 0 (nessuna penalità)
    night_penalty_from_tol = max(0, 5 - pref.night_tolerance)
    # Usa il massimo tra la penalità dichiarata e quella dalla tolleranza
    shift_penalties["night"] = max(shift_penalties["night"], night_penalty_from_tol)

    lines = [
        f'preference_weights["{worker_id}"] = {shift_penalties!r}',
        # night_tolerance nel template (usata per la sezione log/debug)
        f'night_tolerances["{worker_id}"] = {pref.night_tolerance}',
    ]

    if pref.unavailable_dates:
        from datetime import timedelta
        indices = set()
        for d in pref.unavailable_dates:
            delta = (d - HORIZON_START).days
            if 0 <= delta < 31:
                indices.add(delta)
        lines.append(f'unavailable_dates["{worker_id}"] = {indices!r}')

    if pref.preferred_rest_day is not None:
        lines.append(f'preferred_rest_day["{worker_id}"] = {pref.preferred_rest_day}')

    return "\n".join(lines)


def _clean_code_block(text: str) -> str:
    """Rimuove i marker ```python e ``` dalla risposta LLM."""
    import re
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# ── Nodo LangGraph ─────────────────────────────────────────────────────────

def preferences_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 1.
    Processa tutti i lavoratori e genera il codice OR-Tools delle preferenze.
    """
    workers: list[Worker] = state["workers"]
    logger.info(f"Stage 1 — Preferences Definition ({len(workers)} workers)")

    all_prefs_code_lines = []
    updated_workers = []

    for worker in workers:
        # Estrai preferenze strutturate dal testo NL
        pref = extract_preference_from_text(worker)

        # Genera codice OR-Tools
        code = generate_preferences_code(worker, pref)
        all_prefs_code_lines.append(f"    # Worker {worker.id}")
        all_prefs_code_lines.append(f"    {code.replace(chr(10), chr(10) + '    ')}")

        # Aggiorna il worker con le preferenze estratte
        updated_worker = worker.model_copy(update={"preference": pref})
        updated_workers.append(updated_worker)

    combined_code = "\n".join(all_prefs_code_lines)
    logger.info("Stage 1 completato — preferenze formalizzate per tutti i workers")

    return {
        "workers": updated_workers,
        "preferences_collected": True,
        "ortools_preferences_code": combined_code,
    }
