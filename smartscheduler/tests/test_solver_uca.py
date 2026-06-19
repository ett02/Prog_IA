"""
tests/test_solver_uca.py — Test end-to-end del solver OR-Tools su Use Case A.

Bypassa l'LLM e testa direttamente:
1. Parsing del file use_case_a.txt
2. Generazione del template OR-Tools (solver/ortools_builder.py)
3. Esecuzione del solver (solver/ortools_runner.py)
4. Verifica hard constraints (agents/verification_agent.py)
5. Calcolo fairness metrics (solver/fairness_metrics.py)
6. Stampa report leggibile

Eseguibile senza Ollama.
"""

import sys
import os
import re
import json
from datetime import date, timedelta
from typing import Optional

# Assicura che il root del progetto sia nel path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.worker import Worker, WorkerType, Preference, ShiftPreference
from models.schedule import Schedule, ShiftAssignment, ShiftType
from solver.ortools_builder import generate_ortools_template
from solver.ortools_runner import run_ortools_code
from solver.fairness_metrics import compute_fairness_report
from agents.verification_agent import verify_hard_constraints
from config import HORIZON_START, HORIZON_END


# ── Utilità ────────────────────────────────────────────────────────────────

def load_workers_uca() -> list[Worker]:
    """Carica i 13 lavoratori da use_case_a.txt con preferenze semplificate."""
    scenario_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "scenarios", "use_case_a.txt"
    )
    with open(scenario_path, encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r"- id:\s*(\S+)\s*\n"
        r"\s*name:\s*\"([^\"]+)\"\s*\n"
        r"\s*type:\s*(\S+)\s*\n"
        r"\s*preferences:\s*\|\s*\n"
        r"((?:\s{6}[^\n]*\n?)*)",
        re.MULTILINE,
    )

    workers = []
    for match in pattern.finditer(content):
        worker_id = match.group(1)
        name = match.group(2)
        pref_text = " ".join(
            line.strip() for line in match.group(4).splitlines() if line.strip()
        )

        # Preferenze semplificate (senza LLM) basate su keyword nel testo
        pref = _parse_pref_from_text(pref_text)
        workers.append(Worker(
            id=worker_id,
            name=name,
            worker_type=WorkerType.STANDARD,
            preference=pref,
        ))

    return workers


def _parse_pref_from_text(text: str) -> Preference:
    """Parsing rule-based semplice delle preferenze senza LLM."""
    text_lower = text.lower()
    pref_shifts = []

    # Rileva turno preferito
    if "mattut" in text_lower or "mattino" in text_lower:
        pref_shifts.append(ShiftPreference(shift_type="morning", priority=2))
    if "pomerid" in text_lower:
        pref_shifts.append(ShiftPreference(shift_type="afternoon", priority=2))
    if "nottur" in text_lower and ("evit" in text_lower or "prefer" not in text_lower):
        pref_shifts.append(ShiftPreference(shift_type="night", priority=4))

    # Tolleranza notturni
    if "alta tolleranza" in text_lower and "nottur" in text_lower:
        night_tol = 5
    elif "evit" in text_lower and "nottur" in text_lower:
        night_tol = 1
    elif "bassa tolleranza" in text_lower:
        night_tol = 1
    else:
        night_tol = 3

    # Date indisponibili
    unavail = []
    if "natale" in text_lower or "25 dicembre" in text_lower:
        unavail.append(date(2026, 12, 25))
    if "26 dicembre" in text_lower:
        unavail.append(date(2026, 12, 26))
    if "1 gennaio" in text_lower or "capodanno" in text_lower:
        unavail.append(date(2027, 1, 1))
    if "2 gennaio" in text_lower:
        unavail.append(date(2027, 1, 2))

    # Giorno di riposo preferito
    rest_day = None
    rest_map = {
        "lunedì": 0, "martedì": 1, "mercoledì": 2, "giovedì": 3,
        "venerdì": 4, "sabato": 5, "domenica": 6,
    }
    for day_name, day_idx in rest_map.items():
        if day_name in text_lower:
            rest_day = day_idx
            break

    return Preference(
        preferred_shifts=pref_shifts,
        unavailable_dates=unavail,
        preferred_rest_day=rest_day,
        night_tolerance=night_tol,
        holiday_tolerance=3,
        consecutive_tolerance=3,
        raw_text=text,
    )


def parse_solver_result(result: dict, workers: list) -> Optional[Schedule]:
    """Converte il JSON del solver in un oggetto Schedule."""
    if "error" in result or result.get("status") in ("INFEASIBLE", "UNKNOWN"):
        return None

    assignments = []
    for worker_id, shifts in result.get("assignments", {}).items():
        for entry in shifts:
            try:
                assignments.append(ShiftAssignment(
                    worker_id=worker_id,
                    date=date.fromisoformat(entry["date"]),
                    shift_type=ShiftType(entry["shift"]),
                ))
            except (KeyError, ValueError):
                pass

    if not assignments:
        return None

    return Schedule(
        assignments=assignments,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case="A",
    )


def print_report(schedule: Schedule, workers: list[Worker], fairness: dict) -> None:
    """Stampa un report leggibile a terminale."""
    print("\n" + "=" * 70)
    print(f"SMARTSCHEDULER — TEST LOCALE Use Case A (senza LLM)")
    print(f"Orizzonte: {HORIZON_START} → {HORIZON_END}  |  Workers: {len(workers)}")
    print("=" * 70)

    print(f"\n📋 Assegnazioni totali: {len(schedule.assignments)}")
    print(f"📊 Fairness score (min): {fairness['fairness_score']:.3f}")
    print(f"📈 Avg score:            {fairness['avg_score']:.3f}")
    print(f"🏆 Worker peggiore:      {fairness['least_satisfied']} "
          f"({fairness['scores'].get(fairness['least_satisfied'], 0):.3f})")

    print("\n" + "─" * 70)
    print("SATISFACTION SCORES")
    print("─" * 70)
    for wid, score in sorted(fairness["scores"].items(), key=lambda x: x[1]):
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        worker_name = next((w.name for w in workers if w.id == wid), wid)
        print(f"  {wid} {worker_name:20s} [{bar}] {score:.3f}")

    print("\n" + "─" * 70)
    print("STATISTICHE PER LAVORATORE")
    print("─" * 70)
    print(f"  {'ID':5s} {'Nome':20s} {'Units':6s} {'Notti':6s} {'Festivi':8s} {'Score':6s}")
    print(f"  {'─'*5} {'─'*20} {'─'*6} {'─'*6} {'─'*8} {'─'*6}")

    HOLIDAYS = {
        date(2026, 12, 8), date(2026, 12, 25), date(2026, 12, 26),
        date(2027, 1, 1), date(2027, 1, 6),
    }
    for w in workers:
        assignments = schedule.get_worker_assignments(w.id)
        units = schedule.total_units_for_worker(w.id)
        nights = sum(1 for a in assignments if a.shift_type == ShiftType.NIGHT)
        holidays = sum(1 for a in assignments if a.date in HOLIDAYS)
        score = fairness["scores"].get(w.id, 0)
        print(f"  {w.id:5s} {w.name:20s} {units:6d} {nights:6d} {holidays:8d} {score:.3f}")

    print("\n" + "─" * 70)
    print("CALENDARIO (prime 2 settimane)")
    print("─" * 70)
    current = HORIZON_START
    limit = HORIZON_START + timedelta(days=13)
    while current <= limit:
        ds = schedule.get_day_schedule(current)
        day_label = current.strftime("%a %d/%m")
        m = ", ".join(ds.morning) if ds.morning else "—"
        a = ", ".join(ds.afternoon) if ds.afternoon else "—"
        n = ", ".join(ds.night) if ds.night else "—"
        print(f"  {day_label} | M:[{m}]  P:[{a}]  N:[{n}]")
        current += timedelta(days=1)
    print("  ...")


# ── Main ───────────────────────────────────────────────────────────────────

def run_test():
    print("=" * 70)
    print("SMARTSCHEDULER — TEST SOLVER OR-TOOLS (Use Case A, senza LLM)")
    print("=" * 70)

    # 1. Carica lavoratori
    print("\n[1/5] Caricamento lavoratori da use_case_a.txt...")
    workers = load_workers_uca()
    print(f"  ✅ {len(workers)} lavoratori caricati:")
    for w in workers:
        shifts_info = [f"{sp.shift_type}(p={sp.priority})" for sp in w.preference.preferred_shifts] if w.preference else []
        print(f"     {w.id}: {w.name} | prefs={shifts_info}")

    # 2. Genera template OR-Tools (con preferenze rule-based)
    print("\n[2/5] Generazione template OR-Tools...")
    # Costruisce preference_weights rule-based
    pref_code_lines = []
    for w in workers:
        penalties = {"morning": 1, "afternoon": 1, "night": 1}
        if w.preference:
            priority_to_pen = {1: 0, 2: 0, 3: 1, 4: 3}
            for sp in w.preference.preferred_shifts:
                penalties[sp.shift_type] = priority_to_pen.get(sp.priority, 1)
        pref_code_lines.append(f'    preference_weights["{w.id}"] = {penalties!r}')

        if w.preference and w.preference.unavailable_dates:
            indices = set()
            for d in w.preference.unavailable_dates:
                delta = (d - HORIZON_START).days
                if 0 <= delta < 31:
                    indices.add(delta)
            if indices:
                pref_code_lines.append(f'    unavailable_dates["{w.id}"] = {indices!r}')

        if w.preference and w.preference.preferred_rest_day is not None:
            pref_code_lines.append(
                f'    preferred_rest_day["{w.id}"] = {w.preference.preferred_rest_day}'
            )

    preferences_code = "\n".join(pref_code_lines)
    template = generate_ortools_template(
        workers=workers,
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
        use_case="A",
        preferences_code=preferences_code,
    )
    print(f"  ✅ Template generato ({len(template)} caratteri)")

    # Salva il template per ispezione
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(out_dir, exist_ok=True)
    template_path = os.path.join(out_dir, "test_uca_solver.py")
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"  📄 Template salvato in: {template_path}")

    # 3. Esegui solver
    print("\n[3/5] Esecuzione OR-Tools CP-SAT solver...")
    print("  ⏳ (può richiedere fino a 30 secondi)...")
    result = run_ortools_code(template, timeout=120)

    if "error" in result:
        print(f"\n  ❌ SOLVER FALLITO: {result['error']}")
        print("\n  Possibili cause:")
        print("  - Il template OR-Tools ha un errore di sintassi")
        print("  - Il problema è INFEASIBLE con i vincoli attuali")
        print(f"\n  Template salvato in: {template_path}")
        print("  Esegui manualmente: python output/test_uca_solver.py")
        return False

    status = result.get("status", "UNKNOWN")
    obj = result.get("objective", "N/A")
    n_assignments = sum(len(v) for v in result.get("assignments", {}).values())
    print(f"  ✅ Solver completato — Status: {status} | Objective: {obj:.1f} | Assignments: {n_assignments}")

    # 4. Parsa in Schedule
    print("\n[4/5] Verifica vincoli hard...")
    schedule = parse_solver_result(result, workers)
    if schedule is None:
        print("  ❌ Parsing schedule fallito")
        return False

    verification = verify_hard_constraints(schedule, workers, use_case="A")
    if verification["satisfied"]:
        print(f"  ✅ TUTTI i vincoli hard soddisfatti "
              f"({verification['checks_passed']}/{verification['checks_total']} check)")
    else:
        print(f"  ⚠️  {len(verification['violations'])} violazioni rilevate:")
        for v in verification["violations"][:10]:
            print(f"     → {v}")
        if len(verification["violations"]) > 10:
            print(f"     ... e altre {len(verification['violations'])-10} violazioni")

    # 5. Fairness
    print("\n[5/5] Calcolo metriche di fairness...")
    # Aggiorna i workers con le preferenze estratte (per il calcolo fairness)
    fairness = compute_fairness_report(workers, schedule)
    print(f"  ✅ Fairness score (min):  {fairness['fairness_score']:.3f}")
    print(f"     Avg score:             {fairness['avg_score']:.3f}")
    print(f"     Score range:           {fairness['score_range']:.3f}")
    print(f"     Least satisfied:       {fairness['least_satisfied']}")

    # Report completo
    print_report(schedule, workers, fairness)

    # Salva JSON
    json_path = os.path.join(out_dir, "test_uca_result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "status": status,
            "use_case": "A",
            "verified": verification["satisfied"],
            "violations_count": len(verification["violations"]),
            "fairness": fairness,
            "assignments_count": len(schedule.assignments),
        }, f, indent=2, default=str)
    print(f"\n📁 Risultato JSON salvato in: {json_path}")

    return verification["satisfied"]


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
