import json
from ortools.sat.python import cp_model

def solve_schedule():
    model = cp_model.CpModel()
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
    
    # Hard constraints
    for w in all_workers:
        for d in range(n_days):
            model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)
    
    for w in all_workers:
        for d in range(n_days - 1):
            model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)
    
    unavailable_dates = {
        'W01': set(),
        'W02': set([3]),
        'W03': set([5]),
        'W04': set([7]),
        'W05': set([9]),
        'W06': set([11]),
        'W07': set([13]),
        'W08': set([15]),
        'W09': set(),
        'W10': set([17]),
        'W11': set([19]),
        'W12': set([21]),
        'W13': set([23])
    }
    
    for w, unavail_days in unavailable_dates.items():
        for d in unavail_days:
            for s in shifts: model.Add(shift_vars[(w, d, s)] == 0)
    
    for w in all_workers:
        for d in range(n_days):
            if d+1 < n_days:
                model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+1, s)] for s in shifts) <= 1)
            if d+2 < n_days:
                model.Add(shift_vars[(w, d, "night")] + sum(shift_vars[(w, d+2, s)] for s in shifts) <= 1)
    
    shift_hours = {"morning": 6, "afternoon": 6, "night": 12}
    for w in all_workers:
        for start in range(n_days - 7 + 1):
            window = range(start, start + 7)
            model.Add(sum(shift_vars[(w, d, s)] * shift_hours[s] for d in window for s in shifts) <= 36)
    
    shift_units = {"morning": 1, "afternoon": 1, "night": 2}
    for w in all_workers:
        model.Add(sum(shift_vars[(w, d, s)] * shift_units[s] for d in range(n_days) for s in shifts) == 25)
    
    # Soft constraints
    preference_weights = {
        'W01': {'morning': 0, 'afternoon': 1, 'night': 4},
        'W02': {'morning': 1, 'afternoon': 1, 'night': 3},
        'W03': {'morning': 1, 'afternoon': 0, 'night': 1},
        'W04': {'morning': 1, 'afternoon': 1, 'night': 4},
        'W05': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W06': {'morning': 0, 'afternoon': 1, 'night': 3},
        'W07': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W08': {'morning': 1, 'afternoon': 0, 'night': 2},
        'W09': {'morning': 0, 'afternoon': 1, 'night': 1},
        'W10': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W11': {'morning': 1, 'afternoon': 1, 'night': 2},
        'W12': {'morning': 0, 'afternoon': 1, 'night': 1},
        'W13': {'morning': 1, 'afternoon': 1, 'night': 2}
    }
    
    night_tolerances = {
        'W01': 1,
        'W02': 2,
        'W03': 5,
        'W04': 1,
        'W05': 3,
        'W06': 2,
        'W07': 3,
        'W08': 3,
        'W09': 4,
        'W10': 3,
        'W11': 3,
        'W12': 5,
        'W13': 3
    }
    
    holiday_tolerances = {
        'W01': 3,
        'W02': 4,
        'W03': 0,
        'W04': 3,
        'W05': 3,
        'W06': 3,
        'W07': 3,
        'W08': 5,
        'W09': 5,
        'W10': 3,
        'W11': 3,
        'W12': 3,
        'W13': 3
    }
    
    preferred_rest_day = {
        'W02': 3,
        'W04': 5,
        'W06': 6,
        'W08': 0
    }
    
    penalty_preference = sum(shift_vars[(w, d, s)] * preference_weights[w][s] for w in all_workers for d in range(n_days) for s in shifts)
    penalty_rest_day = sum(shift_vars[(w, d, s)] * (d == preferred_rest_day.get(w, -1)) * 2 for w in all_workers for d in range(n_days) for s in shifts)
    holiday_dates = ['2026-12-08', '2026-12-25', '2026-12-26', '2027-01-01', '2027-01-06']
    penalty_holiday = sum(shift_vars[(w, d, s)] * max(0, 5 - holiday_tolerances[w]) for w in all_workers for d in range(n_days) if days[d] in holiday_dates for s in shifts)
    
    model.Minimize(penalty_preference + penalty_rest_day + penalty_holiday)
    
    solver = cp_model.CpSolver()
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
        "status": status,
        "objective": solver.ObjectiveValue(),
        "assignments": assignments
    }
    
    print(json.dumps(result))

solve_schedule()