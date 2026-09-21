import { useEffect, useState } from "react";
import { api } from "./api";
import DashboardView from "./views/DashboardView";
import PerformanceView from "./views/PerformanceView";
import PracticeView from "./views/PracticeView";
import ResultsView from "./views/ResultsView";
import SetupView from "./views/SetupView";

const EMPTY_DASHBOARD = {
  overall: {
    attempted: 0,
    correct: 0,
    accuracy: 0,
    average_time_seconds: 0,
    total_practice_sessions: 0,
    questions_solved_by_section: {},
  },
  sections: [],
  strong_topics: [],
  developing_topics: [],
  needs_practice: [],
  difficulty: [],
  recurring_mistakes: [],
};

function AppHeader({ view, onNavigate }) {
  const navItems = [
    ["dashboard", "Dashboard"],
    ["performance", "Performance"],
  ];

  return (
    <header className="app-header">
      <button className="brand" onClick={() => onNavigate("dashboard")} aria-label="Go to dashboard">
        <span className="brand-mark">C</span>
        <span>CAT Prep <em>AI</em></span>
      </button>
      <nav className="main-nav" aria-label="Main navigation">
        {navItems.map(([key, label]) => (
          <button
            className={view === key ? "nav-link active" : "nav-link"}
            key={key}
            onClick={() => onNavigate(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="header-context">Personal CAT Practice Dashboard</div>
      <div className="header-status"><span className="status-dot" /> Study mode</div>
    </header>
  );
}

function LoadingState({ label = "Reading your study data" }) {
  return (
    <div className="state-panel loading-state">
      <span className="loader" />
      <p>{label}<span className="loading-dots">...</span></p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="state-panel error-state">
      <span className="state-icon">!</span>
      <div>
        <h2>Could not reach your study desk</h2>
        <p>{message}</p>
        <button className="button button-dark" onClick={onRetry}>Try again</button>
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [dashboard, setDashboard] = useState(EMPTY_DASHBOARD);
  const [recommendation, setRecommendation] = useState(null);
  const [topics, setTopics] = useState([]);
  const [patterns, setPatterns] = useState(null);
  const [session, setSession] = useState(null);
  const [result, setResult] = useState(null);
  const [resultTopics, setResultTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const loadStudyData = () => {
    setLoading(true);
    setError("");
    Promise.all([
      api.performanceDashboard(),
      api.getRecommendation(),
      api.performanceTopics(),
      api.analysisPatterns().catch(() => null),
    ])
      .then(([nextDashboard, nextRecommendation, nextTopics, nextPatterns]) => {
        setDashboard(nextDashboard);
        setRecommendation(nextRecommendation);
        setTopics(nextTopics);
        setPatterns(nextPatterns);
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStudyData();
  }, []);

  const startSession = async (setup) => {
    setStarting(true);
    setError("");
    try {
      const nextSession = setup.adaptive
        ? await api.startAdaptivePractice(setup)
        : await api.startPractice(setup);
      setSession(nextSession);
      setView("practice");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStarting(false);
    }
  };

  const finishSession = async () => {
    const nextResult = await api.finishSession(session.id);
    const nextTopics = await api.performanceTopics();
    setResult(nextResult);
    setResultTopics(nextTopics);
    setSession(null);
    setView("results");
    loadStudyData();
  };

  const navigate = (nextView) => {
    setError("");
    setView(nextView);
  };

  if (loading) {
    return <div className="app-frame"><LoadingState /></div>;
  }

  if (error && !session) {
    return (
      <div className="app-frame">
        <AppHeader view={view} onNavigate={navigate} />
        <ErrorState message={error} onRetry={loadStudyData} />
      </div>
    );
  }

  return (
    <div className="app-frame">
      <AppHeader view={view} onNavigate={navigate} />
      {error && <div className="inline-error" role="alert">{error}</div>}
      <main className="page-shell">
        {view === "dashboard" && (
          <DashboardView
            dashboard={dashboard}
            recommendation={recommendation}
            topics={topics}
            patterns={patterns}
            onStart={() => setView("setup")}
            onNavigate={navigate}
          />
        )}
        {view === "setup" && (
          <SetupView onStart={startSession} onBack={() => setView("dashboard")} starting={starting} />
        )}
        {view === "practice" && session && (
          <PracticeView session={session} onFinish={finishSession} onExit={() => setView("dashboard")} />
        )}
        {view === "results" && (
          <ResultsView result={result} topics={resultTopics} onPractice={() => setView("setup")} onDashboard={() => { loadStudyData(); setView("dashboard"); }} />
        )}
        {view === "performance" && (
          <PerformanceView dashboard={dashboard} recommendation={recommendation} topics={topics.length ? topics : dashboard.needs_practice.concat(dashboard.developing_topics, dashboard.strong_topics)} onRefresh={loadStudyData} />
        )}
      </main>
    </div>
  );
}
