import { useEffect, useState } from "react";
import { api } from "../api";

const formatTime = (seconds) => `${Math.floor(seconds / 60)}m ${seconds % 60}s`;

export default function MockSelectionView({ onStart, onBack, initialMocks = null }) {
  const [mocks, setMocks] = useState(initialMocks || []);
  const [loading, setLoading] = useState(!initialMocks);
  const [starting, setStarting] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialMocks) {
      setLoading(false);
      return undefined;
    }
    api.listMocks().then(setMocks).catch((requestError) => setError(requestError.message)).finally(() => setLoading(false));
    return undefined;
  }, [initialMocks]);

  const start = async (mock) => {
    setStarting(mock.mock_id);
    setError("");
    try {
      await onStart(mock.mock_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStarting("");
    }
  };

  return <div className="mock-selection view-stack reveal"><button className="back-link" onClick={onBack}>← Dashboard</button><div className="page-heading"><div><p className="eyebrow">Full mock mode</p><h1>Practice the<br /><span>whole paper.</span></h1><p className="lede">A timed, section-by-section mock built from validated original questions.</p></div></div>{error && <div className="inline-error" role="alert">{error}</div>}{loading ? <div className="state-panel loading-state"><span className="loader" /><p>Loading available mocks...</p></div> : mocks.length ? <div className="mock-catalog">{mocks.map((mock) => <article className="mock-card" key={mock.mock_id}><div className="mock-card-top"><div><p className="eyebrow">Configured mock</p><h2>{mock.title}</h2></div><span className="mock-status">{mock.status === "IN_PROGRESS" ? "In progress" : "Ready"}</span></div><div className="mock-facts"><span><strong>{mock.total_questions}</strong> questions</span><span><strong>{formatTime(mock.total_time_limit)}</strong> total time</span><span><strong>{mock.section_order.join(" · ")}</strong> sections</span></div><div className="mock-sections">{mock.section_order.map((section) => <div key={section}><strong>{section}</strong><span>{mock.sections[section]} questions · {formatTime(mock.section_time_limit[section])}</span></div>)}</div><button className="button button-coral" disabled={Boolean(starting)} onClick={() => start(mock)}>{starting === mock.mock_id ? "Preparing mock..." : "Start full mock ↗"}</button></article>)}</div> : <div className="state-panel"><h2>No mocks available</h2><p className="empty-copy">A configured mock will appear here when the question catalog is ready.</p></div>}</div>;
}
