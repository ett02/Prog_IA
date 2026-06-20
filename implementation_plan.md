# SmartScheduler — Piano di Implementazione Dettagliato

> **Decisioni fissate**: LLM via **Ollama** (modello da definire) · 25 shift-units = vincolo **hard esatto** · Ore settimanali = **finestra scorrevole 7 giorni**

## Descrizione del Problema

SmartScheduler è un framework agentico multi-stage per la pianificazione equa e constraint-aware dei turni ospedalieri. Combina:
- **LLM** (via LangGraph) per ragionamento in linguaggio naturale e generazione del codice OR-Tools
- **OR-Tools CP-SAT** come solver simbolico per la verifica formale e la risoluzione
- **Fairness verification** simbolica per identificare i lavoratori più svantaggiati e guidare il raffinamento

Il sistema opera su un orizzonte di **31 giorni** (7 dicembre 2026 – 6 gennaio 2027) e deve gestire due scenari distinti.

---

## Analisi Approfondita della Traccia

### Orizzonte Temporale e Struttura Turni

| Turno | Ore | Durata | Peso (shift-count) |
|-------|-----|--------|--------------------|
| Mattino | 08:00–14:00 | 6h | 1 |
| Pomeriggio | 14:00–20:00 | 6h | 1 |
| Notte | 20:00–08:00 (+1g) | 12h | 2 (doppio) |

- **31 giorni**, **3 turni/giorno** → **93 slot totali**
- Ogni lavoratore deve coprire **25 turni nel mese** (dove un turno notturno conta come 2)
- Max **36 ore/settimana** → max **~6 turni singoli/settimana** o **~3 notturni**

### Vincoli Hard (Use Case A e B)

| Vincolo | Tipo | Dettaglio |
|---------|------|----------|
| Copertura minima | Hard | ≥ 2 per turno (UC-A); ≥ 3 totali + ≥ 1 spec. (UC-B) |
| Max 1 turno/giorno | Hard | Un lavoratore non può coprire 2 turni nello stesso giorno |
| No turni consecutivi | Hard | notte[d] + mattino[d+1] ≤ 1 (già coperto da riposo post-notte, mantenuto per chiarezza) |
| Riposo post-notte | Hard | 2 giorni liberi obbligatori dopo ogni turno notturno |
| Ore settimanali | Hard | ≤ 36 ore in qualsiasi finestra scorrevole di 7 giorni |
| 25 shift-units/mese | Hard | Ogni lavoratore copre esattamente 25 "shift-units" (notte = 2) |
| Giorno di riposo preferito | **Soft** | I giorni liberi sono garantiti dai vincoli precedenti; il giorno *preferito* è penalità soft |

### Use Case A vs B

| Aspetto | Use Case A | Use Case B |
|---------|-----------|-----------|
| Lavoratori | 13 omogenei | 13 standard + 7 specializzati (20 tot.) |
| Copertura | ≥ 2 qualsiasi | ≥ 3 totali per turno, di cui ≥ 1 specializzato |
| Flessibilità | N/A (tutti omogenei) | ✓ Specializzati possono coprire ruoli standard |

### Preferenze Soft dei Lavoratori

- Turni preferiti (mattino/pomeriggio/notte)
- Vincoli di disponibilità
- Tolleranza verso turni indesiderabili (notte, festivi, consecutivi impegnativi)
- Giorno di riposo preferito

---

## Stack Tecnologico

| Layer | Tecnologia |
|-------|-----------|
| Orchestrazione | **LangGraph** (StateGraph ciclico) |
| LLM | **Ollama** via HTTP API (`http://localhost:11434/api/chat`) o libreria `ollama` Python |
| Modello LLM | Da definire (es. `llama3.2`, `mistral`, `qwen2.5-coder`) — parametro in `config.py` |
| Solver simbolico | **Google OR-Tools CP-SAT** (`ortools`) |
| Modello dati | **Pydantic v2** |
| Serializzazione | JSON (stato intermedio), Python file (codice OR-Tools) |
| Esecuzione codice LLM | `subprocess` con timeout + cattura stdout/stderr (sandbox leggera) |
| Logging | Python `logging` + file di log per ogni run |
| Entry point | Script CLI `main.py` |

### Integrazione Ollama

```python
# agents/base_llm.py
import ollama

def call_llm(prompt: str, model: str = "llama3.2") -> str:
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]
```

### Esecuzione Sicura Codice OR-Tools Generato

```python
# solver/ortools_runner.py
import subprocess, json, tempfile, os

def run_ortools_code(code: str, timeout: int = 60) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return {"error": result.stderr}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "TIMEOUT"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON_PARSE_ERROR: {e}"}
    finally:
        os.unlink(tmp_path)
```

---

## Struttura del Progetto

```
smartscheduler/
│
├── main.py                        # Entry point CLI
├── config.py                      # Configurazione globale (LLM, parametri)
├── requirements.txt
│
├── data/
│   ├── input_model.txt            # Modello di input (shifts, workers, hard constraints)
│   └── scenarios/
│       ├── use_case_a.txt
│       └── use_case_b.txt
│
├── models/
│   ├── worker.py                  # Pydantic: Worker, WorkerType, Preference
│   ├── schedule.py                # Pydantic: Schedule, ShiftAssignment
│   ├── constraints.py             # Pydantic: HardConstraint, SoftConstraint
│   └── state.py                  # LangGraph State TypedDict
│
├── agents/
│   ├── preferences_agent.py       # Stage 1: NL → Preferenze formalizzate
│   ├── drafting_agent.py          # Stage 2 & 4: Genera/Raffina schedule OR-Tools
│   ├── verification_agent.py      # Stage 3a: Verifica hard constraints (simbolica)
│   └── fairness_agent.py          # Stage 3b: Calcola fairness metrics (simbolica)
│
├── solver/
│   ├── ortools_builder.py         # Costruisce il CpModel da Schedule + Constraints
│   ├── ortools_runner.py          # Esegue il solver, ritorna risultati
│   └── fairness_metrics.py        # Calcola satisfaction scores e fairness gap
│
├── graph/
│   └── smartscheduler_graph.py    # Definizione LangGraph StateGraph
│
├── prompts/
│   ├── preferences_prompt.py      # Prompt per preferences agent
│   ├── drafting_prompt.py         # Prompt per drafting agent
│   └── refinement_prompt.py       # Prompt per refinement agent
│
├── output/
│   └── (generato a runtime)
│       ├── schedule_draft.py      # File OR-Tools generato dall'LLM
│       ├── schedule_final.json    # Schedule finale verificato
│       └── report.txt            # Report leggibile
│
└── tests/
    ├── test_constraints.py
    ├── test_fairness.py
    └── test_pipeline.py
```

---

## Modello Dati (Pydantic)

### `models/worker.py`
```python
class WorkerType(str, Enum):
    STANDARD = "standard"
    SPECIALIZED = "specialized"

class ShiftPreference(BaseModel):
    shift_type: Literal["morning", "afternoon", "night"]
    priority: int  # 1=must, 2=prefer, 3=tolerate, 4=avoid

class Preference(BaseModel):
    preferred_shifts: list[ShiftPreference]
    unavailable_dates: list[date]
    preferred_rest_day: Optional[int]  # day-of-week 0=Mon..6=Sun
    night_tolerance: int   # 0-5
    holiday_tolerance: int # 0-5
    consecutive_tolerance: int # 0-5

class Worker(BaseModel):
    id: str
    name: str
    worker_type: WorkerType = WorkerType.STANDARD
    preference: Optional[Preference] = None
    satisfaction_score: float = 0.0
```

### `models/schedule.py`
```python
class ShiftType(str, Enum):
    MORNING = "morning"      # peso 1
    AFTERNOON = "afternoon"  # peso 1
    NIGHT = "night"          # peso 2

class ShiftAssignment(BaseModel):
    worker_id: str
    date: date
    shift_type: ShiftType

class DaySchedule(BaseModel):
    date: date
    morning: list[str]    # worker_ids
    afternoon: list[str]
    night: list[str]

class Schedule(BaseModel):
    assignments: list[ShiftAssignment]
    horizon_start: date
    horizon_end: date
    is_verified: bool = False
    fairness_score: Optional[float] = None
```

### `models/state.py` (LangGraph)
```python
class SmartSchedulerState(TypedDict):
    # Input
    input_model: str               # testo grezzo input
    workers: list[Worker]
    use_case: Literal["A", "B"]
    
    # Stage 1 output
    preferences_collected: bool
    ortools_preferences_code: str  # file .py con preferenze OR-Tools
    
    # Stage 2/4 output
    schedule: Optional[Schedule]
    ortools_schedule_code: str     # file .py con schedule OR-Tools
    draft_iteration: int
    max_draft_iterations: int      # ← limite loop hard-constraint (default 5)
    
    # Stage 3 output
    hard_constraints_satisfied: bool
    violations: list[str]
    fairness_metrics: dict[str, float]  # worker_id -> satisfaction_score
    previous_fairness_score: float      # ← min score dell'iterazione precedente
    least_satisfied_worker: Optional[str]
    
    # Controllo loop raffinamento
    refinement_iteration: int
    max_refinements: int           # default 10
    pipeline_done: bool
```

---

## Stage 1: Preferences Definition

### Obiettivo
Raccogliere preferenze dai lavoratori in NL e convertirle in strutture Pydantic + codice OR-Tools.

### Flusso Dettagliato

1. **Input**: Per ogni worker, una stringa NL con le sue preferenze
2. **Preferences Agent** (LLM):
   - Prompt strutturato con esempi few-shot
   - Output: JSON `Preference` per ogni worker (validato Pydantic)
3. **Formalization**: Conversione in codice Python OR-Tools (soft constraints + penalty weights)
4. **Output**: File `ortools_preferences_code.py` con:
   - Variabili di preferenza per ogni worker
   - Dizionario `preference_weights: dict[worker_id, dict[shift_type, int]]`
   - Dizionario `satisfaction_model: dict[worker_id, callable]`

### Distinzione Hard vs Soft

| Tipo | Esempi | Trattamento OR-Tools |
|------|--------|---------------------|
| Hard | "non disponibile il 25/12" | `model.Add(shift[w,d,s] == 0)` |
| Soft | "preferisce mattino" | penalty term in objective |

### Prompt Template (Preferences Agent)
```
Sei un assistente esperto in pianificazione dei turni ospedalieri.
Dato il seguente testo di un lavoratore, estrai:
1. Turni preferiti con priorità (1=obbligatorio, 4=da evitare)
2. Date di indisponibilità assoluta
3. Giorno di riposo preferito
4. Tolleranza verso turni notturni (0-5)
5. Tolleranza verso turni festivi (0-5)

Testo: {worker_preference_text}

Rispondi SOLO in JSON valido secondo questo schema: {schema}
```

---

## Stage 2: Schedule Drafting

### Obiettivo
Generare un schedule iniziale come file Python OR-Tools valido.

### Flusso Dettagliato

1. **Input**: `input_model.txt` + `ortools_preferences_code.py` + workers list
2. **Drafting Agent** (LLM):
   - Riceve: vincoli hard, preferenze formalize, lista lavoratori, orizzonte temporale
   - Genera: file Python completo con `cp_model.CpModel()`, variabili, vincoli, obiettivo
3. **OR-Tools Runner**:
   - Esegue il file generato in subprocess sandboxed
   - Ritorna: dizionario `{worker_id: [(date, shift_type), ...]}` o errore
4. **Output**: `Schedule` Pydantic + file `schedule_draft.py`

### Struttura del File OR-Tools Generato

```python
from ortools.sat.python import cp_model
import json

def solve_schedule():
    model = cp_model.CpModel()
    
    # Parametri
    workers = [...]
    days = list(range(31))  # 7dic-6gen
    shifts = ["morning", "afternoon", "night"]
    shift_weight = {"morning": 1, "afternoon": 1, "night": 2}
    
    # Variabili booleane: shift[w][d][s] = 1 se worker w copre shift s il giorno d
    shift_vars = {}
    for w in workers:
        for d in days:
            for s in shifts:
                shift_vars[(w, d, s)] = model.NewBoolVar(f"shift_{w}_{d}_{s}")
    
    # === HARD CONSTRAINTS ===
    # 1. Copertura minima per turno
    # 2. Max 1 turno/giorno per worker
    # 3. No turni consecutivi
    # 4. 2 giorni liberi dopo notte
    # 5. Max 36h/settimana
    # 6. 25 shift-units/mese per worker
    
    # === SOFT CONSTRAINTS (objective) ===
    # Preference penalties
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result = {}
        for w in workers:
            result[w] = [(d, s) for d in days for s in shifts 
                         if solver.Value(shift_vars[(w,d,s)])]
        print(json.dumps(result))
    else:
        print(json.dumps({"error": "INFEASIBLE"}))

solve_schedule()
```

### Prompt Template (Drafting Agent)
```
Sei un esperto di constraint programming e pianificazione ospedaliera.
Genera un file Python completo che usi OR-Tools CP-SAT per schedulare i turni.

PARAMETRI:
- Orizzonte: {start_date} → {end_date} ({n_days} giorni)
- Lavoratori: {workers_list}
- Use Case: {use_case}

VINCOLI HARD OBBLIGATORI:
{hard_constraints}

PREFERENZE WORKER (da includere come soft constraints nell'obiettivo):
{preferences_summary}

Il file deve:
1. Definire tutte le variabili shift[worker][day][shift_type]
2. Aggiungere TUTTI i vincoli hard
3. Definire una funzione obiettivo che minimizzi le penalità sulle preferenze
4. Stampare il risultato in JSON
```

---

## Stage 3: Schedule Verification

### Stage 3a — Hard Constraint Verification (Simbolica, NO LLM)

Agente deterministico Python puro che verifica:

| Check | Implementazione |
|-------|----------------|
| Copertura minima | `for each (day, shift): count(assigned_workers) >= min_required` |
| Max 1 turno/giorno | `for each (worker, day): count(shifts_assigned) <= 1` |
| No consecutivi | `for each worker: no (afternoon[d] and night[d]) o (morning[d] and afternoon[d-1... ma notte finisce mattino]` |
| Riposo post-notte | `for each worker: if night[d], then no shift on day d+1, d+2` |
| Ore settimanali | `for each (worker, week): sum(shift_hours) <= 36` |
| 25 shift-units | `for each worker: sum(shift_weights) == 25` |
| UC-B: composizione | `for each (day, shift): count_standard >= 2 and count_specialized >= 1` |

**Output**: `{"satisfied": bool, "violations": [{"type": str, "worker": str, "day": int, "shift": str, "detail": str}]}`

Se non soddisfatto → ritorno al Drafting Agent con lista violations.

### Stage 3b — Fairness Evaluation (Simbolica, NO LLM)

Calcola per ogni worker uno **satisfaction score** normalizzato [0, 1]:

```
satisfaction(w) = 1 - (penalty_incurred(w) / max_possible_penalty(w))
```

Dove `penalty_incurred` conta:
- Turni notturni assegnati × `(5 - night_tolerance)`
- Turni festivi × `(5 - holiday_tolerance)`
- Deviazione dal turno preferito × peso preferenza
- Deviazione dal giorno di riposo preferito

**Fairness metric** (criterio min-max):
```
fairness_score = min(satisfaction(w) for w in workers)
least_satisfied = argmin(satisfaction(w) for w in workers)
```

**Output**: `{"scores": {worker_id: float}, "least_satisfied": str, "fairness_score": float}`

---

## Stage 4: Schedule Refinement

### Obiettivo
Migliorare iterativamente la fairness preservando tutti i vincoli hard.

### Flusso del Loop

```
┌─────────────────────────────────────────┐
│  VERIFICA: hard constraints OK?         │
│  NO → Drafting Agent (con violations)   │
│  SÌ ↓                                   │
│  FAIRNESS: calcola scores               │
│  least_satisfied = argmin(scores)       │
│                                         │
│  RAFFINAMENTO:                          │
│  Drafting Agent riceve:                 │
│  - schedule attuale                     │
│  - worker meno soddisfatto              │
│  - preferenze tutti i worker            │
│  - constraint: non peggiorare altri     │
│                                         │
│  VERIFICA raffinamento:                 │
│  nuovo min(scores) >= vecchio min?      │
│  SÌ → accetta, continua loop           │
│  NO → rigetta, termina                 │
│                                         │
│  TERMINAZIONE:                          │
│  - No miglioramento possibile           │
│  - Tutti i vincoli hard soddisfatti     │
│  - Max iterazioni raggiunte             │
└─────────────────────────────────────────┘
```

### Prompt Template (Refinement Agent)
```
Hai generato uno schedule che soddisfa tutti i vincoli hard.
Il worker meno soddisfatto è: {least_satisfied_worker}
Il suo satisfaction score è: {score:.2f}

OBIETTIVO: Modifica lo schedule per migliorare la soddisfazione di {least_satisfied_worker}
VINCOLO CRITICO: Non peggiorare il satisfaction score minimo degli altri worker.

Schedule attuale: {current_schedule_summary}
Preferenze di {least_satisfied_worker}: {worker_preferences}
Preferenze di tutti i worker: {all_preferences_summary}

Genera un nuovo file Python OR-Tools con lo schedule raffinato.
Motivazione delle modifiche: [spiega le scelte]
```

### Criterio di Stop

Il campo `previous_fairness_score` (aggiunto allo State) tiene traccia del min-score dell'iterazione precedente.

```python
def check_fairness_improvement(state: SmartSchedulerState) -> str:
    new_min = min(state["fairness_metrics"].values())
    old_min = state["previous_fairness_score"]  # campo presente nello State ✓
    
    improved = new_min > old_min
    within_limit = state["refinement_iteration"] < state["max_refinements"]
    
    if improved and within_limit:
        return "continue_refinement"
    return "end"  # nessun miglioramento o limite raggiunto
```

---

## LangGraph — Grafo Completo

```python
# graph/smartscheduler_graph.py

workflow = StateGraph(SmartSchedulerState)

# Nodi
workflow.add_node("preferences", preferences_agent_node)
workflow.add_node("drafting", drafting_agent_node)
workflow.add_node("hard_verification", hard_verification_node)
workflow.add_node("fairness_evaluation", fairness_evaluation_node)
workflow.add_node("refinement", refinement_agent_node)

# Entry point
workflow.set_entry_point("preferences")

# Edges fissi
workflow.add_edge("preferences", "drafting")
workflow.add_edge("drafting", "hard_verification")
# ⚠️ NON aggiungere add_edge fisso da fairness_evaluation → usa solo il condizionale sotto
workflow.add_edge("refinement", "hard_verification")  # riverifica dopo raffinamento

# Edge condizionale 1: hard_verification → drafting (se violato) o fairness (se ok)
workflow.add_conditional_edges(
    "hard_verification",
    check_hard_constraints,
    {
        "violated": "drafting",           # torna a drafting con lista violations
        "draft_limit_reached": END,        # abort se max_draft_iterations superato
        "satisfied": "fairness_evaluation"
    }
)

# Edge condizionale 2: fairness_evaluation → refinement (se migliora) o END
# ⚠️ Questo è l'UNICO edge da fairness_evaluation — nessun add_edge fisso!
workflow.add_conditional_edges(
    "fairness_evaluation",
    check_fairness_improvement,
    {
        "continue_refinement": "refinement",
        "end": END
    }
)

app = workflow.compile()
```

### Logica dei nodi condizionali

```python
def check_hard_constraints(state: SmartSchedulerState) -> str:
    if state["hard_constraints_satisfied"]:
        return "satisfied"
    if state["draft_iteration"] >= state["max_draft_iterations"]:
        return "draft_limit_reached"  # evita loop infinito
    return "violated"

def check_fairness_improvement(state: SmartSchedulerState) -> str:
    new_min = min(state["fairness_metrics"].values())
    if new_min > state["previous_fairness_score"] and \
       state["refinement_iteration"] < state["max_refinements"]:
        return "continue_refinement"
    return "end"
```

---

## Vincoli Hard — Implementazione OR-Tools Dettagliata

### 1. Copertura Minima (UC-A)
```python
for d in days:
    for s in shifts:
        model.Add(sum(shift_vars[w,d,s] for w in workers) >= 2)
```

### 2. Copertura Minima (UC-B)

La traccia dice: "at least two standard workers and one specialized worker must be assigned
*to each shift*. If needed, a specialized worker can also play the role of a standard one."

Questo significa che NON si conta il ruolo del lavoratore ma solo la sua presenza:
- ≥ 1 specializzato assegnato al turno
- ≥ 3 lavoratori in totale (2 ruoli standard + 1 ruolo spec, ma specializzati possono riempire ruoli standard)

```python
for d in days:
    for s in shifts:
        # Almeno 3 lavoratori totali (permette combinazioni: 2std+1spec, 1std+2spec, 0std+3spec)
        model.Add(sum(shift_vars[w,d,s] for w in all_workers) >= 3)
        # Almeno 1 lavoratore specializzato sempre presente
        model.Add(sum(shift_vars[w,d,s] for w in specialized_workers) >= 1)
        # ⚠️ NON imporre standard >= 2: questo violerebbe la flessibilità del ruolo specializzato
```

### 3. Max 1 turno/giorno
```python
for w in workers:
    for d in days:
        model.Add(sum(shift_vars[w,d,s] for s in shifts) <= 1)
```

### 4. No turni consecutivi

> **Nota**: Questo vincolo è **ridondante** dato il vincolo 5 (2 giorni liberi dopo notte),
> che già impone `notte[d] + qualsiasi[d+1] ≤ 1`. Viene mantenuto per documentazione esplicita.
> I turni stesso-giorno consecutivi (es. mattino+pomeriggio) sono già coperti dal vincolo 3.

```python
# Notte finisce alle 8:00 del giorno dopo → mattino del giorno dopo è strettamente consecutivo
for w in workers:
    for d in range(len(days) - 1):
        model.Add(shift_vars[w, d, "night"] + shift_vars[w, d+1, "morning"] <= 1)
        # pomeriggio[d] + notte[d] → già coperto da vincolo 3 (max 1 turno/giorno)
        # pomeriggio[d] + mattino[d+1] → NON consecutivi (c'è la notte in mezzo), consentito
```

### 5. 2 giorni liberi dopo turno notturno
```python
for w in workers:
    for d in range(len(days)):
        if d+1 < len(days):
            model.Add(shift_vars[w,d,"night"] + sum(shift_vars[w,d+1,s] for s in shifts) <= 1)
        if d+2 < len(days):
            model.Add(shift_vars[w,d,"night"] + sum(shift_vars[w,d+2,s] for s in shifts) <= 1)
```

### 6. Max 36 ore/settimana — Finestra Scorrevole

Si usa una **sliding window di 7 giorni** su tutte le 25 finestre possibili (giorni 0–30).
Questo garantisce che nessun lavoratore superi 36h in *qualsiasi* periodo di 7 giorni consecutivi,
covendo automaticamente anche l'ultima settimana parziale (4–6 gen).

```python
hours = {"morning": 6, "afternoon": 6, "night": 12}
n_days = 31
window_size = 7

for w in workers:
    # 25 finestre: [0..6], [1..7], ..., [24..30]
    for start in range(n_days - window_size + 1):
        window = range(start, start + window_size)
        model.Add(
            sum(shift_vars[w, d, s] * hours[s]
                for d in window for s in shifts) <= 36
        )
```

> **Nota**: 25 finestre × numero_worker variabili OR-Tools — computazionalmente gestibile con CP-SAT.

### 7. 25 shift-units/mese
```python
shift_units = {"morning": 1, "afternoon": 1, "night": 2}
for w in workers:
    model.Add(
        sum(shift_vars[w,d,s] * shift_units[s] 
            for d in days for s in shifts) == 25
    )
```

---

## Output del Sistema

### 1. File OR-Tools (Input parziale + Soluzione)
Salvato in `output/schedule_draft.py` — contiene il CpModel completo con vincoli.

### 2. Schedule Finale JSON
```json
{
  "horizon": {"start": "2026-12-07", "end": "2027-01-06"},
  "use_case": "A",
  "verified": true,
  "fairness_score": 0.82,
  "refinement_iterations": 3,
  "assignments": [
    {"worker_id": "W01", "date": "2026-12-07", "shift": "morning"},
    ...
  ],
  "satisfaction_scores": {
    "W01": 0.91, "W02": 0.82, ...
  }
}
```

### 3. Report Leggibile (`output/report.txt`)
- Tabella turni per ogni giorno
- Statistiche per worker (turni totali, notti, festivi, score)
- Violazioni riscontrate (se rimaste)
- Numero iterazioni di raffinamento

---

## Ordine di Implementazione (Task List)

### Fase 1 — Fondamenta (nessuna dipendenza)
- [ ] `requirements.txt` + setup ambiente
- [ ] `config.py` — API keys, parametri globali
- [ ] `models/worker.py` — Pydantic models Worker, Preference
- [ ] `models/schedule.py` — Schedule, ShiftAssignment
- [ ] `models/constraints.py` — HardConstraint, SoftConstraint
- [ ] `models/state.py` — SmartSchedulerState TypedDict
- [ ] `data/scenarios/use_case_a.txt` e `use_case_b.txt`

### Fase 2 — Solver Layer (dipende da Fase 1)
- [ ] `solver/ortools_builder.py` — costruisce CpModel da Schedule+Constraints
- [ ] `solver/ortools_runner.py` — esegue solver in subprocess, parsing output
- [ ] `solver/fairness_metrics.py` — calcola satisfaction scores

### Fase 3 — Agenti (dipende da Fase 1)
- [ ] `prompts/preferences_prompt.py`
- [ ] `prompts/drafting_prompt.py`
- [ ] `prompts/refinement_prompt.py`
- [ ] `agents/preferences_agent.py` — LLM NL→Pydantic
- [ ] `agents/drafting_agent.py` — LLM genera OR-Tools code
- [ ] `agents/verification_agent.py` — simbolico, no LLM
- [ ] `agents/fairness_agent.py` — simbolico, no LLM

### Fase 4 — Orchestrazione (dipende da Fase 2+3)
- [ ] `graph/smartscheduler_graph.py` — LangGraph StateGraph
- [ ] `main.py` — CLI entry point

### Fase 5 — Test e Validazione
- [ ] `tests/test_constraints.py`
- [ ] `tests/test_fairness.py`
- [ ] `tests/test_pipeline.py`
- [ ] Esecuzione Use Case A completo
- [ ] Esecuzione Use Case B completo

---

## Piano di Verifica

### Test Automatici
```bash
pytest tests/ -v
```

| Test | Cosa verifica |
|------|--------------|
| `test_constraints.py` | Ogni vincolo hard viene violato/rispettato correttamente |
| `test_fairness.py` | Satisfaction scores calcolati correttamente su casi noti |
| `test_pipeline.py` | Pipeline end-to-end su input sintetico ridotto (7 giorni) |

### Verifica Manuale
1. Eseguire `main.py --use-case A` → verificare schedule valido nel JSON output
2. Eseguire `main.py --use-case B` → verificare copertura specializzati
3. Controllare il report leggibile per coerenza con vincoli
4. Verificare che il refinement loop effettivamente migliori il min satisfaction score

### Metriche di Successo
- UC-A: schedule valido con 13 worker, fairness_score > 0.7
- UC-B: schedule valido con 20 worker, tutti i turni coperti con composizione corretta
- Refinement: min(satisfaction_score) non peggiora mai dopo un'iterazione accettata

---

## Domande Aperte

> [!IMPORTANT]
> **Quale modello Ollama usare?** Ollama è confermato come runtime. Il modello specifico (es. `llama3.2`, `mistral`, `qwen2.5-coder`) è ancora da definire — da scegliere prima dell'implementazione degli agenti.

> [!NOTE]
> **25 shift-units = vincolo hard esatto** ✅ Confermato. Implementato come `model.Add(total_units == 25)`.

> [!NOTE]
> **Finestra scorrevole 7 giorni** ✅ Confermato per il vincolo 36h/settimana.

> [!NOTE]
> **Interazione NL reale o simulata?** Le preferenze saranno lette da file di testo pre-esistenti. Se vuoi un'interfaccia interattiva CLI, va aggiunta come componente extra.

> [!NOTE]
> **Max iterazioni di raffinamento**: default `max_refinements = 10`, configurabile in `config.py`.

---

## Piano per il Giorno 2 (Esecuzione e Fixing)

Domani il focus sarà sull'attivazione dell'LLM (Ollama) e sul completamento dei test end-to-end. Prima di procedere con le esecuzioni complete, applicheremo alcuni fix emersi durante i test locali.

### 1. Fix da Applicare (Cosa aggiustare)

1. **Fix Indentazione Template OR-Tools (`solver/ortools_builder.py`)**
   - **Problema**: L'agente e i test formattano il codice delle preferenze con un'indentazione di base di 4 spazi. Nel builder, la funzione `_indent(preferences_code, 4)` aggiunge *altri* 4 spazi, causando un `IndentationError` in Python (8 spazi anziché 4) che rompe il solver.
   - **Soluzione**: Rimuovere l'indentazione manuale nell'agente e test e lasciare che se ne occupi solo il builder, oppure rimuovere `_indent()` dal builder e richiedere che il codice sia già fornito con l'indentazione corretta (approccio più pulito).

2. **Gestione Errori Ollama (`main.py` & `agents/base_llm.py`)**
   - **Problema**: Se Ollama non è in esecuzione, il sistema crasha con uno stack trace poco leggibile.
   - **Soluzione**: Intercettare `ConnectionError` in fase di avvio e stampare un messaggio chiaro: "Ollama non è in esecuzione. Avvia Ollama e riprova."

3. **Prompt Tuning (opzionale)**
   - In caso l'LLM restituisca testo non formattato correttamente o syntax errors, potremmo dover aggiungere un layer di retry o specificare meglio i tag ```python nel system prompt.

### 2. Azioni da Svolgere (Test con Ollama)

1. **Setup LLM locale**
   - Eseguire l'installazione di Ollama e scaricare il modello (`ollama pull llama3.2`).
   - Confermare che l'API locale risponda all'indirizzo http://localhost:11434.

2. **Esecuzione Use Case A (Omogenei)**
   - Eseguire: `python main.py --use-case A --model llama3.2`
   - **Verifica**: Controllare che il file `output/schedule_draft.py` sia un file Python valido.
   - **Verifica**: Verificare il completamento della pipeline e leggere il JSON/Text report generato.
   - **Verifica Fairness**: Assicurarsi che il refinement loop migliori lo score senza violare vincoli hard.

3. **Esecuzione Use Case B (Eterogenei)**
   - Eseguire: `python main.py --use-case B --model llama3.2`
   - **Verifica**: Controllare che la copertura minima (≥ 3 totali, ≥ 1 specializzato) venga rispettata.

4. **Validazione Pipeline E2E (`tests/test_pipeline.py`)**
   - Scrivere ed eseguire un test pytest (che richiede Ollama) su una finestra temporale ristretta (es. 3 giorni) per testare la solidità del loop LLM ↔ OR-Tools senza dover attendere i 30 giorni completi di simulazione.

### 3. Obiettivo Finale
Avere i file `output/schedule_final_ucA.json` e `output/schedule_final_ucB.json` completamente generati in autonomia dal sistema agentico, con score di fairness > 0.7.
