import React, { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, getActor, setActor } from "./api.js";
import Overview from "./pages/Overview.jsx";
import Employees from "./pages/Employees.jsx";
import EmployeeDetail from "./pages/EmployeeDetail.jsx";
import Goals from "./pages/Goals.jsx";
import GoalDetail from "./pages/GoalDetail.jsx";
import Reviews from "./pages/Reviews.jsx";
import ReviewDetail from "./pages/ReviewDetail.jsx";
import Plans from "./pages/Plans.jsx";
import Quality from "./pages/Quality.jsx";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

const NAV = [
  ["/", "Overview"], ["/employees", "Employees"], ["/goals", "Goals & OKRs"], ["/reviews", "Reviews"],
  ["/plans", "Development plans"], ["/quality", "Data quality"],
];

export default function App() {
  const [meta, setMeta] = useState(null);
  const [cycle, setCycle] = useState("CYCLE-2026-H1");
  const [actor, setActorState] = useState(getActor());
  const [error, setError] = useState(null);

  useEffect(() => { api.get("/meta").then(setMeta).catch(setError); }, []);
  const changeActor = (id) => { setActor(id); setActorState(id); };

  if (error) return <div className="boot-error">Cannot reach the API ({error.message}). Is the backend running on port 8000?</div>;
  if (!meta) return <div className="loading">Loading…</div>;

  return (
    <AppCtx.Provider value={{ meta, cycle, setCycle, actor }}>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand"><span className="logo">◎</span> PerformanceHub</div>
          <nav>
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>{label}</NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            Dataset <b>{meta.dataset.profile}</b> · seed {meta.dataset.seed}<br />As of {meta.dataset.as_of}
            <br /><a href="/docs" target="_blank" rel="noreferrer">API docs ↗</a>
          </div>
        </aside>
        <main>
          <header className="topbar">
            <label>Cycle
              <select value={cycle} onChange={(e) => setCycle(e.target.value)}>
                {meta.cycles.map((c) => <option key={c.cycle_id} value={c.cycle_id}>{c.name} ({c.status})</option>)}
              </select>
            </label>
            <label title="Simulated login: write actions are performed as this employee (X-Actor-Id)">Acting as
              <select value={meta.demo_actors.some((a) => a.employee_id === actor) ? actor : ""} onChange={(e) => changeActor(e.target.value)}>
                <option value="">— custom / none —</option>
                {meta.demo_actors.map((a) => <option key={a.employee_id} value={a.employee_id}>{a.label}: {a.name} ({a.employee_id})</option>)}
              </select>
              <input value={actor} placeholder="EMP-000123" onChange={(e) => changeActor(e.target.value.trim())} />
            </label>
          </header>
          <div className="content">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/employees" element={<Employees />} />
              <Route path="/employees/:id" element={<EmployeeDetail />} />
              <Route path="/goals" element={<Goals />} />
              <Route path="/goals/:id" element={<GoalDetail />} />
              <Route path="/reviews" element={<Reviews />} />
              <Route path="/reviews/:id" element={<ReviewDetail />} />
              <Route path="/plans" element={<Plans />} />
              <Route path="/quality" element={<Quality />} />
              <Route path="*" element={<p>Page not found.</p>} />
            </Routes>
          </div>
        </main>
      </div>
    </AppCtx.Provider>
  );
}
