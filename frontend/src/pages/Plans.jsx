import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { api, qs } from "../api.js";
import { Badge, Card, ErrorBox, Loading, Notice, Pager, fdate, fmt } from "../components/ui.jsx";

export default function Plans() {
  const { actor } = useApp();
  const [f, setF] = useState({ status: "", page: 1 });
  const [result, setResult] = useState(null);
  const res = useApi(`/development-plans${qs({ ...f, size: 25 })}`);
  const decide = async (plan, decision) => {
    try { await api.post(`/development-plans/${plan.plan_id}/decisions`, { decision }); setResult({ ok: true, message: `${plan.plan_id} ${decision}` }); res.reload(); }
    catch (err) { setResult({ ok: false, error: err }); }
  };
  return (
    <>
      <h1>Development plans</h1>
      <Notice result={result} onClose={() => setResult(null)} />
      <Card>
        <div className="filters">
          <select value={f.status} onChange={(e) => setF({ status: e.target.value, page: 1 })}><option value="">All statuses</option>{["draft", "submitted", "approved", "rejected", "completed"].map((s) => <option key={s}>{s}</option>)}</select>
          <span className="muted small">Mandatory when a competency is rated 1 or two+ are rated ≤ 2. Plans over $1,000 also need HR approval.</span>
        </div>
        <ErrorBox error={res.error} />
        {res.loading && !res.data ? <Loading /> : res.data && (
          <>
            <table>
              <thead><tr><th>Plan</th><th>Employee</th><th>Objective</th><th>Cost</th><th>Target</th><th>Status</th><th>Approvals</th><th></th></tr></thead>
              <tbody>
                {res.data.items.map((p) => {
                  const mine = p.approvals.find((a) => a.decision === "pending" && a.approver_id === actor);
                  return (
                    <tr key={p.plan_id}>
                      <td><code>{p.plan_id}</code><div className="small"><Link to={`/reviews/${p.review_id}`}>{p.review_id}</Link></div></td>
                      <td><Link to={`/employees/${p.employee_id}`}>{p.employee_name}</Link></td>
                      <td className="small">{p.objective}</td><td>${fmt(p.training_cost, 0)}{p.requires_hr_approval && <div><Badge value="HR" tone="warn" /></div>}</td>
                      <td>{fdate(p.target_date)}</td><td><Badge value={p.status} /></td>
                      <td className="small">{p.approvals.map((a) => <div key={a.approval_id}>{a.approver_role}: <Badge value={a.decision} /> <code>{a.approver_id}</code></div>)}</td>
                      <td>{mine && <><button onClick={() => decide(p, "approved")}>Approve</button> <button onClick={() => decide(p, "rejected")}>Reject</button></>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <Pager page={f.page} size={25} total={res.data.total} onPage={(p) => setF({ ...f, page: p })} />
          </>
        )}
      </Card>
    </>
  );
}
