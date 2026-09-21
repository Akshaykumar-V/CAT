export default function ProgressBar({ value = 0, tone = "teal", label, detail }) {
  const safeValue = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className="progress-row">
      <div className="progress-heading"><span>{label}</span><strong>{detail ?? `${safeValue.toFixed(0)}%`}</strong></div>
      <div className="progress-track"><span className={`progress-fill tone-${tone}`} style={{ width: `${safeValue}%` }} /></div>
    </div>
  );
}
