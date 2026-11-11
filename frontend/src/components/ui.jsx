import React from "react";
import { Link } from "react-router-dom";

export const fmt = (n, d = 1) => (n === null || n === undefined ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d }));
export const fdate = (s) => (s ? s.slice(0, 10) : "—");

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h3>{title}</h3>
          <div>{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub, tone }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

const TONES = {
  closed: "neutral", finalized: "good", approved: "good", completed: "good", in_progress: "info", active: "info",
  manager_submitted: "info", self_submitted: "info", submitted: "info", pending_approval: "warn", draft: "neutral",
  not_started: "neutral", cancelled: "bad", rejected: "bad", terminated: "bad", on_leave: "warn", planned: "neutral",
  pending: "warn", Exceptional: "good", Exceeds: "good", Meets: "info", "Partially Meets": "warn", Below: "bad",
  high: "good", medium: "warn", low: "bad",
};
export function Badge({ value, tone }) {
  if (value === null || value === undefined) return <span className="muted">—</span>;
  return <span className={`badge ${tone || TONES[value] || "neutral"}`}>{String(value).replaceAll("_", " ")}</span>;
}

export function Progress({ value, max = 120, marker = 100 }) {
  const v = Math.max(0, Math.min(value ?? 0, max));
  const tone = value >= 100 ? "good" : value >= 70 ? "info" : value >= 40 ? "warn" : "bad";
  return (
    <div className="progress" title={`${fmt(value)}%`}>
      <div className={`progress-fill ${tone}`} style={{ width: `${(v / max) * 100}%` }} />
      <div className="progress-marker" style={{ left: `${(marker / max) * 100}%` }} />
      <span className="progress-label">{fmt(value)}%</span>
    </div>
  );
}

export function Bars({ data, valueKey = "value", labelKey = "label", height = 180, color = "var(--accent)" }) {
  const max = Math.max(1, ...data.map((d) => d[valueKey]));
  return (
    <div className="bars" style={{ height }}>
      {data.map((d) => (
        <div key={d[labelKey]} className="bar-col" title={`${d[labelKey]}: ${fmt(d[valueKey], 0)}`}>
          <div className="bar-value">{fmt(d[valueKey], 0)}</div>
          <div className="bar" style={{ height: `${(d[valueKey] / max) * 100}%`, background: color }} />
          <div className="bar-label">{d[labelKey]}</div>
        </div>
      ))}
    </div>
  );
}

export function HBars({ data }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="hbars">
      {data.map((d) => (
        <div className="hbar-row" key={d.label}>
          <span className="hbar-label">{d.label}</span>
          <div className="hbar-track"><div className={`hbar-fill ${d.tone || ""}`} style={{ width: `${(d.value / max) * 100}%` }} /></div>
          <span className="hbar-value">{fmt(d.value, 0)}</span>
        </div>
      ))}
    </div>
  );
}

export function Loading() { return <div className="loading">Loading…</div>; }

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div className="alert bad">
      <strong>{error.status ? `${error.status} · ` : ""}{error.message}</strong>
      {error.details && <pre>{JSON.stringify(error.details, null, 2)}</pre>}
    </div>
  );
}

export function Notice({ result, onClose }) {
  if (!result) return null;
  return (
    <div className={`alert ${result.ok ? "good" : "bad"}`}>
      <button className="close" onClick={onClose}>×</button>
      <strong>{result.ok ? "Saved" : `${result.error.status} · ${result.error.message}`}</strong>
      {result.message && <div>{result.message}</div>}
      {!result.ok && result.error.details && <pre>{JSON.stringify(result.error.details, null, 2)}</pre>}
    </div>
  );
}

export function Pager({ page, size, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="pager">
      <span>{fmt(total, 0)} records</span>
      <button disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Prev</button>
      <span>Page {page} / {pages}</span>
      <button disabled={page >= pages} onClick={() => onPage(page + 1)}>Next ›</button>
    </div>
  );
}

export const EmpLink = ({ id, name }) => (id ? <Link to={`/employees/${id}`}>{name || id}</Link> : <span className="muted">—</span>);

export function Flags({ flags }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="alert warn">
      <strong>⚠ {flags.length} data-quality finding{flags.length > 1 ? "s" : ""} on this record</strong>
      <ul>
        {flags.map((f, i) => (
          <li key={i}><Badge value={f.issue_type} tone="warn" /> <code>{f.entity_id}</code> — {f.detail}</li>
        ))}
      </ul>
    </div>
  );
}
