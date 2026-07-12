"""
agents/drafting_agent.py — Stage 2 & 4: Schedule Drafting e Refinement.

Stage 2: Usa l'LLM per generare il codice OR-Tools completo.
Stage 4: Usa l'LLM per raffinare il codice OR-Tools e migliorare la fairness.

In entrambi i casi, il codice generato viene validato sintatticamente prima
dell'esecuzione. Se l'LLM fallisce dopo MAX_LLM_RETRIES tentativi,
si usa un fallback deterministico.
"""

from __future__ import annotations
import logging
import os
import re
from datetime import date, timedelta

from models.worker import Worker
from models.schedule import Schedule, ShiftAssignment, ShiftType
from models.state import SmartSchedulerState
from agents.base_llm import call_llm
from solver.ortools_builder import generate_ortools_template, build_days_list
from solver.ortools_runner import run_ortools_code
from prompts.drafting_prompt import (
    DRAFTING_SYSTEM,
    build_drafting_prompt,
    build_retry_prompt,
)
from prompts.refinement_prompt import (
    REFINEMENT_SYSTEM,
    build_refinement_prompt,
    format_schedule_for_prompt,
)
from config import (
    HORIZON_START, HORIZON_END, OUTPUT_DIR, MAX_DRAFT_ITERATIONS,
    MAX_LLM_RETRIES, LLM_TEMPERATURE_DRAFTING, LLM_TEMPERATURE_REFINEMENT,
    ORTOOLS_SOLVER_TIME_LIMIT,
)

logger = logging.getLogger(__name__)


# ── Helper: Estrazione e Validazione Codice LLM ────────────────────────────

def extract_python_code(response: str) -> str:
    """
    Estrae il blocco di codice Python dalla risposta dell'LLM.
    Cerca ```python ... ``` oppure ``` ... ```, altrimenti prende il testo grezzo.
    """
    # Cerca blocco ```python ... ```
    pattern = r"```python\s*\n(.*?)```"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Cerca blocco ``` ... ```
    pattern = r"```\s*\n(.*?)```"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Nessun blocco trovato, usa il testo grezzo (rimuovi eventuale markdown)
    # Cerca se c'è del codice che inizia con import o from o def
    lines = response.strip().splitlines()
    code_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "def ", '"""', "'''", "#")):
            code_start = i
            break
    if code_start is not None:
        return "\n".join(lines[code_start:])

    return response.strip()


def validate_python_syntax(code: str) -> tuple[bool, str]:
    """
    Verifica la correttezza sintattica del codice Python.
    Returns:
        (True, "") se valido, (False, "messaggio errore") se invalido.
    """
    try:
        compile(code, "<llm_generated>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError alla linea {e.lineno}: {e.msg}"


# ── Helper: Parsing risultato solver ────────────────────────────────────────

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


# ── Nodo LangGraph — Drafting (Stage 2) — LLM-DRIVEN ───────────────────────

def drafting_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 2 (Drafting) — LLM-BASED.

    L'LLM genera il codice OR-Tools completo a partire da un prompt dettagliato
    che include tutti i vincoli hard, le preferenze dei lavoratori e la struttura
    output attesa. In caso di errori sintattici, si effettuano fino a
    MAX_LLM_RETRIES tentativi con prompt di correzione. Se tutti falliscono,
    si usa il fallback deterministico (generate_ortools_template).
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    draft_iteration: int = state.get("draft_iteration", 0) + 1
    preferences_code: str = state.get("ortools_preferences_code", "")
    violations: list[str] = state.get("violations", [])
    previous_code: str = state.get("ortools_schedule_code", "")

    logger.info(f"Stage 2 — Drafting (iterazione {draft_iteration}) - LLM Mode")

    # Prepara dati per il prompt
    days_list = build_days_list(HORIZON_START, HORIZON_END)
    n_days = len(days_list)
    horizon_start_str = HORIZON_START.isoformat()
    horizon_end_str = HORIZON_END.isoformat()

    # Costruisci il prompt
    prompt = build_drafting_prompt(
        workers=workers,
        use_case=use_case,
        preferences_code=preferences_code,
        horizon_start_str=horizon_start_str,
        horizon_end_str=horizon_end_str,
        n_days=n_days,
        days_list=days_list,
        violations=violations if violations else None,
        previous_code=previous_code if previous_code else None,
    )

    # Chiama LLM con retry
    code = None
    llm_success = False
    llm_attempts = 0

    for attempt in range(MAX_LLM_RETRIES + 1):
        llm_attempts += 1
        try:
            logger.info(f"Chiamata LLM (drafting, tentativo {attempt + 1}/{MAX_LLM_RETRIES + 1})")
            raw_response = call_llm(
                prompt,
                system_prompt=DRAFTING_SYSTEM,
                temperature=LLM_TEMPERATURE_DRAFTING,
            )
            extracted_code = extract_python_code(raw_response)

            # Validazione sintattica
            syntax_ok, error = validate_python_syntax(extracted_code)
            if syntax_ok:
                code = extracted_code
                llm_success = True
                logger.info(f"LLM drafting: codice valido al tentativo {attempt + 1}")
                break
            else:
                logger.warning(
                    f"LLM drafting tentativo {attempt + 1}: errore sintattico: {error}"
                )
                # Costruisci prompt di retry con l'errore
                prompt = build_retry_prompt(extracted_code, error)

        except Exception as e:
            logger.warning(f"LLM drafting tentativo {attempt + 1}: eccezione: {e}")
            break  # Non riprovare se è un errore di connessione

    # Fallback deterministico se LLM ha fallito
    if code is None:
        logger.warning(
            "Tutti i tentativi LLM falliti — fallback al template deterministico"
        )
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
            "llm_drafting_success": llm_success,
            "llm_drafting_attempts": llm_attempts,
        }

    logger.info(
        f"Schedule generato: {len(schedule.assignments)} assegnazioni "
        f"(LLM={'✅' if llm_success else '⚠️ fallback'})"
    )
    return {
        "draft_iteration": draft_iteration,
        "ortools_schedule_code": code,
        "ortools_preferences_code": preferences_code,
        "schedule": schedule,
        "violations": [],
        "llm_drafting_success": llm_success,
        "llm_drafting_attempts": llm_attempts,
    }


# ── Nodo LangGraph — Refinement (Stage 4) — LLM-DRIVEN + FALLBACK LNS ─────

def _refinement_lns_fallback(state: SmartSchedulerState) -> dict:
    """
    Fallback deterministico per il refinement (LNS — Fix-and-Optimize).

    Usato quando l'LLM non riesce a generare un codice OR-Tools valido.
    Funziona così:
    1. Identifica il worker meno soddisfatto e il suo turno da evitare
    2. Aumenta la penalità per quel turno nel preferences_code
    3. Congela il 50% dei worker più felici (LNS freeze)
    4. Rigenera il template e ri-esegue il solver
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    fairness_metrics: dict = state.get("fairness_metrics", {})
    least_satisfied: str = state.get("least_satisfied_worker", "")
    refinement_iteration: int = state.get("refinement_iteration", 0) + 1
    current_prefs_code: str = state.get("ortools_preferences_code", "")
    previous_schedule = state.get("schedule")

    logger.info(
        f"Stage 4 — Refinement LNS FALLBACK (iterazione {refinement_iteration}) "
        f"— target: {least_satisfied}"
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
        f"Refinement LNS: aumento penalità '{avoid_shift}' per {least_satisfied} "
        f"(night_tol={pref.night_tolerance})"
    )

    # Rigenera il preferences_code con penalità amplificata per W_target
    new_code_lines = []
    for line in current_prefs_code.splitlines():
        if f'preference_weights["{least_satisfied}"]' in line:
            penalties = {"morning": 1, "afternoon": 1, "night": 1}
            for sp in pref.preferred_shifts:
                priority_to_penalty = {1: 0, 2: 0, 3: 1, 4: 3}
                penalties[sp.shift_type] = priority_to_penalty.get(sp.priority, 1)
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
    logger.info("Esecuzione OR-Tools solver (refinement LNS fallback)...")
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
        return {
            "refinement_iteration": refinement_iteration,
            "hard_constraints_satisfied": True,
            "schedule": previous_schedule,
            "violations": ["LNS Fallito - Ottimo locale raggiunto"],
            "llm_refinement_success": False,
            "llm_refinement_attempts": 0,
        }

    logger.info(f"Schedule raffinato (LNS): {len(schedule.assignments)} assegnazioni")
    return {
        "refinement_iteration": refinement_iteration,
        "ortools_schedule_code": template,
        "ortools_preferences_code": refined_prefs_code,
        "schedule": schedule,
        "violations": [],
        "llm_refinement_success": False,
        "llm_refinement_attempts": 0,
    }


def refinement_node(state: SmartSchedulerState) -> dict:
    """
    Nodo LangGraph per Stage 4 (Fairness Refinement) — LLM-BASED.

    L'LLM analizza lo schedule corrente, i fairness scores e le preferenze
    del worker meno soddisfatto, e genera un nuovo codice OR-Tools con
    penalità soft modificate per migliorare la fairness.

    Se l'LLM fallisce (errore sintattico, solver INFEASIBLE, ecc.),
    cade nel fallback LNS deterministico.
    """
    workers: list[Worker] = state["workers"]
    use_case: str = state.get("use_case", "A")
    fairness_metrics: dict = state.get("fairness_metrics", {})
    least_satisfied: str = state.get("least_satisfied_worker", "")
    refinement_iteration: int = state.get("refinement_iteration", 0) + 1
    current_prefs_code: str = state.get("ortools_preferences_code", "")
    previous_schedule = state.get("schedule")
    previous_code: str = state.get("ortools_schedule_code", "")

    logger.info(
        f"Stage 4 — Refinement (iterazione {refinement_iteration}) — LLM Mode "
        f"— target: {least_satisfied} (score: {fairness_metrics.get(least_satisfied, 0):.3f})"
    )

    if previous_schedule is None:
        logger.warning("Nessuno schedule precedente per il refinement")
        return {"refinement_iteration": refinement_iteration}

    # Prepara dati per il prompt
    days_list = build_days_list(HORIZON_START, HORIZON_END)
    n_days = len(days_list)
    horizon_start_str = HORIZON_START.isoformat()
    horizon_end_str = HORIZON_END.isoformat()

    # Formatta lo schedule per il prompt
    schedule_summary = format_schedule_for_prompt(
        previous_schedule, workers, HORIZON_START, HORIZON_END
    )

    # Costruisci il prompt
    prompt = build_refinement_prompt(
        current_schedule_summary=schedule_summary,
        workers=workers,
        least_satisfied_worker=least_satisfied,
        fairness_metrics=fairness_metrics,
        preferences_code=current_prefs_code,
        previous_code=previous_code,
        use_case=use_case,
        horizon_start_str=horizon_start_str,
        horizon_end_str=horizon_end_str,
        n_days=n_days,
        days_list=days_list,
    )

    # Chiama LLM con retry
    code = None
    llm_success = False
    llm_attempts = 0

    for attempt in range(MAX_LLM_RETRIES + 1):
        llm_attempts += 1
        try:
            logger.info(
                f"Chiamata LLM (refinement, tentativo {attempt + 1}/{MAX_LLM_RETRIES + 1})"
            )
            raw_response = call_llm(
                prompt,
                system_prompt=REFINEMENT_SYSTEM,
                temperature=LLM_TEMPERATURE_REFINEMENT,
            )
            extracted_code = extract_python_code(raw_response)

            # Validazione sintattica
            syntax_ok, error = validate_python_syntax(extracted_code)
            if syntax_ok:
                code = extracted_code
                llm_success = True
                logger.info(f"LLM refinement: codice valido al tentativo {attempt + 1}")
                break
            else:
                logger.warning(
                    f"LLM refinement tentativo {attempt + 1}: errore sintattico: {error}"
                )
                # Retry con prompt di correzione
                from prompts.drafting_prompt import build_retry_prompt
                prompt = build_retry_prompt(extracted_code, error)

        except Exception as e:
            logger.warning(f"LLM refinement tentativo {attempt + 1}: eccezione: {e}")
            break

    # Se LLM ha generato codice valido, prova a eseguirlo
    if code is not None:
        save_ortools_code(code, f"schedule_refined_iter{refinement_iteration}.py")
        logger.info("Esecuzione OR-Tools solver (refinement LLM)...")
        result = run_ortools_code(code)

        schedule = parse_solver_result(
            result=result,
            workers=workers,
            horizon_start=HORIZON_START,
            horizon_end=HORIZON_END,
            use_case=use_case,
        )

        if schedule is not None:
            logger.info(
                f"Schedule raffinato (LLM): {len(schedule.assignments)} assegnazioni"
            )
            return {
                "refinement_iteration": refinement_iteration,
                "ortools_schedule_code": code,
                "ortools_preferences_code": current_prefs_code,
                "schedule": schedule,
                "violations": [],
                "llm_refinement_success": True,
                "llm_refinement_attempts": llm_attempts,
            }
        else:
            logger.warning(
                "LLM refinement: codice sintattico OK ma solver INFEASIBLE — fallback LNS"
            )

    # Fallback: LNS deterministico
    logger.warning("Refinement LLM fallito — fallback LNS deterministico")
    fallback_result = _refinement_lns_fallback(state)
    fallback_result["llm_refinement_attempts"] = llm_attempts
    return fallback_result
