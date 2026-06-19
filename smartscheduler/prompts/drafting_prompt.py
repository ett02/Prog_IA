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
2. Completa la sezione "VINCOLI SOFT" aggiungendo penalità per:
   - Turni festivi per worker con bassa tolleranza (holiday_tolerance bassa)
   - Violazioni del giorno di riposo preferito (preferred_rest_day)
   - Qualsiasi altra penalità rilevante basata sulle preferenze
3. L'obiettivo è minimizzare la somma delle penalità.
4. Il codice deve stampare il risultato in JSON su stdout come già previsto dal template.
5. NON aggiungere import aggiuntivi non necessari.

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
