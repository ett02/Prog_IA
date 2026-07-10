"""
config.py — Configurazione globale di SmartScheduler.
Modifica questo file per cambiare il modello Ollama, i parametri del loop
di raffinamento o le costanti di scheduling.
"""

from datetime import date

# ─── LLM ────────────────────────────────────────────────────────────────────
OLLAMA_MODEL: str = "qwen2.5-coder:7b"     # Modello 7B specializzato per codice
OLLAMA_BASE_URL: str = "http://localhost:11434"

# ─── Orizzonte di scheduling ─────────────────────────────────────────────────
HORIZON_START: date = date(2026, 12, 7)
HORIZON_END: date = date(2027, 1, 6)

# ─── Vincoli hard ────────────────────────────────────────────────────────────
TARGET_SHIFT_UNITS_PER_MONTH: int = 25   # esatto, vincolo hard
MAX_HOURS_PER_WEEK_WINDOW: int = 36      # finestra scorrevole 7 giorni
REST_DAYS_AFTER_NIGHT: int = 2           # giorni liberi obbligatori dopo notte

# Copertura minima per turno
MIN_WORKERS_PER_SHIFT_UC_A: int = 2
MIN_WORKERS_PER_SHIFT_UC_B_TOTAL: int = 3       # totale (std + spec)
MIN_SPECIALIZED_PER_SHIFT_UC_B: int = 1

# ─── Parametri loop ──────────────────────────────────────────────────────────
MAX_DRAFT_ITERATIONS: int = 5    # max tentativi se hard constraints violati
MAX_REFINEMENT_ITERATIONS: int = 10  # max iterazioni fairness refinement

# ─── Solver OR-Tools ─────────────────────────────────────────────────────────
SOLVER_TIMEOUT_SECONDS: int = 60     # timeout per ogni run del solver
ORTOOLS_SOLVER_TIME_LIMIT: int = 30  # secondi per il CpSolver interno

# ─── Path ────────────────────────────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_run9")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")

os.makedirs(OUTPUT_DIR, exist_ok=True)
