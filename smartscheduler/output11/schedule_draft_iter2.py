import json
from ortools.sat.python import cp_model

def solve_schedule():
    model = cp_model.CpModel()
    
    # Parameters
    shifts = ["morning", "afternoon", "night"]
    all_workers = ['W01', 'W02', 'W03', 'W04', 'W05', 'W06', 'W07', 'W08', 'W09', 'W10', 'W11', 'W12', 'W13']
    n_days = 31
    days = ['2026-12-07', '2026-12-08', '2026-12-09', '2026-12-10', '2026-12-11', '2026-12-12', '2026-12-13', '2026-12-14', '2026-12-15', '2026-12-16', '2026-12-17', '2026-12-18', '2026-12-19', '2026-12-20', '2026-12-21', '2026-12-22', '2026-12-23', '2026-12-24', '2026-12-25', '2026-12-26', '2026-12-27', '2026-12-28', '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01', '2027-01-02', '2027-01-03', '2027-01-04', '2027-01-05', '2027-01-06']
    unavailable_dates = {
        "W01": set(),
        "W02": set(),
        "W03": set(),
        "W04": set(),
        "W05": set(),
        "W06": set(),
        "W07": set(),
        "W08": set(),
        "W09": set(),
        "W10": set(),
        "W11": set(),
        "W12": set(),
        "W13": set()
    }
    preferred_rest_day = {
        "W01": 3,
        "W02": 6,
        "W03": 0,
        "W04": 5,
        "W05": 4,
        "W06": 0,
        "W07": 3,
        "W08": 1,
        "W09": 3,
        "W10": 2,
        "W11": 1,
        "W12": 5,
        "W13": 4
    }
    night_tolerances = {
        "W01": 1,
        "W02": 2,
        "W03": 5,
        "W04": 1,
        "W05": 3,
        "W06": 2,
        "W07": 3,
        "W08": 3,
        "W09": 4,
        "W10": 3,
        "W11": 3,
        "W12": 5,
        "W13": 3
    }
    holiday_tolerances = {
        "W01": 3,
        "W02": 4,
        "W03": 0,
        "W04": 3,
        "W05": 3,
        "W06": 3,
        "W07": 3,
        "W08": 5,
        "W09": 5,
        "W10": 3,
        "W11": 3,
        "W12": 3,
        "W13": 3
    }
    preference_weights = {
        "W01": {'morning': 0, 'afternoon': 1, 'night': 4},
        "W02": {'morning': 1, 'afternoon': 1, 'night': 3},
        "W03": {'morning': 1, 'afternoon': 0, 'night': 1},
        "W04": {'morning': 1, 'afternoon': 1, 'night': 4},
        "W05": {'morning': 1, 'afternoon': 1, 'night': 2},
        "W06": {'morning': 0, 'afternoon': 1, 'night': 3},
        "W07": {'morning': 1, 'afternoon': 1, 'night': 2},
        "W08": {'morning': 1, 'afternoon': 0, 'night': 2},
        "W09": {'morning': 0, 'afternoon': 1, 'night': 1},
        "W10": {'morning': 1, 'afternoon': 1, 'night': 2},
        "W11": {'morning': 1, 'afternoon': 1, 'night': 2},
        "W12": {'morning': 0, 'afternoon': 1, 'night': 1},
        "W13": {'morning': 1, 'afternoon': 1, 'night': 2}
    }
    
    # Variables
    shift_vars = {}
    for w in all_workers:
        for d in range(n_days):
            for s in shifts:
                shift_vars[(w, d, s)] = model.NewBoolVar(f"{w}_{d}_{s}")
    
    # Constraints
    for w in all_workers:
        for d in range(n_days):
            model.Add(sum(shift_vars[(w, d, s)] for s in shifts) <= 1)
    
    for w in all_workers:
        for d in range(n_days - 1):
            model.Add(shift_vars[(w, d, "night")] + shift_vars[(w, d+1, "morning")] <= 1)
    
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
    
    for w, unavail_days in unavailable_dates.items():
        for d in unavail_days:
            for s in shifts: 
                model.Add(shift_vars[(w, d, s)] == 0)
    
    # Objective
    objective = model.NewIntVar(0, 1000000, 'objective')
    penalty = sum(shift_vars[(w, d, s)] * preference_weights[w][s] for w in all_workers for d in range(n_days) for s in shifts)
    rest_day_penalty = sum(shift_vars[(w, preferred_rest_day[w], "morning")] + shift_vars[(w, preferred_rest_day[w], "afternoon")] + shift_vars[(w, preferred_rest_day[w], "night")] for w in all_workers)
    holiday_penalty = sum(max(0, 5 - holiday_tolerances[w]) * shift_vars[(w, d, s)] for w in all_workers for d in range(n_days) for s in shifts if days[d] in ["2026-12-08", "2026-12-25", "2026-12-26", "2027-01-01", "2027-01-06"])
    model.Add(objective == penalty + rest_day_penalty + holiday_penalty)
    
    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.Solve(model)
    
    # Output
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        assignments = {w: [] for w in all_workers}
        for w in all_workers:
            for d in range(n_days):
                for s in shifts:
                    if solver.Value(shift_vars[(w, d, s)]) == 1:
                        assignments[w].append({"day_idx": d, "date": days[d], "shift": s})
        print(json.dumps({
            "status": status,
            "objective": solver.ObjectiveValue(),
            "assignments": assignments
        }))
    else:
        print(json.dumps({
            "status": status,
            "objective": None,
            "assignments": {}
        }))

solve_schedule()