import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const formatClock = (seconds) => `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.max(0, seconds % 60).toString().padStart(2, "0")}`;

export default function PracticeView({ session, onFinish, onExit }) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState(() => Object.fromEntries(session.questions.filter((question) => question.selected_answer).map((question) => [question.question_id, question.selected_answer])));
  const [remaining, setRemaining] = useState(Math.max(0, session.time_limit_seconds - Math.floor((Date.now() - new Date(session.started_at).getTime()) / 1000)));
  const [saving, setSaving] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState("");
  const question = session.questions[current];
  const answeredCount = Object.keys(answers).length;
  const progress = useMemo(() => ((current + 1) / session.questions.length) * 100, [current, session.questions.length]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - new Date(session.started_at).getTime()) / 1000);
      setRemaining(Math.max(0, session.time_limit_seconds - elapsed));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session.started_at, session.time_limit_seconds]);

  const chooseAnswer = async (label) => {
    if (answers[question.question_id] || saving) return;
    setAnswers((previous) => ({ ...previous, [question.question_id]: label }));
    setSaving(true);
    setError("");
    try {
      await api.submitAnswer(session.id, { question_id: question.question_id, selected_answer: label, time_spent_seconds: Math.max(0, session.time_limit_seconds - remaining) });
    } catch (requestError) {
      setAnswers((previous) => {
        const next = { ...previous };
        delete next[question.question_id];
        return next;
      });
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const finish = async () => {
    setFinishing(true);
    setError("");
    try {
      await onFinish();
    } catch (requestError) {
      setError(requestError.message);
      setFinishing(false);
    }
  };

  return (
    <div className="practice-layout reveal">
      <div className="practice-topbar"><button className="back-link" onClick={onExit}>← Exit practice</button><div className={remaining < 60 ? "timer danger" : "timer"}><span>◷</span>{formatClock(remaining)}</div><div className="practice-count"><strong>{answeredCount}</strong> / {session.questions.length} answered</div></div>
      <div className="practice-progress"><span style={{ width: `${progress}%` }} /></div>
      {error && <div className="inline-error" role="alert">{error}</div>}
      <div className="question-layout">
        <aside className="question-index panel"><p className="eyebrow">Question map</p><div className="question-grid">{session.questions.map((item, index) => <button key={item.question_id} className={`${index === current ? "current " : ""}${answers[item.question_id] ? "answered" : ""}`} onClick={() => setCurrent(index)} aria-label={`Question ${index + 1}${answers[item.question_id] ? ", answered" : ", unanswered"}`}>{String(index + 1).padStart(2, "0")}</button>)}</div><div className="legend"><span><i className="legend-current" /> Current</span><span><i className="legend-answered" /> Answered</span></div></aside>
        <section className="question-card"><div className="question-meta"><span>Question {String(current + 1).padStart(2, "0")}</span><span>{session.section} · {session.difficulty}</span></div><h1>{question.question_text}</h1><div className="options" role="group" aria-label="Answer options">{Object.entries(question.options).map(([label, text]) => <button key={label} className={answers[question.question_id] === label ? "option selected" : "option"} onClick={() => chooseAnswer(label)} disabled={Boolean(answers[question.question_id]) || saving}><span className="option-label">{label}</span><span>{text}</span>{answers[question.question_id] === label && <span className="option-check">✓</span>}</button>)}</div><div className="question-actions"><button className="button button-outline" disabled={current === 0} onClick={() => setCurrent((value) => value - 1)}>← Previous</button>{current < session.questions.length - 1 ? <button className="button button-dark" onClick={() => setCurrent((value) => value + 1)}>Next question →</button> : <button className="button button-coral" disabled={finishing} onClick={finish}>{finishing ? "Finishing..." : "Finish practice"}</button>}</div></section>
      </div>
    </div>
  );
}
