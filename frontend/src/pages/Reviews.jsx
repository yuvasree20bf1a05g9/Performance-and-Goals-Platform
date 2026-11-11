import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { qs } from "../api.js";
import { Badge, Card, ErrorBox, Loading, Pager, fmt } from "../components/ui.jsx";

export default function Reviews() {
  const { meta, cycle } = useApp();
  const [sp] = useSearchParams();
  const [f, setF] = useState({ status: "", complete: "", rating: "", department: sp.get("department") || "", page: 1 });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value, page: 1 });
  const res = useApi(`/reviews${qs({ ...f, cycle_id: cycle, size: 25 })}`);
  return (
    <>
      <h1>Reviews <span className="muted small">· {cycle}</span></h1>
      <Card>
        <div className="filters">
          <select value={f.status} onChange={set("status")}><option value="">All statuses</option>{["not_started", "self_submitted", "manager_submitted", "finalized"].map((s) => <option key={s}>{s}</option>)}</select>
          <select value={f.complete} onChange={set("complete")}><option value="">Complete or not</option><option value="true">Complete</option><option value="false">Incomplete</option></select>
          <select value={f.rating} onChange={set("rating")}><option value="">Any rating</option>{["Exceptional", "Exceeds", "Meets", "Partially Meets", "Below"].map((s) => <option key={s}>{s}</option>)}</select>
          <select value={f.department} onChange={set("department")}><option value="">All departments</option>{meta.departments.map((d) => <option key={d}>{d}</option>)}</select>
        </div>
        <ErrorBox error={res.error} />
        {res.loading && !res.data ? <Loading /> : res.data && (
          <>
            <table>
              <thead><tr><th>Review</th><th>Employee</th><th>Reviewer</th><th>Status</th><th>Goal score</th><th>Competency</th><th>Overall</th><th>Rating</th><th>Missing inputs</th></tr></thead>
              <tbody>
                {res.data.items.map((r) => (
                  <tr key={r.review_id}>
                    <td><Link to={`/reviews/${r.review_id}`}><code>{r.review_id}</code></Link></td>
                    <td><Link to={`/employees/${r.employee_id}`}>{r.employee_name}</Link><div className="muted small">{r.department}</div></td>
                    <td><Link to={`/employees/${r.reviewer_id}`}><code>{r.reviewer_id}</code></Link></td>
                    <td><Badge value={r.status} /></td><td>{fmt(r.goal_score_pct)}%</td><td>{fmt(r.competency_rating, 2)}</td>
                    <td>{fmt(r.overall_score, 2)}</td><td><Badge value={r.overall_rating} /></td>
                    <td className="small">{r.missing_inputs ? r.missing_inputs.split(";").map((m) => <Badge key={m} value={m.startsWith("checkin:") ? "check-in" : m} tone="warn" />) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={f.page} size={25} total={res.data.total} onPage={(p) => setF({ ...f, page: p })} />
          </>
        )}
      </Card>
    </>
  );
}
