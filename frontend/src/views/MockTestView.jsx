import { useEffect, useState } from "react";

const formatClock = (seconds) => `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.max(0, seconds % 60).toString().padStart(2, "0")}`;

export default function MockTestView({ session, onAnswer, onRefresh, onSubmitSection, onFinish }) {
  const [current, setCurrent] = useState(0);
  const [remaining, setRemaining] = useState(session.section_remaining_seconds);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const question = session.questions[current];
  const answered = session.questions.filter((item) => item.answered).length;

  useEffect(() => {
    setRemaining(session.section_remaining_seconds);
    setCurrent(0);
  }, [session.id, session.current_section, session.section_remaining_seconds]);

  useEffect(() => {
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [session.current_section]);

  useEffect(() => {
    if (remaining === 0 && session.status === "IN_PROGRESS") onRefresh();
  }, [remaining, session.status, onRefresh]);

  const answer = async (label) => {
    if (saving || question.answered) return;
    setSaving(true);
    setError("");
    try {
      const next = await onAnswer({ question_id: question.question_id, selected_answer: label, time_spent_seconds: Math.max(0, session.total_time_limit - remaining) });
      if (next) setCurrent(Math.min(current + 1, next.questions.length - 1));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const mark = async () => {
    setError("");
    try {
      await onAnswer({ question_id: question.question_id, marked_for_review: !question.marked_for_review });
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  if (!question) return <div className="state-panel"><h2>Section complete</h2><button className="button button-dark" onClick={onSubmitSection}>Continue</button></div>;

  return <div className="mock-test-layout reveal"><div className="mock-topbar"><div><p className="eyebrow">{session.title}</p><strong>{session.current_section} section</strong><span>{answered} / {session.questions.length} answered</span></div><div className={remaining < 60 ? "timer danger" : "timer"}><span>◷</span>{formatClock(remaining)}</div></div>{error && <div className="inline-error" role="alert">{error}</div>}<div className="mock-progress"><span style={{ width: `${(answered / session.questions.length) * 100}%` }} /></div><div className="mock-question-layout"><aside className="mock-question-index panel"><p className="eyebrow">Question map</p><div className="question-grid">{session.questions.map((item, index) => <button key={item.question_id} className={`${index === current ? "current " : ""}${item.answered ? "answered " : ""}${item.marked_for_review ? "marked" : ""}`} onClick={() => setCurrent(index)} aria-label={`Question ${index + 1}${item.answered ? ", answered" : ", unanswered"}`}>{String(index + 1).padStart(2, "0")}</button>)}</div><p className="mock-index-note">Answered questions are saved by the server. Mark a question to revisit it before submitting the section.</p></aside><section className="mock-question-card"><div className="question-meta"><span>Question {String(current + 1).padStart(2, "0")} / {session.questions.length}</span><span>{question.topic} · {question.difficulty}</span></div><h1>{question.question_text}</h1><div className="options" role="group" aria-label="Answer options">{Object.entries(question.options).map(([label, text]) => <button key={label} className={question.selected_answer === label ? "option selected" : "option"} onClick={() => answer(label)} disabled={question.answered || saving}><span className="option-label">{label}</span><span>{text}</span>{question.selected_answer === label && <span className="option-check">✓</span>}</button>)}</div><div className="mock-actions"><button className="button button-outline" onClick={mark}>{question.marked_for_review ? "Unmark revisit" : "Mark for revisit"}</button><div><button className="button button-outline" disabled={current === 0} onClick={() => setCurrent((value) => value - 1)}>← Previous</button>{current < session.questions.length - 1 ? <button className="button button-dark" onClick={() => setCurrent((value) => value + 1)}>Next →</button> : <button className="button button-coral" onClick={onSubmitSection}>Submit section</button>}</div></div><button className="mock-finish-link" onClick={onFinish}>Finish mock early</button></section></div></div>;
}
