import React from "react";
import { Link } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { qs } from "../api.js";
import { Bars, Card, ErrorBox, HBars, Kpi, Loading, Progress, fmt } from "../components/ui.jsx";

const RATING_TONE = { Exceptional: "good", Exceeds: "good", Meets: "info", "Partially Meets": "warn", Below: "bad" };

export default function Overview() {
  const { cycle } = useApp();
  const ov = useApi(`/metrics/overview${qs({ cycle_id: cycle })}`);
  const dep = useApi(`/metrics/departments${qs({ cycle_id: cycle })}`);
  const q = useApi("/quality/summary");
  if (ov.loading) return <Loading />;
  if (ov.error) return <ErrorBox error={ov.error} />;
  const d = ov.data;
  const anomalies = q.data?.total_findings;
  return (
    <>
      <h1>Overview <span className="muted small">· {cycle}</span></h1>
      <div className="kpis">
        <Kpi label="Active employees" value={fmt(d.people.employees, 0)} sub={`${fmt(d.people.managers, 0)} managers`} />
        <Kpi label="Goals in cycle" value={fmt(d.goals.total, 0)} sub={`${fmt(d.goals.with_checkin_pct)}% have check-ins`} />
        <Kpi label="Avg goal progress" value={`${fmt(d.goals.avg_progress_pct)}%`} sub="derived from key results" tone="info" />
        <Kpi label="Review completion" value={`${fmt(d.reviews.completion_pct)}%`} sub={`${fmt(d.reviews.finalized_pct)}% finalized`} tone={d.reviews.completion_pct > 80 ? "good" : "warn"} />
        <Kpi label="Evidence coverage" value={`${fmt(d.checkins.evidence_coverage_pct)}%`} sub={`${fmt(d.checkins.per_active_goal, 2)} check-ins / goal`} />
        <Kpi label="Data-quality findings" value={anomalies === undefined ? "…" : fmt(anomalies, 0)} sub={<Link to="/quality">review exceptions →</Link>} tone="bad" />
      </div>

      <div className="grid2">
        <Card title="Check-in cadence (per month)">
          <Bars data={d.checkins.monthly.map((m) => ({ label: m.month.slice(5), value: m.count }))} />
        </Card>
        <Card title="Rating distribution (complete reviews)">
          <HBars data={Object.entries(d.reviews.rating_distribution).map(([k, v]) => ({ label: k, value: v, tone: RATING_TONE[k] }))} />
          <p className="muted small">Average overall score {fmt(d.reviews.avg_overall_score, 2)} / 5 · ratings exist only when all required inputs are present.</p>
        </Card>
      </div>

      <div className="grid3">
        <Card title="Review pipeline">
          <HBars data={["not_started", "self_submitted", "manager_submitted", "finalized"].map((s) => ({ label: s.replace("_", " "), value: d.reviews.by_status[s] || 0 }))} />
        </Card>
        <Card title="Why reviews are incomplete">
          <HBars data={Object.entries(d.reviews.missing_inputs).map(([k, v]) => ({ label: k.replaceAll("_", " "), value: v, tone: "warn" }))} />
        </Card>
        <Card title="Feedback & development">
          <dl className="facts">
            <dt>Self / manager / peer</dt><dd>{fmt(d.feedback.by_type.self || 0, 0)} / {fmt(d.feedback.by_type.manager || 0, 0)} / {fmt(d.feedback.by_type.peer || 0, 0)}</dd>
            <dt>Peer response rate</dt><dd>{fmt(d.feedback.peer_response_pct)}%</dd>
            <dt>Conflicting self vs manager</dt><dd>{fmt(d.feedback.conflicting, 0)} competency ratings</dd>
            <dt>Development plans</dt><dd>{fmt(d.development_plans.total, 0)}</dd>
            <dt>Avg days to manager decision</dt><dd>{fmt(d.development_plans.avg_days_to_manager_decision)}</dd>
          </dl>
        </Card>
      </div>

      <Card title="By department">
        {dep.data && (
          <table>
            <thead><tr><th>Department</th><th>Active goals</th><th style={{ width: "30%" }}>Avg progress</th><th>Reviews</th><th>Completion</th><th>Avg score</th></tr></thead>
            <tbody>
              {dep.data.map((r) => (
                <tr key={r.department}>
                  <td><Link to={`/reviews?department=${encodeURIComponent(r.department)}`}>{r.department}</Link></td>
                  <td>{fmt(r.active_goals, 0)}</td><td><Progress value={r.avg_progress_pct} /></td>
                  <td>{fmt(r.reviews, 0)}</td><td>{fmt(r.completion_pct)}%</td><td>{fmt(r.avg_overall_score, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
