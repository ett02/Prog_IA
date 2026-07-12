"""
prompts/refinement_prompt.py — Prompt per lo Stage 4 (Refinement Agent).

Costruisce il prompt che l'LLM usa per raffinare il codice OR-Tools
in modo da migliorare la fairness dello schedule preservando i vincoli hard.
"""

from __future__ import annotations
from models.worker import Worker, WorkerType
from models.schedule import Schedule, ShiftType
from config import ORTOOLS_SOLVER_TIME_LIMIT
from datetime import date, timedelta


REFINEMENT_SYSTEM = """\
Sei un esperto di pianificazione dei turni ospedalieri e ottimizzazione.
Devi raffinare uno schedule esistente per migliorare l'equità (fairness).
Il tuo obiettivo è migliorare il satisfaction score del lavoratore più svantaggiato
SENZA peggiorare gli altri e SENZA violare i vincoli hard.

REGOLE CRITICHE:
1. Genera un file Python COMPLETO e ESEGUIBILE con OR-Tools CP-SAT
2. L'output DEVE essere JSON valido su stdout con print(json.dumps(...))
3. Rispondi SOLO con il blocco ```python ... ``` contenente il codice
4. NON rimuovere vincoli hard — devono essere TUTTI presenti
5. Modifica SOLO i pesi delle penalità soft per favorire il worker svantaggiato
6. Usa SOLO librerie standard + ortools
"""


def format_schedule_for_prompt(
    schedule: Schedule,
    workers: list[Worker],
    horizon_start: date,
    horizon_end: date,
) -> str:
    """
    Formatta lo schedule corrente in un formato tabellare leggibile
    per essere incluso nel prompt all'LLM.
    """
    lines = []
    for w in workers:
        assignments = schedule.get_worker_assignments(w.id)
        shifts_str = []
        for a in sorted(assignments, key=lambda x: x.date):
            day_label = a.date.strftime("%d/%m")
            shifts_str.append(f"{day_label}={a.shift_type.value}")
        line = f"  {w.id} ({w.name}): {', '.join(shifts_str)}"
        lines.append(line)
    return "\n".join(lines)


def format_fairness_summary(
    fairness_metrics: dict[str, float],
    workers: list[Worker],
) -> str:
    """Formatta i satisfaction scores per il prompt."""
    lines = []
    for wid, score in sorted(fairness_metrics.items(), key=lambda x: x[1]):
        w = next((w for w in workers if w.id == wid), None)
        name = w.name if w else "?"
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        lines.append(f"  {wid} ({name}): [{bar}] {score:.3f}")
    return "\n".join(lines)


def build_refinement_prompt(
    current_schedule_summary: str,
    workers: list[Worker],
    least_satisfied_worker: str,
    fairness_metrics: dict[str, float],
    preferences_code: str,
    previous_code: str,
    use_case: str,
    horizon_start_str: str,
    horizon_end_str: str,
    n_days: int,
    days_list: list[str],
) -> str:
    """
    Costruisce il prompt per il Refinement Agent (Stage 4).
    Include lo schedule corrente, i fairness scores, e chiede all'LLM
    di generare un nuovo codice OR-Tools che migliori la fairness.
    """
    all_ids = [w.id for w in workers]
    standard_ids = [w.id for w in workers if w.worker_type == WorkerType.STANDARD]
    specialized_ids = [w.id for w in workers if w.worker_type == WorkerType.SPECIALIZED]

    # Info sul worker meno soddisfatto
    target_worker = next((w for w in workers if w.id == least_satisfied_worker), None)
    target_info = ""
    if target_worker and target_worker.preference:
        pref = target_worker.preference
        shift_prefs = ", ".join(
            f"{sp.shift_type}=priority {sp.priority}"
            for sp in pref.preferred_shifts
        )
        target_info = f"""
DETTAGLI WORKER MENO SODDISFATTO ({least_satisfied_worker} — {target_worker.name}):
- Satisfaction score attuale: {fairness_metrics.get(least_satisfied_worker, 0):.3f}
- Turni preferiti: {shift_prefs or 'nessuna preferenza specifica'}
- Tolleranza notturni: {pref.night_tolerance}/5
- Tolleranza festivi: {pref.holiday_tolerance}/5
- Giorno riposo preferito: {pref.preferred_rest_day if pref.preferred_rest_day is not None else 'nessuno'}
- Date indisponibilità: {[d.isoformat() for d in pref.unavailable_dates] if pref.unavailable_dates else 'nessuna'}
"""

    # Fairness summary
    fairness_summary = format_fairness_summary(fairness_metrics, workers)

    # Coverage constraint per use case
    if use_case == "A":
        coverage_desc = "Almeno 2 lavoratori per turno"
    else:
        coverage_desc = "Almeno 3 totali per turno + almeno 1 specializzato"

    # Limita il codice precedente
    prev_code_lines = previous_code.strip().splitlines()
    if len(prev_code_lines) > 200:
        prev_code_lines = prev_code_lines[:200] + ["# ... (troncato)"]
    prev_code_str = "\n".join(prev_code_lines)

    prompt = f"""\
Hai generato uno schedule che soddisfa tutti i vincoli hard, ma la fairness è migliorabile.

SCHEDULE ATTUALE:
{current_schedule_summary}

SATISFACTION SCORES (0=pessimo, 1=perfetto):
{fairness_summary}

Il worker meno soddisfatto è: {least_satisfied_worker}
{target_info}
OBIETTIVO:
Modifica il codice OR-Tools per migliorare la soddisfazione di {least_satisfied_worker}
aumentando le penalità sui turni che NON preferisce (specialmente notturni se ha bassa tolleranza).

VINCOLO CRITICO: Non peggiorare il satisfaction score minimo degli altri worker.
VINCOLO CRITICO: Tutti i vincoli hard devono rimanere — NON rimuoverli.

PARAMETRI:
- Orizzonte: {horizon_start_str} → {horizon_end_str} ({n_days} giorni)
- Use Case: {use_case} ({coverage_desc})
- all_workers = {all_ids!r}
- standard_workers = {standard_ids!r}
- specialized_workers = {specialized_ids!r}
- days = {days_list!r}
- solver.parameters.max_time_in_seconds = {ORTOOLS_SOLVER_TIME_LIMIT}

VINCOLI HARD DA MANTENERE:
1. Copertura minima ({coverage_desc})
2. Max 1 turno/giorno per lavoratore
3. No notte[d] + mattino[d+1]
4. Indisponibilità assoluta
5. 2 giorni liberi dopo notte
6. Max 36 ore in finestra scorrevole 7 giorni
7. Esattamente 25 shift-units/mese per lavoratore

PREFERENZE LAVORATORI (da inserire nel codice):
{preferences_code}

CODICE OR-TOOLS PRECEDENTE (da modificare):
```python
{prev_code_str}
```

STRATEGIA SUGGERITA:
- Aumenta le penalità per i turni scomodi di {least_satisfied_worker}
  (es. se odia le notti, metti penalty night=5 per lui)
- Abbassa leggermente le penalità degli altri worker per compensare

FORMATO OUTPUT:
Il codice deve stampare JSON con la stessa struttura del codice precedente:
{{"status": "...", "objective": ..., "assignments": {{...}}}}

Genera il codice Python COMPLETO e CORRETTO. Rispondi SOLO con ```python ... ```."""

    return prompt
