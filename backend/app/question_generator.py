"""Template-based, original CAT-style question generator.

This module has no external AI dependency. A future LLM-backed generator can
implement the same ``generate_question`` interface and replace this service.
"""

import random
from collections.abc import Callable

from .schemas import GeneratedQuestion, QuestionGenerationRequest


Template = Callable[[QuestionGenerationRequest], GeneratedQuestion]


def _mcq(
    request: QuestionGenerationRequest,
    question_text: str,
    correct_answer: str,
    distractors: list[str],
    explanation: str,
) -> GeneratedQuestion:
    """Build an MCQ and shuffle its options while preserving the answer text."""
    options = [correct_answer, *distractors]
    random.SystemRandom().shuffle(options)
    return GeneratedQuestion(
        question_text=question_text,
        options=options,
        correct_answer=correct_answer,
        explanation=explanation,
        section=request.section,
        topic=request.topic,
        subtopic=request.subtopic,
        difficulty=request.difficulty,
        question_type=request.question_type,
    )


def _numeric_options(answer: int, unit: str = "") -> tuple[str, list[str]]:
    """Create three nearby but distinct incorrect values for an integer answer."""
    correct = f"{answer}{unit}"
    offsets = [-2, -1, 1, 2, 3]
    distractors = []
    for offset in offsets:
        value = answer + offset
        if value >= 0 and value != answer:
            distractors.append(f"{value}{unit}")
        if len(distractors) == 3:
            break
    return correct, distractors


def generate_percentages(request: QuestionGenerationRequest) -> GeneratedQuestion:
    base = random.choice(range(120, 401, 20))
    increase = random.choice([10, 15, 20, 25])
    answer = base * (100 + increase) // 100
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"A subscription costs Rs. {base}. Its price is increased by {increase}%. What is the new price?",
        correct,
        distractors,
        f"An increase of {increase}% means multiplying {base} by {100 + increase}/100. The new price is Rs. {answer}.",
    )


def generate_profit_loss(request: QuestionGenerationRequest) -> GeneratedQuestion:
    cost = random.choice(range(200, 801, 50))
    profit = random.choice([10, 15, 20, 25])
    answer = cost * (100 + profit) // 100
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"A shopkeeper buys an item for Rs. {cost} and sells it at a profit of {profit}%. What is its selling price?",
        correct,
        distractors,
        f"Selling price = {cost} x {100 + profit}/100 = Rs. {answer}.",
    )


def generate_ratio(request: QuestionGenerationRequest) -> GeneratedQuestion:
    first, second = random.choice([(2, 3), (3, 4), (3, 5), (4, 5)])
    multiplier = random.choice(range(8, 21))
    total = (first + second) * multiplier
    answer = first * multiplier
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"The ratio of red to blue tokens is {first}:{second}. If there are {total} tokens in all, how many are red?",
        correct,
        distractors,
        f"Total parts = {first + second}. One part is {total}/{first + second} = {multiplier}, so red tokens = {first} x {multiplier} = {answer}.",
    )


def generate_averages(request: QuestionGenerationRequest) -> GeneratedQuestion:
    average = random.choice(range(12, 31))
    count = random.choice([4, 5, 6])
    known_total = average * count - random.choice(range(5, 16))
    answer = average * count - known_total
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"The average of {count} numbers is {average}. The sum of {count - 1} of them is {known_total}. What is the remaining number?",
        correct,
        distractors,
        f"The total of all {count} numbers is {count} x {average} = {count * average}. Subtracting {known_total} gives {answer}.",
    )


def generate_time_work(request: QuestionGenerationRequest) -> GeneratedQuestion:
    first_days, second_days = random.choice([(6, 12), (8, 8), (10, 10), (12, 12)])
    answer = first_days * second_days // (first_days + second_days)
    correct, distractors = _numeric_options(answer, " days")
    return _mcq(
        request,
        f"Asha can complete a task in {first_days} days and Bilal can complete it in {second_days} days. Working together at constant rates, how many days will they take?",
        correct,
        distractors,
        f"Their combined daily work is 1/{first_days} + 1/{second_days}. The time is {first_days * second_days}/({first_days} + {second_days}) = {answer} days.",
    )


def generate_tsd(request: QuestionGenerationRequest) -> GeneratedQuestion:
    speed = random.choice([30, 40, 50, 60])
    time = random.choice([2, 3, 4])
    answer = speed * time
    correct, distractors = _numeric_options(answer, " km")
    return _mcq(
        request,
        f"A cyclist travels at {speed} km/h for {time} hours at a constant speed. What distance does the cyclist cover?",
        correct,
        distractors,
        f"Distance = speed x time = {speed} x {time} = {answer} km.",
    )


def generate_algebra(request: QuestionGenerationRequest) -> GeneratedQuestion:
    answer = random.choice(range(5, 31))
    addend = random.choice(range(3, 16))
    right_side = 3 * answer + addend
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"Solve for x: 3x + {addend} = {right_side}.",
        correct,
        distractors,
        f"Subtract {addend} from both sides: 3x = {3 * answer}. Therefore x = {answer}.",
    )


def generate_number_system(request: QuestionGenerationRequest) -> GeneratedQuestion:
    divisor = random.choice([5, 6, 7, 8, 9])
    quotient = random.choice(range(8, 25))
    remainder = random.choice(range(1, divisor))
    number = divisor * quotient + remainder
    correct, distractors = _numeric_options(remainder)
    return _mcq(
        request,
        f"What is the remainder when {number} is divided by {divisor}?",
        correct,
        distractors,
        f"{number} = {divisor} x {quotient} + {remainder}, so the remainder is {remainder}.",
    )


def generate_reading_comprehension(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Passage: A city library replaced late fines with reminder messages. Borrowers returned more books on time, while membership rose among students who had previously avoided borrowing. Which is the best central idea?",
        "Removing a small barrier can increase participation without reducing responsible behaviour.",
        [
            "Libraries should stop tracking borrowed books.",
            "Students are the only people who return books late.",
            "Reminder messages are more expensive than late fines.",
        ],
        "The passage links fewer fines with more borrowing and better return behaviour, supporting the broader idea about removing barriers.",
    )


def generate_para_summary(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "A neighbourhood market introduced shared delivery routes for small vendors. The vendors retained their own customers but combined nearby orders into one trip. Fuel use fell, and customers still received their purchases on the same day. Choose the best summary.",
        "Coordinated delivery can reduce costs while preserving independent businesses and service quality.",
        [
            "Small vendors should merge into one company.",
            "Same-day delivery always increases fuel use.",
            "Customers care only about the price of deliveries.",
        ],
        "The paragraph focuses on shared logistics creating efficiency without removing vendor independence or timely delivery.",
    )


def generate_odd_sentence(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Which sentence is the odd one out in a paragraph about testing a new community garden?",
        "The mountain trail was closed after heavy rainfall.",
        [
            "Volunteers first measured the amount of sunlight in each plot.",
            "They then planted the same seeds in the selected plots.",
            "After six weeks, they compared the height of the plants.",
        ],
        "Three sentences describe the garden experiment in sequence. The mountain-trail sentence is unrelated.",
    )


def generate_para_jumbles(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Arrange the following sentences into the most logical order: (1) The team first listed every recurring complaint. (2) It then tested one small change for each complaint. (3) Finally, it kept the changes that reduced support requests. (4) The review began after the team noticed a rise in support requests.",
        "4-1-2-3",
        ["1-4-2-3", "4-2-1-3", "1-2-3-4"],
        "The rise in requests triggers the review, followed by listing issues, testing changes, and retaining successful changes.",
    )


def generate_tables(request: QuestionGenerationRequest) -> GeneratedQuestion:
    north = random.choice(range(40, 81, 10))
    south = north - random.choice([5, 10, 15])
    east = north + random.choice([5, 10, 15])
    answer = east
    correct, distractors = _numeric_options(answer)
    return _mcq(
        request,
        f"A table lists completed tasks: North {north}, South {south}, East {east}. Which region completed the highest number of tasks?",
        f"East ({correct})",
        [f"North ({north})", f"South ({south})", "All regions completed the same number"],
        f"East completed {east} tasks, which is more than North ({north}) and South ({south}).",
    )


def generate_arrangements(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Four people—Anu, Dev, Isha, and Rohan—sit in a row. Anu sits immediately left of Dev. Isha sits at the far right. Who can sit at the far left?",
        "Rohan",
        ["Anu", "Dev", "Isha"],
        "Isha must be at the far right, and Anu-Dev must occupy adjacent seats in that order. Rohan can therefore take the far-left seat.",
    )


def generate_distribution(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Twelve identical notebooks are distributed equally among three clubs. How many notebooks does each club receive?",
        "4",
        ["3", "5", "6"],
        "Equal distribution means 12 divided by 3, which is 4.",
    )


def generate_selection(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "A committee of two must be selected from Aria, Bhav, and Chitra. Aria and Bhav cannot be selected together. Which pair can be selected?",
        "Aria and Chitra",
        ["Aria and Bhav", "Bhav and Aria", "No pair can be selected"],
        "The only restriction excludes Aria and Bhav together. Aria and Chitra is therefore a valid pair.",
    )


def generate_games(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "In a round-robin mini tournament, each of four teams plays every other team exactly once. How many matches are played?",
        "6",
        ["4", "8", "12"],
        "The number of unique pairings among four teams is 4 x 3 / 2 = 6.",
    )


def generate_data_comparison(request: QuestionGenerationRequest) -> GeneratedQuestion:
    return _mcq(
        request,
        "Team A completed 36 tasks in three days. Team B completed 48 tasks in four days. Which statement is correct?",
        "Both teams completed 12 tasks per day on average.",
        [
            "Team A completed more tasks per day on average.",
            "Team B completed more tasks per day on average.",
            "Neither team's daily average can be calculated.",
        ],
        "Team A's average is 36/3 = 12 and Team B's is 48/4 = 12 tasks per day.",
    )


TEMPLATES: dict[tuple[str, str, str], Template] = {
    ("QA", "Arithmetic", "Percentages"): generate_percentages,
    ("QA", "Arithmetic", "Profit & Loss"): generate_profit_loss,
    ("QA", "Arithmetic", "Ratio"): generate_ratio,
    ("QA", "Arithmetic", "Averages"): generate_averages,
    ("QA", "Arithmetic", "Time & Work"): generate_time_work,
    ("QA", "Arithmetic", "Time, Speed & Distance"): generate_tsd,
    ("QA", "Algebra", "Algebra"): generate_algebra,
    ("QA", "Number System", "Number System"): generate_number_system,
    ("VARC", "Reading Comprehension", "Reading Comprehension"): generate_reading_comprehension,
    ("VARC", "Verbal Ability", "Para Summary"): generate_para_summary,
    ("VARC", "Verbal Ability", "Odd Sentence Out"): generate_odd_sentence,
    ("VARC", "Verbal Ability", "Para Jumbles"): generate_para_jumbles,
    ("DILR", "Data Interpretation", "Tables"): generate_tables,
    ("DILR", "Logical Reasoning", "Arrangements"): generate_arrangements,
    ("DILR", "Logical Reasoning", "Distribution"): generate_distribution,
    ("DILR", "Logical Reasoning", "Selection"): generate_selection,
    ("DILR", "Logical Reasoning", "Games/Tournaments"): generate_games,
    ("DILR", "Data Interpretation", "Data Comparison"): generate_data_comparison,
}


def generate_question(request: QuestionGenerationRequest) -> GeneratedQuestion:
    """Generate one original question for an already-validated request."""
    return TEMPLATES[(request.section, request.topic, request.subtopic)](request)
