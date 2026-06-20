"""
prompts/drafting_prompt.py — Prompt per Stage 2 (Schedule Drafting).
"""

from __future__ import annotations
from models.worker import Worker


def build_drafting_prompt(
    ortools_template: str,
    workers: list[Worker],
    use_case: str,
    preferences_summary: str,
    violations: list[str] | None = None,
    draft_iteration: int = 1,
) -> str:
    """
    Prompt per il Drafting Agent.
    Alla prima iterazione genera uno schedule, nelle iterazioni successive
    corregge le violazioni segnalate.
    """
    worker_list = "\n".join(
        f"  - {w.id} ({w.name}, {w.worker_type.value})" for w in workers
    )

    violations_section = ""
    if violations:
        violations_str = "\n".join(f"  - {v}" for v in violations)
        violations_section = f"""
⚠️ ATTENZIONE — VIOLAZIONI DA CORREGGERE (iterazione {draft_iteration}):
Il precedente schedule ha le seguenti violazioni dei vincoli hard. DEVONO essere corrette:
{violations_str}

Analizza attentamente ogni violazione e modifica il codice per eliminarle TUTTE.
"""

    return f"""\
Sei un esperto di constraint programming e pianificazione ospedaliera.
Il tuo compito è completare il codice OR-Tools CP-SAT seguente per generare
uno schedule valido per i lavoratori ospedalieri.
{violations_section}
LAVORATORI ({len(workers)} totali — Use Case {use_case}):
{worker_list}

PREFERENZE DEI LAVORATORI (già integrate nel template come preference_weights):
{preferences_summary}

ISTRUZIONI:
1. Il template seguente ha già tutti i vincoli hard implementati. NON modificarli.
2. Il template ha già implementato: preference_weights, unavailable_dates,
   night_tolerances (vincolo 8) e la penalità preferred_rest_day. NON reimplementarli.
3. Completa la sezione "TODO (LLM)" aggiungendo SOLO penalità per turni festivi:
   - Usa le date festive: 2026-12-08, 2026-12-25, 2026-12-26, 2027-01-01, 2027-01-06
   - Penalizza i turni in quelle date per worker con bassa tolleranza (holiday_tolerance)
4. REGOLE CRITICHE per il codice OR-Tools:
   - NON usare shift_vars[(w,d,s)] in un if Python — è un BoolVar, non un bool!
   - Per aggiungere penalità usa: penalty_terms.append(shift_vars[(w,d,s)] * peso)
   - NON usare operatori % su oggetti date (usa .weekday() invece)
   - NON aggiungere import aggiuntivi

TEMPLATE OR-TOOLS DA COMPLETARE:
```python
{ortools_template}
```

Restituisci il codice Python COMPLETO e FUNZIONANTE nel blocco ```python ... ```.
"""


def build_drafting_summary_prompt(workers: list[Worker]) -> str:
    """
    Genera una sintesi leggibile delle preferenze da includere nel prompt del drafting.
    """
    lines = []
    for w in workers:
        if w.preference:
            pref = w.preference
            shifts_info = ", ".join(
                f"{sp.shift_type}(p={sp.priority})" for sp in pref.preferred_shifts
            ) or "nessuna"
            lines.append(
                f"  {w.id}: turni=[{shifts_info}], "
                f"night_tol={pref.night_tolerance}, "
                f"holiday_tol={pref.holiday_tolerance}, "
                f"rest_day={pref.preferred_rest_day}"
            )
        else:
            lines.append(f"  {w.id}: nessuna preferenza")
    return "\n".join(lines)
