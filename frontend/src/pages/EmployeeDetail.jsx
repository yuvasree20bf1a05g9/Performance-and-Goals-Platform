import React from "react";
import { Link, useParams } from "react-router-dom";
import { useApi } from "../hooks.js";
import { Badge, Card, EmpLink, ErrorBox, Loading, Progress, fdate, fmt } from "../components/ui.jsx";

export default function EmployeeDetail() {
  const { id } = useParams();
  const { data: e, error, loading } = useApi(`/employees/${id}`);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const byCycle = e.goals.reduce((acc, g) => ({ ...acc, [g.cycle_id]: [...(acc[g.cycle_id] || []), g] }), {});
  return (
    <>
      <div className="crumbs">{[...e.manager_chain].reverse().map((m) => <span key={m.employee_id}><EmpLink id={m.employee_id} name={m.name} /> ›</span>)}</div>
      <h1>{e.name} <span className="muted small"><code>{e.employee_id}</code></span></h1>
      <div className="grid3">
        <Card title="Profile">
          <dl className="facts">
            <dt>Title</dt><dd>{e.job_title} ({e.job_level})</dd>
            <dt>Department</dt><dd>{e.department}</dd>
            <dt>Role</dt><dd><Badge value={e.role} tone="neutral" /></dd>
            <dt>Status</dt><dd><Badge value={e.employment_status} /></dd>
            <dt>Location</dt><dd>{e.location}</dd>
            <dt>Hired</dt><dd>{e.hire_date}{e.termination_date && ` · left ${e.termination_date}`}</dd>
            <dt>E-mail</dt><dd>{e.email}</dd>
          </dl>
        </Card>
        <Card title="Reporting history (effective-dated)">
          <ul className="timeline">
            {e.assignments.map((a) => (
              <li key={a.assignment_id}>
                <b>{a.effective_from}</b> → {a.effective_to || "present"} · <EmpLink id={a.manager_id} name={a.manager?.name} />
                <div className="muted small">{a.department} · <Badge value={a.change_reason} tone={a.change_reason === "transfer" || a.change_reason === "reorg" ? "warn" : "neutral"} /></div>
              </li>
            ))}
            {e.assignments.length === 0 && <li className="muted">Top of hierarchy</li>}
          </ul>
        </Card>
        <Card title={`Direct reports (${e.direct_reports.length})`}>
          <ul className="plain scroll">
            {e.direct_reports.map((r) => <li key={r.employee_id}><EmpLink id={r.employee_id} name={r.name} /> <span className="muted small">{r.job_title}</span></li>)}
            {e.direct_reports.length === 0 && <li className="muted">None</li>}
          </ul>
        </Card>
      </div>
      <Card title="Reviews">
        <table>
          <thead><tr><th>Review</th><th>Cycle</th><th>Status</th><th>Goal score</th><th>Competency</th><th>Overall</th><th>Rating</th><th>Missing inputs</th></tr></thead>
          <tbody>
            {e.reviews.map((r) => (
              <tr key={r.review_id}>
                <td><Link to={`/reviews/${r.review_id}`}><code>{r.review_id}</code></Link></td><td>{r.cycle_id}</td>
                <td><Badge value={r.status} /></td><td>{fmt(r.goal_score_pct)}%</td><td>{fmt(r.competency_rating, 2)}</td>
                <td>{fmt(r.overall_score, 2)}</td><td><Badge value={r.overall_rating} /></td><td className="small">{r.missing_inputs || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {Object.entries(byCycle).map(([cyc, goals]) => (
        <Card key={cyc} title={`Goals · ${cyc}`}>
          <table>
            <thead><tr><th>Goal</th><th>Title</th><th>Weight</th><th>Status</th><th style={{ width: "28%" }}>Progress</th><th>Created</th></tr></thead>
            <tbody>
              {goals.map((g) => (
                <tr key={g.goal_id}>
                  <td><Link to={`/goals/${g.goal_id}`}><code>{g.goal_id}</code></Link></td><td>{g.title}</td><td>{g.weight_pct}%</td>
                  <td><Badge value={g.status} /></td><td><Progress value={g.progress_pct} /></td><td>{fdate(g.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </>
  );
}
