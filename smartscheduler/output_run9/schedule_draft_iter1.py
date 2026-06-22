"""
OR-Tools CP-SAT Schedule — Use Case B
Orizzonte: 2026-12-07 → 2027-01-06 (31 giorni)
Generato da SmartScheduler ortools_builder.py
"""

from ortools.sat.python import cp_model
import json
from datetime import date, timedelta

def solve_schedule():
    model = cp_model.CpModel()

    # ── Parametri ─────────────────────────────────────────────────────────
    all_workers = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10', 'S11', 'S12', 'S13', 'P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07']
    standard_workers = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10', 'S11', 'S12', 'S13']
    specialized_workers = ['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07']

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
    night_tolerances = {}   # worker_id -> int 0-5 (0=intollerante, 5=molto tollerante)
    holiday_tolerances = {} # worker_id -> int 0-5

    # Worker S01
    preference_weights["S01"] = {'morning': 0, 'afternoon': 1, 'night': 4}
    night_tolerances["S01"] = 1
    holiday_tolerances["S01"] = 3
    preferred_rest_day["S01"] = 5
    # Worker S02
    preference_weights["S02"] = {'morning': 1, 'afternoon': 1, 'night': 0}
    night_tolerances["S02"] = 5
    holiday_tolerances["S02"] = 3
    preferred_rest_day["S02"] = 3
    # Worker S03
    preference_weights["S03"] = {'morning': 1, 'afternoon': 0, 'night': 1}
    night_tolerances["S03"] = 5
    holiday_tolerances["S03"] = 4
    # Worker S04
    preference_weights["S04"] = {'morning': 1, 'afternoon': 1, 'night': 3}
    night_tolerances["S04"] = 3
    holiday_tolerances["S04"] = 3
    preferred_rest_day["S04"] = 5
    # Worker S05
    preference_weights["S05"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["S05"] = 3
    holiday_tolerances["S05"] = 3
    # Worker S06
    preference_weights["S06"] = {'morning': 0, 'afternoon': 1, 'night': 1}
    night_tolerances["S06"] = 4
    holiday_tolerances["S06"] = 3
    preferred_rest_day["S06"] = 6
    # Worker S07
    preference_weights["S07"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["S07"] = 3
    holiday_tolerances["S07"] = 3
    unavailable_dates["S07"] = set()
    # Worker S08
    preference_weights["S08"] = {'morning': 1, 'afternoon': 0, 'night': 1}
    night_tolerances["S08"] = 5
    holiday_tolerances["S08"] = 3
    preferred_rest_day["S08"] = 0
    # Worker S09
    preference_weights["S09"] = {'morning': 0, 'afternoon': 1, 'night': 1}
    night_tolerances["S09"] = 4
    holiday_tolerances["S09"] = 3
    unavailable_dates["S09"] = {18}
    # Worker S10
    preference_weights["S10"] = {'morning': 1, 'afternoon': 1, 'night': 0}
    night_tolerances["S10"] = 5
    holiday_tolerances["S10"] = 3
    preferred_rest_day["S10"] = 4
    # Worker S11
    preference_weights["S11"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["S11"] = 3
    holiday_tolerances["S11"] = 3
    # Worker S12
    preference_weights["S12"] = {'morning': 0, 'afternoon': 1, 'night': 1}
    night_tolerances["S12"] = 4
    holiday_tolerances["S12"] = 3
    unavailable_dates["S12"] = set()
    # Worker S13
    preference_weights["S13"] = {'morning': 1, 'afternoon': 1, 'night': 1}
    night_tolerances["S13"] = 4
    holiday_tolerances["S13"] = 3
    preferred_rest_day["S13"] = 2
    # Worker P01
    preference_weights["P01"] = {'morning': 0, 'afternoon': 0, 'night': 3}
    night_tolerances["P01"] = 2
    holiday_tolerances["P01"] = 3
    preferred_rest_day["P01"] = 6
    # Worker P02
    preference_weights["P02"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["P02"] = 3
    holiday_tolerances["P02"] = 3
    # Worker P03
    preference_weights["P03"] = {'morning': 1, 'afternoon': 0, 'night': 2}
    night_tolerances["P03"] = 3
    holiday_tolerances["P03"] = 3
    preferred_rest_day["P03"] = 5
    # Worker P04
    preference_weights["P04"] = {'morning': 1, 'afternoon': 1, 'night': 5}
    night_tolerances["P04"] = 0
    holiday_tolerances["P04"] = 3
    # Worker P05
    preference_weights["P05"] = {'morning': 0, 'afternoon': 1, 'night': 3}
    night_tolerances["P05"] = 2
    holiday_tolerances["P05"] = 3
    preferred_rest_day["P05"] = 0
    # Worker P06
    preference_weights["P06"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["P06"] = 3
    holiday_tolerances["P06"] = 3
    # Worker P07
    preference_weights["P07"] = {'morning': 1, 'afternoon': 0, 'night': 2}
    night_tolerances["P07"] = 3
    holiday_tolerances["P07"] = 3
    preferred_rest_day["P07"] = 4

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
            # Almeno 3 lavoratori totali (specializzati possono coprire ruoli standard)
            model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 3)
            # Almeno 1 specializzato sempre presente
            model.Add(sum(shift_vars[(w, d, s)] for w in specialized_workers) >= 1)

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

    # NOTA: Il bilanciamento dei turni notturni è gestito come VINCOLO SOFT
    # tramite le penaltà in preference_weights (generate da preferences_agent.py).
    # Le penaltà sono proporzionali alla night_tolerance di ogni worker:
    # tolerance 0 → night penalty=5, tolerance 5 → night penalty=0.
    # Un vincolo hard causerebbe INFEASIBLE (capacità max < notti richieste).

    # ========== VINCOLI SOFT (OBIETTIVO) ==================================
    # L'obiettivo minimizza la somma pesata delle penalità sulle preferenze.

    penalty_terms = []

    # Penalità per turni non preferiti (da preference_weights)
    for w in all_workers:
        w_prefs = preference_weights.get(w, {})
        for d in range(n_days):
            for s in shifts:
                pen = w_prefs.get(s, 1)  # 0=preferito, 1=neutro, 3=da evitare
                if pen > 0:
                    penalty_terms.append(shift_vars[(w, d, s)] * pen)

    # Penalità giorno di riposo preferito (IMPLEMENTATA NEL TEMPLATE)
    # Per ogni worker con preferred_rest_day, penalizza i turni nel suo giorno preferito
    for w in all_workers:
        prd = preferred_rest_day.get(w)
        if prd is None:
            continue
        for d in range(n_days):
            if date.fromisoformat(days[d]).weekday() == prd:
                for s in shifts:
                    penalty_terms.append(shift_vars[(w, d, s)] * 2)

    # Penalità turni festivi (IMPLEMENTATA NEL TEMPLATE)
    # Festività: 8 Dicembre, 25-26 Dicembre, 1 Gennaio, 6 Gennaio (per Use Case A e B)
    # Penalità = max(0, 5 - holiday_tolerance) -> da evitare fortemente se tolleranza 0
    holiday_dates = {"2026-12-08", "2026-12-25", "2026-12-26", "2027-01-01", "2027-01-06"}
    for w in all_workers:
        htol = holiday_tolerances.get(w, 3)
        hpen = max(0, 5 - htol)
        if hpen > 0:
            for d in range(n_days):
                if days[d] in holiday_dates:
                    for s in shifts:
                        penalty_terms.append(shift_vars[(w, d, s)] * hpen)

    # ========== ASSEGNAZIONI FISSE (PER FIX-AND-OPTIMIZE LNS) =============


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
