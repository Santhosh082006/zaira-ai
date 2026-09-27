"""Analytical engine initialization."""
from analytical_engine.vocal_metrics import evaluate_vocal_performance
from analytical_engine.visual_metrics import evaluate_visual_performance
from analytical_engine.evaluator import (
    compute_deterministic_scores,
    evaluate_account_with_explanation,
    calculate_overall_communication_score,
)
from analytical_engine.cross_comparator import compare_multimodal_performance
