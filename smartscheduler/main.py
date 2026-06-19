"""
main.py — Entry point CLI di SmartScheduler.

Uso:
    python main.py --use-case A
    python main.py --use-case B
    python main.py --use-case A --model llama3.2 --max-refinements 5
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta

# Setup logging prima di qualsiasi import locale
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

from config import (
    HORIZON_START, HORIZON_END, OUTPUT_DIR,
    MAX_DRAFT_ITERATIONS, MAX_REFINEMENT_ITERATIONS,
    OLLAMA_MODEL,
)
from models.worker import Worker, WorkerType, Preference
from models.schedule import Schedule
from graph.smartscheduler_graph import app

logger = logging.getLogger("main")


# ── Parser scenario ────────────────────────────────────────────────────────

def load_workers_from_scenario(use_case: str) -> list[Worker]:
    """
    Carica i lavoratori dal file di scenario corrispondente.
    Legge le preferenze in NL dal file txt e crea oggetti Worker.
    """
    from config import SCENARIOS_DIR

    path = os.path.join(SCENARIOS_DIR, f"use_case_{use_case.lower()}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File scenario non trovato: {path}")

    workers = []
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Parsing semplice del formato YAML-like del file scenario
    import re

    # Trova tutti i blocchi worker
    pattern = re.compile(
        r"- id:\s*(\S+)\s*\n"
        r"\s*name:\s*\"([^\"]+)\"\s*\n"
        r"\s*type:\s*(\S+)\s*\n"
        r"\s*preferences:\s*\|\s*\n"
        r"((?:\s{6}[^\n]*\n?)*)",
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        worker_id = match.group(1)
        name = match.group(2)
        worker_type_str = match.group(3)
        pref_text = "\n".join(
            line.strip() for line in match.group(4).splitlines() if line.strip()
        )

        worker_type = (
            WorkerType.SPECIALIZED
            if worker_type_str == "specialized"
            else WorkerType.STANDARD
        )

        workers.append(Worker(
            id=worker_id,
            name=name,
            worker_type=worker_type,
            preference=Preference(raw_text=pref_text),
        ))

    logger.info(f"Caricati {len(workers)} lavoratori per Use Case {use_case}")
    return workers


# ── Output report ──────────────────────────────────────────────────────────

def generate_report(final_state: dict, use_case: str) -> str:
    """Genera il report testuale finale."""
    schedule: Schedule | None = final_state.get("schedule")
    scores: dict = final_state.get("fairness_metrics", {})
    violations: list = final_state.get("violations", [])
    refinement_iter: int = final_state.get("refinement_iteration", 0)
    draft_iter: int = final_state.get("draft_iteration", 0)

    lines = [
        "=" * 70,
        f"SMARTSCHEDULER — REPORT FINALE (Use Case {use_case})",
        f"Orizzonte: {HORIZON_START.isoformat()} → {HORIZON_END.isoformat()}",
        "=" * 70,
        "",
    ]

    if schedule is None:
        lines.append("⛔ Nessuno schedule valido generato.")
        if violations:
            lines.append("\nViolazioni non risolte:")
            for v in violations:
                lines.append(f"  • {v}")
        return "\n".join(lines)

    lines += [
        f"✅ Schedule verificato: {schedule.is_verified}",
        f"📊 Fairness score (min): {schedule.fairness_score:.3f}" if schedule.fairness_score else "",
        f"🔄 Iterazioni drafting: {draft_iter}",
        f"🔄 Iterazioni raffinamento: {refinement_iter}",
        f"📋 Assegnazioni totali: {len(schedule.assignments)}",
        "",
        "─" * 70,
        "SATISFACTION SCORES DEI LAVORATORI",
        "─" * 70,
    ]

    if scores:
        for wid, score in sorted(scores.items(), key=lambda x: x[1]):
            bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
            lines.append(f"  {wid:5s} [{bar}] {score:.3f}")

    lines += ["", "─" * 70, "CALENDARIO TURNI", "─" * 70]

    current = HORIZON_START
    while current <= HORIZON_END:
        ds = schedule.get_day_schedule(current)
        day_name = current.strftime("%a %d/%m")
        m = ", ".join(ds.morning) or "—"
        a = ", ".join(ds.afternoon) or "—"
        n = ", ".join(ds.night) or "—"
        lines.append(f"  {day_name} | M: {m:30s} | P: {a:30s} | N: {n}")
        current += timedelta(days=1)

    lines += ["", "─" * 70, "STATISTICHE PER LAVORATORE", "─" * 70]
    workers: list = final_state.get("workers", [])
    for w in workers:
        assignments = schedule.get_worker_assignments(w.id)
        total_units = schedule.total_units_for_worker(w.id)
        nights = sum(1 for a in assignments if a.shift_type.value == "night")
        holidays = sum(
            1 for a in assignments
            if a.date in {
                date(2026, 12, 8), date(2026, 12, 25), date(2026, 12, 26),
                date(2027, 1, 1), date(2027, 1, 6),
            }
        )
        lines.append(
            f"  {w.id:5s} ({w.name:20s}): "
            f"units={total_units:2d}, notti={nights:2d}, festivi={holidays}, "
            f"score={scores.get(w.id, 0):.3f}"
        )

    if violations:
        lines += ["", "─" * 70, "⚠️ VIOLAZIONI RESIDUE", "─" * 70]
        for v in violations:
            lines.append(f"  • {v}")

    return "\n".join(lines)


def save_outputs(final_state: dict, use_case: str) -> None:
    """Salva JSON e report testuale in output/."""
    schedule: Schedule | None = final_state.get("schedule")
    scores = final_state.get("fairness_metrics", {})

    # JSON
    json_path = os.path.join(OUTPUT_DIR, f"schedule_final_uc{use_case}.json")
    output_data = {
        "use_case": use_case,
        "horizon": {
            "start": HORIZON_START.isoformat(),
            "end": HORIZON_END.isoformat(),
        },
        "verified": schedule.is_verified if schedule else False,
        "fairness_score": schedule.fairness_score if schedule else None,
        "refinement_iterations": final_state.get("refinement_iteration", 0),
        "draft_iterations": final_state.get("draft_iteration", 0),
        "satisfaction_scores": scores,
        "assignments": [
            {
                "worker_id": a.worker_id,
                "date": a.date.isoformat(),
                "shift": a.shift_type.value,
            }
            for a in (schedule.assignments if schedule else [])
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON salvato: {json_path}")

    # Report testuale
    report = generate_report(final_state, use_case)
    report_path = os.path.join(OUTPUT_DIR, f"report_uc{use_case}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"Report salvato: {report_path}")

    print("\n" + report)


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SmartScheduler — Pianificazione turni ospedalieri con LLM + OR-Tools"
    )
    parser.add_argument(
        "--use-case", "-u",
        choices=["A", "B"],
        required=True,
        help="Use Case: A (omogenei) o B (standard + specializzati)",
    )
    parser.add_argument(
        "--model", "-m",
        default=OLLAMA_MODEL,
        help=f"Modello Ollama da usare (default: {OLLAMA_MODEL})",
    )
    parser.add_argument(
        "--max-refinements",
        type=int,
        default=MAX_REFINEMENT_ITERATIONS,
        help=f"Max iterazioni di raffinamento fairness (default: {MAX_REFINEMENT_ITERATIONS})",
    )
    parser.add_argument(
        "--max-drafts",
        type=int,
        default=MAX_DRAFT_ITERATIONS,
        help=f"Max tentativi di drafting (default: {MAX_DRAFT_ITERATIONS})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Output di log dettagliato (DEBUG level)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Aggiorna il modello Ollama da CLI
    import config
    config.OLLAMA_MODEL = args.model

    logger.info(f"🚀 SmartScheduler avviato — Use Case {args.use_case} | Modello: {args.model}")

    # Carica lavoratori
    workers = load_workers_from_scenario(args.use_case)

    # Stato iniziale
    initial_state: dict = {
        "input_model": open(
            os.path.join(config.DATA_DIR, "input_model.txt"), encoding="utf-8"
        ).read(),
        "workers": workers,
        "use_case": args.use_case,
        "preferences_collected": False,
        "ortools_preferences_code": "",
        "schedule": None,
        "ortools_schedule_code": "",
        "draft_iteration": 0,
        "max_draft_iterations": args.max_drafts,
        "hard_constraints_satisfied": False,
        "violations": [],
        "fairness_metrics": {},
        "previous_fairness_score": 0.0,
        "least_satisfied_worker": None,
        "refinement_iteration": 0,
        "max_refinements": args.max_refinements,
        "pipeline_done": False,
        "error_message": None,
    }

    logger.info("Esecuzione pipeline SmartScheduler...")
    try:
        final_state = app.invoke(
            initial_state,
            config={"recursion_limit": 100},
        )
        logger.info("✅ Pipeline completata")
        save_outputs(final_state, args.use_case)

    except Exception as e:
        logger.exception(f"❌ Errore durante l'esecuzione: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
