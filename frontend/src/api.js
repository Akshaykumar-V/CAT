const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new Error("The backend is unavailable. Start FastAPI and try again.");
  }

  if (!response.ok) {
    let detail = "Something went wrong while talking to the backend.";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the useful generic message when the backend did not return JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

const get = (path) => request(path);
const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => get("/health"),
  analysisOverview: () => get("/analysis/overview"),
  analysisSections: () => get("/analysis/sections"),
  analysisTopics: () => get("/analysis/topics"),
  analysisDifficulty: () => get("/analysis/difficulty"),
  analysisTrends: () => get("/analysis/trends"),
  startPractice: (body) => post("/practice/start", body),
  startAdaptivePractice: (body) => post("/practice/adaptive-start", body),
  getRecommendation: (section) => get(`/practice/recommendation${section ? `?section=${section}` : ""}`),
  getSession: (sessionId) => get(`/practice/${sessionId}`),
  submitAnswer: (sessionId, body) => post(`/practice/${sessionId}/answer`, body),
  getExplanation: (questionId) => get(`/questions/${questionId}/explanation`),
  requestExplanation: (questionId, body) => post(`/questions/${questionId}/explanation`, body),
  finishSession: (sessionId) => post(`/practice/${sessionId}/finish`),
  performanceOverview: () => get("/performance/overview"),
  performanceSections: () => get("/performance/sections"),
  performanceTopics: () => get("/performance/topics"),
  performanceDifficulty: () => get("/performance/difficulty"),
  weakTopics: () => get("/performance/weak-topics"),
  performanceDashboard: () => get("/performance/dashboard"),
  generateQuestion: (body) => post("/questions/generate", body),
  generateQuestionBatch: (body) => post("/questions/generate-batch", body),
};

export { API_BASE_URL, request };
