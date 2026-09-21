import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import DashboardView from "./views/DashboardView.jsx";

const callbacks = { onStart: vi.fn(), onNavigate: vi.fn() };

const emptyDashboard = {
  overall: { total_practice_sessions: 0, attempted: 0, correct: 0, accuracy: 0, average_time_seconds: 0 },
  sections: [],
  needs_practice: [],
  strong_topics: [],
};

const populatedDashboard = {
  overall: { total_practice_sessions: 3, attempted: 18, correct: 13, accuracy: 72.2, average_time_seconds: 84 },
  sections: [
    { section: "VARC", accuracy: 80, attempted: 6, average_time_seconds: 72 },
    { section: "DILR", accuracy: 66.7, attempted: 6, average_time_seconds: 91 },
    { section: "QA", accuracy: 70, attempted: 6, average_time_seconds: 89 },
  ],
  needs_practice: [{ topic: "Arithmetic", accuracy: 52, attempted: 8, average_time_seconds: 95 }],
  strong_topics: [{ topic: "Reading Comprehension", accuracy: 84, attempted: 5, average_time_seconds: 70 }],
};

const patterns = {
  topics: { Arithmetic: 5, Algebra: 3, Geometry: 2 },
  difficulty: { Easy: 4, Medium: 5, Hard: 1 },
  question_types: { MCQ: 8, TITA: 2 },
  sections: { QA: 5, VARC: 3, DILR: 2 },
};

function render(props = {}) {
  return renderToStaticMarkup(<DashboardView {...callbacks} dashboard={emptyDashboard} topics={[]} patterns={null} {...props} />);
}

describe("DashboardView", () => {
  it("renders the personal dashboard header and adaptive practice action", () => {
    const html = render();

    expect(html).toContain("Personal CAT");
    expect(html).toContain("Practice Dashboard");
    expect(html).toContain("Start Adaptive Practice");
    expect(html).toContain("Your personal map starts with one session");
  });

  it("renders personal performance data and recommendations", () => {
    const html = render({
      dashboard: populatedDashboard,
      topics: populatedDashboard.needs_practice,
      recommendation: {
        section: "QA",
        recommended_topics: [{ topic: "Arithmetic", accuracy: 52, reason: "Your recent accuracy is below your other QA topics." }],
        recommended_difficulties: ["Medium"],
      },
    });

    expect(html).toContain("18");
    expect(html).toContain("80% accuracy");
    expect(html).toContain("Weak topics");
    expect(html).toContain("Strong topics");
    expect(html).toContain("QA — Arithmetic");
    expect(html).toContain("Medium");
  });

  it("renders historical pattern data and comparison rows", () => {
    const html = render({ dashboard: populatedDashboard, topics: populatedDashboard.needs_practice, patterns });

    expect(html).toContain("Historical CAT Pattern Data");
    expect(html).toContain("Topic distribution");
    expect(html).toContain("Difficulty distribution");
    expect(html).toContain("Historical vs personal");
    expect(html).toContain("Arithmetic");
    expect(html).toContain("52%");
    expect(html).toContain("not next-exam predictions");
  });

  it("does not invent historical statistics when metadata is unavailable", () => {
    const html = render({ dashboard: populatedDashboard });

    expect(html).toContain("No historical metadata is available yet");
    expect(html).not.toContain("Topic distribution");
  });

  it("labels sections without attempts instead of showing zero performance", () => {
    const html = render({ dashboard: { ...populatedDashboard, sections: [{ section: "VARC", attempted: 0, accuracy: 0, average_time_seconds: 0 }] } });

    expect(html).toContain("No attempts");
    expect(html).toContain("No completed attempts yet.");
    expect(html).not.toContain("0% accuracy");
  });
});
