export default function TopicRow({ topic, tone = "teal", reason }) {
  return (
    <div className="topic-row">
      <div className={`topic-bullet tone-${tone}`} />
      <div className="topic-copy"><strong>{topic.topic}</strong>{reason && <span>{reason}</span>}</div>
      <strong className="topic-score">{Number(topic.accuracy || 0).toFixed(0)}%</strong>
    </div>
  );
}
