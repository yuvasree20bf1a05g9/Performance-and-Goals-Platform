// Thin fetch wrapper. Writes send the acting user in X-Actor-Id (simulated auth).
let actorId = localStorageSafe("actorId") || "";

function localStorageSafe(key, value) {
  try {
    if (value === undefined) return window.localStorage.getItem(key);
    window.localStorage.setItem(key, value);
  } catch { /* storage unavailable - keep in memory only */ }
  return null;
}

export function setActor(id) { actorId = id; localStorageSafe("actorId", id); }
export function getActor() { return actorId; }

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || body?.detail?.[0]?.msg || `HTTP ${status}`);
    this.status = status;
    this.details = body?.error?.details || body?.detail;
  }
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (actorId) headers["X-Actor-Id"] = actorId;
  const res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const qs = (params) => {
  const p = Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null);
  return p.length ? "?" + new URLSearchParams(p).toString() : "";
};

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
};
