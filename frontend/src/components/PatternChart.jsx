function formatLabel(value) {
  return String(value).replaceAll("_", " ");
}

export default function PatternChart({ title, eyebrow, data = {}, tone = "teal", emptyText = "No metadata available yet." }) {
  const entries = Object.entries(data).filter(([, value]) => Number(value) > 0);
  const maximum = Math.max(...entries.map(([, value]) => Number(value)), 1);

  return (
    <section className="pattern-chart">
      <div className="chart-heading">
        <div><p className="eyebrow">{eyebrow}</p><h3>{title}</h3></div>
        {entries.length > 0 && <span className="chart-count">{entries.reduce((sum, [, value]) => sum + Number(value), 0)} records</span>}
      </div>
      {entries.length ? <div className="bar-list">{entries.map(([label, value]) => <div className="bar-row" key={label}><div className="bar-label"><span>{formatLabel(label)}</span><strong>{value}</strong></div><div className="bar-track"><span className={`bar-fill tone-${tone}`} style={{ width: `${(Number(value) / maximum) * 100}%` }} /></div></div>)}</div> : <p className="empty-copy">{emptyText}</p>}
    </section>
  );
}

export function patternOccurrence(count, total) {
  const share = total ? count / total : 0;
  if (share >= 0.2) return "High occurrence";
  if (share >= 0.1) return "Moderate occurrence";
  return "Light occurrence";
}
