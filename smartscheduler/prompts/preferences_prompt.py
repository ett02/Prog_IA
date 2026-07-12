"""
prompts/preferences_prompt.py — Prompt per lo Stage 1 (Preferences Agent).
"""

from __future__ import annotations
from models.worker import Worker


PREFERENCES_SYSTEM = """\
Sei un assistente esperto in pianificazione dei turni ospedalieri.
Il tuo compito è analizzare i testi forniti da una lista di lavoratori e estrarre
le loro preferenze di scheduling in formato JSON strutturato in un colpo solo.

Regole:
- Rispondi SOLO con JSON valido contenente un dizionario dove le chiavi sono i worker_id, e i valori sono i dizionari delle loro preferenze.
- Se un'informazione non è presente nel testo di un lavoratore, usa il valore di default indicato.
- Le priorità dei turni vanno da 1 (obbligatorio/da non togliere) a 4 (da evitare).
- Le tolleranze vanno da 0 (nessuna tolleranza) a 5 (tolleranza massima).
- Il giorno di riposo preferito: 0=Lunedì, 1=Martedì, ..., 6=Domenica, null=nessuna preferenza.
- Le date di indisponibilità devono essere nel formato ISO 8601 (YYYY-MM-DD).
"""

PREFERENCES_SCHEMA = """\
{
  "worker_id_1": {
    "preferred_shifts": [
      {"shift_type": "morning|afternoon|night", "priority": 1-4}
    ],
    "unavailable_dates": ["YYYY-MM-DD", ...],
    "preferred_rest_day": 0-6 or null,
    "night_tolerance": 0-5,
    "holiday_tolerance": 0-5,
    "consecutive_tolerance": 0-5
  },
  "worker_id_2": {
    ...
  }
}"""

PREFERENCES_EXAMPLES = """\
Esempio:
Testi forniti:
---
Lavoratore W01 (Mario Rossi):
"Preferisco i turni mattutini e vorrei evitare i turni notturni quando possibile."
---
Lavoratore W02 (Luigi Bianchi):
"Posso lavorare nei weekend, ma non nei giorni festivi consecutivi. Non voglio lavorare il 25 dicembre."

Output:
{
  "W01": {
    "preferred_shifts": [
      {"shift_type": "morning", "priority": 2},
      {"shift_type": "night", "priority": 4}
    ],
    "unavailable_dates": [],
    "preferred_rest_day": null,
    "night_tolerance": 1,
    "holiday_tolerance": 3,
    "consecutive_tolerance": 3
  },
  "W02": {
    "preferred_shifts": [],
    "unavailable_dates": ["2026-12-25"],
    "preferred_rest_day": null,
    "night_tolerance": 3,
    "holiday_tolerance": 1,
    "consecutive_tolerance": 1
  }
}"""


def build_preferences_prompt(workers: list[Worker]) -> str:
    """Costruisce il prompt per estrarre le preferenze di un batch di lavoratori."""
    workers_text_blocks = []
    for worker in workers:
        raw_text = (
            worker.preference.raw_text
            if worker.preference and worker.preference.raw_text
            else "Nessuna preferenza specificata."
        )
        workers_text_blocks.append(f"---\nLavoratore {worker.id} ({worker.name}):\n\"{raw_text}\"")

    combined_text = "\n".join(workers_text_blocks)

    return f"""\
Analizza i seguenti testi forniti dai lavoratori ed estrai le loro preferenze di scheduling.

{PREFERENCES_EXAMPLES}

Ora analizza questi testi:
{combined_text}

Schema di output atteso:
{PREFERENCES_SCHEMA}

Rispondi SOLO con il JSON delle preferenze estratte, nulla di più."""


def build_preferences_code_prompt(
    worker: Worker,
    pref_json: dict,
    horizon_start: str,
    horizon_end: str,
) -> str:
    """
    Costruisce il prompt per generare il codice Python OR-Tools
    delle preferenze (soft constraints + penalty weights).
    """
    return f"""\
Dato il seguente dizionario di preferenze per il lavoratore "{worker.id}",
genera le strutture dati Python corrispondenti per essere inserite
in un modello OR-Tools CP-SAT.

Worker ID: {worker.id!r}
Preferenze: {pref_json}
Orizzonte: {horizon_start} → {horizon_end}

Genera SOLO il codice Python (senza import, senza def) che definisce:
1. preference_weights["{worker.id}"] = dict con chiavi "morning", "afternoon", "night"
   e valori interi da 0 (preferito) a 3 (da evitare)
2. Se ci sono date di indisponibilità, aggiungi:
   unavailable_dates["{worker.id}"] = set di indici giorno (0-based dall'inizio orizzonte)
3. Se c'è un giorno di riposo preferito, aggiungi:
   preferred_rest_day["{worker.id}"] = <weekday int>

Esempio di output atteso:
preference_weights["W01"] = {{"morning": 0, "afternoon": 1, "night": 3}}
unavailable_dates["W01"] = {{18}}  # 25 dicembre = giorno 18 nell'orizzonte
preferred_rest_day["W01"] = 6  # domenica

Rispondi SOLO con le righe di codice Python, nessuna spiegazione."""
