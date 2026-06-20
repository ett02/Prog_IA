"""
OR-Tools CP-SAT Schedule — Use Case A
Orizzonte: 2026-12-07 → 2027-01-06 (31 giorni)
Generato da SmartScheduler ortools_builder.py
"""

from ortools.sat.python import cp_model
import json
from datetime import date, timedelta

def solve_schedule():
    model = cp_model.CpModel()

    # ── Parametri ─────────────────────────────────────────────────────────
    all_workers = ['W01', 'W02', 'W03', 'W04', 'W05', 'W06', 'W07', 'W08', 'W09', 'W10', 'W11', 'W12', 'W13']
    standard_workers = ['W01', 'W02', 'W03', 'W04', 'W05', 'W06', 'W07', 'W08', 'W09', 'W10', 'W11', 'W12', 'W13']
    specialized_workers = []

    days = ['2026-12-07', '2026-12-08', '2026-12-09', '2026-12-10', '2026-12-11', '2026-12-12', '2026-12-13', '2026-12-14', '2026-12-15', '2026-12-16', '2026-12-17', '2026-12-18', '2026-12-19', '2026-12-20', '2026-12-21', '2026-12-22', '2026-12-23', '2026-12-24', '2026-12-25', '2026-12-26', '2026-12-27', '2026-12-28', '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01', '2027-01-02', '2027-01-03', '2027-01-04', '2027-01-05', '2027-01-06']
    n_days = 31
    shifts = ["morning", "afternoon", "night"]
    shift_hours = {"morning": 6, "afternoon": 6, "night": 12}
    shift_units = {"morning": 1, "afternoon": 1, "night": 2}

    # ── Preferenze dei lavoratori (da Stage 1) ────────────────────────────
    # preference_weights[worker_id][shift_type] = penalità (0=preferito, 3=da evitare)
    preference_weights = {}
    unavailable_dates = {}  # worker_id -> set di indici giorno (0-based)
    preferred_rest_day = {}  # worker_id -> weekday (0=Mon..6=Sun), o None

    # Worker W01
    preference_weights["W01"] = {"morning": 0, "afternoon": 1, "night": 3}
    unavailable_dates["W01"] = {18}  
    preferred_rest_day["W01"] = 6
    # Worker W02
    preference_weights["W02"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = set()
    preference_weights['unavailable_dates']['W02'] = set()
    
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = None
    else:
        if 'raw_text' in preference_weights['W02']:
            import re
            pattern = r'\b(\w+)\b'
            match = re.search(pattern, preference_weights['W02']['raw_text'])
            if match:
                day_of_week = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
                day_index = [day_of_week.index(day) for day in match.group(1)]
                preference_weights['preferred_rest_day']['W02'] = day_index[0]
    # Worker W03
    preference_weights["W03"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = {}
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = None
    if len(preference_weights["W03"]["preferred_shifts"]) > 0 and preference_weights["W03"]["preferred_shifts"][0]["shift_type"] == "afternoon":
        preference_weights["W03"]["preferred_rest_day"] = 6 if preference_weights["W03"]["raw_text"].find("Preferisco i turni") != -1 else None
    else:
        preference_weights["W03"]["preferred_rest_day"] = None
    
    if len(preference_weights["W03"]["unavailable_dates"]) > 0:
        unavailable_dates["W03"] = set(range(preference_weights["W03"]["unavailable_dates"][0]))
    # Worker W04
    preference_weights["W04"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = {}
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = None
    if len(preference_weights["W04"]["unavailable_dates"]) > 0:
        unavailable_dates["W04"] = set([i for i, date in enumerate(preference_weights["W04"]["unavailable_dates"])])
    if 'preferred_rest_day' in preference_weights["W04"]:
        preferred_rest_day["W04"] = preference_weights["W04"]["preferred_rest_day"]
    # Worker W05
    preference_weights["W05"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = set()
    preference_weights['unavailable_dates']['W05'] = set()
    
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = None
    else:
        if 'preferred_rest_day' in preference_weights['W05']:
            preferred_rest_day = preference_weights['W05']['preferred_rest_day']
            if preferred_rest_day is not None and isinstance(preferred_rest_day, int):
                preference_weights["W05"] = {"morning": 0, "afternoon": 1, "night": 3}
                if 'unavailable_dates' in preference_weights:
                    unavailable_dates = preference_weights['unavailable_dates']
                    if 'W05' in unavailable_dates:
                        preferred_rest_day_index = (preferred_rest_day - 1) % 7
                        unavailable_dates["W05"].add(preferred_rest_day_index)
        else:
            preference_weights['preferred_rest_day']['W05'] = None
    # Worker W06
    preference_weights["W06"] = {
        "morning": 0,
        "afternoon": 1,
        "night": 3
    }
    
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = {}
    
    preference_weights['unavailable_dates']['W06'] = set()
    
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = {}
    
    preference_weights['preferred_rest_day']['W06'] = 6
    # Worker W07
    preference_weights["W07"] = {"morning": 0, "afternoon": 1, "night": 3}
    unavailable_dates["W07"] = set([18])
    if 'preferred_rest_day' in WorkerID['W07']:
        preferred_rest_day["W07"] = WorkerID['W07']['preferred_rest_day']
    else:
        preferred_rest_day["W07"] = None
    # Worker W08
    preference_weights["W08"] = {
        "morning": 0,
        "afternoon": 1,
        "night": 3
    }
    
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = {}
    
    preference_weights['unavailable_dates']['W08'] = set()
    
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = {}
    
    preference_weights['preferred_rest_day']['W08'] = 6
    # Worker W09
    preference_weights["W09"] = {
        "morning": 0,
        "afternoon": 1,
        "night": 3
    }
    
    if 'unavailable_dates' in preference_weights['W09']:
        unavailable_dates["W09"] = set(range(preference_weights['W09']['unavailable_dates'].index('2026-12-25') + 1))
    
    preferred_rest_day["W09"] = 6 if preference_weights['W09']['preferred_rest_day'] is not None else None
    # Worker W10
    preference_weights["W10"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' not in preference_weights:
        preference_weights['unavailable_dates'] = {}
    if 'preferred_rest_day' not in preference_weights:
        preference_weights['preferred_rest_day'] = None
    if len(preference_weights["W10"]["preferred_shifts"]) > 0 and preference_weights["W10"]["preferred_shifts"][0]["shift_type"] == "afternoon":
        preference_weights["W10"]["preferred_rest_day"] = 6
    else:
        preference_weights["W10"]["preferred_rest_day"] = None
    if len(preference_weights["W10"]["unavailable_dates"]) > 0:
        unavailable_dates["W10"] = set(range(len(preference_weights["W10"]["unavailable_dates"])))
    # Worker W11
    preference_weights["W11"] = {"morning": 0, "afternoon": 1, "night": 3}
    if "unavailable_dates" not in preference_weights:
        preference_weights["unavailable_dates"] = set()
    preference_weights["unavailable_dates"]["W11"] = set()
    
    if "preferred_rest_day" not in preference_weights:
        preference_weights["preferred_rest_day"] = None
    else:
        preferred_rest_day = preference_weights["preferred_rest_day"]
        if preferred_rest_day is not None and isinstance(preferred_rest_day, int):
            preference_weights["unavailable_dates"]["W11"].add(6 - preferred_rest_day)
    # Worker W12
    preference_weights["W12"] = {"morning": 0, "afternoon": 1, "night": 3}
    unavailable_dates["W12"] = set([2026-12-26, 2027-01-02])
    preferred_rest_day["W12"] = 6 if preference_weights["W12"]["preferred_shifts"][0]["shift_type"] == "morning" else None
    # Worker W13
    preference_weights["W13"] = {"morning": 0, "afternoon": 1, "night": 3}
    if 'unavailable_dates' in preference_weights['W13']:
        unavailable_dates["W13"] = set(range(len(preference_weights['W13']['unavailable_dates'])))
    else:
        unavailable_dates["W13"] = set()
    preferred_rest_day["W13"] = 6

    # ── Variabili booleane ────────────────────────────────────────────────
    # shift_vars[(worker, day_idx, shift)] = 1 se worker copre quel turno
    shift_vars = {}
    for w in all_workers:
        for d in range(n_days):
            for s in shifts:
                shift_vars[(w, d, s)] = model.NewBoolVar(f"shift_{w}_d{d}_{s}")

    # ========== VINCOLI HARD ==============================================

    # 1. Copertura minima per turno
    for d in range(n_days):
        for s in shifts:
            model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 2)

    # 2. Max 1 turno al giorno per lavoratore
    for w in all_workers:
        for d in range(n_days):
            model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)

    # 3. No turni consecutivi: notte[d] + mattino[d+1] <= 1
    #    (ridondante con vincolo 5, mantenuto per esplicitezza)
    for w in all_workers:
        for d in range(n_days - 1):
            model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)

    # 4. Indisponibilità assoluta dei lavoratori (da preferenze)
    for w, unavail_days in unavailable_dates.items():
        for d in unavail_days:
            if 0 <= d < n_days:
                for s in shifts:
                    model.Add(shift_vars[(w, d, s)] == 0)

    # 5. 2 giorni liberi obbligatori dopo ogni turno notturno
    for w in all_workers:
        for d in range(n_days):
            if d + 1 < n_days:
                model.Add(
                    shift_vars[(w, d, "night")] +
                    sum(shift_vars[(w, d+1, s)] for s in shifts) <= 1
                )
            if d + 2 < n_days:
                model.Add(
                    shift_vars[(w, d, "night")] +
                    sum(shift_vars[(w, d+2, s)] for s in shifts) <= 1
                )

    # 6. Max 36 ore in qualsiasi finestra scorrevole di 7 giorni
    window_size = 7
    for w in all_workers:
        for start in range(n_days - window_size + 1):
            window = range(start, start + window_size)
            model.Add(
                sum(shift_vars[(w, d, s)] * shift_hours[s]
                    for d in window for s in shifts) <= 36
            )

    # 7. Esattamente 25 shift-units per lavoratore nel mese
    for w in all_workers:
        model.Add(
            sum(shift_vars[(w, d, s)] * shift_units[s]
                for d in range(n_days) for s in shifts) == 25
        )

    # ========== VINCOLI SOFT (OBIETTIVO) ==================================
    # L'obiettivo minimizza la somma pesata delle penalità sulle preferenze.
    # penalty_terms viene popolato qui sotto usando preference_weights.

    penalty_terms = []

    # Penalità per turni non preferiti
    for w in all_workers:
        w_prefs = preference_weights.get(w, {})
        for d in range(n_days):
            for s in shifts:
                pen = w_prefs.get(s, 1)  # default: penalità 1 (neutro)
                if pen > 0:
                    penalty_terms.append(shift_vars[(w, d, s)] * pen)

    # Penalità per turni festivi per worker con bassa tolleranza
    for w in all_workers:
        w_prefs = preference_weights.get(w, {})
        for d in range(n_days):
            if days[d] in ["2026-12-25", "2027-01-01"]:
                pen = 5  # penalità per turni festivi
                if w_prefs.get("night", 3) < 4:
                    pen += 2  # penalità aggiuntiva per bassa tolleranza
                penalty_terms.append(shift_vars[(w, d, "night")] * pen)

    # Penalità per violazioni del giorno di riposo preferito
    for w in all_workers:
        w_prefs = preference_weights.get(w, {})
        preferred_rest_day = w_prefs.get("preferred_rest_day", None)
        if preferred_rest_day is not None and days[0] != preferred_rest_day:
            pen = 3  # penalità per violazione del giorno di riposo preferito
            penalty_terms.append(shift_vars[(w, 0, "morning")] * pen)

    # Qualsiasi altra penalità rilevante basata sulle preferenze
    for w in all_workers:
        w_prefs = preference_weights.get(w, {})
        if 'unavailable_dates' in w_prefs and len(w_prefs['unavailable_dates']) > 0:
            penalty_terms.append(sum(shift_vars[(w, d, s)] for d in range(n_days) for s in shifts) * 2)

    model.Minimize(sum(penalty_terms))

    # ========== SOLVE =====================================================
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result = {}
        for w in all_workers:
            result[w] = []
            for d in range(n_days):
                for s in shifts:
                    if solver.Value(shift_vars[(w, d, s)]):
                        result[w].append({
                            "day_idx": d,
                            "date": days[d],
                            "shift": s
                        })
        output = {
            "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "objective": solver.ObjectiveValue(),
            "assignments": result
        }
        print(json.dumps(output))
    else:
        print(json.dumps({
            "status": "INFEASIBLE" if status == cp_model.INFEASIBLE else "UNKNOWN",
            "error": "Nessuna soluzione trovata"
        }))

solve_schedule()