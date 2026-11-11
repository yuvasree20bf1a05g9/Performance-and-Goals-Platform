import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { api } from "../api.js";
import { Badge, Card, EmpLink, ErrorBox, Flags, Kpi, Loading, Notice, Progress, fdate, fmt } from "../components/ui.jsx";

const NEXT = { not_started: "self_submitted", self_submitted: "manager_submitted", manager_submitted: "finalized" };

function FeedbackMatrix({ review }) {
  const comps = [...new Set(review.feedback.map((f) => f.competency_id))].sort();
  const name = Object.fromEntries(review.feedback.map((f) => [f.competency_id, f.competency]));
  const cell = (cid, pred) => review.feedback.filter((f) => f.competency_id === cid && pred(f));
  const conflict = new Set(review.conflicting_competencies);
  return (
    <table>
      <thead><tr><th>Competency</th><th>Self</th><th>Reviewer</th><th>Other managers</th><th>Peers</th></tr></thead>
      <tbody>
        {comps.map((cid) => {
          const self = cell(cid, (f) => f.feedback_type === "self");
          const mgr = cell(cid, (f) => f.feedback_type === "manager" && f.giver_employee_id === review.reviewer_id);
          const other = cell(cid, (f) => f.feedback_type === "manager" && f.giver_employee_id !== review.reviewer_id);
          const peers = cell(cid, (f) => f.feedback_type === "peer");
          return (
            <tr key={cid} className={conflict.has(cid) ? "row-warn" : ""}>
              <td>{name[cid]} {conflict.has(cid) && <Badge value="conflict" tone="warn" />}</td>
              <td>{self.map((f) => f.rating).join(", ") || "—"}</td>
              <td>{mgr.map((f) => f.rating).join(", ") || "—"}</td>
              <td>{other.map((f) => `${f.rating} (${f.giver_employee_id})`).join(", ") || "—"}</td>
              <td>{peers.map((f) => <span key={f.feedback_id} title={f.giver ? f.giver.name : "untraceable"} className={f.giver ? "" : "bad-text"}>{f.rating}{f.giver ? "" : "?"} </span>)}{peers.length === 0 && "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function FeedbackForm({ review, competencies, onDone }) {
  const [v, setV] = useState({ feedback_type: "self", competency_id: competencies[0]?.competency_id, rating: 3, comment: "" });
  const [result, setResult] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post(`/reviews/${review.review_id}/feedback`, { ...v, rating: Number(v.rating) });
      setResult({ ok: true, message: `Feedback ${r.feedback.feedback_id} saved. Missing inputs: ${r.review.missing_inputs || "none"}` });
      onDone();
    } catch (err) { setResult({ ok: false, error: err }); }
  };
  return (
    <form className="form" onSubmit={submit}>
      <Notice result={result} onClose={() => setResult(null)} />
      <div className="form-row">
        <select value={v.feedback_type} onChange={(e) => setV({ ...v, feedback_type: e.target.value })}>{["self", "manager", "peer"].map((t) => <option key={t}>{t}</option>)}</select>
        <select value={v.competency_id} onChange={(e) => setV({ ...v, competency_id: e.target.value })}>{competencies.map((c) => <option key={c.competency_id} value={c.competency_id}>{c.name}</option>)}</select>
        <select value={v.rating} onChange={(e) => setV({ ...v, rating: e.target.value })}>{[1, 2, 3, 4, 5].map((r) => <option key={r}>{r}</option>)}</select>
      </div>
      <textarea required minLength={3} placeholder="Specific, evidence-based comment" value={v.comment} onChange={(e) => setV({ ...v, comment: e.target.value })} />
      <button className="primary" type="submit">Submit feedback</button>
    </form>
  );
}

export default function ReviewDetail() {
  const { id } = useParams();
  const { meta } = useApp();
  const { data: r, error, loading, reload } = useApi(`/reviews/${id}`);
  const [result, setResult] = useState(null);
  if (loading && !r) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const advance = async () => {
    try { await api.post(`/reviews/${r.review_id}/transition`, { to_status: NEXT[r.status] }); setResult({ ok: true, message: `Moved to ${NEXT[r.status]}` }); reload(); }
    catch (err) { setResult({ ok: false, error: err }); }
  };
  return (
    <>
      <div className="crumbs"><Link to="/reviews">Reviews</Link> › <code>{r.review_id}</code></div>
      <h1>Review · {r.employee.name} <span className="muted small">{r.cycle_id}</span></h1>
      <Flags flags={r.flags} />
      <div className="kpis">
        <Kpi label="Status" value={<Badge value={r.status} />} sub={r.is_complete ? "all inputs present" : "incomplete"} />
        <Kpi label="Goal score" value={`${fmt(r.goal_score_pct)}%`} sub={`rating ${fmt(r.goal_rating, 2)} × 60%`} />
        <Kpi label="Competency rating" value={fmt(r.competency_rating, 2)} sub="reviewer average × 40%" />
        <Kpi label="Overall" value={fmt(r.overall_score, 2)} sub={<Badge value={r.overall_rating} />} tone="info" />
      </div>
      <Notice result={result} onClose={() => setResult(null)} />
      <div className="grid2">
        <Card title="Participants & workflow" actions={NEXT[r.status] && r.cycle.status !== "closed" && <button onClick={advance}>Move to {NEXT[r.status].replace("_", " ")} →</button>}>
          <dl className="facts">
            <dt>Employee</dt><dd><EmpLink id={r.employee.employee_id} name={r.employee.name} /> · {r.employee.job_title}</dd>
            <dt>Reviewer</dt><dd><EmpLink id={r.reviewer.employee_id} name={r.reviewer.name} /></dd>
            <dt>Self submitted</dt><dd>{fdate(r.self_submitted_at)}</dd>
            <dt>Manager submitted</dt><dd>{fdate(r.manager_submitted_at)}</dd>
            <dt>Finalized</dt><dd>{fdate(r.finalized_at)}</dd>
            <dt>Missing inputs</dt><dd>{r.missing_inputs ? r.missing_inputs.split(";").map((m) => <Badge key={m} value={m} tone="warn" />) : "none"}</dd>
            <dt>Manager summary</dt><dd>{r.manager_summary || "—"}</dd>
          </dl>
        </Card>
        <Card title="Add feedback (as acting user)">
          {r.cycle.status === "closed" ? <p className="muted">This cycle is closed — feedback is locked.</p> : <FeedbackForm review={r} competencies={meta.competencies} onDone={reload} />}
        </Card>
      </div>
      <Card title="Competency feedback (self vs reviewer vs peers)"><FeedbackMatrix review={r} /></Card>
      <div className="grid2">
        <Card title="Goals in scope">
          <table>
            <tbody>{r.goals.map((g) => (
              <tr key={g.goal_id}><td><Link to={`/goals/${g.goal_id}`}><code>{g.goal_id}</code></Link><div className="small">{g.title}</div></td><td>{g.weight_pct}%</td><td><Badge value={g.status} /></td><td style={{ width: "35%" }}><Progress value={g.progress_pct} /></td></tr>
            ))}</tbody>
          </table>
        </Card>
        <Card title="Audit trail">
          <ul className="timeline">
            {r.events.map((e) => (
              <li key={e.event_id} className={e.occurred_at > (r.cycle.closed_at || "9999") && !(e.rationale && e.approved_by) ? "row-bad" : ""}>
                <b>{e.occurred_at.replace("T", " ").slice(0, 16)}</b> · <Badge value={e.event_type} tone="neutral" /> {e.from_status || ""} {e.to_status ? `→ ${e.to_status}` : ""}
                <div className="small">by <EmpLink id={e.actor_id} />{e.field_name && ` · ${e.field_name}`}{e.rationale && ` · “${e.rationale}”`}{e.approved_by && <> · approved by <EmpLink id={e.approved_by} /></>}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      {r.development_plans.length > 0 && (
        <Card title="Development plans">
          {r.development_plans.map((p) => (
            <div key={p.plan_id} className="plan">
              <b>{p.plan_id}</b> <Badge value={p.status} /> — {p.objective} · cost ${fmt(p.training_cost, 0)} {p.requires_hr_approval && <Badge value="needs HR approval" tone="warn" />}
              <div className="small muted">{p.approvals.map((a) => `${a.approver_role} ${a.approver_id}: ${a.decision}`).join(" · ") || "no approvals yet"}</div>
            </div>
          ))}
        </Card>
      )}
    </>
  );
}
