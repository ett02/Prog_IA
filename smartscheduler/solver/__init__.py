"""
solver/__init__.py
"""
from solver.ortools_runner import run_ortools_code, extract_code_from_llm_response
from solver.ortools_builder import generate_ortools_template
from solver.fairness_metrics import (
    compute_satisfaction_score,
    compute_all_scores,
    find_least_satisfied,
    compute_fairness_report,
)

__all__ = [
    "run_ortools_code",
    "extract_code_from_llm_response",
    "generate_ortools_template",
    "compute_satisfaction_score",
    "compute_all_scores",
    "find_least_satisfied",
    "compute_fairness_report",
]
