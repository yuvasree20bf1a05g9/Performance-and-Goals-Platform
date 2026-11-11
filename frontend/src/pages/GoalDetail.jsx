import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { api } from "../api.js";
import { Badge, Card, EmpLink, ErrorBox, Flags, Loading, Notice, Progress, fdate, fmt } from "../components/ui.jsx";

function CheckInForm({ goal, onDone }) {
  const [vals, setVals] = useState({});
  const [rat, setRat] = useState({});
  const [note, setNote] = useState("");
  const [confidence, setConfidence] = useState("medium");
  const [evidence, setEvidence] = useState("");
  const [result, setResult] = useState(null);
  useEffect(() => setVals(Object.fromEntries(goal.key_results.map((k) => [k.kr_id, k.current_value]))), [goal]);
  const raw = (k) => ((Number(vals[k.kr_id]) - k.start_value) / (k.target_value - k.start_value)) * 100;
  const submit = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post(`/goals/${goal.goal_id}/checkins`, {
        confidence, note,
        updates: goal.key_results.map((k) => ({ kr_id: k.kr_id, reported_value: Number(vals[k.kr_id]), over_scale_rationale: rat[k.kr_id] || null })),
        evidence: evidence ? [{ evidence_type: "document", uri: evidence }] : [],
      });
      setResult({ ok: true, message: `Check-in ${r.checkin.checkin_id} recorded. Goal progress is now ${r.goal_progress_pct}%.` });
      onDone();
    } catch (err) { setResult({ ok: false, error: err }); }
  };
  return (
    <form onSubmit={submit} className="form">
      <Notice result={result} onClose={() => setResult(null)} />
      {goal.key_results.map((k) => (
        <div className="form-row" key={k.kr_id}>
          <label>{k.description} <span className="muted small">({k.start_value} → {k.target_value} {k.unit})</span></label>
          <input type="number" step="any" value={vals[k.kr_id] ?? ""} onChange={(e) => setVals({ ...vals, [k.kr_id]: e.target.value })} />
          <span className={`small ${raw(k) > 100 ? "warn-text" : "muted"}`}>{fmt(raw(k))}%</span>
          {raw(k) > 100 && <input placeholder="Rationale required above 100%" value={rat[k.kr_id] || ""} onChange={(e) => setRat({ ...rat, [k.kr_id]: e.target.value })} />}
        </div>
      ))}
      <div className="form-row">
        <label>Confidence</label>
        <select value={confidence} onChange={(e) => setConfidence(e.target.value)}>{["low", "medium", "high"].map((c) => <option key={c}>{c}</option>)}</select>
        <input placeholder="Evidence link (https://…)" value={evidence} onChange={(e) => setEvidence(e.target.value)} />
      </div>
      <textarea placeholder="What changed since the last check-in?" value={note} onChange={(e) => setNote(e.target.value)} required minLength={3} />
      <button className="primary" type="submit">Submit check-in</button>
    </form>
  );
}

function TargetForm({ goal, onDone }) {
  const [kr, setKr] = useState(goal.key_results[0]?.kr_id);
  const [target, setTarget] = useState("");
  const [rationale, setRationale] = useState("");
  const [result, setResult] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.patch(`/goals/${goal.goal_id}`, { kr_targets: [{ kr_id: kr, target_value: Number(target) }], rationale: rationale || null });
      setResult({ ok: true, message: "Target changed and versioned." });
      onDone();
    } catch (err) { setResult({ ok: false, error: err }); }
  };
  return (
    <form onSubmit={submit} className="form">
      <Notice result={result} onClose={() => setResult(null)} />
      <div className="form-row">
        <select value={kr} onChange={(e) => setKr(e.target.value)}>{goal.key_results.map((k) => <option key={k.kr_id} value={k.kr_id}>{k.description} (target {k.target_value})</option>)}</select>
        <input type="number" step="any" placeholder="New target" value={target} onChange={(e) => setTarget(e.target.value)} required />
      </div>
      <input placeholder="Rationale (required; HR/admin only after cycle close)" value={rationale} onChange={(e) => setRationale(e.target.value)} />
      <button type="submit">Change target</button>
    </form>
  );
}

export default function GoalDetail() {
  const { id } = useParams();
  const { actor } = useApp();
  const { data: g, error, loading, reload } = useApi(`/goals/${id}`);
  if (loading && !g) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <div className="crumbs"><Link to="/goals">Goals</Link> › <code>{g.goal_id}</code></div>
      <h1>{g.title}</h1>
      <Flags flags={g.flags} />
      <div className="grid3">
        <Card title="Goal">
          <dl className="facts">
            <dt>Owner</dt><dd><EmpLink id={g.employee_id} name={g.owner?.name} /> {!g.goal_id.includes(g.employee_id) && <Badge value="owner mismatch" tone="bad" />}</dd>
            <dt>Cycle</dt><dd>{g.cycle_id} <Badge value={g.cycle.status} /></dd>
            <dt>Status</dt><dd><Badge value={g.status} /></dd>
            <dt>Weight</dt><dd>{g.weight_pct}% of owner's goals</dd>
            <dt>Approved by</dt><dd>{g.approver ? <EmpLink id={g.approver.employee_id} name={g.approver.name} /> : "—"} {fdate(g.approved_at)}</dd>
            <dt>Version</dt><dd>v{g.current_version}</dd>
          </dl>
        </Card>
        <Card title="Progress (derived from key results)" className="span2">
          <div className="big-progress"><Progress value={g.progress_pct} /></div>
          <table>
            <thead><tr><th>Key result</th><th>Start</th><th>Current</th><th>Target</th><th>Weight</th><th>Raw</th><th style={{ width: "26%" }}>Scored</th></tr></thead>
            <tbody>
              {g.key_results.map((k) => (
                <tr key={k.kr_id}>
                  <td>{k.description}<div className="muted small"><code>{k.kr_id}</code> · {k.direction} · {k.unit}</div></td>
                  <td>{fmt(k.start_value, 2)}</td><td>{fmt(k.current_value, 2)}</td><td>{fmt(k.target_value, 2)}</td><td>{k.weight_pct}%</td>
                  <td className={k.raw_progress_pct > 100 ? "warn-text" : ""}>{fmt(k.raw_progress_pct)}%</td><td><Progress value={k.scoring_progress_pct} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Scored progress is capped at 100%, or 120% when the latest update carries an over-achievement rationale.</p>
        </Card>
      </div>
      <div className="grid2">
        <Card title={`New check-in ${actor ? `as ${actor}` : "(choose 'Acting as' first)"}`}>
          {g.status === "in_progress" && g.cycle.status === "active"
            ? <CheckInForm goal={g} onDone={reload} />
            : <p className="muted">Check-ins are accepted only on approved goals in an active cycle (this goal is <b>{g.status}</b>, cycle is <b>{g.cycle.status}</b>).</p>}
        </Card>
        <Card title={g.cycle.status === "closed" ? "Post-close correction (HR / admin only)" : "Change a target (versioned)"}><TargetForm goal={g} onDone={reload} /></Card>
      </div>
      <div className="grid2">
        <Card title={`Check-ins (${g.checkins.length})`}>
          <ul className="timeline">
            {[...g.checkins].reverse().map((c) => (
              <li key={c.checkin_id}>
                <b>{c.checkin_date}</b> · #{c.sequence_no} · <Badge value={c.confidence} /> · goal {fmt(c.goal_progress_pct)}%
                <div className="small">by <EmpLink id={c.submitted_by} name={c.submitted_by_name} /> — {c.note}</div>
                <div className="small muted">{c.updates.map((u) => `${u.kr_id.slice(-2)}: ${fmt(u.reported_value, 2)} (${fmt(u.raw_progress_pct)}%)${u.over_scale_rationale ? " ✎ " + u.over_scale_rationale : ""}`).join(" · ")}</div>
                {c.evidence.map((e) => <div key={e.evidence_id} className="small"><Badge value={e.evidence_type} tone="neutral" /> <span className="muted">{e.uri}</span></div>)}
              </li>
            ))}
            {g.checkins.length === 0 && <li className="muted">No check-ins yet.</li>}
          </ul>
        </Card>
        <Card title="Version history (append-only)">
          <table>
            <thead><tr><th>v</th><th>When</th><th>Change</th><th>Old → New</th><th>By / approved</th></tr></thead>
            <tbody>
              {[...g.versions].reverse().map((v) => (
                <tr key={v.version_id}>
                  <td>{v.version_no}</td><td className="small">{v.changed_at.replace("T", " ").slice(0, 16)}</td>
                  <td><Badge value={v.change_type} tone={v.change_type === "post_close_correction" ? "warn" : "neutral"} />{v.rationale && <div className="small muted">{v.rationale}</div>}</td>
                  <td className="small">{v.old_value ?? "—"} → {v.new_value ?? "—"}</td>
                  <td className="small"><EmpLink id={v.changed_by} />{v.approved_by && <> / <EmpLink id={v.approved_by} /></>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
