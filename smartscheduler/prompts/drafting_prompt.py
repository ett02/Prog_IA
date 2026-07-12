"""
prompts/drafting_prompt.py — Prompt per lo Stage 2 (Drafting Agent).

Costruisce il prompt che l'LLM usa per generare il codice OR-Tools CP-SAT
completo per lo scheduling dei turni ospedalieri.
"""

from __future__ import annotations
from models.worker import Worker, WorkerType
from config import ORTOOLS_SOLVER_TIME_LIMIT


DRAFTING_SYSTEM = """\
Sei un esperto di constraint programming con Google OR-Tools CP-SAT.
Il tuo compito è generare un file Python COMPLETO e ESEGUIBILE che risolva
un problema di scheduling dei turni ospedalieri.

REGOLE CRITICHE:
1. Il file DEVE essere eseguibile direttamente con `python file.py`
2. L'output DEVE essere un JSON valido stampato su stdout con `print(json.dumps(...))`
3. NON usare commenti o testo prima o dopo il codice Python
4. Rispondi SOLO con il blocco ```python ... ``` contenente il codice
5. NON usare f-string con apici annidati complessi
6. Usa SOLO librerie standard + ortools (import json, from ortools.sat.python import cp_model)
7. Il codice DEVE contenere una funzione solve_schedule() chiamata alla fine
"""


def build_drafting_prompt(
    workers: list[Worker],
    use_case: str,
    preferences_code: str,
    horizon_start_str: str,
    horizon_end_str: str,
    n_days: int,
    days_list: list[str],
    violations: list[str] | None = None,
    previous_code: str | None = None,
) -> str:
    """
    Costruisce il prompt completo per il Drafting Agent (Stage 2).

    Se `violations` è non-vuoto, il prompt include le violazioni trovate
    dalla verifica precedente e chiede all'LLM di correggere il codice.
    """
    all_ids = [w.id for w in workers]
    standard_ids = [w.id for w in workers if w.worker_type == WorkerType.STANDARD]
    specialized_ids = [w.id for w in workers if w.worker_type == WorkerType.SPECIALIZED]

    # Sezione copertura in base all'use case
    if use_case == "A":
        coverage_desc = (
            "- Copertura: almeno 2 lavoratori per ogni turno di ogni giorno\n"
            "  Codice: model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 2)"
        )
    else:
        coverage_desc = (
            "- Copertura: almeno 3 lavoratori totali per turno + almeno 1 specializzato\n"
            "  Codice per totali: model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 3)\n"
            "  Codice per specializzati: model.Add(sum(shift_vars[(w, d, s)] for w in specialized_workers) >= 1)"
        )

    # Sezione violazioni (per retry dopo verifica fallita)
    violations_section = ""
    if violations:
        violations_text = "\n".join(f"  - {v}" for v in violations[:10])
        violations_section = f"""
ATTENZIONE — VIOLAZIONI TROVATE NELLA VERSIONE PRECEDENTE:
Il codice precedente ha generato uno schedule con le seguenti violazioni.
Devi correggerle nel nuovo codice:
{violations_text}
"""

    # Sezione codice precedente (per retry)
    previous_code_section = ""
    if previous_code:
        # Limita a 200 righe per non eccedere il contesto
        lines = previous_code.strip().splitlines()
        if len(lines) > 200:
            lines = lines[:200] + ["# ... (troncato)"]
        previous_code_section = f"""
CODICE PRECEDENTE (da correggere):
```python
{chr(10).join(lines)}
```
"""

    prompt = f"""\
Genera un file Python COMPLETO che usi OR-Tools CP-SAT per schedulare i turni ospedalieri.

PARAMETRI:
- Orizzonte: {horizon_start_str} → {horizon_end_str} ({n_days} giorni)
- Use Case: {use_case}
- Lavoratori totali: {len(all_ids)}
  - all_workers = {all_ids!r}
  - standard_workers = {standard_ids!r}
  - specialized_workers = {specialized_ids!r}
- Turni: ["morning" (6h, peso 1), "afternoon" (6h, peso 1), "night" (12h, peso 2)]

VINCOLI HARD OBBLIGATORI (TUTTI devono essere implementati):

1. {coverage_desc}

2. Max 1 turno al giorno per lavoratore:
   for w in all_workers:
       for d in range(n_days):
           model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)

3. No turni consecutivi notte-mattino:
   for w in all_workers:
       for d in range(n_days - 1):
           model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)

4. Indisponibilità assoluta (dal dizionario unavailable_dates):
   for w, unavail_days in unavailable_dates.items():
       for d in unavail_days:
           for s in shifts: model.Add(shift_vars[(w, d, s)] == 0)

5. 2 giorni liberi obbligatori dopo ogni turno notturno:
   for w in all_workers:
       for d in range(n_days):
           if d+1 < n_days:
               model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+1, s)] for s in shifts) <= 1)
           if d+2 < n_days:
               model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+2, s)] for s in shifts) <= 1)

6. Max 36 ore in qualsiasi finestra scorrevole di 7 giorni:
   shift_hours = {{"morning": 6, "afternoon": 6, "night": 12}}
   for w in all_workers:
       for start in range(n_days - 7 + 1):
           window = range(start, start + 7)
           model.Add(sum(shift_vars[(w, d, s)] * shift_hours[s] for d in window for s in shifts) <= 36)

7. Esattamente 25 shift-units per lavoratore nel mese:
   shift_units = {{"morning": 1, "afternoon": 1, "night": 2}}
   for w in all_workers:
       model.Add(sum(shift_vars[(w, d, s)] * shift_units[s] for d in range(n_days) for s in shifts) == 25)

PREFERENZE DEI LAVORATORI (soft constraints, da includere nell'obiettivo):
Il codice deve definire i dizionari preference_weights, unavailable_dates,
preferred_rest_day, night_tolerances, holiday_tolerances e poi inserire
il seguente codice di inizializzazione preferenze:

{preferences_code}

VINCOLI SOFT (obiettivo da minimizzare):
- Penalità per turni non preferiti: sum(shift_vars[(w,d,s)] * preference_weights[w][s])
- Penalità giorno di riposo preferito: se worker lavora nel suo preferred_rest_day, +2
- Penalità turni festivi: per date festive (2026-12-08, 2026-12-25, 2026-12-26, 2027-01-01, 2027-01-06),
  penalità = max(0, 5 - holiday_tolerance) per ogni turno festivo

STRUTTURA OUTPUT:
Il codice deve usare solver.parameters.max_time_in_seconds = {ORTOOLS_SOLVER_TIME_LIMIT}
e stampare il risultato come JSON con questa struttura:
{{
    "status": "OPTIMAL"|"FEASIBLE"|"INFEASIBLE"|"UNKNOWN",
    "objective": <float>,
    "assignments": {{
        "<worker_id>": [
            {{"day_idx": <int>, "date": "<YYYY-MM-DD>", "shift": "<shift_type>"}},
            ...
        ]
    }}
}}

La lista days da usare per mappare day_idx → date è:
days = {days_list!r}
{violations_section}{previous_code_section}
Genera il codice Python COMPLETO. Rispondi SOLO con il blocco ```python ... ```."""

    return prompt


def build_retry_prompt(
    failed_code: str,
    error_message: str,
) -> str:
    """
    Costruisce un prompt di retry dopo un errore sintattico nel codice generato.
    """
    return f"""\
Il codice Python che hai generato contiene un ERRORE e non può essere eseguito.

ERRORE:
{error_message}

CODICE CON ERRORE:
```python
{failed_code}
```

Correggi l'errore e genera il codice Python COMPLETO e CORRETTO.
Rispondi SOLO con il blocco ```python ... ``` contenente il codice corretto.
NON cambiare la logica, correggi SOLO l'errore sintattico."""
