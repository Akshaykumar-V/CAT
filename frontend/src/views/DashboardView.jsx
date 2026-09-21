import MetricCard from "../components/MetricCard";
import PatternChart, { patternOccurrence } from "../components/PatternChart";
import ProgressBar from "../components/ProgressBar";
import TopicRow from "../components/TopicRow";

const SECTION_TONES = { VARC: "teal", DILR: "yellow", QA: "coral" };

function formatTime(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value)) return "—";
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}
function SectionPerformance({ sections, hasHistory, onNavigate }) {
  return <section className="panel section-panel dashboard-section-panel">
    <div className="panel-heading"><div><p className="eyebrow">Personal overview</p><h2>Section performance</h2></div><button className="text-button" onClick={() => onNavigate("performance")}>View detail <span>→</span></button></div>
    {hasHistory ? <div className="section-performance-list">{sections.map((section) => <div className="section-performance" key={section.section}><div className="section-performance-heading"><strong>{section.section}</strong><span>{section.attempted ? `${Number(section.accuracy || 0).toFixed(0)}% accuracy` : "No attempts"}</span></div>{section.attempted ? <><ProgressBar value={section.accuracy} tone={SECTION_TONES[section.section] || "teal"} label={`${section.attempted} attempted`} detail={`${formatTime(section.average_time_seconds)} avg`} /><div className="section-meta"><span>{section.attempted} attempted</span><span>{formatTime(section.average_time_seconds)} / question</span></div></> : <p className="section-empty">No completed attempts yet.</p>}</div>)}</div> : <p className="empty-copy">Complete a practice session to see VARC, DILR, and QA performance here.</p>}
  </section>;
}

function TopicGroup({ title, topics, tone, emptyText }) {
  return <section className="panel topic-panel"><div className="panel-heading"><div><p className="eyebrow">Personal signal</p><h2>{title}</h2></div><span className={`pill pill-${tone}`}>{topics.length}</span></div>{topics.length ? topics.slice(0, 5).map((topic) => <TopicRow key={topic.topic} topic={topic} tone={tone} reason={`${topic.attempted || 0} attempts · ${formatTime(topic.average_time_seconds)} avg`} />) : <p className="empty-copy">{emptyText}</p>}</section>;
}

function HistoricalVsPersonal({ patterns, topics }) {
  const historicalTopics = patterns?.topics || {};
  const total = Object.values(historicalTopics).reduce((sum, value) => sum + Number(value), 0);
  const personalByTopic = Object.fromEntries((topics || []).map((topic) => [topic.topic, topic]));
  const rows = Object.entries(historicalTopics).sort(([, first], [, second]) => second - first).slice(0, 6);

  return <section className="panel comparison-panel"><div className="panel-heading"><div><p className="eyebrow">Context, not prediction</p><h2>Historical vs personal</h2></div></div>{rows.length ? <div className="comparison-table"><div className="comparison-row comparison-header"><span>Topic</span><span>Historical pattern</span><span>Your accuracy</span></div>{rows.map(([topic, count]) => <div className="comparison-row" key={topic}><strong>{topic}</strong><span>{patternOccurrence(Number(count), total)}</span><strong className={personalByTopic[topic] ? "comparison-score" : "comparison-muted"}>{personalByTopic[topic] ? `${Number(personalByTopic[topic].accuracy || 0).toFixed(0)}%` : "No attempts"}</strong></div>)}</div> : <p className="empty-copy">Historical CAT Pattern Data will appear when metadata is available.</p>}</section>;
}

export default function DashboardView({ dashboard, recommendation, topics, patterns, onStart, onNavigate }) {
  const overall = dashboard.overall || {};
  const hasHistory = Number(overall.total_practice_sessions) > 0;
  const historicalAvailable = Boolean(patterns && Object.keys(patterns.topics || {}).length);
  const recommended = recommendation?.recommended_topics?.[0];
  const recommendedDifficulty = recommendation?.recommended_difficulties?.[0];
  const personalTopics = topics || [];

  return <div className="dashboard-view view-stack">
    <section className="dashboard-hero reveal"><div><p className="eyebrow">CAT Prep AI</p><h1>Personal CAT<br /><span>Practice Dashboard.</span></h1><p className="lede">A clear read on your preparation, with your practice history beside the patterns found in the metadata.</p></div><button className="button button-coral button-large" onClick={onStart}><span>↗</span> Start Adaptive Practice</button></section>

    {!hasHistory && <div className="empty-banner"><span className="empty-spark">✦</span><div><strong>Your personal map starts with one session.</strong><p>No practice statistics are shown until you complete a session.</p></div><button className="text-button" onClick={onStart}>Begin practice <span>→</span></button></div>}

    <section className="metric-grid reveal reveal-delay-1"><MetricCard label="Questions solved" value={hasHistory ? overall.attempted : "—"} detail={hasHistory ? `${overall.correct} correct` : "No practice history"} accent="coral" /><MetricCard label="Overall accuracy" value={hasHistory ? `${Number(overall.accuracy).toFixed(1)}%` : "—"} detail={hasHistory ? "Completed sessions" : "No practice history"} accent="teal" /><MetricCard label="Average time / question" value={hasHistory ? formatTime(overall.average_time_seconds) : "—"} detail={hasHistory ? "Across attempted questions" : "No practice history"} accent="yellow" /><MetricCard label="Practice sessions" value={hasHistory ? overall.total_practice_sessions : "—"} detail={hasHistory ? "Completed sessions" : "No practice history"} accent="ink" /></section>

    <div className="dashboard-main-grid reveal reveal-delay-2"><SectionPerformance sections={dashboard.sections || []} hasHistory={hasHistory} onNavigate={onNavigate} /><section className="recommendation-panel dashboard-recommendation"><p className="eyebrow">Today's recommendation</p><h2>{recommended ? `${recommended.topic} is the next useful rep.` : "Build your first signal."}</h2>{recommended ? <><div className="recommendation-focus"><span className="recommendation-icon">↗</span><div><strong>{recommendation.section || "QA"} — {recommended.topic}</strong><p>{recommended.reason || "Based on your personal practice performance."}</p></div></div><div className="recommendation-specs"><span><b>Difficulty</b>{recommendedDifficulty || "Adaptive"}</span><span><b>Questions</b>10</span></div><button className="button button-coral full-button" onClick={onStart}>Start adaptive set</button></> : <><p className="empty-copy">Finish a session to receive a recommendation based on your own performance.</p><button className="button button-coral full-button" onClick={onStart}>Start first session</button></>}</section></div>

    <div className="topic-groups-grid reveal reveal-delay-3"><TopicGroup title="Weak topics" topics={dashboard.needs_practice || []} tone="coral" emptyText={hasHistory ? "Nothing needs urgent attention yet." : "Weak topics will appear after completed practice."} /><TopicGroup title="Strong topics" topics={dashboard.strong_topics || []} tone="teal" emptyText={hasHistory ? "Keep practicing to build strong topics." : "Strong topics will appear after completed practice."} /></div>

    <section className="historical-band reveal"><div className="historical-heading"><div><p className="eyebrow">Historical CAT Pattern Data</p><h2>Read the archive without treating it as a forecast.</h2></div><span className="historical-note">Metadata patterns only · not next-exam predictions</span></div>{historicalAvailable ? <div className="pattern-chart-grid"><PatternChart title="Topic distribution" eyebrow="Occurrence" data={patterns.topics} tone="teal" /><PatternChart title="Difficulty distribution" eyebrow="Level mix" data={patterns.difficulty} tone="yellow" /><PatternChart title="Question types" eyebrow="Format mix" data={patterns.question_types} tone="coral" /><PatternChart title="Section distribution" eyebrow="Section mix" data={patterns.sections} tone="ink" /></div> : <div className="historical-empty"><p className="empty-copy">No historical metadata is available yet. Personal practice remains available.</p></div>}</section>

    <HistoricalVsPersonal patterns={patterns} topics={personalTopics} />
  </div>;
}
