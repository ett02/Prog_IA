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
    night_tolerances = {}   # worker_id -> int 0-5 (0=intollerante, 5=molto tollerante)
    holiday_tolerances = {} # worker_id -> int 0-5

    # Worker W01
    preference_weights["W01"] = {'morning': 0, 'afternoon': 1, 'night': 4}
    night_tolerances["W01"] = 1
    holiday_tolerances["W01"] = 3
    unavailable_dates["W01"] = set()
    # Worker W02
    preference_weights["W02"] = {'morning': 1, 'afternoon': 1, 'night': 0}
    night_tolerances["W02"] = 5
    holiday_tolerances["W02"] = 3
    preferred_rest_day["W02"] = 3
    # Worker W03
    preference_weights["W03"] = {'morning': 1, 'afternoon': 0, 'night': 1}
    night_tolerances["W03"] = 5
    holiday_tolerances["W03"] = 0
    # Worker W04
    preference_weights["W04"] = {'morning': 1, 'afternoon': 1, 'night': 4}
    night_tolerances["W04"] = 1
    holiday_tolerances["W04"] = 3
    preferred_rest_day["W04"] = 5
    # Worker W05
    preference_weights["W05"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["W05"] = 3
    holiday_tolerances["W05"] = 3
    # Worker W06
    preference_weights["W06"] = {'morning': 0, 'afternoon': 1, 'night': 3}
    night_tolerances["W06"] = 3
    holiday_tolerances["W06"] = 3
    preferred_rest_day["W06"] = 6
    # Worker W07
    preference_weights["W07"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["W07"] = 3
    holiday_tolerances["W07"] = 3
    # Worker W08
    preference_weights["W08"] = {'morning': 1, 'afternoon': 0, 'night': 3}
    night_tolerances["W08"] = 2
    holiday_tolerances["W08"] = 4
    preferred_rest_day["W08"] = 0
    # Worker W09
    preference_weights["W09"] = {'morning': 0, 'afternoon': 1, 'night': 1}
    night_tolerances["W09"] = 4
    holiday_tolerances["W09"] = 3
    unavailable_dates["W09"] = set()
    # Worker W10
    preference_weights["W10"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["W10"] = 3
    holiday_tolerances["W10"] = 3
    preferred_rest_day["W10"] = 4
    # Worker W11
    preference_weights["W11"] = {'morning': 1, 'afternoon': 1, 'night': 2}
    night_tolerances["W11"] = 3
    holiday_tolerances["W11"] = 3
    # Worker W12
    preference_weights["W12"] = {'morning': 0, 'afternoon': 1, 'night': 1}
    night_tolerances["W12"] = 5
    holiday_tolerances["W12"] = 3
    unavailable_dates["W12"] = set()
    # Worker W13
    preference_weights["W13"] = {'morning': 3, 'afternoon': 1, 'night': 1}
    night_tolerances["W13"] = 3
    holiday_tolerances["W13"] = 3

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
    # Vincoli hard: LNS Freeze
    model.Add(shift_vars[('W09', 0, 'morning')] == 0)
    model.Add(shift_vars[('W09', 0, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 0, 'night')] == 1)
    model.Add(shift_vars[('W09', 1, 'morning')] == 0)
    model.Add(shift_vars[('W09', 1, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 1, 'night')] == 0)
    model.Add(shift_vars[('W09', 2, 'morning')] == 0)
    model.Add(shift_vars[('W09', 2, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 2, 'night')] == 0)
    model.Add(shift_vars[('W09', 3, 'morning')] == 1)
    model.Add(shift_vars[('W09', 3, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 3, 'night')] == 0)
    model.Add(shift_vars[('W09', 4, 'morning')] == 1)
    model.Add(shift_vars[('W09', 4, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 4, 'night')] == 0)
    model.Add(shift_vars[('W09', 5, 'morning')] == 1)
    model.Add(shift_vars[('W09', 5, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 5, 'night')] == 0)
    model.Add(shift_vars[('W09', 6, 'morning')] == 1)
    model.Add(shift_vars[('W09', 6, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 6, 'night')] == 0)
    model.Add(shift_vars[('W09', 7, 'morning')] == 0)
    model.Add(shift_vars[('W09', 7, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 7, 'night')] == 1)
    model.Add(shift_vars[('W09', 8, 'morning')] == 0)
    model.Add(shift_vars[('W09', 8, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 8, 'night')] == 0)
    model.Add(shift_vars[('W09', 9, 'morning')] == 0)
    model.Add(shift_vars[('W09', 9, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 9, 'night')] == 0)
    model.Add(shift_vars[('W09', 10, 'morning')] == 1)
    model.Add(shift_vars[('W09', 10, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 10, 'night')] == 0)
    model.Add(shift_vars[('W09', 11, 'morning')] == 1)
    model.Add(shift_vars[('W09', 11, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 11, 'night')] == 0)
    model.Add(shift_vars[('W09', 12, 'morning')] == 1)
    model.Add(shift_vars[('W09', 12, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 12, 'night')] == 0)
    model.Add(shift_vars[('W09', 13, 'morning')] == 1)
    model.Add(shift_vars[('W09', 13, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 13, 'night')] == 0)
    model.Add(shift_vars[('W09', 14, 'morning')] == 0)
    model.Add(shift_vars[('W09', 14, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 14, 'night')] == 1)
    model.Add(shift_vars[('W09', 15, 'morning')] == 0)
    model.Add(shift_vars[('W09', 15, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 15, 'night')] == 0)
    model.Add(shift_vars[('W09', 16, 'morning')] == 0)
    model.Add(shift_vars[('W09', 16, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 16, 'night')] == 0)
    model.Add(shift_vars[('W09', 17, 'morning')] == 1)
    model.Add(shift_vars[('W09', 17, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 17, 'night')] == 0)
    model.Add(shift_vars[('W09', 18, 'morning')] == 0)
    model.Add(shift_vars[('W09', 18, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 18, 'night')] == 0)
    model.Add(shift_vars[('W09', 19, 'morning')] == 1)
    model.Add(shift_vars[('W09', 19, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 19, 'night')] == 0)
    model.Add(shift_vars[('W09', 20, 'morning')] == 1)
    model.Add(shift_vars[('W09', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 20, 'night')] == 0)
    model.Add(shift_vars[('W09', 21, 'morning')] == 0)
    model.Add(shift_vars[('W09', 21, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 21, 'night')] == 1)
    model.Add(shift_vars[('W09', 22, 'morning')] == 0)
    model.Add(shift_vars[('W09', 22, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 22, 'night')] == 0)
    model.Add(shift_vars[('W09', 23, 'morning')] == 0)
    model.Add(shift_vars[('W09', 23, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 23, 'night')] == 0)
    model.Add(shift_vars[('W09', 24, 'morning')] == 1)
    model.Add(shift_vars[('W09', 24, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 24, 'night')] == 0)
    model.Add(shift_vars[('W09', 25, 'morning')] == 1)
    model.Add(shift_vars[('W09', 25, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 25, 'night')] == 0)
    model.Add(shift_vars[('W09', 26, 'morning')] == 1)
    model.Add(shift_vars[('W09', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 26, 'night')] == 0)
    model.Add(shift_vars[('W09', 27, 'morning')] == 1)
    model.Add(shift_vars[('W09', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 27, 'night')] == 0)
    model.Add(shift_vars[('W09', 28, 'morning')] == 0)
    model.Add(shift_vars[('W09', 28, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 28, 'night')] == 1)
    model.Add(shift_vars[('W09', 29, 'morning')] == 0)
    model.Add(shift_vars[('W09', 29, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 29, 'night')] == 0)
    model.Add(shift_vars[('W09', 30, 'morning')] == 0)
    model.Add(shift_vars[('W09', 30, 'afternoon')] == 0)
    model.Add(shift_vars[('W09', 30, 'night')] == 0)
    model.Add(shift_vars[('W04', 0, 'morning')] == 0)
    model.Add(shift_vars[('W04', 0, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 0, 'night')] == 0)
    model.Add(shift_vars[('W04', 1, 'morning')] == 0)
    model.Add(shift_vars[('W04', 1, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 1, 'night')] == 0)
    model.Add(shift_vars[('W04', 2, 'morning')] == 0)
    model.Add(shift_vars[('W04', 2, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 2, 'night')] == 0)
    model.Add(shift_vars[('W04', 3, 'morning')] == 0)
    model.Add(shift_vars[('W04', 3, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 3, 'night')] == 0)
    model.Add(shift_vars[('W04', 4, 'morning')] == 0)
    model.Add(shift_vars[('W04', 4, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 4, 'night')] == 0)
    model.Add(shift_vars[('W04', 5, 'morning')] == 0)
    model.Add(shift_vars[('W04', 5, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 5, 'night')] == 0)
    model.Add(shift_vars[('W04', 6, 'morning')] == 0)
    model.Add(shift_vars[('W04', 6, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 6, 'night')] == 1)
    model.Add(shift_vars[('W04', 7, 'morning')] == 0)
    model.Add(shift_vars[('W04', 7, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 7, 'night')] == 0)
    model.Add(shift_vars[('W04', 8, 'morning')] == 0)
    model.Add(shift_vars[('W04', 8, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 8, 'night')] == 0)
    model.Add(shift_vars[('W04', 9, 'morning')] == 0)
    model.Add(shift_vars[('W04', 9, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 9, 'night')] == 0)
    model.Add(shift_vars[('W04', 10, 'morning')] == 0)
    model.Add(shift_vars[('W04', 10, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 10, 'night')] == 0)
    model.Add(shift_vars[('W04', 11, 'morning')] == 0)
    model.Add(shift_vars[('W04', 11, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 11, 'night')] == 1)
    model.Add(shift_vars[('W04', 12, 'morning')] == 0)
    model.Add(shift_vars[('W04', 12, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 12, 'night')] == 0)
    model.Add(shift_vars[('W04', 13, 'morning')] == 0)
    model.Add(shift_vars[('W04', 13, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 13, 'night')] == 0)
    model.Add(shift_vars[('W04', 14, 'morning')] == 0)
    model.Add(shift_vars[('W04', 14, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 14, 'night')] == 0)
    model.Add(shift_vars[('W04', 15, 'morning')] == 0)
    model.Add(shift_vars[('W04', 15, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 15, 'night')] == 0)
    model.Add(shift_vars[('W04', 16, 'morning')] == 0)
    model.Add(shift_vars[('W04', 16, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 16, 'night')] == 0)
    model.Add(shift_vars[('W04', 17, 'morning')] == 0)
    model.Add(shift_vars[('W04', 17, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 17, 'night')] == 0)
    model.Add(shift_vars[('W04', 18, 'morning')] == 0)
    model.Add(shift_vars[('W04', 18, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 18, 'night')] == 1)
    model.Add(shift_vars[('W04', 19, 'morning')] == 0)
    model.Add(shift_vars[('W04', 19, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 19, 'night')] == 0)
    model.Add(shift_vars[('W04', 20, 'morning')] == 0)
    model.Add(shift_vars[('W04', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 20, 'night')] == 0)
    model.Add(shift_vars[('W04', 21, 'morning')] == 0)
    model.Add(shift_vars[('W04', 21, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 21, 'night')] == 0)
    model.Add(shift_vars[('W04', 22, 'morning')] == 0)
    model.Add(shift_vars[('W04', 22, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 22, 'night')] == 0)
    model.Add(shift_vars[('W04', 23, 'morning')] == 1)
    model.Add(shift_vars[('W04', 23, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 23, 'night')] == 0)
    model.Add(shift_vars[('W04', 24, 'morning')] == 0)
    model.Add(shift_vars[('W04', 24, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 24, 'night')] == 0)
    model.Add(shift_vars[('W04', 25, 'morning')] == 0)
    model.Add(shift_vars[('W04', 25, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 25, 'night')] == 1)
    model.Add(shift_vars[('W04', 26, 'morning')] == 0)
    model.Add(shift_vars[('W04', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 26, 'night')] == 0)
    model.Add(shift_vars[('W04', 27, 'morning')] == 0)
    model.Add(shift_vars[('W04', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W04', 27, 'night')] == 0)
    model.Add(shift_vars[('W04', 28, 'morning')] == 0)
    model.Add(shift_vars[('W04', 28, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 28, 'night')] == 0)
    model.Add(shift_vars[('W04', 29, 'morning')] == 0)
    model.Add(shift_vars[('W04', 29, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 29, 'night')] == 0)
    model.Add(shift_vars[('W04', 30, 'morning')] == 0)
    model.Add(shift_vars[('W04', 30, 'afternoon')] == 1)
    model.Add(shift_vars[('W04', 30, 'night')] == 0)
    model.Add(shift_vars[('W10', 0, 'morning')] == 0)
    model.Add(shift_vars[('W10', 0, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 0, 'night')] == 0)
    model.Add(shift_vars[('W10', 1, 'morning')] == 1)
    model.Add(shift_vars[('W10', 1, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 1, 'night')] == 0)
    model.Add(shift_vars[('W10', 2, 'morning')] == 0)
    model.Add(shift_vars[('W10', 2, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 2, 'night')] == 1)
    model.Add(shift_vars[('W10', 3, 'morning')] == 0)
    model.Add(shift_vars[('W10', 3, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 3, 'night')] == 0)
    model.Add(shift_vars[('W10', 4, 'morning')] == 0)
    model.Add(shift_vars[('W10', 4, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 4, 'night')] == 0)
    model.Add(shift_vars[('W10', 5, 'morning')] == 0)
    model.Add(shift_vars[('W10', 5, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 5, 'night')] == 0)
    model.Add(shift_vars[('W10', 6, 'morning')] == 0)
    model.Add(shift_vars[('W10', 6, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 6, 'night')] == 0)
    model.Add(shift_vars[('W10', 7, 'morning')] == 1)
    model.Add(shift_vars[('W10', 7, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 7, 'night')] == 0)
    model.Add(shift_vars[('W10', 8, 'morning')] == 0)
    model.Add(shift_vars[('W10', 8, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 8, 'night')] == 0)
    model.Add(shift_vars[('W10', 9, 'morning')] == 0)
    model.Add(shift_vars[('W10', 9, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 9, 'night')] == 1)
    model.Add(shift_vars[('W10', 10, 'morning')] == 0)
    model.Add(shift_vars[('W10', 10, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 10, 'night')] == 0)
    model.Add(shift_vars[('W10', 11, 'morning')] == 0)
    model.Add(shift_vars[('W10', 11, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 11, 'night')] == 0)
    model.Add(shift_vars[('W10', 12, 'morning')] == 1)
    model.Add(shift_vars[('W10', 12, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 12, 'night')] == 0)
    model.Add(shift_vars[('W10', 13, 'morning')] == 0)
    model.Add(shift_vars[('W10', 13, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 13, 'night')] == 0)
    model.Add(shift_vars[('W10', 14, 'morning')] == 0)
    model.Add(shift_vars[('W10', 14, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 14, 'night')] == 0)
    model.Add(shift_vars[('W10', 15, 'morning')] == 0)
    model.Add(shift_vars[('W10', 15, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 15, 'night')] == 0)
    model.Add(shift_vars[('W10', 16, 'morning')] == 0)
    model.Add(shift_vars[('W10', 16, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 16, 'night')] == 1)
    model.Add(shift_vars[('W10', 17, 'morning')] == 0)
    model.Add(shift_vars[('W10', 17, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 17, 'night')] == 0)
    model.Add(shift_vars[('W10', 18, 'morning')] == 0)
    model.Add(shift_vars[('W10', 18, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 18, 'night')] == 0)
    model.Add(shift_vars[('W10', 19, 'morning')] == 0)
    model.Add(shift_vars[('W10', 19, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 19, 'night')] == 0)
    model.Add(shift_vars[('W10', 20, 'morning')] == 0)
    model.Add(shift_vars[('W10', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 20, 'night')] == 1)
    model.Add(shift_vars[('W10', 21, 'morning')] == 0)
    model.Add(shift_vars[('W10', 21, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 21, 'night')] == 0)
    model.Add(shift_vars[('W10', 22, 'morning')] == 0)
    model.Add(shift_vars[('W10', 22, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 22, 'night')] == 0)
    model.Add(shift_vars[('W10', 23, 'morning')] == 0)
    model.Add(shift_vars[('W10', 23, 'afternoon')] == 1)
    model.Add(shift_vars[('W10', 23, 'night')] == 0)
    model.Add(shift_vars[('W10', 24, 'morning')] == 0)
    model.Add(shift_vars[('W10', 24, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 24, 'night')] == 1)
    model.Add(shift_vars[('W10', 25, 'morning')] == 0)
    model.Add(shift_vars[('W10', 25, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 25, 'night')] == 0)
    model.Add(shift_vars[('W10', 26, 'morning')] == 0)
    model.Add(shift_vars[('W10', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 26, 'night')] == 0)
    model.Add(shift_vars[('W10', 27, 'morning')] == 0)
    model.Add(shift_vars[('W10', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 27, 'night')] == 1)
    model.Add(shift_vars[('W10', 28, 'morning')] == 0)
    model.Add(shift_vars[('W10', 28, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 28, 'night')] == 0)
    model.Add(shift_vars[('W10', 29, 'morning')] == 0)
    model.Add(shift_vars[('W10', 29, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 29, 'night')] == 0)
    model.Add(shift_vars[('W10', 30, 'morning')] == 0)
    model.Add(shift_vars[('W10', 30, 'afternoon')] == 0)
    model.Add(shift_vars[('W10', 30, 'night')] == 1)
    model.Add(shift_vars[('W05', 0, 'morning')] == 0)
    model.Add(shift_vars[('W05', 0, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 0, 'night')] == 0)
    model.Add(shift_vars[('W05', 1, 'morning')] == 0)
    model.Add(shift_vars[('W05', 1, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 1, 'night')] == 1)
    model.Add(shift_vars[('W05', 2, 'morning')] == 0)
    model.Add(shift_vars[('W05', 2, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 2, 'night')] == 0)
    model.Add(shift_vars[('W05', 3, 'morning')] == 0)
    model.Add(shift_vars[('W05', 3, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 3, 'night')] == 0)
    model.Add(shift_vars[('W05', 4, 'morning')] == 1)
    model.Add(shift_vars[('W05', 4, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 4, 'night')] == 0)
    model.Add(shift_vars[('W05', 5, 'morning')] == 1)
    model.Add(shift_vars[('W05', 5, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 5, 'night')] == 0)
    model.Add(shift_vars[('W05', 6, 'morning')] == 0)
    model.Add(shift_vars[('W05', 6, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 6, 'night')] == 0)
    model.Add(shift_vars[('W05', 7, 'morning')] == 0)
    model.Add(shift_vars[('W05', 7, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 7, 'night')] == 0)
    model.Add(shift_vars[('W05', 8, 'morning')] == 0)
    model.Add(shift_vars[('W05', 8, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 8, 'night')] == 1)
    model.Add(shift_vars[('W05', 9, 'morning')] == 0)
    model.Add(shift_vars[('W05', 9, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 9, 'night')] == 0)
    model.Add(shift_vars[('W05', 10, 'morning')] == 0)
    model.Add(shift_vars[('W05', 10, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 10, 'night')] == 0)
    model.Add(shift_vars[('W05', 11, 'morning')] == 0)
    model.Add(shift_vars[('W05', 11, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 11, 'night')] == 0)
    model.Add(shift_vars[('W05', 12, 'morning')] == 0)
    model.Add(shift_vars[('W05', 12, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 12, 'night')] == 0)
    model.Add(shift_vars[('W05', 13, 'morning')] == 0)
    model.Add(shift_vars[('W05', 13, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 13, 'night')] == 0)
    model.Add(shift_vars[('W05', 14, 'morning')] == 0)
    model.Add(shift_vars[('W05', 14, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 14, 'night')] == 0)
    model.Add(shift_vars[('W05', 15, 'morning')] == 0)
    model.Add(shift_vars[('W05', 15, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 15, 'night')] == 1)
    model.Add(shift_vars[('W05', 16, 'morning')] == 0)
    model.Add(shift_vars[('W05', 16, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 16, 'night')] == 0)
    model.Add(shift_vars[('W05', 17, 'morning')] == 0)
    model.Add(shift_vars[('W05', 17, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 17, 'night')] == 0)
    model.Add(shift_vars[('W05', 18, 'morning')] == 0)
    model.Add(shift_vars[('W05', 18, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 18, 'night')] == 0)
    model.Add(shift_vars[('W05', 19, 'morning')] == 0)
    model.Add(shift_vars[('W05', 19, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 19, 'night')] == 0)
    model.Add(shift_vars[('W05', 20, 'morning')] == 1)
    model.Add(shift_vars[('W05', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 20, 'night')] == 0)
    model.Add(shift_vars[('W05', 21, 'morning')] == 0)
    model.Add(shift_vars[('W05', 21, 'afternoon')] == 1)
    model.Add(shift_vars[('W05', 21, 'night')] == 0)
    model.Add(shift_vars[('W05', 22, 'morning')] == 0)
    model.Add(shift_vars[('W05', 22, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 22, 'night')] == 1)
    model.Add(shift_vars[('W05', 23, 'morning')] == 0)
    model.Add(shift_vars[('W05', 23, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 23, 'night')] == 0)
    model.Add(shift_vars[('W05', 24, 'morning')] == 0)
    model.Add(shift_vars[('W05', 24, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 24, 'night')] == 0)
    model.Add(shift_vars[('W05', 25, 'morning')] == 0)
    model.Add(shift_vars[('W05', 25, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 25, 'night')] == 0)
    model.Add(shift_vars[('W05', 26, 'morning')] == 0)
    model.Add(shift_vars[('W05', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 26, 'night')] == 1)
    model.Add(shift_vars[('W05', 27, 'morning')] == 0)
    model.Add(shift_vars[('W05', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 27, 'night')] == 0)
    model.Add(shift_vars[('W05', 28, 'morning')] == 0)
    model.Add(shift_vars[('W05', 28, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 28, 'night')] == 0)
    model.Add(shift_vars[('W05', 29, 'morning')] == 0)
    model.Add(shift_vars[('W05', 29, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 29, 'night')] == 1)
    model.Add(shift_vars[('W05', 30, 'morning')] == 0)
    model.Add(shift_vars[('W05', 30, 'afternoon')] == 0)
    model.Add(shift_vars[('W05', 30, 'night')] == 0)
    model.Add(shift_vars[('W11', 0, 'morning')] == 0)
    model.Add(shift_vars[('W11', 0, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 0, 'night')] == 0)
    model.Add(shift_vars[('W11', 1, 'morning')] == 0)
    model.Add(shift_vars[('W11', 1, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 1, 'night')] == 0)
    model.Add(shift_vars[('W11', 2, 'morning')] == 0)
    model.Add(shift_vars[('W11', 2, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 2, 'night')] == 0)
    model.Add(shift_vars[('W11', 3, 'morning')] == 0)
    model.Add(shift_vars[('W11', 3, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 3, 'night')] == 1)
    model.Add(shift_vars[('W11', 4, 'morning')] == 0)
    model.Add(shift_vars[('W11', 4, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 4, 'night')] == 0)
    model.Add(shift_vars[('W11', 5, 'morning')] == 0)
    model.Add(shift_vars[('W11', 5, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 5, 'night')] == 0)
    model.Add(shift_vars[('W11', 6, 'morning')] == 0)
    model.Add(shift_vars[('W11', 6, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 6, 'night')] == 0)
    model.Add(shift_vars[('W11', 7, 'morning')] == 0)
    model.Add(shift_vars[('W11', 7, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 7, 'night')] == 0)
    model.Add(shift_vars[('W11', 8, 'morning')] == 1)
    model.Add(shift_vars[('W11', 8, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 8, 'night')] == 0)
    model.Add(shift_vars[('W11', 9, 'morning')] == 0)
    model.Add(shift_vars[('W11', 9, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 9, 'night')] == 0)
    model.Add(shift_vars[('W11', 10, 'morning')] == 0)
    model.Add(shift_vars[('W11', 10, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 10, 'night')] == 1)
    model.Add(shift_vars[('W11', 11, 'morning')] == 0)
    model.Add(shift_vars[('W11', 11, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 11, 'night')] == 0)
    model.Add(shift_vars[('W11', 12, 'morning')] == 0)
    model.Add(shift_vars[('W11', 12, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 12, 'night')] == 0)
    model.Add(shift_vars[('W11', 13, 'morning')] == 0)
    model.Add(shift_vars[('W11', 13, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 13, 'night')] == 0)
    model.Add(shift_vars[('W11', 14, 'morning')] == 0)
    model.Add(shift_vars[('W11', 14, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 14, 'night')] == 0)
    model.Add(shift_vars[('W11', 15, 'morning')] == 1)
    model.Add(shift_vars[('W11', 15, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 15, 'night')] == 0)
    model.Add(shift_vars[('W11', 16, 'morning')] == 0)
    model.Add(shift_vars[('W11', 16, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 16, 'night')] == 0)
    model.Add(shift_vars[('W11', 17, 'morning')] == 0)
    model.Add(shift_vars[('W11', 17, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 17, 'night')] == 1)
    model.Add(shift_vars[('W11', 18, 'morning')] == 0)
    model.Add(shift_vars[('W11', 18, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 18, 'night')] == 0)
    model.Add(shift_vars[('W11', 19, 'morning')] == 0)
    model.Add(shift_vars[('W11', 19, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 19, 'night')] == 0)
    model.Add(shift_vars[('W11', 20, 'morning')] == 0)
    model.Add(shift_vars[('W11', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 20, 'night')] == 1)
    model.Add(shift_vars[('W11', 21, 'morning')] == 0)
    model.Add(shift_vars[('W11', 21, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 21, 'night')] == 0)
    model.Add(shift_vars[('W11', 22, 'morning')] == 0)
    model.Add(shift_vars[('W11', 22, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 22, 'night')] == 0)
    model.Add(shift_vars[('W11', 23, 'morning')] == 0)
    model.Add(shift_vars[('W11', 23, 'afternoon')] == 1)
    model.Add(shift_vars[('W11', 23, 'night')] == 0)
    model.Add(shift_vars[('W11', 24, 'morning')] == 0)
    model.Add(shift_vars[('W11', 24, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 24, 'night')] == 1)
    model.Add(shift_vars[('W11', 25, 'morning')] == 0)
    model.Add(shift_vars[('W11', 25, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 25, 'night')] == 0)
    model.Add(shift_vars[('W11', 26, 'morning')] == 0)
    model.Add(shift_vars[('W11', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 26, 'night')] == 0)
    model.Add(shift_vars[('W11', 27, 'morning')] == 0)
    model.Add(shift_vars[('W11', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 27, 'night')] == 1)
    model.Add(shift_vars[('W11', 28, 'morning')] == 0)
    model.Add(shift_vars[('W11', 28, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 28, 'night')] == 0)
    model.Add(shift_vars[('W11', 29, 'morning')] == 0)
    model.Add(shift_vars[('W11', 29, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 29, 'night')] == 0)
    model.Add(shift_vars[('W11', 30, 'morning')] == 0)
    model.Add(shift_vars[('W11', 30, 'afternoon')] == 0)
    model.Add(shift_vars[('W11', 30, 'night')] == 1)
    model.Add(shift_vars[('W07', 0, 'morning')] == 0)
    model.Add(shift_vars[('W07', 0, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 0, 'night')] == 1)
    model.Add(shift_vars[('W07', 1, 'morning')] == 0)
    model.Add(shift_vars[('W07', 1, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 1, 'night')] == 0)
    model.Add(shift_vars[('W07', 2, 'morning')] == 0)
    model.Add(shift_vars[('W07', 2, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 2, 'night')] == 0)
    model.Add(shift_vars[('W07', 3, 'morning')] == 0)
    model.Add(shift_vars[('W07', 3, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 3, 'night')] == 0)
    model.Add(shift_vars[('W07', 4, 'morning')] == 0)
    model.Add(shift_vars[('W07', 4, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 4, 'night')] == 1)
    model.Add(shift_vars[('W07', 5, 'morning')] == 0)
    model.Add(shift_vars[('W07', 5, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 5, 'night')] == 0)
    model.Add(shift_vars[('W07', 6, 'morning')] == 0)
    model.Add(shift_vars[('W07', 6, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 6, 'night')] == 0)
    model.Add(shift_vars[('W07', 7, 'morning')] == 0)
    model.Add(shift_vars[('W07', 7, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 7, 'night')] == 0)
    model.Add(shift_vars[('W07', 8, 'morning')] == 0)
    model.Add(shift_vars[('W07', 8, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 8, 'night')] == 0)
    model.Add(shift_vars[('W07', 9, 'morning')] == 1)
    model.Add(shift_vars[('W07', 9, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 9, 'night')] == 0)
    model.Add(shift_vars[('W07', 10, 'morning')] == 0)
    model.Add(shift_vars[('W07', 10, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 10, 'night')] == 0)
    model.Add(shift_vars[('W07', 11, 'morning')] == 0)
    model.Add(shift_vars[('W07', 11, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 11, 'night')] == 1)
    model.Add(shift_vars[('W07', 12, 'morning')] == 0)
    model.Add(shift_vars[('W07', 12, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 12, 'night')] == 0)
    model.Add(shift_vars[('W07', 13, 'morning')] == 0)
    model.Add(shift_vars[('W07', 13, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 13, 'night')] == 0)
    model.Add(shift_vars[('W07', 14, 'morning')] == 1)
    model.Add(shift_vars[('W07', 14, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 14, 'night')] == 0)
    model.Add(shift_vars[('W07', 15, 'morning')] == 1)
    model.Add(shift_vars[('W07', 15, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 15, 'night')] == 0)
    model.Add(shift_vars[('W07', 16, 'morning')] == 0)
    model.Add(shift_vars[('W07', 16, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 16, 'night')] == 0)
    model.Add(shift_vars[('W07', 17, 'morning')] == 0)
    model.Add(shift_vars[('W07', 17, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 17, 'night')] == 0)
    model.Add(shift_vars[('W07', 18, 'morning')] == 0)
    model.Add(shift_vars[('W07', 18, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 18, 'night')] == 0)
    model.Add(shift_vars[('W07', 19, 'morning')] == 0)
    model.Add(shift_vars[('W07', 19, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 19, 'night')] == 1)
    model.Add(shift_vars[('W07', 20, 'morning')] == 0)
    model.Add(shift_vars[('W07', 20, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 20, 'night')] == 0)
    model.Add(shift_vars[('W07', 21, 'morning')] == 0)
    model.Add(shift_vars[('W07', 21, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 21, 'night')] == 0)
    model.Add(shift_vars[('W07', 22, 'morning')] == 0)
    model.Add(shift_vars[('W07', 22, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 22, 'night')] == 1)
    model.Add(shift_vars[('W07', 23, 'morning')] == 0)
    model.Add(shift_vars[('W07', 23, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 23, 'night')] == 0)
    model.Add(shift_vars[('W07', 24, 'morning')] == 0)
    model.Add(shift_vars[('W07', 24, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 24, 'night')] == 0)
    model.Add(shift_vars[('W07', 25, 'morning')] == 0)
    model.Add(shift_vars[('W07', 25, 'afternoon')] == 1)
    model.Add(shift_vars[('W07', 25, 'night')] == 0)
    model.Add(shift_vars[('W07', 26, 'morning')] == 0)
    model.Add(shift_vars[('W07', 26, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 26, 'night')] == 1)
    model.Add(shift_vars[('W07', 27, 'morning')] == 0)
    model.Add(shift_vars[('W07', 27, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 27, 'night')] == 0)
    model.Add(shift_vars[('W07', 28, 'morning')] == 0)
    model.Add(shift_vars[('W07', 28, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 28, 'night')] == 0)
    model.Add(shift_vars[('W07', 29, 'morning')] == 1)
    model.Add(shift_vars[('W07', 29, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 29, 'night')] == 0)
    model.Add(shift_vars[('W07', 30, 'morning')] == 0)
    model.Add(shift_vars[('W07', 30, 'afternoon')] == 0)
    model.Add(shift_vars[('W07', 30, 'night')] == 1)

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
