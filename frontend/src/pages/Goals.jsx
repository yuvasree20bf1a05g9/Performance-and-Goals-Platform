import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { qs } from "../api.js";
import { Badge, Card, ErrorBox, Loading, Pager, Progress } from "../components/ui.jsx";

export default function Goals() {
  const { meta, cycle } = useApp();
  const [f, setF] = useState({ q: "", status: "", department: "", page: 1 });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value, page: 1 });
  const res = useApi(`/goals${qs({ ...f, cycle_id: cycle, size: 25 })}`);
  return (
    <>
      <h1>Goals & key results <span className="muted small">· {cycle}</span></h1>
      <Card>
        <div className="filters">
          <input placeholder="Search title or goal ID" value={f.q} onChange={set("q")} />
          <select value={f.status} onChange={set("status")}><option value="">All statuses</option>{["draft", "pending_approval", "in_progress", "closed", "cancelled"].map((s) => <option key={s}>{s}</option>)}</select>
          <select value={f.department} onChange={set("department")}><option value="">All departments</option>{meta.departments.map((d) => <option key={d}>{d}</option>)}</select>
        </div>
        <ErrorBox error={res.error} />
        {res.loading && !res.data ? <Loading /> : res.data && (
          <>
            <table>
              <thead><tr><th>Goal</th><th>Title</th><th>Owner</th><th>Category</th><th>Weight</th><th>Status</th><th style={{ width: "24%" }}>Progress</th></tr></thead>
              <tbody>
                {res.data.items.map((g) => (
                  <tr key={g.goal_id}>
                    <td><Link to={`/goals/${g.goal_id}`}><code>{g.goal_id}</code></Link></td>
                    <td>{g.title}</td><td><Link to={`/employees/${g.employee_id}`}>{g.owner_name}</Link><div className="muted small">{g.department}</div></td>
                    <td>{g.category}</td><td>{g.weight_pct}%</td><td><Badge value={g.status} /></td><td><Progress value={g.progress_pct} /></td>
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
