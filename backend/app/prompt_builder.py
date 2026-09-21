"""Prompt construction for original blueprint-driven question writing."""

from .schemas import QuestionBlueprint


def build_question_prompt(blueprint: QuestionBlueprint) -> str:
    """Build a copyright-safe prompt containing blueprint metadata only."""
    concepts = ", ".join(blueprint.concepts)
    return f"""You are an original educational question writer.

Create one ORIGINAL CAT-style practice question using only this structured blueprint.
Do not copy, quote, paraphrase, transform, or closely imitate any known CAT question.
Do not request or use any source question text. The result must be newly authored.

Blueprint:
- section: {blueprint.section}
- topic: {blueprint.topic}
- subtopic: {blueprint.subtopic}
- question_type: {blueprint.question_type}
- difficulty: {blueprint.difficulty}
- concepts: {concepts}
- number_of_steps: {blueprint.number_of_steps}
- reasoning_level: {blueprint.reasoning_level}
- calculation_load: {blueprint.calculation_load}
- information_density: {blueprint.information_density}
- trap_type: {blueprint.trap_type}
- expected_time_seconds: {blueprint.expected_time_seconds}

Requirements:
1. Create an original question that follows the blueprint.
2. Ensure exactly one correct answer and make all four options plausible.
3. Provide a concise explanation that independently supports the answer.
4. Return only a JSON object matching the requested schema. Do not return markdown or prose outside JSON.

Required JSON fields:
question_text, options, correct_answer, explanation, section, topic, subtopic, difficulty, question_type
"""