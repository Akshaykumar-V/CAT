import MetricCard from "../components/MetricCard";
import ProgressBar from "../components/ProgressBar";
import TopicRow from "../components/TopicRow";

const formatTime = (seconds) => {
  const value = Number(seconds) || 0;
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
};

function TopicGroup({ title, topics, tone, emptyText }) {
  return (
    <section className="panel topic-panel">
      <div className="panel-heading"><div><p className="eyebrow">Topic focus</p><h2>{title}</h2></div><span className={`pill pill-${tone}`}>{topics.length}</span></div>
      {topics.length ? topics.slice(0, 4).map((topic) => <TopicRow key={topic.topic} topic={topic} tone={tone} />) : <p className="empty-copy">{emptyText}</p>}
    </section>
  );
}

export default function DashboardView({ dashboard, recommendation, onStart, onNavigate }) {
  const overall = dashboard.overall || {};
  const hasHistory = Number(overall.total_practice_sessions) > 0;
  const sections = dashboard.sections || [];
  const recommended = recommendation?.recommended_topics?.[0];

  return (
    <div className="view-stack">
      <section className="welcome-row reveal">
        <div><p className="eyebrow">Your study desk</p><h1>Build your next<br /><span>breakthrough.</span></h1><p className="lede">A focused snapshot of how your CAT preparation is moving.</p></div>
        <button className="button button-coral button-large" onClick={onStart}><span>↗</span> Start Adaptive Practice</button>
      </section>

      {!hasHistory && <div className="empty-banner"><span className="empty-spark">✦</span><div><strong>Your first practice session is waiting.</strong><p>Complete a session to unlock your accuracy, pace, and topic map.</p></div><button className="text-button" onClick={onStart}>Set up practice <span>→</span></button></div>}

      <section className="metric-grid reveal reveal-delay-1">
        <MetricCard label="Overall accuracy" value={`${Number(overall.accuracy || 0).toFixed(1)}%`} detail={hasHistory ? "Across completed practice" : "No attempts yet"} accent="teal" />
        <MetricCard label="Questions solved" value={overall.attempted || 0} detail={`${overall.correct || 0} correct`} accent="coral" />
        <MetricCard label="Average time" value={formatTime(overall.average_time_seconds)} detail="Per attempted question" accent="yellow" />
        <MetricCard label="Practice sessions" value={overall.total_practice_sessions || 0} detail="Completed sessions" accent="ink" />
      </section>

      <section className="content-grid reveal reveal-delay-2">
        <section className="panel section-panel">
          <div className="panel-heading"><div><p className="eyebrow">The three arenas</p><h2>Section performance</h2></div><button className="text-button" onClick={() => onNavigate("performance")}>View detail <span>→</span></button></div>
          {sections.length ? sections.map((section) => <ProgressBar key={section.section} label={section.section} value={section.accuracy} detail={`${Number(section.accuracy || 0).toFixed(1)}%`} tone={section.section === "QA" ? "coral" : section.section === "DILR" ? "yellow" : "teal"} />) : <p className="empty-copy">Section data will appear after your first session.</p>}
        </section>
        <section className="panel recommendation-panel">
          <p className="eyebrow">Suggested next</p><h2>Keep the rhythm.</h2>
          {recommended ? <><div className="recommendation-topic"><span className="recommendation-icon">↗</span><div><strong>{recommended.topic}</strong><p>{recommended.reason}</p></div><span className="recommendation-score">{Number(recommended.accuracy || 0).toFixed(0)}%</span></div><button className="button button-dark full-button" onClick={onStart}>Practice {recommended.topic}</button></> : <><p className="empty-copy">Your next recommendation will appear here after you have some practice history.</p><button className="button button-dark full-button" onClick={onStart}>Start a session</button></>}
        </section>
      </section>

      <section className="content-grid reveal reveal-delay-3">
        <TopicGroup title="Strong topics" topics={dashboard.strong_topics || []} tone="teal" emptyText="Strong topics will appear as your map fills in." />
        <TopicGroup title="Needs practice" topics={dashboard.needs_practice || []} tone="coral" emptyText="Nothing flagged yet. Keep going." />
      </section>
    </div>
  );
}
