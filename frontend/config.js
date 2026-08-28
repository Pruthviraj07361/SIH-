// Shared across all StudyAI pages.
// Change API_BASE if your backend runs somewhere other than localhost:8000.
const API_BASE = "http://127.0.0.1:8000";

// TEMP: stand-in for real auth. Swap this for the logged-in user's id once
// Supabase Auth is wired in (see README "Not implemented yet").
// Kept as a plain JS constant (not localStorage) so this file behaves the
// same whether opened directly or embedded in a viewer.
const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPostForm(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPatchForm(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, { method: "PATCH", body: formData });
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
  return res.json();
}

// Small helper: read/write query-string params so pages can pass
// material_id / topic_id / session_id to each other via real links.
function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}
