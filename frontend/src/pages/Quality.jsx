import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks.js";
import { qs } from "../api.js";
import { Badge, Card, ErrorBox, Kpi, Loading, Pager, fmt } from "../components/ui.jsx";

const LABELS = {
  goal_owner_mismatch: "Goal owner mismatch",
  progress_over_scale_no_rationale: "Progress > 100% without rationale",
  reviewer_lacks_relationship: "Reviewer lacks relationship",
  closed_cycle_silent_edit: "Closed cycle silent edit",
  untraceable_feedback: "Untraceable feedback",
};

function entityLink(f) {
  const goal = f.related_ids.find((x) => x.startsWith("GOAL-"));
  const rev = f.related_ids.find((x) => x.startsWith("REV-"));
  if (f.entity_type === "goal") return `/goals/${f.entity_id}`;
  if (f.entity_type === "review") return `/reviews/${f.entity_id}`;
  if (goal) return `/goals/${goal}`;
  if (rev) return `/reviews/${rev}`;
  return null;
}

export default function Quality() {
  const [issue, setIssue] = useState("");
  const [page, setPage] = useState(1);
  const sum = useApi("/quality/summary");
  const ev = useApi("/quality/evaluation");
  const fs = useApi(`/quality/findings${qs({ issue_type: issue, page, size: 20 })}`);
  if (sum.loading) return <Loading />;
  return (
    <>
      <h1>Data quality & exceptions</h1>
      <p className="muted">Rule detectors run against the live database. Their output is compared with <code>ground_truth.csv</code>, which is kept outside the database so labels never leak into features.</p>
      <div className="kpis">
        {Object.entries(LABELS).map(([k, label]) => (
          <button key={k} className={`kpi kpi-btn ${issue === k ? "selected" : ""}`} onClick={() => { setIssue(issue === k ? "" : k); setPage(1); }}>
            <div className="kpi-label">{label}</div>
            <div className="kpi-value">{fmt(sum.data.by_issue_type[k]?.total || 0, 0)}</div>
            <div className="kpi-sub">{Object.entries(sum.data.by_issue_type[k]?.by_sub_type || {}).map(([s, n]) => `${s.replaceAll("_", " ")}: ${n}`).join(" · ")}</div>
          </button>
        ))}
      </div>
      <div className="grid2">
        <Card title="Detectors vs ground truth">
          <ErrorBox error={ev.error} />
          {ev.data && (
            <table>
              <thead><tr><th>Issue</th><th>Labels</th><th>Findings</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead>
              <tbody>{Object.entries(ev.data.detectors_vs_ground_truth).map(([k, m]) => (
                <tr key={k}><td>{LABELS[k] || k}</td><td>{m.labels}</td><td>{m.findings}</td><td>{m.precision.toFixed(3)}</td><td>{m.recall.toFixed(3)}</td><td><b>{m.f1.toFixed(3)}</b></td></tr>
              ))}</tbody>
            </table>
          )}
          <p className="muted small">One labelled anomaly can produce several findings (e.g. a wrongly-assigned reviewer also invalidates their manager feedback rows); each finding is matched to its label.</p>
        </Card>
        <Card title={ev.data?.validation ? `Generator validation: ${ev.data.validation.overall_status} (${ev.data.validation.checks_passed}/${ev.data.validation.checks_total})` : "Generator validation"}>
          {ev.data?.validation && (
            <div className="scroll">
              <table>
                <thead><tr><th>Check</th><th>Rows</th><th>Violations</th><th>Explained</th><th></th></tr></thead>
                <tbody>{ev.data.validation.checks.map((c) => (
                  <tr key={c.check}><td className="small">{c.check}</td><td>{fmt(c.rows_checked, 0)}</td><td>{c.violations}</td><td>{c.explained_by_ground_truth}</td><td><Badge value={c.status} tone={c.status === "PASS" ? "good" : "bad"} /></td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
      <Card title={`Findings ${issue ? `· ${LABELS[issue]}` : ""}`}>
        <ErrorBox error={fs.error} />
        {fs.data && (
          <>
            <table>
              <thead><tr><th>Issue</th><th>Entity</th><th>Detail</th><th>Related</th></tr></thead>
              <tbody>{fs.data.items.map((f, i) => {
                const to = entityLink(f);
                return (
                  <tr key={i}>
                    <td><Badge value={f.sub_type} tone="warn" /></td>
                    <td>{to ? <Link to={to}><code>{f.entity_id}</code></Link> : <code>{f.entity_id}</code>}<div className="muted small">{f.entity_type}</div></td>
                    <td className="small">{f.detail}</td><td className="small muted">{f.related_ids.join(", ")}</td>
                  </tr>
                );
              })}</tbody>
            </table>
            <Pager page={page} size={20} total={fs.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
