import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../App.jsx";
import { useApi } from "../hooks.js";
import { qs } from "../api.js";
import { Badge, Card, ErrorBox, Loading, Pager } from "../components/ui.jsx";

export default function Employees() {
  const { meta } = useApp();
  const [f, setF] = useState({ q: "", department: "", role: "", status: "", page: 1 });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value, page: 1 });
  const res = useApi(`/employees${qs({ ...f, size: 25 })}`);
  return (
    <>
      <h1>Employees</h1>
      <Card>
        <div className="filters">
          <input placeholder="Search name, ID or e-mail" value={f.q} onChange={set("q")} />
          <select value={f.department} onChange={set("department")}><option value="">All departments</option>{meta.departments.map((d) => <option key={d}>{d}</option>)}</select>
          <select value={f.role} onChange={set("role")}><option value="">All roles</option>{["employee", "manager", "executive", "hr_partner", "it_ops", "admin"].map((r) => <option key={r}>{r}</option>)}</select>
          <select value={f.status} onChange={set("status")}><option value="">Any status</option>{["active", "on_leave", "terminated"].map((r) => <option key={r}>{r}</option>)}</select>
        </div>
        <ErrorBox error={res.error} />
        {res.loading && !res.data ? <Loading /> : res.data && (
          <>
            <table>
              <thead><tr><th>ID</th><th>Name</th><th>Title</th><th>Department</th><th>Role</th><th>Status</th><th>Manager</th></tr></thead>
              <tbody>
                {res.data.items.map((e) => (
                  <tr key={e.employee_id}>
                    <td><Link to={`/employees/${e.employee_id}`}><code>{e.employee_id}</code></Link></td>
                    <td>{e.name}</td><td>{e.job_title}</td><td>{e.department}</td>
                    <td><Badge value={e.role} tone="neutral" /></td><td><Badge value={e.employment_status} /></td>
                    <td>{e.current_manager_id ? <Link to={`/employees/${e.current_manager_id}`}><code>{e.current_manager_id}</code></Link> : "—"}</td>
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
