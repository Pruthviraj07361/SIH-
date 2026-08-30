// Shared across all SANKHYASETU StudyAI pages.
// Change API_BASE if your backend runs somewhere other than the current origin.
const API_BASE = window.location.origin;

// ---- Supabase Auth (client-side) ----
// SUPABASE_URL is not secret. This key MUST be the "publishable"/"anon" key,
// never the secret/service_role key — that one stays server-side only (.env).
const SUPABASE_URL = "https://ewsyfddvxecdodscgnmu.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3c3lmZGR2eGVjZG9kc2Nnbm11Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyMjUyNDMsImV4cCI6MjEwMTgwMTI0M30.HH5wqwvmWb4Cd54a_SEa8UxIwGt8OKCcr7CxDWBCLrc";
const supabaseAuth = supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

// Real logged-in user id, read from the current Supabase session.
// Every page that needs the user must `await getCurrentUserId()` — if it
// returns null, the page should redirect to login.html.
async function getCurrentUserId() {
  const { data: { session } } = await supabaseAuth.auth.getSession();
  return session ? session.user.id : null;
}

// Call at the top of any protected page. Redirects to login.html and
// returns null if there's no active session; otherwise returns the user id.
async function requireLogin() {
  const userId = await getCurrentUserId();
  if (!userId) {
    window.location.href = "login.html";
    return null;
  }
  return userId;
}

async function logout() {
  await supabaseAuth.auth.signOut();
  window.location.href = "login.html";
}

// ---- API helpers ----
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