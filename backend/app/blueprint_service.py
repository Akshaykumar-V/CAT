"""Centralized rules for constructing original CAT-style question blueprints."""

from dataclasses import dataclass

from fastapi import HTTPException
import pandas as pd

from .analysis import pattern_signal
from .question_generator import TEMPLATES
from .schemas import QuestionBlueprint, QuestionGenerationRequest


@dataclass(frozen=True)
class BlueprintRule:
    """Topic-level structure shared across difficulty variants."""

    concepts: tuple[str, ...]
    trap_type: str
    information_density: str
    calculation_load: str
    base_steps: int
    expected_time_seconds: int


DIFFICULTY_RULES = {
    "Easy": {
        "step_adjustment": 0,
        "reasoning_level": "low",
        "time_adjustment": 0,
    },
    "Medium": {
        "step_adjustment": 1,
        "reasoning_level": "medium",
        "time_adjustment": 30,
    },
    "Hard": {
        "step_adjustment": 2,
        "reasoning_level": "high",
        "time_adjustment": 75,
    },
}


BLUEPRINT_RULES: dict[tuple[str, str, str], BlueprintRule] = {
    ("QA", "Arithmetic", "Percentages"): BlueprintRule(("successive_percentage_change", "reverse_percentage"), "reverse_calculation", "medium", "medium", 2, 90),
    ("QA", "Arithmetic", "Profit & Loss"): BlueprintRule(("cost_price", "selling_price", "percentage_change"), "base_value_confusion", "medium", "medium", 2, 90),
    ("QA", "Arithmetic", "Ratio"): BlueprintRule(("ratio_parts", "proportional_scaling"), "part_to_whole_confusion", "low", "low", 1, 75),
    ("QA", "Arithmetic", "Averages"): BlueprintRule(("total_from_average", "missing_value"), "wrong_denominator", "medium", "medium", 2, 90),
    ("QA", "Arithmetic", "Time & Work"): BlueprintRule(("individual_rates", "combined_rate"), "additive_time_error", "medium", "high", 2, 120),
    ("QA", "Arithmetic", "Time, Speed & Distance"): BlueprintRule(("distance_rate_time", "unit_consistency"), "unit_conversion", "low", "low", 1, 75),
    ("QA", "Algebra", "Algebra"): BlueprintRule(("linear_equation", "inverse_operation"), "sign_error", "low", "low", 1, 75),
    ("QA", "Number System", "Number System"): BlueprintRule(("division_algorithm", "remainders"), "quotient_remainder_confusion", "medium", "medium", 2, 90),
    ("VARC", "Reading Comprehension", "Reading Comprehension"): BlueprintRule(("central_idea", "evidence_inference"), "overgeneralization", "high", "low", 2, 150),
    ("VARC", "Verbal Ability", "Para Summary"): BlueprintRule(("main_claim", "supporting_detail"), "detail_over_main_idea", "medium", "low", 2, 120),
    ("VARC", "Verbal Ability", "Odd Sentence Out"): BlueprintRule(("coherence", "topic_consistency"), "surface_keyword_match", "medium", "low", 2, 120),
    ("VARC", "Verbal Ability", "Para Jumbles"): BlueprintRule(("sequence", "pronoun_reference", "logical_flow"), "local_pairing", "high", "low", 3, 150),
    ("DILR", "Data Interpretation", "Tables"): BlueprintRule(("table_reading", "comparison"), "wrong_row_or_column", "high", "medium", 2, 150),
    ("DILR", "Logical Reasoning", "Arrangements"): BlueprintRule(("ordering_constraints", "adjacency"), "constraint_omission", "high", "low", 3, 180),
    ("DILR", "Logical Reasoning", "Distribution"): BlueprintRule(("equal_distribution", "constraint_tracking"), "premature_division", "medium", "medium", 2, 150),
    ("DILR", "Logical Reasoning", "Selection"): BlueprintRule(("selection_constraints", "case_elimination"), "invalid_pairing", "medium", "low", 2, 150),
    ("DILR", "Logical Reasoning", "Games/Tournaments"): BlueprintRule(("round_robin_pairings", "counting"), "double_counting", "medium", "medium", 2, 150),
    ("DILR", "Data Interpretation", "Data Comparison"): BlueprintRule(("rate_comparison", "normalization"), "raw_total_comparison", "medium", "medium", 2, 150),
}


def generate_blueprint(
    request: QuestionGenerationRequest, metadata: pd.DataFrame | None = None
) -> QuestionBlueprint:
    """Create a blueprint from a supported original-question template."""
    key = (request.section, request.topic, request.subtopic)
    rule = BLUEPRINT_RULES.get(key)
    if rule is None or key not in TEMPLATES:
        raise HTTPException(status_code=422, detail="This topic does not have a blueprint configuration")
    difficulty_rule = DIFFICULTY_RULES[request.difficulty]
    return QuestionBlueprint(
        section=request.section,
        topic=request.topic,
        subtopic=request.subtopic,
        question_type=request.question_type,
        difficulty=request.difficulty,
        concepts=list(rule.concepts),
        number_of_steps=min(8, rule.base_steps + difficulty_rule["step_adjustment"]),
        reasoning_level=difficulty_rule["reasoning_level"],
        calculation_load=rule.calculation_load,
        information_density=rule.information_density,
        trap_type=rule.trap_type,
        expected_time_seconds=rule.expected_time_seconds + difficulty_rule["time_adjustment"],
        metadata_signal=pattern_signal(metadata, request.section, request.topic, request.subtopic)
        if metadata is not None else None,
    )