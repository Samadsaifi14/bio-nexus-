"""Question-oriented scientific benchmark figure specification.

A panel should answer a scientific comparison question, not merely visualize a
benchmark score. The object returned here can be rendered by the Figure Engine
or exported as JSON alongside publication figures.
"""
from __future__ import annotations

from typing import Any

from app.services.performance_validation import comparison_report, failure_analysis


def benchmark_question_panel(
    *,
    question: str,
    candidate_label: str,
    reference_label: str,
    candidate_values: list[float],
    reference_values: list[float],
    biological_implication: str | None = None,
    failures: list[dict] | None = None,
    metric: str = "benchmark metric",
    higher_is_better: bool = True,
    seed: int = 0,
) -> dict[str, Any]:
    stats = comparison_report(candidate_values, reference_values, seed=seed)
    diff = stats["difference"].get("estimate")
    direction = None
    if diff is not None:
        improved = diff > 0 if higher_is_better else diff < 0
        direction = "candidate_favoured" if improved else ("reference_favoured" if diff != 0 else "no_mean_difference")

    return {
        "schema": "bionexus-scientific-figure-panel/v1",
        "question": question,
        "metric": metric,
        "comparison": {
            "candidate": candidate_label,
            "reference": reference_label,
            "higher_is_better": higher_is_better,
            "direction": direction,
        },
        "statistics": {
            "sample_size": stats.get("n"),
            "candidate_estimate": stats["candidate"].get("estimate"),
            "candidate_ci": stats["candidate"].get("ci"),
            "reference_estimate": stats["reference"].get("estimate"),
            "reference_ci": stats["reference"].get("ci"),
            "difference_estimate": stats["difference"].get("estimate"),
            "difference_ci": stats["difference"].get("ci"),
            "effect_size": stats.get("effect_size"),
            "statistical_significance": stats.get("statistical_significance"),
        },
        "failure_analysis": failure_analysis(failures or []),
        "biological_implication": biological_implication,
        "caption_contract": [
            "state the scientific question",
            "name candidate and reference",
            "report sample size",
            "report uncertainty interval",
            "report effect size",
            "report significance only when a valid predeclared test exists",
            "summarize failures",
            "state biological implication separately from statistical performance",
        ],
        "boundary": "Biological implication is an interpretation field and must be supported by the Evidence Graph; benchmark statistics alone do not establish biological or clinical significance.",
    }
