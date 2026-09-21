export default function MetricCard({ label, value, detail, accent = "teal" }) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      {detail && <span>{detail}</span>}
    </article>
  );
}
