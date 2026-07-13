import json
from ortools.sat.python import cp_model

def solve_schedule():
    model = cp_model.CpModel()
    solver = cp_model.CpSolver()

    n_days = 31
    shifts = ["morning", "afternoon", "night"]
    all_workers = ['W01', 'W02', 'W03', 'W04', 'W05', 'W06', 'W07', 'W08', 'W09', 'W10', 'W11', 'W12', 'W13']
    standard_workers = all_workers
    specialized_workers = []

    shift_vars = {}
    for w in all_workers:
        for d in range(n_days):
            for s in shifts:
                shift_vars[(w, d, s)] = model.NewBoolVar(f'{w}_{d}_{s}')

    # HARD CONSTRAINTS
    # Copertura: almeno 2 lavoratori per ogni turno di ogni giorno
    for d in range(n_days):
        for s in shifts:
            model.Add(sum(shift_vars[(w, d, s)] for w in all_workers) >= 2)

    # Max 1 turno al giorno per lavoratore
    for w in all_workers:
        for d in range(n_days):
            model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)

    # No turni consecutivi notte-mattino
    for w in all_workers:
        for d in range(n_days - 1):
            model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)

    # Indisponibilità assoluta
    unavailable_dates = {
        'W01': {8},
        'W02': {25, 26},
        'W03': {25, 26},
        'W04': {25, 26},
        'W05': {25, 26},
        'W06': {25, 26},
        'W07': {25, 26},
        'W08': {25, 26},
        'W09': {8},
        'W10': {25, 26},
        'W11': set(),
        'W12': {8},
        'W13': {25, 26}
    }
    for w, unavail_days in unavailable_dates.items():
        for d in unavail_days:
            for s in shifts: model.Add(shift_vars[(w, d, s)] == 0)

    # 2 giorni liberi obbligatori dopo ogni turno notturno
    for w in all_workers:
        for d in range(n_days):
            if d+1 < n_days:
                model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+1, s)] for s in shifts) <= 1)
            if d+2 < n_days:
                model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+2, s)] for s in shifts) <= 1)

    # Max 36 ore in qualsiasi finestra scorrevole di 7 giorni
    shift_hours = {"morning": 6, "afternoon": 6, "night": 12}
    for w in all_workers:
        for start in range(n_days - 7 + 1):
            window = range(start, start + 7)
            model.Add(sum(shift_vars[(w, d, s)] * shift_hours[s] for d in window for s in shifts) <= 36)

    # Esattamente 25 shift-units per lavoratore nel mese
    shift_units = {"morning": 1, "afternoon": 1, "night": 2}
    for w in all_workers:
        model.Add(sum(shift_vars[(w, d, s)] * shift_units[s] for d in range(n_days) for s in shifts) == 25)

    # PREFERENZE DEI LAVORATORI
    preference_weights = {
        'W01': {'morning': 0, 'afternoon': 1, 'night': 4},
        'W02': {'morning': 1, 'afternoon': 1, 'night': 0},
        'W03': {'morning': 1, 'afternoon': 0, 'night': 1},
        'W04': {'morning': 1, 'afternoon': 1, 'night': 4},
        'W05': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W06': {'morning': 0, 'afternoon': 1, 'night': 3},
        'W07': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W08': {'morning': 1, 'afternoon': 0, 'night': 3},
        'W09': {'morning': 0, 'afternoon': 1, 'night': 1},
        'W10': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W11': {'morning': 0, 'afternoon': 0, 'night': 0},
        'W12': {'morning': 0, 'afternoon': 1, 'night': 4},
        'W13': {'morning': 1, 'afternoon': 1, 'night': 2}
    }
    night_tolerances = {
        'W01': 1,
        'W02': 5,
        'W03': 5,
        'W04': 1,
        'W05': 3,
        'W06': 2,
        'W07': 3,
        'W08': 2,
        'W09': 4,
        'W10': 3,
        'W11': 5,
        'W12': 1,
        'W13': 3
    }
    holiday_tolerances = {
        'W01': 3,
        'W02': 3,
        'W03': 0,
        'W04': 3,
        'W05': 3,
        'W06': 3,
        'W07': 3,
        'W08': 4,
        'W09': 3,
        'W10': 3,
        'W11': 5,
        'W12': 3,
        'W13': 3
    }
    preferred_rest_day = {
        'W02': 3,
        'W04': 5,
        'W06': 6,
        'W08': 0,
        'W10': 4
    }

    # Penalità per turni non preferiti
    penalty_non_preferred_shifts = sum(shift_vars[(w, d, s)] * preference_weights[w][s] for w in all_workers for d in range(n_days) for s in shifts)

    # Penalità giorno di riposo preferito
    penalty_preferred_rest_day = sum(shift_vars[(w, preferred_rest_day[w], "morning")] + shift_vars[(w, preferred_rest_day[w], "afternoon")] + shift_vars[(w, preferred_rest_day[w], "night")] for w in all_workers if preferred_rest_day.get(w) is not None)

    # Penalità turni festivi
    holidays = ['2026-12-08', '2026-12-25', '2026-12-26', '2027-01-01', '2027-01-06']
    penalty_holidays = sum(max(0, 5 - holiday_tolerances[w]) * shift_vars[(w, d, s)] for w in all_workers for d in range(n_days) if days[d] in holidays for s in shifts)

    # Obiettivo
    model.Minimize(penalty_non_preferred_shifts + penalty_preferred_rest_day + penalty_holidays)

    solver.parameters.max_time_in_seconds = 30

    status = solver.Solve(model)
    assignments = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for w in all_workers:
            assignments[w] = []
            for d in range(n_days):
                for s in shifts:
                    if solver.Value(shift_vars[(w, d, s)]):
                        assignments[w].append({"day_idx": d, "date": days[d], "shift": s})

    result = {
        "status": status.name,
        "objective": solver.ObjectiveValue(),
        "assignments": assignments
    }

    print(json.dumps(result))

solve_schedule()