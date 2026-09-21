import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import MockReviewView from "./views/MockReviewView.jsx";
import MockResultView from "./views/MockResultView.jsx";
import MockSelectionView from "./views/MockSelectionView.jsx";
import MockTestView from "./views/MockTestView.jsx";

const callbacks = { onBack: vi.fn(), onStart: vi.fn(), onAnswer: vi.fn(), onRefresh: vi.fn(), onSubmitSection: vi.fn(), onFinish: vi.fn() };
const question = { question_id: 1, question_order: 1, section: "QA", topic: "Arithmetic", subtopic: "Percentages", difficulty: "Medium", question_text: "A synthetic question?", options: { A: "10", B: "20", C: "30", D: "40" }, answered: false, selected_answer: null, marked_for_review: false };

const mock = { mock_id: "cat-v2-mock-1", title: "CAT Full Mock 01", total_questions: 9, sections: { VARC: 3, DILR: 3, QA: 3 }, section_order: ["VARC", "DILR", "QA"], section_time_limit: { VARC: 900, DILR: 900, QA: 900 }, total_time_limit: 2700, status: "NOT_STARTED" };

const session = { id: 4, mock_id: mock.mock_id, title: mock.title, status: "IN_PROGRESS", current_section: "QA", section_order: ["QA"], section_remaining_seconds: 900, total_elapsed_seconds: 20, total_time_limit: 900, questions: [question] };
const result = { mock_session_id: 4, status: "COMPLETED", attempted: 1, correct: 1, incorrect: 0, unanswered: 0, accuracy: 100, total_time_seconds: 20, sections: [{ section: "QA", attempted: 1, correct: 1, incorrect: 0, unanswered: 0, accuracy: 100, time_used_seconds: 20 }], topics: [{ topic: "Arithmetic", attempted: 1, correct: 1, accuracy: 100 }], difficulties: [{ difficulty: "Medium", attempted: 1, correct: 1, accuracy: 100 }], strongest_section: "QA", weakest_section: "QA", strongest_topics: ["Arithmetic"], topics_needing_practice: [], time_management_observations: [] };
const review = { mock_session_id: 4, questions: [{ question_id: 1, question_order: 1, section: "QA", topic: "Arithmetic", question_text: "A synthetic question?", options: question.options, selected_answer: "A", correct_answer: "A", is_correct: true, explanation: { short_answer: "The answer is 10.", approach: "Apply the stated relationship.", steps: ["Read the values.", "Match the result."], shortcut: "Estimate first.", common_mistake: "Skipping the final check.", difficulty_note: "Medium." } }] };

describe("mock views", () => {
  it("renders mock selection configuration", () => {
    const html = renderToStaticMarkup(<MockSelectionView {...callbacks} initialMocks={[mock]} />);
    expect(html).toContain("CAT Full Mock 01");
    expect(html).toContain("9");
    expect(html).toContain("Start full mock");
  });

  it("renders timed mock questions and navigation state", () => {
    const html = renderToStaticMarkup(<MockTestView {...callbacks} session={session} />);
    expect(html).toContain("QA section");
    expect(html).toContain("15:00");
    expect(html).toContain("A synthetic question?");
    expect(html).toContain("Mark for revisit");
  });

  it("renders mock result analysis", () => {
    const html = renderToStaticMarkup(<MockResultView {...callbacks} result={result} />);
    expect(html).toContain("Mock complete");
    expect(html).toContain("100%");
    expect(html).toContain("Section analysis");
    expect(html).toContain("not a CAT percentile or rank prediction");
  });

  it("renders mock review with answer and explanation", () => {
    const html = renderToStaticMarkup(<MockReviewView review={review} onBack={callbacks.onBack} />);
    expect(html).toContain("Mock review");
    expect(html).toContain("Correct answer");
    expect(html).toContain("The answer is 10.");
    expect(html).toContain("Estimate first.");
  });
});
