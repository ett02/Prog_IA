"""
run_test_uca.py — Script di test end-to-end Use Case A (senza LLM, senza emoji).
Esegui con: python run_test_uca.py
"""

from __future__ import annotations
import sys
import os
import re
import json
from datetime import date, timedelta
from typing import Optional


ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from models.worker import Worker, WorkerType, Preference, ShiftPreference
from models.schedule import Schedule, ShiftAssignment, ShiftType
from solver.ortools_builder import generate_ortools_template
from solver.ortools_runner import run_ortools_code
from solver.fairness_metrics import compute_fairness_report
from agents.verification_agent import verify_hard_constraints
from config import HORIZON_START, HORIZON_END

HOLIDAYS = {
    date(2026, 12, 8), date(2026, 12, 25), date(2026, 12, 26),
    date(2027, 1, 1), date(2027, 1, 6),
}


def load_workers() -> list[Worker]:
    path = os.path.join(ROOT, "data", "scenarios", "use_case_a.txt")
    with open(path, encoding="utf-8") as f:
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
        wid = match.group(1)
        name = match.group(2)
        txt = " ".join(l.strip() for l in match.group(4).splitlines() if l.strip())
        workers.append(Worker(id=wid, name=name, worker_type=WorkerType.STANDARD,
                               preference=_parse_pref(txt)))
    return workers


def _parse_pref(text: str) -> Preference:
    t = text.lower()
    pref_shifts = []
    if "mattut" in t or "mattino" in t:
        pref_shifts.append(ShiftPreference(shift_type="morning", priority=2))
    if "pomerid" in t:
        pref_shifts.append(ShiftPreference(shift_type="afternoon", priority=2))
    if "nottur" in t and "evit" in t:
        pref_shifts.append(ShiftPreference(shift_type="night", priority=4))

    night_tol = 5 if ("alta tolleranza" in t and "nottur" in t) else \
                1 if ("evit" in t and "nottur" in t) else \
                1 if "bassa tolleranza" in t else 3

    unavail = []
    if "natale" in t or "25 dicembre" in t: unavail.append(date(2026, 12, 25))
    if "26 dicembre" in t: unavail.append(date(2026, 12, 26))
    if "1 gennaio" in t: unavail.append(date(2027, 1, 1))
    if "2 gennaio" in t: unavail.append(date(2027, 1, 2))

    rest_day = None
    for nm, idx in [("lunedi",0),("martedi",1),("mercoledi",2),("giovedi",3),
                    ("venerdi",4),("sabato",5),("domenica",6)]:
        if nm in t.replace('\xec','i').replace('\xe0','a').replace('\xf9','u'):
            rest_day = idx
            break

    return Preference(preferred_shifts=pref_shifts, unavailable_dates=unavail,
                      preferred_rest_day=rest_day, night_tolerance=night_tol,
                      holiday_tolerance=3, consecutive_tolerance=3, raw_text=text)


def parse_result(result: dict) -> Optional[Schedule]:
    if "error" in result or result.get("status") in ("INFEASIBLE", "UNKNOWN"):
        return None
    assignments = []
    for wid, shifts in result.get("assignments", {}).items():
        for e in shifts:
            try:
                assignments.append(ShiftAssignment(
                    worker_id=wid,
                    date=date.fromisoformat(e["date"]),
                    shift_type=ShiftType(e["shift"]),
                ))
            except (KeyError, ValueError):
                pass
    return Schedule(assignments=assignments, horizon_start=HORIZON_START,
                    horizon_end=HORIZON_END, use_case="A") if assignments else None


def build_pref_code(workers: list[Worker]) -> str:
    lines = []
    pen_map = {1: 0, 2: 0, 3: 1, 4: 3}
    for w in workers:
        p = {"morning": 1, "afternoon": 1, "night": 1}
        if w.preference:
            for sp in w.preference.preferred_shifts:
                p[sp.shift_type] = pen_map.get(sp.priority, 1)
        lines.append(f'    preference_weights["{w.id}"] = {p!r}')
        if w.preference and w.preference.unavailable_dates:
            idxs = {(d - HORIZON_START).days for d in w.preference.unavailable_dates
                    if 0 <= (d - HORIZON_START).days < 31}
            if idxs:
                lines.append(f'    unavailable_dates["{w.id}"] = {idxs!r}')
        if w.preference and w.preference.preferred_rest_day is not None:
            lines.append(f'    preferred_rest_day["{w.id}"] = {w.preference.preferred_rest_day}')
    return "\n".join(lines)


def main():
    sep = "=" * 68
    print(sep)
    print("SMARTSCHEDULER - TEST SOLVER OR-TOOLS - Use Case A (no LLM)")
    print(f"Orizzonte: {HORIZON_START} -> {HORIZON_END}")
    print(sep)

    # 1. Carica workers
    print("\n[1/5] Caricamento lavoratori da use_case_a.txt...")
    workers = load_workers()
    print(f"  CARICATI: {len(workers)} lavoratori")
    for w in workers:
        info = [f"{sp.shift_type}(p={sp.priority})" for sp in (w.preference.preferred_shifts if w.preference else [])]
        print(f"    {w.id}: {w.name} | prefs={info}")

    # 2. Genera template
    print("\n[2/5] Generazione template OR-Tools con vincoli hard...")
    pref_code = build_pref_code(workers)
    template = generate_ortools_template(
        workers=workers, horizon_start=HORIZON_START, horizon_end=HORIZON_END,
        use_case="A", preferences_code=pref_code,
    )
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    tpath = os.path.join(out_dir, "test_uca_solver.py")
    with open(tpath, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"  OK - Template ({len(template)} chars) salvato: {tpath}")

    # 3. Esegui solver
    print("\n[3/5] Esecuzione CP-SAT solver (timeout 120s)...")
    result = run_ortools_code(template, timeout=120)

    if "error" in result:
        print(f"  ERRORE SOLVER: {result['error'][:300]}")
        print(f"\n  Puoi eseguire manualmente: python {tpath}")
        return 1

    status = result.get("status", "?")
    obj = result.get("objective", 0)
    n_ass = sum(len(v) for v in result.get("assignments", {}).values())
    print(f"  SOLVER OK - Status: {status} | Objective: {obj:.1f} | Assignments: {n_ass}")

    # 4. Verifica vincoli hard
    print("\n[4/5] Verifica vincoli hard...")
    schedule = parse_result(result)
    if schedule is None:
        print("  ERRORE: impossibile parsare lo schedule")
        return 1

    ver = verify_hard_constraints(schedule, workers, use_case="A")
    if ver["satisfied"]:
        print(f"  TUTTI SODDISFATTI ({ver['checks_passed']}/{ver['checks_total']} check)")
    else:
        print(f"  VIOLAZIONI: {len(ver['violations'])} trovate:")
        for v in ver["violations"][:10]:
            print(f"    -> {v}")
        if len(ver["violations"]) > 10:
            print(f"    ... e altre {len(ver['violations'])-10}")

    # 5. Fairness
    print("\n[5/5] Calcolo fairness metrics...")
    fairness = compute_fairness_report(workers, schedule)
    print(f"  Fairness score (min): {fairness['fairness_score']:.3f}")
    print(f"  Avg score:            {fairness['avg_score']:.3f}")
    print(f"  Score range:          {fairness['score_range']:.3f}")
    print(f"  Least satisfied:      {fairness['least_satisfied']} "
          f"({fairness['scores'].get(fairness['least_satisfied'],0):.3f})")

    # Report tabellare
    print("\n" + "─" * 68)
    print("SATISFACTION SCORES")
    print("─" * 68)
    for wid, score in sorted(fairness["scores"].items(), key=lambda x: x[1]):
        bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
        name = next((w.name for w in workers if w.id == wid), wid)
        print(f"  {wid} {name:20s} [{bar}] {score:.3f}")

    print("\n" + "─" * 68)
    print(f"  {'ID':5s} {'Nome':20s} {'Units':6s} {'Notti':6s} {'Fstv':5s} {'Score':6s}")
    print(f"  {'─'*5} {'─'*20} {'─'*6} {'─'*6} {'─'*5} {'─'*6}")
    for w in workers:
        asgs = schedule.get_worker_assignments(w.id)
        units = schedule.total_units_for_worker(w.id)
        nights = sum(1 for a in asgs if a.shift_type == ShiftType.NIGHT)
        hols = sum(1 for a in asgs if a.date in HOLIDAYS)
        score = fairness["scores"].get(w.id, 0)
        print(f"  {w.id:5s} {w.name:20s} {units:6d} {nights:6d} {hols:5d} {score:.3f}")

    print("\n" + "─" * 68)
    print("CALENDARIO - Prime 14 giorni")
    print("─" * 68)
    cur = HORIZON_START
    for _ in range(14):
        ds = schedule.get_day_schedule(cur)
        m = ",".join(ds.morning) if ds.morning else "-"
        a = ",".join(ds.afternoon) if ds.afternoon else "-"
        n = ",".join(ds.night) if ds.night else "-"
        print(f"  {cur.strftime('%a %d/%m')} | M:[{m}] P:[{a}] N:[{n}]")
        cur += timedelta(days=1)
    print("  ...")

    # Salva JSON
    jpath = os.path.join(out_dir, "test_uca_result.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump({
            "status": status, "use_case": "A",
            "verified": ver["satisfied"],
            "violations_count": len(ver["violations"]),
            "violations": ver["violations"],
            "fairness": {k: (v if not isinstance(v, dict) else {str(kk): float(vv) for kk,vv in v.items()})
                         for k, v in fairness.items()},
            "assignments_count": len(schedule.assignments),
        }, f, indent=2, default=str)
    print(f"\nRisultato JSON: {jpath}")
    print(f"Template solver: {tpath}")
    print(sep)
    print("TEST COMPLETATO" + (" - SCHEDULE VALIDO" if ver["satisfied"] else " - VIOLAZIONI PRESENTI"))
    print(sep)
    return 0 if ver["satisfied"] else 1


if __name__ == "__main__":
    sys.exit(main())
