"""
prompts/refinement_prompt.py — Prompt per Stage 4 (Schedule Refinement).
"""

from __future__ import annotations
from models.worker import Worker


def build_refinement_prompt(
    current_ortools_code: str,
    workers: list[Worker],
    least_satisfied_worker_id: str,
    least_satisfied_score: float,
    all_scores: dict[str, float],
    refinement_iteration: int,
) -> str:
    """
    Prompt per il Refinement Agent.
    Chiede all'LLM di migliorare la soddisfazione del worker meno soddisfatto
    senza peggiorare il minimo degli altri.
    """
    # Trova le preferenze del worker meno soddisfatto
    target_worker = next((w for w in workers if w.id == least_satisfied_worker_id), None)
    target_pref_str = "Nessuna preferenza registrata."
    if target_worker and target_worker.preference:
        p = target_worker.preference
        shifts_info = ", ".join(
            f"{sp.shift_type}(priority={sp.priority})" for sp in p.preferred_shifts
        ) or "nessuna"
        target_pref_str = (
            f"Turni preferiti: {shifts_info}\n"
            f"Tolleranza notturni: {p.night_tolerance}/5\n"
            f"Tolleranza festivi: {p.holiday_tolerance}/5\n"
            f"Giorno di riposo preferito: {p.preferred_rest_day} "
            f"(0=Lun..6=Dom, None=qualsiasi)"
        )

    # Sintesi score degli altri worker
    other_scores = {
        wid: score for wid, score in all_scores.items()
        if wid != least_satisfied_worker_id
    }
    min_other = min(other_scores.values()) if other_scores else 0.0
    scores_table = "\n".join(
        f"  {wid}: {score:.3f}" + (" ← TARGET" if wid == least_satisfied_worker_id else "")
        for wid, score in sorted(all_scores.items(), key=lambda x: x[1])
    )

    return f"""\
Sei un esperto di ottimizzazione equa dei turni ospedalieri.
Stai lavorando all'iterazione {refinement_iteration} di raffinamento dello schedule.

SITUAZIONE ATTUALE:
{scores_table}

WORKER MENO SODDISFATTO: {least_satisfied_worker_id} (score: {least_satisfied_score:.3f})
Preferenze di {least_satisfied_worker_id}:
{target_pref_str}

OBIETTIVO:
Modifica il codice OR-Tools seguente per migliorare la soddisfazione di {least_satisfied_worker_id}.

VINCOLI CRITICI (non negoziabili):
1. Tutti i vincoli hard DEVONO rimanere soddisfatti (NON modificare la sezione VINCOLI HARD).
2. Il nuovo schedule NON deve peggiorare il satisfaction score minimo degli altri worker
   (attuale minimo degli altri: {min_other:.3f}).
3. Il codice deve restituire l'output JSON nel formato identico al template.

STRATEGIE SUGGERITE per migliorare {least_satisfied_worker_id}:
- Assegnare più turni del tipo preferito (priority 1 o 2)
- Ridurre i turni del tipo da evitare (priority 4)
- Rispettare il giorno di riposo preferito
- Ridurre turni notturni se bassa tolleranza

Per fare questo, modifica i pesi nell'obiettivo: dai peso molto alto alle
penalità di {least_satisfied_worker_id} e aggiusta le penalità degli altri
per bilanciare equamente.

CODICE OR-TOOLS ATTUALE:
```python
{current_ortools_code}
```

Restituisci il codice Python COMPLETO e MODIFICATO nel blocco ```python ... ```.
Alla fine del blocco aggiungi un commento che spiega brevemente le modifiche:
# MODIFICHE: <spiegazione>
"""
