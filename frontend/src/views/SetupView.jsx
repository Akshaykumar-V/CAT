import { useState } from "react";

const sections = [
  ["VARC", "Verbal ability & reading"],
  ["DILR", "Data interpretation & logic"],
  ["QA", "Quantitative aptitude"],
];

export default function SetupView({ onStart, onBack, starting }) {
  const [section, setSection] = useState("QA");
  const [questionCount, setQuestionCount] = useState(10);
  const [timeLimit, setTimeLimit] = useState(1200);

  const submit = (adaptive) => onStart({ section, question_count: Number(questionCount), time_limit_seconds: Number(timeLimit), adaptive });

  return (
    <div className="setup-layout reveal">
      <button className="back-link" onClick={onBack}>← Dashboard</button>
      <div className="setup-intro"><p className="eyebrow">Practice setup</p><h1>Choose your<br /><span>next rep.</span></h1><p className="lede">Set a pace that feels challenging, then let the questions do the work.</p></div>
      <div className="setup-form panel">
        <div className="form-block"><label>Section</label><div className="section-picker">{sections.map(([value, description]) => <button type="button" key={value} className={section === value ? "section-option selected" : "section-option"} onClick={() => setSection(value)}><strong>{value}</strong><span>{description}</span></button>)}</div></div>
        <div className="form-row"><div className="form-block"><label htmlFor="question-count">Questions</label><select id="question-count" value={questionCount} onChange={(event) => setQuestionCount(event.target.value)}><option value="5">5 questions</option><option value="10">10 questions</option><option value="15">15 questions</option><option value="20">20 questions</option></select></div><div className="form-block"><label htmlFor="time-limit">Time limit</label><select id="time-limit" value={timeLimit} onChange={(event) => setTimeLimit(event.target.value)}><option value="600">10 minutes</option><option value="1200">20 minutes</option><option value="1800">30 minutes</option><option value="2400">40 minutes</option></select></div></div>
        <div className="setup-actions"><button className="button button-coral button-large full-button" disabled={starting} onClick={() => submit(true)}>{starting ? "Preparing..." : "Adaptive Practice ↗"}</button><button className="button button-outline full-button" disabled={starting} onClick={() => submit(false)}>Standard practice</button></div>
        <p className="form-note"><span>i</span> Adaptive practice uses your completed sessions to choose topics and difficulty. No predictions, just useful repetition.</p>
      </div>
    </div>
  );
}
